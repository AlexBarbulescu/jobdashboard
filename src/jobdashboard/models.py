from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class JobRecord:
    source_name: str
    title: str
    company: str
    location: str
    summary: str
    apply_url: str
    source_url: str
    posted_at: datetime | None
    status: str = "new"
    is_new: bool = False


@dataclass(slots=True)
class SourceHealth:
    source_name: str
    status: str
    message: str
    checked_at: datetime | None


@dataclass(slots=True)
class RefreshReport:
    success_count: int
    failure_count: int
    jobs_written: int
    started_at: datetime
    finished_at: datetime