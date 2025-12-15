"""
FastAPI backend for the Reeld Analytics Dashboard.

Provides REST API endpoints for:
- /api/metrics/today - Today's metrics
- /api/metrics/{days} - Metrics for last N days
- /api/runs - Recent pipeline runs
- /api/runs/{run_id}/metrics - Metrics for a specific run
- /api/pipeline-status - Current pipeline status
- /api/api-usage - Claude API usage statistics

Run with:
    uvicorn dashboard:app --reload --port 8080

Or:
    python dashboard.py
"""

import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from analytics import Analytics, ANALYTICS_DB_PATH

# Initialize FastAPI app
app = FastAPI(
    title="Reeld Analytics Dashboard",
    description="Analytics and monitoring for the Reeld video processing pipeline",
    version="1.0.0",
)

# CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Analytics instance for queries
analytics = Analytics(script_name="dashboard", enabled=False)  # Read-only, don't track dashboard itself


# -------------------------------------------------------------------------
# Pydantic models for API responses
# -------------------------------------------------------------------------

class MetricSummary(BaseModel):
    """Summary of metrics."""
    videos_processed: int = 0
    videos_spoofed: int = 0
    captions_generated: int = 0
    claude_api_calls: int = 0
    errors: int = 0
    processing_time_ms: float = 0


class DailyMetrics(BaseModel):
    """Daily metrics summary."""
    date: str
    metrics: Dict[str, float]


class RunInfo(BaseModel):
    """Pipeline run information."""
    id: int
    script_name: str
    start_time: str
    end_time: Optional[str]
    status: str
    duration_seconds: Optional[float] = None


class PipelineStatus(BaseModel):
    """Current pipeline status."""
    is_running: bool
    current_step: Optional[str] = None
    progress_pct: Optional[float] = None
    start_time: Optional[str] = None
    pid: Optional[int] = None


class ApiUsage(BaseModel):
    """Claude API usage statistics."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    estimated_cost_usd: float = 0.0
    calls_today: int = 0
    calls_this_week: int = 0


# -------------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------------

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": ANALYTICS_DB_PATH,
    }


@app.get("/api/metrics/today", response_model=Dict[str, float])
async def get_metrics_today():
    """Get aggregated metrics for today."""
    return analytics.get_metrics_today()


@app.get("/api/metrics/{days}", response_model=List[DailyMetrics])
async def get_metrics_range(days: int = 7):
    """Get daily metrics for the last N days.

    Args:
        days: Number of days to include (default: 7, max: 90)
    """
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="Days must be between 1 and 90")

    return [
        DailyMetrics(date=d["date"], metrics=d["metrics"])
        for d in analytics.get_metrics_range(days)
    ]


@app.get("/api/runs", response_model=List[RunInfo])
async def get_runs(
    limit: int = Query(50, ge=1, le=500),
    script: Optional[str] = None,
    status: Optional[str] = None,
):
    """Get recent pipeline runs.

    Args:
        limit: Maximum number of runs to return
        script: Filter by script name
        status: Filter by status (running, completed, failed)
    """
    runs = analytics.get_runs(limit)

    # Apply filters
    if script:
        runs = [r for r in runs if r["script_name"] == script]
    if status:
        runs = [r for r in runs if r["status"] == status]

    # Calculate durations
    result = []
    for run in runs:
        duration = None
        if run["end_time"]:
            try:
                start = datetime.fromisoformat(run["start_time"])
                end = datetime.fromisoformat(run["end_time"])
                duration = (end - start).total_seconds()
            except ValueError:
                pass

        result.append(RunInfo(
            id=run["id"],
            script_name=run["script_name"],
            start_time=run["start_time"],
            end_time=run["end_time"],
            status=run["status"],
            duration_seconds=duration,
        ))

    return result


@app.get("/api/runs/{run_id}/metrics", response_model=List[Dict[str, Any]])
async def get_run_metrics(run_id: int):
    """Get metrics for a specific run."""
    metrics = analytics.get_run_metrics(run_id)
    if not metrics:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found or has no metrics")
    return metrics


@app.get("/api/pipeline-status", response_model=PipelineStatus)
async def get_pipeline_status():
    """Get current pipeline status from pipeline_state.json."""
    state_file = Path("pipeline_state.json")

    if not state_file.exists():
        return PipelineStatus(is_running=False)

    try:
        with open(state_file) as f:
            state = json.load(f)

        return PipelineStatus(
            is_running=state.get("is_running", False),
            current_step=state.get("current_step"),
            progress_pct=state.get("progress_pct"),
            start_time=state.get("start_time"),
            pid=state.get("pid"),
        )
    except (json.JSONDecodeError, IOError):
        return PipelineStatus(is_running=False)


@app.get("/api/api-usage", response_model=ApiUsage)
async def get_api_usage():
    """Get Claude API usage statistics."""
    today = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    # Get metrics
    today_metrics = analytics.get_metrics_today()
    week_metrics = {}
    for day in analytics.get_metrics_range(7):
        for metric, value in day["metrics"].items():
            week_metrics[metric] = week_metrics.get(metric, 0) + value

    # Calculate API usage
    total_calls = int(week_metrics.get("claude_api_calls", 0))
    errors = int(week_metrics.get("api_errors", 0))

    # Rough cost estimate: ~$0.01 per 1K input tokens, assume ~2K tokens per call
    estimated_cost = total_calls * 0.02

    return ApiUsage(
        total_calls=total_calls,
        successful_calls=total_calls - errors,
        failed_calls=errors,
        estimated_cost_usd=round(estimated_cost, 2),
        calls_today=int(today_metrics.get("claude_api_calls", 0)),
        calls_this_week=total_calls,
    )


@app.get("/api/summary")
async def get_summary():
    """Get a comprehensive summary of all metrics."""
    today = analytics.get_metrics_today()
    week = analytics.get_metrics_range(7)
    runs = analytics.get_runs(10)

    # Calculate totals
    week_totals = {}
    for day in week:
        for metric, value in day["metrics"].items():
            week_totals[metric] = week_totals.get(metric, 0) + value

    return {
        "today": today,
        "week_totals": week_totals,
        "daily_breakdown": week,
        "recent_runs": runs[:10],
        "generated_at": datetime.now().isoformat(),
    }


# -------------------------------------------------------------------------
# Static file serving for frontend (if built)
# -------------------------------------------------------------------------

frontend_dir = Path(__file__).parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")

    @app.get("/")
    async def serve_frontend():
        """Serve the frontend index.html."""
        return FileResponse(frontend_dir / "index.html")

    @app.get("/{path:path}")
    async def serve_frontend_routes(path: str):
        """Serve frontend routes (SPA fallback)."""
        file_path = frontend_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dir / "index.html")
else:
    @app.get("/")
    async def no_frontend():
        """Placeholder when frontend is not built."""
        return {
            "message": "Reeld Analytics Dashboard API",
            "docs": "/docs",
            "frontend": "Not built. Run 'cd frontend && npm run build' to build.",
        }


# -------------------------------------------------------------------------
# Run with uvicorn
# -------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)
