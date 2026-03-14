from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

from .config import Settings
from .models import JobRecord


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CryptoDesignSentinel/1.0"


@dataclass(slots=True)
class SourceResult:
    source_name: str
    jobs: list[JobRecord]
    status: str
    message: str


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _looks_relevant(text: str, markers: Iterable[str]) -> bool:
    normalized = _normalize(text)
    return any(marker.lower() in normalized for marker in markers)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def _parse_unix_millis(value: int | float | None) -> datetime | None:
    if value is None:
        return None
    try:
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, tz=UTC)
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _sanitize_text(html_value: str | None) -> str:
    if not html_value:
        return ""
    soup = BeautifulSoup(html_value, "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def _line_to_source(raw: str) -> tuple[str, str]:
    name, url = raw.split("|", 1)
    return name.strip(), url.strip()


def _metadata_text(metadata: list[dict] | None) -> str:
    if not metadata:
        return ""
    chunks: list[str] = []
    for item in metadata:
        name = str(item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if name and value:
            chunks.append(f"{name}: {value}")
    return " | ".join(chunks)


def _filter_job(settings: Settings, title: str, location: str, body: str) -> bool:
    composite = " ".join([title, location, body])
    return (
        _looks_relevant(title, settings.allowed_titles)
        and _looks_relevant(location or body, settings.remote_markers)
        and _looks_relevant(composite, settings.industry_markers)
    )


class RssSource:
    def __init__(self, source_name: str, url: str, settings: Settings) -> None:
        self.source_name = source_name
        self.url = url
        self.settings = settings

    def fetch(self) -> SourceResult:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(self.url, timeout=self.settings.request_timeout_seconds, headers=headers)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        jobs: list[JobRecord] = []
        for entry in parsed.entries:
            title = (entry.get("title") or "").strip()
            company = (entry.get("author") or entry.get("source", {}).get("title") or self.source_name).strip()
            location = (entry.get("location") or entry.get("tags", [{}])[0].get("term") or "Remote").strip()
            summary = _sanitize_text(entry.get("summary") or entry.get("description") or "")
            body = " ".join(filter(None, [summary, title, company, location]))
            if not _filter_job(self.settings, title, location, body):
                continue
            jobs.append(
                JobRecord(
                    source_name=self.source_name,
                    title=title,
                    company=company or "Unknown",
                    location=location or "Remote",
                    summary=summary[:1200],
                    apply_url=(entry.get("link") or self.url).strip(),
                    source_url=(entry.get("link") or self.url).strip(),
                    posted_at=_parse_datetime(entry.get("published") or entry.get("updated")),
                )
            )
        return SourceResult(self.source_name, jobs, "ok", f"Fetched {len(jobs)} matching jobs")


class SchemaSource:
    def __init__(self, source_name: str, url: str, settings: Settings) -> None:
        self.source_name = source_name
        self.url = url
        self.settings = settings

    def fetch(self) -> SourceResult:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(self.url, timeout=self.settings.request_timeout_seconds, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        jobs: list[JobRecord] = []
        for script in soup.select('script[type="application/ld+json"]'):
            raw = script.string or script.get_text(strip=True)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            jobs.extend(self._extract_jobs(payload))
        return SourceResult(self.source_name, jobs, "ok", f"Fetched {len(jobs)} matching jobs")

    def _extract_jobs(self, payload: object) -> list[JobRecord]:
        extracted: list[JobRecord] = []
        if isinstance(payload, list):
            for item in payload:
                extracted.extend(self._extract_jobs(item))
            return extracted
        if isinstance(payload, dict) and "@graph" in payload:
            return self._extract_jobs(payload.get("@graph"))
        if not isinstance(payload, dict):
            return extracted
        item_type = str(payload.get("@type", ""))
        if "JobPosting" not in item_type:
            return extracted

        title = str(payload.get("title") or "").strip()
        hiring_org = payload.get("hiringOrganization") or {}
        company = str(hiring_org.get("name") or self.source_name).strip()
        location = "Remote"
        job_location_type = str(payload.get("jobLocationType") or "")
        job_location = payload.get("jobLocation") or {}
        if isinstance(job_location, list) and job_location:
            job_location = job_location[0]
        if isinstance(job_location, dict):
            address = job_location.get("address") or {}
            location = ", ".join(
                filter(None, [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")])
            ) or location
        if job_location_type:
            location = job_location_type.replace("TELECOMMUTE", "Remote")
        description = _sanitize_text(str(payload.get("description") or ""))
        body = " ".join(filter(None, [title, company, location, description]))
        if not _filter_job(self.settings, title, location, body):
            return extracted
        apply_url = str(payload.get("url") or self.url).strip()
        extracted.append(
            JobRecord(
                source_name=self.source_name,
                title=title,
                company=company or "Unknown",
                location=location,
                summary=description[:1200],
                apply_url=apply_url,
                source_url=apply_url,
                posted_at=_parse_datetime(str(payload.get("datePosted") or "")),
            )
        )
        return extracted


class GreenhouseSource:
    def __init__(self, source_name: str, board_token: str, settings: Settings) -> None:
        self.source_name = source_name
        self.board_token = board_token
        self.settings = settings
        self.url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

    def fetch(self) -> SourceResult:
        response = requests.get(
            self.url,
            timeout=self.settings.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
        jobs: list[JobRecord] = []
        for item in payload.get("jobs", []):
            title = str(item.get("title") or "").strip()
            company = str(item.get("company_name") or self.source_name).strip()
            location = str((item.get("location") or {}).get("name") or "Remote").strip()
            metadata_text = _metadata_text(item.get("metadata"))
            body = f"{title} {company} {location} {metadata_text} crypto web3 blockchain defi"
            if not _filter_job(self.settings, title, location, body):
                continue
            jobs.append(
                JobRecord(
                    source_name=self.source_name,
                    title=title,
                    company=company,
                    location=location,
                    summary=(metadata_text or f"Direct company careers listing from {self.source_name}.")[:1200],
                    apply_url=str(item.get("absolute_url") or self.url).strip(),
                    source_url=str(item.get("absolute_url") or self.url).strip(),
                    posted_at=_parse_datetime(str(item.get("first_published") or item.get("updated_at") or "")),
                )
            )
        return SourceResult(self.source_name, jobs, "ok", f"Fetched {len(jobs)} matching jobs")


class LeverSource:
    def __init__(self, source_name: str, board_token: str, settings: Settings) -> None:
        self.source_name = source_name
        self.board_token = board_token
        self.settings = settings
        self.url = f"https://api.lever.co/v0/postings/{board_token}?mode=json"

    def fetch(self) -> SourceResult:
        response = requests.get(
            self.url,
            timeout=self.settings.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
        jobs: list[JobRecord] = []
        for item in payload:
            title = str(item.get("text") or "").strip()
            categories = item.get("categories") or {}
            workplace_type = str(item.get("workplaceType") or "").strip()
            category_parts = [str(value).strip() for value in categories.values() if value]
            location = workplace_type or str(categories.get("location") or item.get("country") or "Remote").strip()
            summary_parts = [
                str(item.get("descriptionPlain") or "").strip(),
                str(item.get("openingPlain") or "").strip(),
                str(item.get("additionalPlain") or "").strip(),
            ]
            summary = " ".join(part for part in summary_parts if part)
            body = " ".join([title, self.source_name, location, summary, *category_parts, "crypto web3 blockchain defi"])
            if not _filter_job(self.settings, title, location, body):
                continue
            apply_url = str(item.get("hostedUrl") or item.get("applyUrl") or self.url).strip()
            jobs.append(
                JobRecord(
                    source_name=self.source_name,
                    title=title,
                    company=self.source_name,
                    location=location,
                    summary=(summary or "Direct company careers listing.")[:1200],
                    apply_url=apply_url,
                    source_url=apply_url,
                    posted_at=_parse_unix_millis(item.get("createdAt")),
                )
            )
        return SourceResult(self.source_name, jobs, "ok", f"Fetched {len(jobs)} matching jobs")


class RemoteOkSource:
    def __init__(self, source_name: str, settings: Settings) -> None:
        self.source_name = source_name
        self.settings = settings
        self.url = "https://remoteok.com/api"

    def fetch(self) -> SourceResult:
        response = requests.get(
            self.url,
            timeout=self.settings.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
        jobs: list[JobRecord] = []
        for item in payload:
            if not isinstance(item, dict) or "position" not in item:
                continue
            title = str(item.get("position") or "").strip()
            company = str(item.get("company") or self.source_name).strip()
            location = str(item.get("location") or "Remote").strip()
            tags = item.get("tags") or []
            tag_text = " ".join(str(tag) for tag in tags)
            summary = _sanitize_text(str(item.get("description") or ""))
            body = " ".join([title, company, location, summary, tag_text])
            if not _filter_job(self.settings, title, location, body):
                continue
            apply_url = str(item.get("apply_url") or item.get("url") or self.url).strip()
            jobs.append(
                JobRecord(
                    source_name=self.source_name,
                    title=title,
                    company=company,
                    location=location,
                    summary=summary[:1200],
                    apply_url=apply_url,
                    source_url=str(item.get("url") or apply_url).strip(),
                    posted_at=_parse_datetime(str(item.get("date") or "")) or _parse_unix_millis(item.get("epoch")),
                )
            )
        return SourceResult(self.source_name, jobs, "ok", f"Fetched {len(jobs)} matching jobs")


class RemotiveSource:
    def __init__(self, source_name: str, settings: Settings) -> None:
        self.source_name = source_name
        self.settings = settings
        self.url = "https://remotive.com/api/remote-jobs"

    def fetch(self) -> SourceResult:
        response = requests.get(
            self.url,
            timeout=self.settings.request_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        payload = response.json()
        jobs: list[JobRecord] = []
        for item in payload.get("jobs", []):
            title = str(item.get("title") or "").strip()
            company = str(item.get("company_name") or self.source_name).strip()
            location = str(item.get("candidate_required_location") or item.get("job_type") or "Remote").strip()
            tags = item.get("tags") or []
            category = str(item.get("category") or "").strip()
            summary = _sanitize_text(str(item.get("description") or ""))
            body = " ".join([title, company, location, summary, category, *[str(tag) for tag in tags]])
            if not _filter_job(self.settings, title, location, body):
                continue
            jobs.append(
                JobRecord(
                    source_name=self.source_name,
                    title=title,
                    company=company,
                    location=location,
                    summary=summary[:1200],
                    apply_url=str(item.get("url") or self.url).strip(),
                    source_url=str(item.get("url") or self.url).strip(),
                    posted_at=_parse_datetime(str(item.get("publication_date") or "")),
                )
            )
        return SourceResult(self.source_name, jobs, "ok", f"Fetched {len(jobs)} matching jobs")


def build_sources(settings: Settings) -> list[object]:
    sources: list[object] = []
    for raw in settings.rss_sources:
        name, url = _line_to_source(raw)
        sources.append(RssSource(name, url, settings))
    for raw in settings.schema_sources:
        name, url = _line_to_source(raw)
        sources.append(SchemaSource(name, url, settings))
    for raw in settings.greenhouse_sources:
        name, token = _line_to_source(raw)
        sources.append(GreenhouseSource(name, token, settings))
    for raw in settings.lever_sources:
        name, token = _line_to_source(raw)
        sources.append(LeverSource(name, token, settings))
    for raw in settings.remote_api_sources:
        name, provider = _line_to_source(raw)
        normalized_provider = provider.strip().lower()
        if normalized_provider == "remoteok":
            sources.append(RemoteOkSource(name, settings))
        elif normalized_provider == "remotive":
            sources.append(RemotiveSource(name, settings))
    return sources