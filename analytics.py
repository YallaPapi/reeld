"""
Centralized analytics tracking module for the Reeld pipeline.

Thread-safe metrics collector supporting:
- videos_processed, captions_generated, claude_api_calls
- processing_times, errors per script
- Batch flushes for parallel workers

Uses SQLite for storage with schema:
- runs: timestamp, script_name, status
- metrics: run_id, metric_type, value, timestamp

Usage:
    from analytics import Analytics

    # Initialize (usually at script start)
    analytics = Analytics()

    # Track metrics
    analytics.track("videos_processed", 1)
    analytics.track("processing_time_ms", 1234)
    analytics.track("errors", 1, tags={"error_type": "ffmpeg"})

    # Flush at end of script
    analytics.flush()

    # Or use context manager for auto-flush
    with Analytics(script_name="spoof_videos") as analytics:
        analytics.track("videos_processed", 1)

Environment variables:
    ANALYTICS_ENABLED: Set to "false" to disable tracking (default: true)
    ANALYTICS_DB_PATH: Path to SQLite database (default: analytics.db)
"""

import os
import json
import sqlite3
import threading
import atexit
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager


# Environment configuration
ANALYTICS_ENABLED = os.environ.get("ANALYTICS_ENABLED", "true").lower() != "false"
ANALYTICS_DB_PATH = os.environ.get("ANALYTICS_DB_PATH", "analytics.db")


