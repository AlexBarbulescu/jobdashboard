from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from .models import JobRecord, SourceHealth


STATUS_VALUES = {"new", "saved", "applied", "ignored"}


def _to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _from_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def build_job_key(source_name: str, title: str, company: str, apply_url: str) -> str:
    raw = "|".join([source_name.strip().lower(), title.strip().lower(), company.strip().lower(), apply_url.strip()])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Storage:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_key TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    apply_url TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    posted_at TEXT,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'new'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_checks (
                    source_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    checked_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS refresh_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    success_count INTEGER NOT NULL,
                    failure_count INTEGER NOT NULL,
                    jobs_written INTEGER NOT NULL
                )
                """
            )

    def has_jobs(self) -> bool:
        with self.connect() as connection:
            row = connection.execute("SELECT COUNT(1) AS total FROM jobs").fetchone()
            return bool(row and row["total"])

    def upsert_jobs(self, jobs: list[JobRecord]) -> int:
        if not jobs:
            return 0
        now = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            for job in jobs:
                job_key = build_job_key(job.source_name, job.title, job.company, job.apply_url)
                connection.execute(
                    """
                    INSERT INTO jobs (
                        job_key, source_name, title, company, location, summary,
                        apply_url, source_url, posted_at, first_seen_at, last_seen_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(job_key) DO UPDATE SET
                        location = excluded.location,
                        summary = excluded.summary,
                        source_url = excluded.source_url,
                        posted_at = COALESCE(excluded.posted_at, jobs.posted_at),
                        last_seen_at = excluded.last_seen_at
                    """,
                    (
                        job_key,
                        job.source_name,
                        job.title,
                        job.company,
                        job.location,
                        job.summary,
                        job.apply_url,
                        job.source_url,
                        _to_iso(job.posted_at),
                        now,
                        now,
                        job.status if job.status in STATUS_VALUES else "new",
                    ),
                )
            return len(jobs)

    def record_source_check(self, source_name: str, status: str, message: str) -> None:
        checked_at = datetime.now(UTC).isoformat()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO source_checks (source_name, status, message, checked_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_name) DO UPDATE SET
                    status = excluded.status,
                    message = excluded.message,
                    checked_at = excluded.checked_at
                """,
                (source_name, status, message, checked_at),
            )

    def prune_source_checks(self, active_source_names: list[str]) -> None:
        with self.connect() as connection:
            if not active_source_names:
                connection.execute("DELETE FROM source_checks")
                return
            placeholders = ", ".join("?" for _ in active_source_names)
            connection.execute(
                f"DELETE FROM source_checks WHERE source_name NOT IN ({placeholders})",
                active_source_names,
            )

    def record_refresh_run(
        self,
        started_at: datetime,
        finished_at: datetime,
        success_count: int,
        failure_count: int,
        jobs_written: int,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO refresh_runs (started_at, finished_at, success_count, failure_count, jobs_written)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _to_iso(started_at),
                    _to_iso(finished_at),
                    success_count,
                    failure_count,
                    jobs_written,
                ),
            )

    def update_job_status(self, job_key: str, status: str) -> None:
        if status not in STATUS_VALUES:
            raise ValueError(f"Unsupported status: {status}")
        with self.connect() as connection:
            connection.execute("UPDATE jobs SET status = ? WHERE job_key = ?", (status, job_key))

    def list_jobs(self, status: str = "all", search: str = "", limit: int = 200) -> list[dict]:
        clauses = []
        params: list[object] = []
        if status != "all":
            clauses.append("status = ?")
            params.append(status)
        if search:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(summary) LIKE ?)")
            needle = f"%{search.lower()}%"
            params.extend([needle, needle, needle])

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        query = f"""
            SELECT job_key, source_name, title, company, location, summary,
                   apply_url, source_url, posted_at, first_seen_at, last_seen_at, status
            FROM jobs
            {where_clause}
            ORDER BY COALESCE(posted_at, first_seen_at) DESC, last_seen_at DESC
            LIMIT ?
        """
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        now = datetime.now(UTC)
        jobs: list[dict] = []
        for row in rows:
            first_seen_at = _from_iso(row["first_seen_at"])
            posted_at = _from_iso(row["posted_at"])
            freshness_reference = posted_at or first_seen_at
            is_new = bool(freshness_reference and freshness_reference >= now - timedelta(hours=24))
            jobs.append(
                {
                    "job_key": row["job_key"],
                    "source_name": row["source_name"],
                    "title": row["title"],
                    "company": row["company"],
                    "location": row["location"],
                    "summary": row["summary"],
                    "apply_url": row["apply_url"],
                    "source_url": row["source_url"],
                    "posted_at": posted_at,
                    "first_seen_at": first_seen_at,
                    "last_seen_at": _from_iso(row["last_seen_at"]),
                    "status": row["status"],
                    "is_new": is_new,
                }
            )
        return jobs

    def get_metrics(self) -> dict:
        with self.connect() as connection:
            totals = connection.execute(
                """
                SELECT
                    COUNT(1) AS total_jobs,
                    SUM(CASE WHEN status = 'saved' THEN 1 ELSE 0 END) AS saved_jobs,
                    SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END) AS applied_jobs,
                    SUM(CASE WHEN COALESCE(posted_at, first_seen_at) >= ? THEN 1 ELSE 0 END) AS new_jobs
                FROM jobs
                """,
                ((datetime.now(UTC) - timedelta(hours=24)).isoformat(),),
            ).fetchone()
            latest_run = connection.execute(
                "SELECT finished_at, success_count, failure_count, jobs_written FROM refresh_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return {
            "total_jobs": totals["total_jobs"] or 0,
            "saved_jobs": totals["saved_jobs"] or 0,
            "applied_jobs": totals["applied_jobs"] or 0,
            "new_jobs": totals["new_jobs"] or 0,
            "latest_run": dict(latest_run) if latest_run else None,
        }

    def list_source_health(self) -> list[SourceHealth]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT source_name, status, message, checked_at FROM source_checks ORDER BY checked_at DESC"
            ).fetchall()
        return [
            SourceHealth(
                source_name=row["source_name"],
                status=row["status"],
                message=row["message"],
                checked_at=_from_iso(row["checked_at"]),
            )
            for row in rows
        ]