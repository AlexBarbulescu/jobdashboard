from datetime import datetime, timedelta
from html import escape
import os

import pandas as pd
import streamlit as st

from shared.db import get_jobs_df, init_db, update_job_status
from shared.job_dates import parse_date_posted

STATUS_OPTIONS = ["New", "Applied", "Saved", "Ignored"]
SOURCE_OPTIONS = ["CryptocurrencyJobs", "Web3.career", "CryptoJobsList", "crypto.jobs", "eJobs.ro"]
AGE_WINDOWS = {
    "Any time": None,
    "Last 24 hours": timedelta(days=1),
    "Last 3 days": timedelta(days=3),
    "Last 7 days": timedelta(days=7),
    "Last 30 days": timedelta(days=30),
}
SORT_OPTIONS = ["Newest posted", "Recently refreshed", "Compensation first"]
SCOPE_OPTIONS = ["Crypto-only", "All remote design jobs"]
SCOPE_DEFAULTS = {
    "crypto-only": "Crypto-only",
    "all-remote-design": "All remote design jobs",
}
DEFAULT_SCOPE = SCOPE_DEFAULTS.get(
    os.environ.get("DASHBOARD_SCOPE_DEFAULT", "crypto-only").strip().lower(),
    "Crypto-only",
)


def parse_tags(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return value
    return [tag.strip() for tag in str(value).split(",") if tag.strip()]


def format_relative_time(value):
    if pd.isna(value):
        return "Unknown"

    delta = datetime.now() - value.to_pydatetime()
    if delta < timedelta(minutes=1):
        return "just now"
    if delta < timedelta(hours=1):
        minutes = max(int(delta.total_seconds() // 60), 1)
        return f"{minutes}m ago"
    if delta < timedelta(days=1):
        hours = max(int(delta.total_seconds() // 3600), 1)
        return f"{hours}h ago"
    days = max(delta.days, 1)
    return f"{days}d ago"


def load_jobs():
    jobs_df = get_jobs_df()
    if jobs_df.empty:
        return jobs_df

    jobs_df["created_at"] = pd.to_datetime(jobs_df["created_at"], errors="coerce")
    jobs_df["last_seen_at"] = pd.to_datetime(jobs_df.get("last_seen_at"), errors="coerce")
    jobs_df["date_posted"] = jobs_df.get("date_posted", "Unknown").fillna("Unknown")
    jobs_df["source_site"] = jobs_df.get("source_site", "Unknown").fillna("Unknown")
    jobs_df["company"] = jobs_df.get("company", "Unknown").fillna("Unknown")
    jobs_df["title"] = jobs_df.get("title", "Untitled role").fillna("Untitled role")
    jobs_df["status"] = jobs_df.get("status", "New").fillna("New")
    jobs_df["location"] = jobs_df.get("location", "").fillna("")
    jobs_df["employment_type"] = jobs_df.get("employment_type", "").fillna("")
    jobs_df["compensation"] = jobs_df.get("compensation", "").fillna("")
    jobs_df["tags"] = jobs_df.get("tags", "").fillna("")
    jobs_df["is_crypto_relevant"] = jobs_df.get("is_crypto_relevant", 1).fillna(1).astype(int).astype(bool)

    now = datetime.now()
    jobs_df["posted_at"] = jobs_df["date_posted"].apply(parse_date_posted)
    jobs_df["effective_posted_at"] = jobs_df["posted_at"].fillna(jobs_df["created_at"])
    age_delta = now - jobs_df["effective_posted_at"]
    jobs_df["is_new"] = age_delta < timedelta(days=1)
    jobs_df["new_badge"] = jobs_df["is_new"].map(lambda value: "New" if value else "")
    jobs_df["created_label"] = jobs_df["created_at"].apply(format_relative_time)
    jobs_df["last_seen_label"] = jobs_df["last_seen_at"].apply(format_relative_time)
    jobs_df["posted_label"] = jobs_df["effective_posted_at"].apply(format_relative_time)
    jobs_df["tags_list"] = jobs_df["tags"].apply(parse_tags)
    jobs_df["tags_label"] = jobs_df["tags_list"].apply(lambda tags: ", ".join(tags))
    jobs_df["remote_flag"] = jobs_df["location"].str.contains("Remote|Anywhere|Distributed", case=False, na=False)
    jobs_df["compensation_flag"] = jobs_df["compensation"].str.len() > 0
    return jobs_df


def apply_filters(
    jobs_df,
    search_term,
    selected_statuses,
    selected_sources,
    selected_tags,
    selected_scope,
    max_age_label,
    remote_only,
    compensation_only,
    sort_mode,
):
    filtered = jobs_df[jobs_df["status"].isin(selected_statuses)].copy()

    if selected_scope == "Crypto-only":
        filtered = filtered[filtered["is_crypto_relevant"]]

    if selected_sources:
        filtered = filtered[filtered["source_site"].isin(selected_sources)]

    if selected_tags:
        filtered = filtered[
            filtered["tags_list"].apply(lambda tags: any(tag in tags for tag in selected_tags))
        ]

    if remote_only:
        filtered = filtered[filtered["remote_flag"]]

    if compensation_only:
        filtered = filtered[filtered["compensation_flag"]]

    if search_term:
        search_mask = (
            filtered["title"].str.contains(search_term, case=False, na=False)
            | filtered["company"].str.contains(search_term, case=False, na=False)
            | filtered["source_site"].str.contains(search_term, case=False, na=False)
            | filtered["location"].str.contains(search_term, case=False, na=False)
            | filtered["tags_label"].str.contains(search_term, case=False, na=False)
        )
        filtered = filtered[search_mask]

    age_limit = AGE_WINDOWS[max_age_label]
    if age_limit is not None:
        filtered = filtered[filtered["effective_posted_at"] >= (datetime.now() - age_limit)]

    if sort_mode == "Recently refreshed":
        return filtered.sort_values(by=["last_seen_at", "created_at"], ascending=[False, False])
    if sort_mode == "Compensation first":
        return filtered.sort_values(by=["compensation_flag", "is_new", "effective_posted_at"], ascending=[False, False, False])
    return filtered.sort_values(by=["effective_posted_at", "created_at"], ascending=[False, False])


def render_metric_strip(jobs_df):
    total_jobs = len(jobs_df)
    new_jobs = int(jobs_df["is_new"].sum())
    remote_jobs = int(jobs_df["remote_flag"].sum())
    saved_jobs = int((jobs_df["status"] == "Saved").sum())
    applied_jobs = int((jobs_df["status"] == "Applied").sum())
    latest_seen = jobs_df["last_seen_at"].max()
    latest_label = format_relative_time(latest_seen) if pd.notna(latest_seen) else "Unknown"
    recent_jobs = int((jobs_df["effective_posted_at"] >= (datetime.now() - timedelta(days=7))).sum())
    crypto_jobs = int(jobs_df["is_crypto_relevant"].sum())

    metric_cards = [
        ("Tracked roles", total_jobs),
        ("New in 24h", new_jobs),
        ("Recent 7d", recent_jobs),
        ("Crypto relevant", crypto_jobs),
        ("Saved", saved_jobs),
        ("Latest refresh", latest_label),
    ]
    cards_html = "".join(
        f"<div class='metric-card'><span>{escape(label)}</span><strong>{escape(str(value))}</strong></div>"
        for label, value in metric_cards
    )
    st.markdown(f"<div class='metric-grid'>{cards_html}</div>", unsafe_allow_html=True)


def render_status_breakdown(jobs_df):
    counts = jobs_df["status"].value_counts().reindex(STATUS_OPTIONS, fill_value=0)
    pills = "".join(
        f"<div class='mix-pill'><span>{escape(status)}</span><strong>{counts[status]}</strong></div>"
        for status in STATUS_OPTIONS
    )
    st.markdown(f"<div class='mix-strip'>{pills}</div>", unsafe_allow_html=True)


def render_table_view(filtered_df):
    table_df = filtered_df[
        [
            "id",
            "new_badge",
            "title",
            "company",
            "location",
            "source_site",
            "employment_type",
            "compensation",
            "date_posted",
            "status",
            "apply_link",
        ]
    ].copy()
    table_df = table_df.rename(
        columns={
            "new_badge": "New",
            "title": "Role",
            "company": "Company",
            "location": "Location",
            "source_site": "Source",
            "employment_type": "Type",
            "compensation": "Comp",
            "date_posted": "Posted",
            "status": "Status",
            "apply_link": "Apply",
        }
    )
    table_df = table_df.set_index("id")

    edited_df = st.data_editor(
        table_df,
        column_config={
            "New": st.column_config.TextColumn(width="small", disabled=True),
            "Role": st.column_config.TextColumn(width="large", disabled=True),
            "Company": st.column_config.TextColumn(disabled=True),
            "Location": st.column_config.TextColumn(disabled=True),
            "Source": st.column_config.TextColumn(disabled=True),
            "Type": st.column_config.TextColumn(disabled=True),
            "Comp": st.column_config.TextColumn(disabled=True),
            "Posted": st.column_config.TextColumn(disabled=True),
            "Status": st.column_config.SelectboxColumn(options=STATUS_OPTIONS, required=True),
            "Apply": st.column_config.LinkColumn(disabled=True, width="large"),
        },
        disabled=["New", "Role", "Company", "Location", "Source", "Type", "Comp", "Posted", "Apply"],
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
    )

    if table_df.equals(edited_df):
        return

    for job_id in edited_df.index:
        old_status = table_df.loc[job_id, "Status"]
        new_status = edited_df.loc[job_id, "Status"]
        if old_status != new_status:
            update_job_status(str(job_id), new_status)
            st.toast(f"{edited_df.loc[job_id, 'Role']}: {old_status} -> {new_status}")
    st.rerun()


def render_card(job):
    title = escape(str(job["title"]))
    company = escape(str(job["company"]))
    source_site = escape(str(job["source_site"]))
    location = escape(str(job["location"] or "Location unknown"))
    employment_type = escape(str(job["employment_type"] or "Type unknown"))
    compensation = escape(str(job["compensation"] or "Comp not listed"))
    posted = escape(str(job["date_posted"]))
    posted_label = escape(str(job["posted_label"]))
    created_label = escape(str(job["created_label"]))
    last_seen_label = escape(str(job["last_seen_label"]))
    apply_link = escape(str(job["apply_link"]), quote=True)
    status = escape(str(job["status"]))
    badges = []
    if job["is_new"]:
        badges.append("<span class='badge badge-new'>New</span>")
    badges.append(f"<span class='badge badge-{job['status'].lower()}'>{status}</span>")
    for tag in job["tags_list"][:5]:
        badges.append(f"<span class='badge badge-tag'>{escape(tag)}</span>")

    st.markdown(
        f"""
        <div class="job-card">
            <div class="job-card__top">
                <div class="job-card__heading">
                    <div class="job-card__title">{title}</div>
                    <div class="job-card__meta">{company} • {source_site}</div>
                </div>
                <div class="job-card__badges">{''.join(badges)}</div>
            </div>
            <div class="job-card__facts">
                <div><span>Location</span><strong>{location}</strong></div>
                <div><span>Type</span><strong>{employment_type}</strong></div>
                <div><span>Comp</span><strong>{compensation}</strong></div>
                <div><span>Posted</span><strong>{posted}</strong></div>
            </div>
            <div class="job-card__footer">
                <span>Posted {posted_label} • first seen {created_label} • refreshed {last_seen_label}</span>
                <a href="{apply_link}" target="_blank">Open posting</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_status = st.selectbox(
        f"Update status for {job['title']}",
        STATUS_OPTIONS,
        index=STATUS_OPTIONS.index(job["status"]),
        key=f"card-status-{job['id']}",
        label_visibility="collapsed",
    )
    if selected_status != job["status"]:
        update_job_status(str(job["id"]), selected_status)
        st.toast(f"{job['title']}: {job['status']} -> {selected_status}")
        st.rerun()


def render_card_view(filtered_df):
    for _, job in filtered_df.iterrows():
        render_card(job)


def render_pipeline_view(jobs_df):
    st.subheader("Pipeline")
    for status in STATUS_OPTIONS:
        subset = jobs_df[jobs_df["status"] == status].head(5)
        with st.expander(f"{status} ({len(jobs_df[jobs_df['status'] == status])})", expanded=status in {"New", "Saved"}):
            if subset.empty:
                st.caption("No jobs in this state.")
                continue
            for _, job in subset.iterrows():
                st.markdown(
                    f"**{job['title']}**  \n{job['company']} • {job['location'] or 'Location unknown'} • {job['source_site']}"
                )


def render_insights(jobs_df):
    st.subheader("Insights")
    left_col, right_col = st.columns(2)

    with left_col:
        source_counts = jobs_df["source_site"].value_counts().reindex(SOURCE_OPTIONS, fill_value=0).rename_axis("Source").reset_index(name="Jobs")
        st.caption("Source coverage")
        st.bar_chart(source_counts.set_index("Source"))

    with right_col:
        tag_counts = {}
        for tags in jobs_df["tags_list"]:
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        if tag_counts:
            tags_df = pd.DataFrame(sorted(tag_counts.items(), key=lambda item: item[1], reverse=True)[:10], columns=["Tag", "Jobs"])
            st.caption("Top tags")
            st.bar_chart(tags_df.set_index("Tag"))
        else:
            st.caption("No tag data available yet.")


st.set_page_config(page_title="Crypto Design Job Sentinel", page_icon="🛡️", layout="wide")

st.markdown(
    """
    <style>
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(16, 129, 91, 0.18), transparent 24%),
            radial-gradient(circle at bottom right, rgba(222, 168, 87, 0.12), transparent 28%),
            linear-gradient(180deg, #f7f4ed 0%, #edf1ea 100%);
    }
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .hero {
        padding: 1.5rem;
        border: 1px solid rgba(20, 35, 29, 0.08);
        border-radius: 24px;
        background: linear-gradient(135deg, rgba(255, 250, 239, 0.92), rgba(241, 248, 243, 0.86));
        box-shadow: 0 18px 48px rgba(18, 53, 36, 0.08);
        margin-bottom: 1rem;
    }
    .hero h1 {
        margin: 0;
        font-size: 2.2rem;
        color: #143728;
    }
    .hero p {
        margin: 0.45rem 0 0;
        color: #4b6256;
        max-width: 60rem;
    }
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 0.8rem;
        margin: 1rem 0;
    }
    .metric-card,
    .mix-pill {
        border: 1px solid rgba(20, 35, 29, 0.08);
        border-radius: 18px;
        background: rgba(255, 255, 255, 0.78);
        padding: 0.9rem 1rem;
        box-shadow: 0 12px 32px rgba(18, 53, 36, 0.05);
    }
    .metric-card span,
    .mix-pill span,
    .job-card__facts span {
        display: block;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #6f7f76;
    }
    .metric-card strong,
    .mix-pill strong,
    .job-card__facts strong {
        display: block;
        margin-top: 0.2rem;
        color: #153a2a;
        font-size: 1.1rem;
    }
    .mix-strip {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 0.7rem;
        margin-bottom: 1rem;
    }
    .job-card {
        border: 1px solid rgba(20, 35, 29, 0.08);
        border-radius: 20px;
        padding: 1rem 1.05rem;
        background: rgba(255, 255, 255, 0.82);
        margin-bottom: 0.55rem;
        box-shadow: 0 12px 32px rgba(18, 53, 36, 0.06);
    }
    .job-card__top,
    .job-card__footer {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
    }
    .job-card__title {
        font-size: 1.08rem;
        font-weight: 700;
        color: #153a2a;
    }
    .job-card__meta,
    .job-card__footer span {
        color: #5b6d63;
        font-size: 0.93rem;
    }
    .job-card__badges {
        display: flex;
        gap: 0.45rem;
        flex-wrap: wrap;
        justify-content: flex-end;
    }
    .job-card__facts {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
        gap: 0.8rem;
        padding-top: 0.95rem;
        margin-top: 0.95rem;
        border-top: 1px solid rgba(20, 35, 29, 0.08);
    }
    .job-card__footer {
        margin-top: 0.95rem;
        flex-wrap: wrap;
    }
    .job-card__footer a {
        color: #0f7a52;
        text-decoration: none;
        font-weight: 700;
    }
    .badge {
        border-radius: 999px;
        padding: 0.28rem 0.62rem;
        font-size: 0.74rem;
        font-weight: 700;
        text-transform: uppercase;
        border: 1px solid transparent;
    }
    .badge-new {
        background: #d7f2e5;
        color: #0f7a52;
    }
    .badge-new,
    .badge-saved,
    .badge-applied,
    .badge-ignored,
    .badge-tag {
        border-color: rgba(20, 35, 29, 0.05);
    }
    .badge-saved {
        background: #fff0c7;
        color: #8b5d00;
    }
    .badge-applied {
        background: #d9ebff;
        color: #004a93;
    }
    .badge-ignored {
        background: #ececec;
        color: #505050;
    }
    .badge-tag {
        background: #f0efe8;
        color: #57655c;
    }
    @media (max-width: 720px) {
        .hero {
            padding: 1.15rem;
        }
        .hero h1 {
            font-size: 1.75rem;
        }
        .job-card__top,
        .job-card__footer {
            flex-direction: column;
        }
        .job-card__badges {
            justify-content: flex-start;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

init_db()

st.markdown(
    """
    <div class="hero">
        <h1>Crypto Design Job Sentinel</h1>
        <p>Track remote design roles across Web3 and crypto boards with richer metadata, cleaner triage, and a dashboard that works better on both desktop and smaller screens.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

toolbar_left, toolbar_right = st.columns([5, 1])
with toolbar_left:
    st.caption("SQLite-backed job inventory populated by the worker. Status changes stay local and persist across refreshes.")
with toolbar_right:
    if st.button("Refresh", use_container_width=True):
        st.rerun()

df = load_jobs()

if df.empty:
    st.info("No jobs found yet. Start the scraper worker or wait for the next refresh cycle.")
else:
    with st.sidebar:
        st.header("Filters")
        search_term = st.text_input("Search roles, companies, places, or tags")
        scope_index = SCOPE_OPTIONS.index(DEFAULT_SCOPE) if DEFAULT_SCOPE in SCOPE_OPTIONS else 0
        selected_scope = st.radio("Scope", SCOPE_OPTIONS, index=scope_index)
        selected_statuses = st.multiselect("Status", STATUS_OPTIONS, default=STATUS_OPTIONS)
        selected_sources = st.multiselect("Source", SOURCE_OPTIONS, default=SOURCE_OPTIONS)
        tag_options = sorted({tag for tags in df["tags_list"] for tag in tags})
        selected_tags = st.multiselect("Tags", tag_options)
        max_age_label = st.selectbox("Recency", list(AGE_WINDOWS.keys()), index=2)
        sort_mode = st.selectbox("Sort", SORT_OPTIONS, index=0)
        remote_only = st.toggle("Remote only", value=False)
        compensation_only = st.toggle("Only jobs with pay info", value=False)
        view_mode = st.radio("Board view", ["Cards", "Table"], horizontal=True)

    if not selected_statuses:
        st.warning("Select at least one status to see results.")
        st.stop()

    filtered_df = apply_filters(
        df,
        search_term,
        selected_statuses,
        selected_sources,
        selected_tags,
        selected_scope,
        max_age_label,
        remote_only,
        compensation_only,
        sort_mode,
    )

    render_metric_strip(df)
    render_status_breakdown(df)

    board_tab, pipeline_tab, insights_tab = st.tabs(["Board", "Pipeline", "Insights"])

    with board_tab:
        st.subheader("Open roles")
        st.caption(f"Showing {len(filtered_df)} of {len(df)} tracked jobs")
        if filtered_df.empty:
            st.warning("No jobs match the current filters.")
        elif view_mode == "Table":
            render_table_view(filtered_df)
        else:
            render_card_view(filtered_df)

    with pipeline_tab:
        render_pipeline_view(df)

    with insights_tab:
        render_insights(df)