class Analytics:
    """Thread-safe analytics collector with SQLite persistence."""

    _instance: Optional["Analytics"] = None
    _lock = threading.Lock()

    def __init__(
        self,
        script_name: Optional[str] = None,
        db_path: str = ANALYTICS_DB_PATH,
        enabled: bool = ANALYTICS_ENABLED,
    ):
        """Initialize analytics collector.

        Args:
            script_name: Name of the script using analytics (auto-detected if None)
            db_path: Path to SQLite database file
            enabled: Whether tracking is enabled
        """
        self.script_name = script_name or self._detect_script_name()
        self.db_path = db_path
        self.enabled = enabled
        self.run_id: Optional[int] = None
        self.start_time = datetime.now()

        # Thread-local storage for metrics buffer
        self._local = threading.local()
        self._global_buffer: List[Dict[str, Any]] = []
        self._buffer_lock = threading.Lock()

        if self.enabled:
            self._init_db()
            self._start_run()
            # Register flush on exit
            atexit.register(self.flush)

    def _detect_script_name(self) -> str:
        """Detect the calling script name."""
        import sys
        if sys.argv:
            return Path(sys.argv[0]).stem
        return "unknown"

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    script_name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'running',
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER,
                    metric_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    tags TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(id)
                );

                CREATE INDEX IF NOT EXISTS idx_metrics_run_id ON metrics(run_id);
                CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(metric_type);
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp);
                CREATE INDEX IF NOT EXISTS idx_runs_script ON runs(script_name);
                CREATE INDEX IF NOT EXISTS idx_runs_start ON runs(start_time);
            """)

    @contextmanager
    def _get_connection(self):
        """Get a thread-safe database connection."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _start_run(self) -> None:
        """Record the start of a new run."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (script_name, start_time, status) VALUES (?, ?, ?)",
                (self.script_name, self.start_time.isoformat(), "running")
            )
            self.run_id = cursor.lastrowid

    def track(
        self,
        metric_type: str,
        value: float = 1,
        tags: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Track a metric value.

        Thread-safe: can be called from worker threads.

        Args:
            metric_type: Type of metric (e.g., "videos_processed", "errors")
            value: Numeric value to record (default: 1 for counters)
            tags: Optional tags for categorization
        """
        if not self.enabled:
            return

        metric = {
            "metric_type": metric_type,
            "value": value,
            "tags": json.dumps(tags) if tags else None,
            "timestamp": datetime.now().isoformat(),
        }

        with self._buffer_lock:
            self._global_buffer.append(metric)

            # Auto-flush if buffer gets large
            if len(self._global_buffer) >= 100:
                self._flush_buffer()

    def increment(self, metric_type: str, amount: float = 1) -> None:
        """Convenience method for incrementing counters.

        Args:
            metric_type: Type of metric to increment
            amount: Amount to increment by (default: 1)
        """
        self.track(metric_type, amount)

    def timing(self, metric_type: str, duration_ms: float) -> None:
        """Record a timing metric.

        Args:
            metric_type: Type of timing metric
            duration_ms: Duration in milliseconds
        """
        self.track(metric_type, duration_ms, tags={"unit": "ms"})

    def error(self, error_type: str, message: str = "") -> None:
        """Record an error.

        Args:
            error_type: Type/category of error
            message: Optional error message
        """
        self.track("errors", 1, tags={"error_type": error_type, "message": message[:200]})

    def _flush_buffer(self) -> None:
        """Flush buffered metrics to database (internal, assumes lock held)."""
        if not self._global_buffer:
            return

        metrics_to_write = self._global_buffer.copy()
        self._global_buffer.clear()

        try:
            with self._get_connection() as conn:
                conn.executemany(
                    """INSERT INTO metrics (run_id, metric_type, value, tags, timestamp)
                       VALUES (?, ?, ?, ?, ?)""",
                    [
                        (self.run_id, m["metric_type"], m["value"], m["tags"], m["timestamp"])
                        for m in metrics_to_write
                    ]
                )
        except Exception as e:
            # Don't crash the main script if analytics fails
            print(f"[Analytics] Warning: Failed to flush metrics: {e}")

    def flush(self, status: str = "completed") -> None:
        """Flush all buffered metrics and mark run as complete.

        Args:
            status: Final run status ("completed", "failed", "cancelled")
        """
        if not self.enabled:
            return

        with self._buffer_lock:
            self._flush_buffer()

        # Update run status
        if self.run_id:
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        "UPDATE runs SET end_time = ?, status = ? WHERE id = ?",
                        (datetime.now().isoformat(), status, self.run_id)
                    )
            except Exception as e:
                print(f"[Analytics] Warning: Failed to update run status: {e}")

    def __enter__(self) -> "Analytics":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with auto-flush."""
        status = "failed" if exc_type else "completed"
        self.flush(status)

    # -------------------------------------------------------------------------
    # Query methods for dashboard
    # -------------------------------------------------------------------------

    def get_metrics_today(self) -> Dict[str, float]:
        """Get aggregated metrics for today.

        Returns:
            Dict mapping metric_type to total value
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return self._get_metrics_for_date(today)

    def get_metrics_range(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily metrics for the last N days.

        Args:
            days: Number of days to include

        Returns:
            List of daily summaries with date and metrics
        """
        results = []
        for i in range(days):
            from datetime import timedelta
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            metrics = self._get_metrics_for_date(date)
            if metrics:
                results.append({"date": date, "metrics": metrics})
        return results

    def _get_metrics_for_date(self, date: str) -> Dict[str, float]:
        """Get aggregated metrics for a specific date."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT metric_type, SUM(value) as total
                       FROM metrics
                       WHERE timestamp LIKE ?
                       GROUP BY metric_type""",
                    (f"{date}%",)
                )
                return {row["metric_type"]: row["total"] for row in cursor}
        except Exception:
            return {}

    def get_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent pipeline runs.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of run records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT id, script_name, start_time, end_time, status
                       FROM runs
                       ORDER BY start_time DESC
                       LIMIT ?""",
                    (limit,)
                )
                return [dict(row) for row in cursor]
        except Exception:
            return []

    def get_run_metrics(self, run_id: int) -> List[Dict[str, Any]]:
        """Get metrics for a specific run.

        Args:
            run_id: ID of the run

        Returns:
            List of metric records
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """SELECT metric_type, SUM(value) as total, COUNT(*) as count
                       FROM metrics
                       WHERE run_id = ?
                       GROUP BY metric_type""",
                    (run_id,)
                )
                return [dict(row) for row in cursor]
        except Exception:
            return []


# Global instance for simple usage
_analytics: Optional[Analytics] = None


def get_analytics(script_name: Optional[str] = None) -> Analytics:
    """Get or create the global analytics instance.

    Args:
        script_name: Optional script name override

    Returns:
        Analytics instance
    """
    global _analytics
    if _analytics is None:
        _analytics = Analytics(script_name=script_name)
    return _analytics


def track(metric_type: str, value: float = 1, tags: Optional[Dict[str, Any]] = None) -> None:
    """Convenience function for tracking metrics using global instance.

    Args:
        metric_type: Type of metric
        value: Value to record
        tags: Optional tags
    """
    get_analytics().track(metric_type, value, tags)


def flush(status: str = "completed") -> None:
    """Flush the global analytics instance.

    Args:
        status: Final run status
    """
    if _analytics:
        _analytics.flush(status)


# CLI for quick reporting
if __name__ == "__main__":
    import sys

    analytics = Analytics(script_name="analytics_cli")

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "--today":
            metrics = analytics.get_metrics_today()
            print("=== Today's Metrics ===")
            for metric, value in sorted(metrics.items()):
                print(f"  {metric}: {value:,.0f}")

        elif cmd == "--summary":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            print(f"=== Last {days} Days ===")
            for day_data in analytics.get_metrics_range(days):
                print(f"\n{day_data['date']}:")
                for metric, value in sorted(day_data["metrics"].items()):
                    print(f"  {metric}: {value:,.0f}")

        elif cmd == "--runs":
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            runs = analytics.get_runs(limit)
            print(f"=== Recent Runs (last {limit}) ===")
            for run in runs:
                status_icon = {"completed": "+", "failed": "X", "running": "~"}.get(run["status"], "?")
                print(f"  [{status_icon}] {run['script_name']} @ {run['start_time'][:19]}")

        else:
            print("Usage: python analytics.py [--today | --summary [days] | --runs [limit]]")
    else:
        print("Usage: python analytics.py [--today | --summary [days] | --runs [limit]]")
        print("\nAnalytics tracking module for Reeld pipeline.")
        print(f"Database: {ANALYTICS_DB_PATH}")
        print(f"Enabled: {ANALYTICS_ENABLED}")
