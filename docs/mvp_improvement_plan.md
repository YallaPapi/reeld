# MVP Improvement Plan

**Generated:** 2025-12-15 18:45:30
**Profile:** Feature Focus: add a functional frontend with analytics dashboard
**Status:** Ready for implementation

---

## PRD Summary

# Reeld Project Documentation

## Overview
This is an automated Instagram video content reposting system that downloads videos, modifies them to avoid detection, extracts metadata, rewrites captions using AI, and exports everything to CSV for bulk upload.

---

## Project Architecture

### Data Flow Pipeline

```
1. Download Videos (parallel_download.py)
   ↓
2. Embed Shortcodes in Audio (embed_audio_id.py) [OPTIONAL - for tracking]
   ↓
3. Spoof Videos (spoof_videos.py)
   ↓
4. Extract Shortcodes from Spoofed Videos (extract_audio_id.py) [OPTIONAL - if step 2 was used]
   ↓

*[PRD truncated for brevity]*

## Analysis Stages

### Feature: Web-based analytics dashboard displaying key pipel

**Core Functionality:** Web-based analytics dashboard displaying key pipeline metrics: total videos processed per script/step, captions generated via Claude API, daily API call counts, processing times, and pipeline status overview.

**Suggested Additions:** 6 additional features recommended
  - Real-time progress tracking for long-running parallel processes (downloads/spoofing)
  - API usage cost estimator and rate limit monitoring
  - Historical trend charts (7/30 day views)
  - Pipeline status overview (which step is running/complete/failed)
  - Exportable analytics reports as CSV/PDF
  - ... and 1 more

**Affected Files:** parallel_download.py, spoof_videos.py, embed_audio_id.py, extract_audio_id.py, generate_csv_from_mapping.py, [NEW] analytics.py, [NEW] dashboard.py, [NEW] frontend/

**Architecture Notes:** Add lightweight analytics tracking layer that instruments existing scripts without modifying core logic. Use SQLite for metrics storage (matches CSV-based workflow simplicity). Serve dashboard via Flask/FastAPI with static frontend. Track at script boundaries and key milestones to minimize performance impact on parallel workers.

**Customized Analysis Prompts:** 4 prompts tailored to this feature
  - architecture_layer_identification: New frontend requires clean architectural separation between...
  - architecture_diagram_generation: Visualizes complete system architecture with new frontend in...
  - performance_bottleneck_identification: Analytics tracking must not slow down the performance-critic...
  - quality_code_duplication_analysis: Prevents metrics collection code duplication across multiple...

**Recommendations:**
- Consider adding: Real-time progress tracking for long-running parallel processes (downloads/spoofing)
- Consider adding: API usage cost estimator and rate limit monitoring
- Consider adding: Historical trend charts (7/30 day views)
- Consider adding: Pipeline status overview (which step is running/complete/failed)
- Consider adding: Exportable analytics reports as CSV/PDF
- Consider adding: Alerts for failures or high API usage
- Analysis focus: New frontend requires clean architectural separation between existing batch processing scripts and analytics/dashboard layer
- Analysis focus: Visualizes complete system architecture with new frontend integration
- Analysis focus: Analytics tracking must not slow down the performance-critical parallel processing pipeline
- Analysis focus: Prevents metrics collection code duplication across multiple processing scripts


## Implementation Tasks

### [CRITICAL] Critical Priority

- [ ] **Create centralized analytics tracking module** (`analytics.py`)
  - Build analytics.py with thread-safe metrics collector for: videos_processed, captions_generated, claude_api_calls, processing_times, errors. Support batch flushes for parallel workers. Use SQLite for storage with schema: runs(timestamp), metrics(run_id, script_name, metric_type, value, timestamp).
- [ ] **Build FastAPI backend for dashboard** (`dashboard.py`)
  - Create dashboard.py FastAPI server with endpoints: /api/metrics/today, /api/metrics/{days}, /api/pipeline-status, /api/api-usage. Query SQLite analytics db. Add /api/runs endpoint for pipeline execution history. Include CORS for frontend.
- [ ] **Create React/Vue frontend dashboard** (`frontend/`)
  - Build frontend/ with dashboard showing: 1) KPIs (videos processed, captions generated, API calls today), 2) Pipeline status timeline, 3) 7/30-day trend charts, 4) Per-script breakdown tables, 5) API cost estimator. Use Chart.js/Recharts.

### [HIGH] High Priority

- [ ] **Instrument parallel_download.py with analytics** (`parallel_download.py`)
  - Add analytics tracking to parallel_download.py: total_videos_attempted, videos_skipped_exists, videos_successful, total_download_time, avg_download_speed. Track per username folder stats. Flush metrics at completion using new analytics module.
- [ ] **Instrument spoof_videos.py and generate_csv_from_mapping.py** (`spoof_videos.py, generate_csv_from_mapping.py`)
  - Add tracking to spoof_videos.py: videos_spoofed, spoofing_time_per_video, gpu_utilization_estimate, crop/scale/trim params stats. For generate_csv_from_mapping.py: captions_rewritten, claude_api_calls, api_errors, csv_rows_generated, chunk_stats.

### [MEDIUM] Medium Priority

- [ ] **Add optional analytics to all scripts** (`parallel_download.py, spoof_videos.py, embed_audio_id.py, extract_audio_id.py, generate_csv_from_mapping.py`)
  - Add ENABLE_ANALYTICS env var (default=true) to all processing scripts. Minimal 2-line integration using analytics.track() calls. Create auto-instrumentation decorator for worker functions.
- [ ] **Pipeline status tracking and alerts** (`dashboard.py, analytics.py`)
  - Add pipeline_state.json with current_step, progress_pct, start_time, pid. Dashboard polls this file. Add simple email/Slack alerts for failures via SMTP or webhook when metrics show errors > threshold.

### [LOW] Low Priority

- [ ] **Docker setup for dashboard** (`docker-compose.yml, Dockerfile`)
  - Create docker-compose.yml with FastAPI backend + frontend + SQLite volume. Expose port 8080. Include nginx reverse proxy. Add to project root README.


---

## Instructions for Claude Code

### IMPORTANT: Use Taskmaster for Implementation

**You MUST use Taskmaster to implement these tasks.** Do NOT manage tasks manually.

To import and implement the tasks:

```bash
# First, import the tasks file into Taskmaster
task-master parse-prd .meta-agent-tasks.md --append

# Work through tasks using Taskmaster:
task-master list                    # See all tasks
task-master next                    # Get next task to work on
task-master set-status --id=<id> --status=in-progress
task-master set-status --id=<id> --status=done
```

### Task Workflow

1. Import tasks into Taskmaster using `parse-prd --append`
2. Use `task-master next` to get the highest priority task
3. Mark task as `in-progress` before starting work
4. Implement the task following the description
5. Run relevant tests
6. Mark task as `done` when complete
7. Commit changes after completing related tasks

### Implementation Notes

- Work through tasks systematically, starting with Critical/High priority
- Run tests after each significant change
- Commit changes incrementally with descriptive messages
- If a task is unclear, review the relevant stage summary above for context
