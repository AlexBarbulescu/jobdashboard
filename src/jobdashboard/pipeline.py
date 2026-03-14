from __future__ import annotations

from datetime import UTC, datetime

from .config import Settings
from .sources import build_sources
from .storage import Storage


def refresh_jobs(storage: Storage, settings: Settings) -> dict:
    started_at = datetime.now(UTC)
    success_count = 0
    failure_count = 0
    jobs_written = 0
    sources = build_sources(settings)

    storage.prune_source_checks([source.source_name for source in sources])

    for source in sources:
        try:
            result = source.fetch()
        except Exception as exc:  # noqa: BLE001
            failure_count += 1
            storage.record_source_check(source.source_name, "error", str(exc)[:250])
            continue

        success_count += 1
        jobs_written += storage.upsert_jobs(result.jobs)
        storage.record_source_check(result.source_name, result.status, result.message)

    finished_at = datetime.now(UTC)
    storage.record_refresh_run(started_at, finished_at, success_count, failure_count, jobs_written)
    return {
        "success_count": success_count,
        "failure_count": failure_count,
        "jobs_written": jobs_written,
        "started_at": started_at,
        "finished_at": finished_at,
    }


def bootstrap_if_empty(storage: Storage, settings: Settings) -> dict | None:
    storage.initialize()
    if storage.has_jobs():
        return None
    return refresh_jobs(storage, settings)