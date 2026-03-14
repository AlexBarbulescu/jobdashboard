from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobdashboard import get_settings  # noqa: E402
from jobdashboard.pipeline import bootstrap_if_empty, refresh_jobs  # noqa: E402
from jobdashboard.storage import Storage  # noqa: E402


def main() -> None:
    settings = get_settings()
    storage = Storage(settings.database_path)
    bootstrap_if_empty(storage, settings)
    while True:
        refresh_jobs(storage, settings)
        time.sleep(settings.refresh_interval_seconds)


if __name__ == "__main__":
    main()