import os
import sqlite3

import pandas as pd
from dotenv import load_dotenv


load_dotenv()


JOB_COLUMNS = {
    "id": "TEXT PRIMARY KEY",
    "title": "TEXT NOT NULL",
    "company": "TEXT NOT NULL",
    "source_site": "TEXT",
    "date_posted": "TEXT",
    "apply_link": "TEXT UNIQUE",
    "location": "TEXT",
    "employment_type": "TEXT",
    "compensation": "TEXT",
    "tags": "TEXT",
    "status": "TEXT DEFAULT 'New'",
    "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    "last_seen_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
}

ALTER_COLUMN_DEFINITIONS = {
    "created_at": "TIMESTAMP",
    "last_seen_at": "TIMESTAMP",
}


def get_db_connection():
    db_path = os.environ.get("DB_PATH", "data/jobs.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            source_site TEXT,
            date_posted TEXT,
            apply_link TEXT UNIQUE,
            location TEXT,
            employment_type TEXT,
            compensation TEXT,
            tags TEXT,
            status TEXT DEFAULT 'New',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    )

    existing_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(jobs)").fetchall()
    }
    for column_name, definition in JOB_COLUMNS.items():
        if column_name not in existing_columns:
            alter_definition = ALTER_COLUMN_DEFINITIONS.get(column_name, definition)
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {alter_definition}")

    cursor.execute(
        "UPDATE jobs SET last_seen_at = COALESCE(last_seen_at, created_at, CURRENT_TIMESTAMP)"
    )
    conn.commit()
    conn.close()


def serialize_tags(tags):
    if not tags:
        return ""
    if isinstance(tags, str):
        return tags

    normalized = []
    seen = set()
    for tag in tags:
        value = str(tag).strip()
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(value)
    return ", ".join(normalized)


def insert_job(
    job_id,
    title,
    company,
    source_site,
    date_posted,
    apply_link,
    location="",
    employment_type="",
    compensation="",
    tags="",
):
    conn = get_db_connection()
    cursor = conn.cursor()
    serialized_tags = serialize_tags(tags)
    try:
        cursor.execute(
            '''
            INSERT INTO jobs (
                id,
                title,
                company,
                source_site,
                date_posted,
                apply_link,
                location,
                employment_type,
                compensation,
                tags,
                status,
                created_at,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'New', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(apply_link) DO UPDATE SET
                title = excluded.title,
                company = excluded.company,
                source_site = excluded.source_site,
                date_posted = excluded.date_posted,
                location = excluded.location,
                employment_type = excluded.employment_type,
                compensation = excluded.compensation,
                tags = excluded.tags,
                last_seen_at = CURRENT_TIMESTAMP
            ''',
            (
                job_id,
                title,
                company,
                source_site,
                date_posted,
                apply_link,
                location,
                employment_type,
                compensation,
                serialized_tags,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_jobs_df():
    conn = get_db_connection()
    df = pd.read_sql_query(
        "SELECT * FROM jobs ORDER BY datetime(created_at) DESC, datetime(last_seen_at) DESC",
        conn,
    )
    conn.close()
    return df


def update_job_status(job_id, new_status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
    conn.commit()
    conn.close()
