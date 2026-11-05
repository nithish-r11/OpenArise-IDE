"""
Local SQLite Usage Analytics Database for OpenArise IDE.
Stores and aggregates actual Ollama generation metrics (tokens, latency, speed, status).
Completely local, privacy-first, zero cloud telemetry.
"""

from __future__ import annotations
import csv
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


OPERATION_CHAT = "Chat"
OPERATION_INLINE = "Inline AI Edit"
OPERATION_TEST_GEN = "Test Generation"
OPERATION_AGENT = "AI Agent"
OPERATION_GIT = "Git AI Assistant"

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


@dataclass
class ModelUsageMetrics:
    model: str
    operation_type: str
    input_tokens: Optional[int] = None       # prompt_eval_count
    output_tokens: Optional[int] = None      # eval_count
    total_tokens: Optional[int] = None       # input_tokens + output_tokens
    duration_ms: Optional[float] = None      # total_duration in ms
    load_duration_ms: Optional[float] = None  # load_duration in ms
    eval_duration_ms: Optional[float] = None  # eval_duration in ms
    tokens_per_second: Optional[float] = None # calculated speed
    status: str = STATUS_SUCCESS
    error_message: str = ""
    timestamp: float = field(default_factory=time.time)

    @classmethod
    def from_ollama_payload(
        cls,
        model: str,
        operation_type: str,
        payload: dict,
        status: str = STATUS_SUCCESS,
        error_message: str = "",
        timestamp: Optional[float] = None,
    ) -> ModelUsageMetrics:
        """
        Constructs a ModelUsageMetrics instance from an Ollama response payload.
        Authoritative metrics are preserved; nulls remain null when unmeasured.
        """
        input_tokens = payload.get("prompt_eval_count")
        output_tokens = payload.get("eval_count")
        total_dur_ns = payload.get("total_duration")
        load_dur_ns = payload.get("load_duration")
        eval_dur_ns = payload.get("eval_duration")

        # Total tokens
        total_tokens = None
        if input_tokens is not None or output_tokens is not None:
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        # Durations in ms
        duration_ms = (total_dur_ns / 1e6) if total_dur_ns is not None else None
        load_duration_ms = (load_dur_ns / 1e6) if load_dur_ns is not None else None
        eval_duration_ms = (eval_dur_ns / 1e6) if eval_dur_ns is not None else None

        # Tokens per second = eval_count / (eval_duration in seconds)
        tokens_per_second = None
        if output_tokens is not None and eval_dur_ns and eval_dur_ns > 0:
            tokens_per_second = round(output_tokens / (eval_dur_ns / 1e9), 2)

        return cls(
            model=model or payload.get("model", "unknown"),
            operation_type=operation_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            load_duration_ms=round(load_duration_ms, 2) if load_duration_ms is not None else None,
            eval_duration_ms=round(eval_duration_ms, 2) if eval_duration_ms is not None else None,
            tokens_per_second=tokens_per_second,
            status=status,
            error_message=error_message,
            timestamp=timestamp if timestamp is not None else time.time(),
        )


