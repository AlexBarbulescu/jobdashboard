from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jobdashboard import get_settings  # noqa: E402
from jobdashboard.pipeline import bootstrap_if_empty, refresh_jobs  # noqa: E402
from jobdashboard.storage import STATUS_VALUES, Storage  # noqa: E402


STATUS_ORDER = ["new", "saved", "applied", "ignored"]
STATUS_LABELS = {
    "new": "Track",
    "saved": "Saved",
    "applied": "Applied",
    "ignored": "Ignored",
}


def format_relative(value: datetime | None) -> str:
    if value is None:
        return "Unknown"
    delta = datetime.now(UTC) - value.astimezone(UTC)
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

        :root {
            --bg: #09111c;
            --panel: rgba(13, 22, 36, 0.88);
            --panel-border: rgba(111, 255, 214, 0.16);
            --text: #e6f7ff;
            --muted: #8ba6b6;
            --mint: #66f2c5;
            --amber: #ffbf69;
            --danger: #ff6b6b;
            --cyan: #4ad8ff;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(74, 216, 255, 0.18), transparent 28%),
                radial-gradient(circle at top right, rgba(255, 191, 105, 0.18), transparent 22%),
                linear-gradient(180deg, #06101b 0%, #08131f 40%, #04070d 100%);
            color: var(--text);
            font-family: 'Space Grotesk', sans-serif;
        }

        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2rem;
            max-width: 1420px;
        }

        h1, h2, h3, h4, p, div, span, label {
            color: var(--text);
        }

        [data-testid="stSidebar"] {
            background: rgba(5, 10, 18, 0.92);
            border-right: 1px solid rgba(111, 255, 214, 0.12);
        }

        [data-testid="stMetric"] {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 18px;
            padding: 0.8rem 1rem;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02);
        }

        div[data-testid="stMetricValue"] {
            font-family: 'IBM Plex Mono', monospace;
        }

        .hero {
            background: linear-gradient(135deg, rgba(9, 20, 33, 0.95), rgba(8, 16, 26, 0.74));
            border: 1px solid var(--panel-border);
            border-radius: 24px;
            padding: 1.25rem 1.4rem;
            margin-bottom: 1rem;
            position: relative;
            overflow: hidden;
        }

        .hero::after {
            content: '';
            position: absolute;
            inset: auto -40px -40px auto;
            width: 180px;
            height: 180px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(102, 242, 197, 0.25), transparent 65%);
        }

        .hero-top {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
        }

        .eyebrow, .meta-strip, .card-meta, .health-chip {
            font-family: 'IBM Plex Mono', monospace;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }

        .eyebrow {
            color: var(--mint);
            font-size: 0.75rem;
            margin-bottom: 0.3rem;
        }

        .hero h1 {
            margin: 0;
            font-size: 2.2rem;
            line-height: 1;
        }

        .hero p {
            color: var(--muted);
            max-width: 720px;
            margin: 0.55rem 0 0;
        }

        .live-pill {
            border: 1px solid rgba(74, 216, 255, 0.28);
            color: var(--cyan);
            background: rgba(74, 216, 255, 0.08);
            border-radius: 999px;
            padding: 0.5rem 0.85rem;
            white-space: nowrap;
        }

        .dot {
            display: inline-block;
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: var(--mint);
            margin-right: 0.45rem;
            box-shadow: 0 0 0 0 rgba(102, 242, 197, 0.7);
            animation: pulse 1.8s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(102, 242, 197, 0.55); }
            70% { box-shadow: 0 0 0 14px rgba(102, 242, 197, 0); }
            100% { box-shadow: 0 0 0 0 rgba(102, 242, 197, 0); }
        }

        .meta-strip {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin-top: 1rem;
            color: var(--muted);
            font-size: 0.78rem;
        }

        .meta-strip span {
            padding: 0.4rem 0.6rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.05);
        }

        .feed-shell {
            display: grid;
            gap: 0.9rem;
        }

        .feed-card {
            background: var(--panel);
            border: 1px solid var(--panel-border);
            border-radius: 22px;
            padding: 1rem 1rem 0.8rem;
            position: relative;
            overflow: hidden;
        }

        .feed-card::before {
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, rgba(102, 242, 197, 0.04), transparent 55%);
            pointer-events: none;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
            margin-bottom: 0.6rem;
        }

        .card-title {
            font-size: 1.1rem;
            font-weight: 700;
            margin: 0;
        }

        .card-company {
            color: var(--amber);
            margin-top: 0.15rem;
            font-size: 0.95rem;
        }

        .badge-row {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
            margin-bottom: 0.75rem;
        }

        .badge {
            border-radius: 999px;
            padding: 0.22rem 0.58rem;
            font-size: 0.72rem;
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.04);
            color: var(--text);
        }

        .badge-new {
            border-color: rgba(102, 242, 197, 0.3);
            color: var(--mint);
            background: rgba(102, 242, 197, 0.08);
        }

        .card-summary {
            color: #bad0dd;
            margin-bottom: 0.85rem;
            line-height: 1.55;
        }

        .health-row {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin-top: 0.5rem;
        }

        .health-chip {
            padding: 0.45rem 0.7rem;
            border-radius: 999px;
            font-size: 0.72rem;
            border: 1px solid rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.03);
        }

        .health-ok {
            color: var(--mint);
            border-color: rgba(102, 242, 197, 0.2);
        }

        .health-error {
            color: var(--danger);
            border-color: rgba(255, 107, 107, 0.2);
        }

        .empty-state {
            padding: 1.2rem;
            border-radius: 20px;
            border: 1px dashed rgba(255,255,255,0.14);
            color: var(--muted);
            background: rgba(255,255,255,0.02);
            text-align: center;
        }

        .stButton button, .stLinkButton a {
            border-radius: 999px;
            border: 1px solid rgba(102, 242, 197, 0.22);
            background: rgba(102, 242, 197, 0.08);
            color: var(--text);
        }

        .stSelectbox [data-baseweb="select"] > div,
        .stTextInput input {
            background: rgba(255,255,255,0.03);
            border-color: rgba(255,255,255,0.08);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(metrics: dict, health_count: int, settings) -> None:
    latest_run = metrics.get("latest_run") or {}
    last_refresh = latest_run.get("finished_at")
    last_refresh_label = "waiting for first sync"
    if last_refresh:
        parsed = datetime.fromisoformat(last_refresh)
        last_refresh_label = format_relative(parsed)

    st.markdown(
        f"""
        <section class="hero">
            <div class="hero-top">
                <div>
                    <div class="eyebrow">Crypto Design Watch</div>
                    <h1>{settings.app_name}</h1>
                    <p>Live remote design roles from crypto-native sources, with persistent local tracking and a terminal-style feed optimized for fast scanning.</p>
                </div>
                <div class="live-pill"><span class="dot"></span>Live refresh every {settings.dashboard_poll_seconds}s</div>
            </div>
            <div class="meta-strip">
                <span>last sync: {last_refresh_label}</span>
                <span>sources online: {health_count}</span>
                <span>job capacity: {settings.job_limit}</span>
                <span>worker cadence: {settings.refresh_interval_seconds}s</span>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_job_card(storage: Storage, job: dict) -> None:
    posted_at = job["posted_at"] or job["first_seen_at"]
    card_col, action_col = st.columns([5, 1.25], vertical_alignment="top")
    query = quote_plus(f"{job['title']} {job['company']}")
    linkedin_url = f"https://www.linkedin.com/jobs/search/?keywords={query}"
    x_url = f"https://x.com/search?q={query}"
    indeed_url = f"https://www.indeed.com/jobs?q={query}"

    with card_col:
        badge_markup = [f'<span class="badge">{job["source_name"]}</span>', f'<span class="badge">{job["location"]}</span>']
        if job["is_new"]:
            badge_markup.insert(0, '<span class="badge badge-new">new</span>')
        st.markdown(
            f"""
            <div class="feed-card">
                <div class="card-header">
                    <div>
                        <div class="card-meta">{format_relative(posted_at)}</div>
                        <div class="card-title">{job['title']}</div>
                        <div class="card-company">{job['company']}</div>
                    </div>
                </div>
                <div class="badge-row">{''.join(badge_markup)}</div>
                <div class="card-summary">{job['summary'] or 'No summary available from source.'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with action_col:
        selected_status = st.selectbox(
            "Status",
            STATUS_ORDER,
            index=STATUS_ORDER.index(job["status"]) if job["status"] in STATUS_ORDER else 0,
            key=f"status-{job['job_key']}",
            format_func=lambda value: STATUS_LABELS[value],
            label_visibility="collapsed",
        )
        if selected_status != job["status"]:
            storage.update_job_status(job["job_key"], selected_status)
            st.rerun()
        st.link_button("Apply", job["apply_url"], use_container_width=True)
        st.link_button("Source", job["source_url"], use_container_width=True)
        st.markdown(
            f"[LinkedIn]({linkedin_url}) | [X]({x_url}) | [Indeed]({indeed_url})",
            unsafe_allow_html=False,
        )


def main() -> None:
    st.set_page_config(page_title="Crypto Design Job Sentinel", page_icon="CD", layout="wide")
    _inject_styles()

    settings = get_settings()
    storage = Storage(settings.database_path)
    bootstrap_if_empty(storage, settings)

    st_autorefresh(interval=settings.dashboard_poll_seconds * 1000, key="dashboard-autorefresh")

    with st.sidebar:
        st.markdown("### Terminal Controls")
        if st.button("Refresh now", use_container_width=True):
            with st.spinner("Refreshing live sources..."):
                refresh_jobs(storage, settings)
            st.rerun()
        status_filter = st.selectbox("Status lane", ["all", *STATUS_ORDER], format_func=lambda value: value.title())
        source_health = storage.list_source_health()
        source_names = sorted({item.source_name for item in source_health})
        selected_sources = st.multiselect("Sources", source_names, default=source_names)
        search = st.text_input("Search title, company, summary")
        only_new = st.toggle("Only fresh jobs", value=False)
        st.caption("Status state persists in the local SQLite database volume.")

    metrics = storage.get_metrics()
    health = storage.list_source_health()
    healthy_count = len([item for item in health if item.status == "ok"])

    render_hero(metrics, healthy_count, settings)

    metric_cols = st.columns(4)
    metric_cols[0].metric("Live jobs", metrics["total_jobs"])
    metric_cols[1].metric("Fresh 24h", metrics["new_jobs"])
    metric_cols[2].metric("Saved", metrics["saved_jobs"])
    metric_cols[3].metric("Applied", metrics["applied_jobs"])

    st.markdown("### Source Health")
    if health:
        chips = []
        for item in health:
            status_class = "health-ok" if item.status == "ok" else "health-error"
            checked = format_relative(item.checked_at)
            chips.append(
                f'<span class="health-chip {status_class}">{item.source_name} | {item.status} | {checked} | {item.message}</span>'
            )
        st.markdown(f'<div class="health-row">{"".join(chips)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="empty-state">No source checks yet. The worker will publish source health after the first successful or failed sweep.</div>', unsafe_allow_html=True)

    jobs = storage.list_jobs(status=status_filter, search=search, limit=settings.job_limit)
    if selected_sources:
        jobs = [job for job in jobs if job["source_name"] in selected_sources]
    if only_new:
        jobs = [job for job in jobs if job["is_new"]]

    st.markdown("### Live Feed")
    if not jobs:
        st.markdown('<div class="empty-state">No jobs matched the current lane. Broaden the filters or trigger a fresh source pull.</div>', unsafe_allow_html=True)
        return

    with st.container():
        st.markdown('<div class="feed-shell">', unsafe_allow_html=True)
        for job in jobs:
            render_job_card(storage, job)
        st.markdown('</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()