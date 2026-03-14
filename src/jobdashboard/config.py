from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


DEFAULT_RSS_SOURCES = [
    "CryptoCurrencyJobs|https://cryptocurrencyjobs.co/feed/",
    "Web3 Career|https://web3.career/feed",
]

DEFAULT_SCHEMA_SOURCES = [
    "CryptoJobsList|https://cryptojobslist.com/design",
]

DEFAULT_GREENHOUSE_SOURCES = [
    "Coinbase|coinbase",
    "Ripple|ripple",
    "Consensys|consensys",
    "Alchemy|alchemy",
    "Fireblocks|fireblocks",
    "Gemini|gemini",
    "BitGo|bitgo",
]

DEFAULT_LEVER_SOURCES = [
    "Anchorage|anchorage",
    "MoonPay|moonpay",
    "Kraken|kraken",
]

DEFAULT_REMOTE_API_SOURCES = [
    "RemoteOK|remoteok",
    "Remotive|remotive",
]


def _get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _split_lines(value: str | None, default: list[str]) -> list[str]:
    if value is None:
        return default
    return [segment.strip() for segment in re.split(r"[\r\n;]+", value) if segment.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str
    database_path: Path
    refresh_interval_seconds: int
    dashboard_poll_seconds: int
    request_timeout_seconds: int
    job_limit: int
    rss_sources: list[str]
    schema_sources: list[str]
    greenhouse_sources: list[str]
    lever_sources: list[str]
    remote_api_sources: list[str]
    allowed_titles: list[str]
    remote_markers: list[str]
    industry_markers: list[str]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    database_path = Path(os.getenv("DATABASE_PATH", str(data_dir / "jobs.db")))
    return Settings(
        app_name=os.getenv("APP_NAME", "Crypto Design Job Sentinel"),
        database_path=database_path,
        refresh_interval_seconds=_get_env_int("REFRESH_INTERVAL_SECONDS", 300),
        dashboard_poll_seconds=_get_env_int("DASHBOARD_POLL_SECONDS", 20),
        request_timeout_seconds=_get_env_int("REQUEST_TIMEOUT_SECONDS", 25),
        job_limit=_get_env_int("JOB_LIMIT", 200),
        rss_sources=_split_lines(os.getenv("RSS_SOURCES"), DEFAULT_RSS_SOURCES),
        schema_sources=_split_lines(os.getenv("SCHEMA_SOURCES"), DEFAULT_SCHEMA_SOURCES),
        greenhouse_sources=_split_lines(os.getenv("GREENHOUSE_SOURCES"), DEFAULT_GREENHOUSE_SOURCES),
        lever_sources=_split_lines(os.getenv("LEVER_SOURCES"), DEFAULT_LEVER_SOURCES),
        remote_api_sources=_split_lines(os.getenv("REMOTE_API_SOURCES"), DEFAULT_REMOTE_API_SOURCES),
        allowed_titles=_split_lines(
            os.getenv("ALLOWED_TITLES"),
            [
                "ui/ux",
                "product designer",
                "product design",
                "ui designer",
                "ux designer",
                "advertising designer",
                "graphic designer",
                "visual designer",
                "brand designer",
                "marketing designer",
                "motion designer",
                "content designer",
                "design lead",
                "senior designer",
            ],
        ),
        remote_markers=_split_lines(
            os.getenv("REMOTE_MARKERS"),
            ["remote", "anywhere", "distributed", "worldwide"],
        ),
        industry_markers=_split_lines(
            os.getenv("INDUSTRY_MARKERS"),
            ["crypto", "web3", "blockchain", "defi"],
        ),
    )