class AnalyticsDatabase:
    """
    Manages the local SQLite database storing model usage events and computing
    performance statistics.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            config_dir = Path.home() / ".openarise"
            config_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = config_dir / "analytics.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usage_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    model TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    total_tokens INTEGER,
                    duration_ms REAL,
                    load_duration_ms REAL,
                    eval_duration_ms REAL,
                    tokens_per_second REAL,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON usage_events (timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_model ON usage_events (model)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_op ON usage_events (operation_type)")

    def record_event(self, metrics: ModelUsageMetrics) -> int:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO usage_events (
                    timestamp, model, operation_type, input_tokens, output_tokens,
                    total_tokens, duration_ms, load_duration_ms, eval_duration_ms,
                    tokens_per_second, status, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.timestamp,
                metrics.model,
                metrics.operation_type,
                metrics.input_tokens,
                metrics.output_tokens,
                metrics.total_tokens,
                metrics.duration_ms,
                metrics.load_duration_ms,
                metrics.eval_duration_ms,
                metrics.tokens_per_second,
                metrics.status,
                metrics.error_message,
            ))
            return cur.lastrowid

    def get_summary_stats(self) -> dict[str, Any]:
        """Calculates global aggregate metrics."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    COUNT(*) AS total_requests,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successful_requests,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_requests,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_requests,
                    COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS total_output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    AVG(duration_ms) AS avg_duration_ms,
                    AVG(load_duration_ms) AS avg_load_duration_ms,
                    AVG(tokens_per_second) AS avg_tokens_per_second
                FROM usage_events
            """)
            row = cur.fetchone()
            if not row or row["total_requests"] == 0:
                return {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "cancelled_requests": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "total_tokens": 0,
                    "avg_duration_ms": 0.0,
                    "avg_load_duration_ms": 0.0,
                    "avg_tokens_per_second": 0.0,
                    "success_rate": 0.0,
                }

            total = row["total_requests"]
            success = row["successful_requests"] or 0
            return {
                "total_requests": total,
                "successful_requests": success,
                "failed_requests": row["failed_requests"] or 0,
                "cancelled_requests": row["cancelled_requests"] or 0,
                "total_input_tokens": row["total_input_tokens"] or 0,
                "total_output_tokens": row["total_output_tokens"] or 0,
                "total_tokens": row["total_tokens"] or 0,
                "avg_duration_ms": round(row["avg_duration_ms"] or 0.0, 2),
                "avg_load_duration_ms": round(row["avg_load_duration_ms"] or 0.0, 2),
                "avg_tokens_per_second": round(row["avg_tokens_per_second"] or 0.0, 2),
                "success_rate": round((success / total) * 100, 1) if total else 0.0,
            }

    def get_daily_usage(self, days: int = 30) -> list[dict[str, Any]]:
        since = time.time() - (days * 86400)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    strftime('%Y-%m-%d', datetime(timestamp, 'unixepoch', 'localtime')) AS period,
                    COUNT(*) AS request_count,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    AVG(tokens_per_second) AS avg_speed
                FROM usage_events
                WHERE timestamp >= ?
                GROUP BY period
                ORDER BY period DESC
            """, (since,))
            return [dict(r) for r in cur.fetchall()]

    def get_weekly_usage(self, weeks: int = 12) -> list[dict[str, Any]]:
        since = time.time() - (weeks * 7 * 86400)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    strftime('%Y-W%W', datetime(timestamp, 'unixepoch', 'localtime')) AS period,
                    COUNT(*) AS request_count,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    AVG(tokens_per_second) AS avg_speed
                FROM usage_events
                WHERE timestamp >= ?
                GROUP BY period
                ORDER BY period DESC
            """, (since,))
            return [dict(r) for r in cur.fetchall()]

    def get_monthly_usage(self, months: int = 12) -> list[dict[str, Any]]:
        since = time.time() - (months * 31 * 86400)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    strftime('%Y-%m', datetime(timestamp, 'unixepoch', 'localtime')) AS period,
                    COUNT(*) AS request_count,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    AVG(tokens_per_second) AS avg_speed
                FROM usage_events
                WHERE timestamp >= ?
                GROUP BY period
                ORDER BY period DESC
            """, (since,))
            return [dict(r) for r in cur.fetchall()]

    def get_per_model_usage(self) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    model,
                    COUNT(*) AS request_count,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    AVG(tokens_per_second) AS avg_speed,
                    AVG(duration_ms) AS avg_duration
                FROM usage_events
                GROUP BY model
                ORDER BY total_tokens DESC
            """)
            results = []
            for r in cur.fetchall():
                d = dict(r)
                reqs = d["request_count"]
                succ = d["success_count"]
                d["success_rate"] = round((succ / reqs) * 100, 1) if reqs else 0.0
                d["avg_speed"] = round(d["avg_speed"] or 0.0, 2)
                d["avg_duration"] = round(d["avg_duration"] or 0.0, 2)
                results.append(d)
            return results

    def get_per_operation_usage(self) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    operation_type,
                    COUNT(*) AS request_count,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    AVG(duration_ms) AS avg_duration
                FROM usage_events
                GROUP BY operation_type
                ORDER BY request_count DESC
            """)
            return [dict(r) for r in cur.fetchall()]

    def get_recent_requests(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 
                    id,
                    datetime(timestamp, 'unixepoch', 'localtime') AS formatted_time,
                    model,
                    operation_type,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    duration_ms,
                    tokens_per_second,
                    status,
                    error_message
                FROM usage_events
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            return [dict(r) for r in cur.fetchall()]

    def export_to_csv(self, target_path: Path) -> tuple[bool, str]:
        """Exports the entire event history to a CSV file."""
        try:
            target_path = Path(target_path)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with self._get_connection() as conn, open(target_path, "w", newline="", encoding="utf-8") as f:
                cur = conn.cursor()
                cur.execute("""
                    SELECT 
                        id,
                        datetime(timestamp, 'unixepoch', 'localtime') AS timestamp_local,
                        model,
                        operation_type,
                        input_tokens,
                        output_tokens,
                        total_tokens,
                        duration_ms,
                        load_duration_ms,
                        eval_duration_ms,
                        tokens_per_second,
                        status,
                        error_message
                    FROM usage_events
                    ORDER BY timestamp ASC
                """)
                rows = cur.fetchall()
                if not rows:
                    writer = csv.writer(f)
                    writer.writerow([
                        "id", "timestamp_local", "model", "operation_type",
                        "input_tokens", "output_tokens", "total_tokens",
                        "duration_ms", "load_duration_ms", "eval_duration_ms",
                        "tokens_per_second", "status", "error_message"
                    ])
                    return True, "Exported empty CSV header."

                writer = csv.writer(f)
                writer.writerow(rows[0].keys())
                for r in rows:
                    writer.writerow(tuple(r))

            return True, f"Successfully exported {len(rows)} record(s) to '{target_path.name}'."
        except Exception as exc:
            return False, f"Failed to export CSV: {exc}"

    def clear_history(self) -> int:
        """Clears all records and recovers space with VACUUM."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM usage_events")
            count = cur.fetchone()[0]
            cur.execute("DELETE FROM usage_events")
            conn.commit()
            cur.execute("VACUUM")
            return count

