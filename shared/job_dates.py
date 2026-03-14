from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import re


ROMANIAN_MONTHS = {
    "ian": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "mai": 5,
    "iun": 6,
    "iul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def parse_relative_age_to_datetime(value, now=None):
    if not value:
        return None

    now = now or datetime.now()
    normalized = str(value).strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)

    if normalized in {"today", "recent", "just now"}:
        return now
    if normalized == "yesterday":
        return now - timedelta(days=1)

    ago_match = re.search(r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks|month|months|year|years)\s+ago", normalized)
    if ago_match:
        amount = int(ago_match.group(1))
        unit = ago_match.group(2)
        return now - _unit_to_timedelta(amount, unit)

    compact_match = re.fullmatch(r"(\d+)\s*(m|min|mins|h|hr|hrs|d|w|mo|mon|month|months|y)", normalized)
    if compact_match:
        amount = int(compact_match.group(1))
        unit = compact_match.group(2)
        return now - _unit_to_timedelta(amount, unit)

    days_view_match = re.search(r"(\d+)\s+days?\s+ago", normalized)
    if days_view_match:
        return now - timedelta(days=int(days_view_match.group(1)))

    return None


def parse_absolute_date(value, now=None):
    if not value:
        return None

    now = now or datetime.now()
    raw = str(value).strip()
    cleaned = re.sub(r"\s+", " ", raw).replace(",", "")

    try:
        dt = parsedate_to_datetime(cleaned)
        if dt is not None:
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)
            return dt
    except (TypeError, ValueError, IndexError, OverflowError):
        pass

    english_candidate = cleaned.replace(".", "")
    for fmt in ["%d %b %Y", "%d %B %Y"]:
        try:
            return datetime.strptime(english_candidate, fmt)
        except ValueError:
            continue

    romanian_match = re.fullmatch(r"(\d{1,2})\s+([A-Za-zĂÂÎȘȚăâîșț]+)\.?\s+(\d{4})", cleaned)
    if romanian_match:
        day = int(romanian_match.group(1))
        month_token = romanian_match.group(2).lower()
        month = ROMANIAN_MONTHS.get(month_token[:4].rstrip(".")) or ROMANIAN_MONTHS.get(month_token[:3].rstrip("."))
        year = int(romanian_match.group(3))
        if month:
            return datetime(year, month, day)

    return None


def parse_date_posted(value, now=None):
    now = now or datetime.now()
    return parse_relative_age_to_datetime(value, now=now) or parse_absolute_date(value, now=now)


def is_recent_post(value, max_age_days, now=None):
    parsed = parse_date_posted(value, now=now)
    if parsed is None:
        return True
    return parsed >= (now or datetime.now()) - timedelta(days=max_age_days)


def _unit_to_timedelta(amount, unit):
    normalized_unit = unit.lower()
    if normalized_unit in {"m", "min", "mins", "minute", "minutes"}:
        return timedelta(minutes=amount)
    if normalized_unit in {"h", "hr", "hrs", "hour", "hours"}:
        return timedelta(hours=amount)
    if normalized_unit in {"d", "day", "days"}:
        return timedelta(days=amount)
    if normalized_unit in {"w", "week", "weeks"}:
        return timedelta(weeks=amount)
    if normalized_unit in {"mo", "mon", "month", "months"}:
        return timedelta(days=30 * amount)
    if normalized_unit in {"y", "year", "years"}:
        return timedelta(days=365 * amount)
    return timedelta(0)