"""
database.py
Postgres (Neon) connection layer that stores: the content queue state, every
video produced, the performance data used by the adaptive scheduler, and
customer service records. This is the shared memory across all agents.
"""
import os
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

SCHEMA = """
CREATE TABLE IF NOT EXISTS content_queue (
    id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    title_seed TEXT NOT NULL,
    angle TEXT NOT NULL,
    times_used INTEGER DEFAULT 0,
    last_used_at TEXT
);

CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    topic_id TEXT NOT NULL,
    title TEXT NOT NULL,
    title_variant_label TEXT,
    script TEXT,
    status TEXT DEFAULT 'queued',
    youtube_video_id TEXT,
    created_at TEXT NOT NULL,
    uploaded_at TEXT,
    FOREIGN KEY (topic_id) REFERENCES content_queue (id)
);

CREATE TABLE IF NOT EXISTS performance (
    video_id TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    PRIMARY KEY (video_id, checked_at),
    FOREIGN KEY (video_id) REFERENCES videos (video_id)
);

CREATE TABLE IF NOT EXISTS customer_services (
    id SERIAL PRIMARY KEY,
    customer_name TEXT NOT NULL,
    mobile_number TEXT NOT NULL,
    customer_detail TEXT,
    service_name TEXT NOT NULL,
    amount REAL DEFAULT 0,
    payment_status TEXT DEFAULT 'Paid',
    payment_method TEXT DEFAULT 'Cash',
    notes TEXT,
    service_date TEXT NOT NULL,
    created_at TEXT DEFAULT NOW()::text
);
"""


_conn = None


def get_conn():
    """
    Returns a cached, reusable connection instead of opening a new one on
    every call. Reconnects automatically if the cached connection has gone
    stale (e.g. Neon suspended the compute after inactivity).
    """
    global _conn
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")

    if _conn is not None:
        try:
            probe = _conn.cursor()
            probe.execute("SELECT 1;")
            probe.close()
            return _conn
        except Exception:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None

    _conn = psycopg2.connect(
        DATABASE_URL,
        cursor_factory=psycopg2.extras.RealDictCursor,
        connect_timeout=10,
    )
    _conn.autocommit = True
    return _conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(SCHEMA)


def seed_queue_from_json(services_json):
    conn = get_conn()
    cur = conn.cursor()
    for category in services_json["categories"]:
        for topic in category["topics"]:
            cur.execute(
                """INSERT INTO content_queue (id, category, title_seed, angle)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (id) DO NOTHING""",
                (topic["id"], category["category"], topic["title_seed"], topic["angle"]),
            )


def next_topics(n=3):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT * FROM content_queue
           ORDER BY times_used ASC, (last_used_at IS NOT NULL) ASC, last_used_at ASC
           LIMIT %s""",
        (n,),
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def mark_topic_used(topic_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE content_queue SET times_used = times_used + 1,
           last_used_at = %s WHERE id = %s""",
        (datetime.now(timezone.utc).isoformat(), topic_id),
    )


def insert_video(video_id, topic_id, title, title_variant_label=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO videos (video_id, topic_id, title, title_variant_label, status, created_at)
           VALUES (%s, %s, %s, %s, 'queued', %s)""",
        (video_id, topic_id, title, title_variant_label, datetime.now(timezone.utc).isoformat()),
    )


def update_video(video_id, **fields):
    conn = get_conn()
    cur = conn.cursor()
    keys = ", ".join(f"{k} = %s" for k in fields)
    cur.execute(f"UPDATE videos SET {keys} WHERE video_id = %s", (*fields.values(), video_id))


def log_performance(video_id, views, likes, comments):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO performance (video_id, checked_at, views, likes, comments)
           VALUES (%s, %s, %s, %s, %s)""",
        (video_id, datetime.now(timezone.utc).isoformat(), views, likes, comments),
    )


def best_performing_categories(limit=3):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT cq.category, AVG(p.views) as avg_views
           FROM performance p
           JOIN videos v ON v.video_id = p.video_id
           JOIN content_queue cq ON cq.id = v.topic_id
           GROUP BY cq.category
           ORDER BY avg_views DESC
           LIMIT %s""",
        (limit,),
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def get_tracked_videos(max_age_hours=72):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT video_id, youtube_video_id, uploaded_at FROM videos
           WHERE status = 'uploaded' AND youtube_video_id IS NOT NULL
           AND uploaded_at IS NOT NULL"""
    )
    rows = cur.fetchall()
    cutoff = datetime.now(timezone.utc)
    result = []
    for r in rows:
        uploaded_at = datetime.fromisoformat(r["uploaded_at"])
        age_hours = (cutoff - uploaded_at).total_seconds() / 3600
        if age_hours <= max_age_hours:
            result.append(dict(r))
    return result


def videos_created_today():
    conn = get_conn()
    cur = conn.cursor()
    today = datetime.now().date().isoformat()
    cur.execute(
        "SELECT COUNT(*) as c FROM videos WHERE LEFT(created_at, 10) = %s AND status = 'uploaded'", (today,)
    )
    row = cur.fetchone()
    return row["c"]


def velocity_by_upload_hour(early_window_hours=24, min_hour_buckets=3):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT v.uploaded_at, p.checked_at, p.views
           FROM videos v JOIN performance p ON p.video_id = v.video_id
           WHERE v.uploaded_at IS NOT NULL"""
    )
    rows = cur.fetchall()

    from collections import defaultdict
    per_video_logs = defaultdict(list)
    for r in rows:
        per_video_logs[r["uploaded_at"]].append((r["checked_at"], r["views"]))

    hour_velocities = defaultdict(list)
    for uploaded_at_str, logs in per_video_logs.items():
        uploaded_at = datetime.fromisoformat(uploaded_at_str)
        candidates = []
        for checked_at_str, views in logs:
            checked_at = datetime.fromisoformat(checked_at_str)
            age_hours = (checked_at - uploaded_at).total_seconds() / 3600
            if 0 < age_hours <= early_window_hours:
                candidates.append((age_hours, views))
        if not candidates:
            continue
        age_hours, views = max(candidates, key=lambda c: c[0])
        velocity = views / age_hours
        local_hour = uploaded_at.astimezone().hour
        hour_velocities[local_hour].append(velocity)

    if len(hour_velocities) < min_hour_buckets:
        return {}

    return {h: sum(vs) / len(vs) for h, vs in hour_velocities.items()}


def recent_video_performance(limit=10):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT v.video_id, v.title, v.uploaded_at,
               p.views, p.likes, p.comments
        FROM videos v
        JOIN performance p ON p.video_id = v.video_id
        WHERE p.checked_at = (
            SELECT MAX(p2.checked_at) FROM performance p2
            WHERE p2.video_id = v.video_id
        )
        AND v.status = 'uploaded'
        ORDER BY v.uploaded_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]


import sqlite3
import threading
import time

LOCAL_CACHE_PATH = os.getenv("LOCAL_CACHE_PATH", "./local_cache.db")

_sync_thread_started = False
_sync_lock = threading.Lock()


def _local_conn():
    conn = sqlite3.connect(LOCAL_CACHE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_local_cache():
    """
    Local SQLite mirror for customer service records. Every save happens
    here instantly (no network wait). A background thread pushes any
    un-synced rows to Neon every 20 seconds, so the shop owner never waits
    on the network, but the data still ends up safely in Neon.
    """
    conn = _local_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_services_cache (
            local_id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT NOT NULL,
            mobile_number TEXT NOT NULL,
            customer_detail TEXT,
            service_name TEXT NOT NULL,
            amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'Paid',
            payment_method TEXT DEFAULT 'Cash',
            notes TEXT,
            service_date TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            synced INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def save_customer_service_local(customer_name, mobile_number, customer_detail,
                                  service_name, amount, payment_status,
                                  payment_method, notes, service_date):
    """Instant local save — never waits on Neon."""
    conn = _local_conn()
    conn.execute(
        """INSERT INTO customer_services_cache
           (customer_name, mobile_number, customer_detail, service_name, amount,
            payment_status, payment_method, notes, service_date)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (customer_name, mobile_number, customer_detail, service_name, amount,
         payment_status, payment_method, notes, service_date),
    )
    conn.commit()
    conn.close()


def get_customer_history_local():
    """Always reads from local disk — instant, works even if Neon is asleep."""
    conn = _local_conn()
    rows = conn.execute(
        "SELECT * FROM customer_services_cache ORDER BY service_date DESC, local_id DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _sync_customer_services_once():
    """Pushes any un-synced local rows up to Neon. Safe to call repeatedly."""
    local = _local_conn()
    pending = local.execute(
        "SELECT * FROM customer_services_cache WHERE synced = 0"
    ).fetchall()
    if not pending:
        local.close()
        return

    try:
        conn = get_conn()
        cur = conn.cursor()
        for row in pending:
            cur.execute(
                """INSERT INTO customer_services
                   (customer_name, mobile_number, customer_detail, service_name, amount,
                    payment_status, payment_method, notes, service_date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (row["customer_name"], row["mobile_number"], row["customer_detail"],
                 row["service_name"], row["amount"], row["payment_status"],
                 row["payment_method"], row["notes"], row["service_date"]),
            )
            local.execute(
                "UPDATE customer_services_cache SET synced = 1 WHERE local_id = ?",
                (row["local_id"],),
            )
        local.commit()
        print(f"[sync] Pushed {len(pending)} record(s) to Neon.")
    except Exception as e:
        print(f"[sync] Neon sync failed, will retry in {20}s: {e}")
    finally:
        local.close()


def start_background_sync(interval_seconds=20):
    """Starts a daemon thread that syncs local records to Neon periodically."""
    global _sync_thread_started
    with _sync_lock:
        if _sync_thread_started:
            return
        _sync_thread_started = True

    def _loop():
        while True:
            _sync_customer_services_once()
            time.sleep(interval_seconds)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()


if __name__ == "__main__":
    import json
    init_db()
    with open("data/services.json") as f:
        seed_queue_from_json(json.load(f))
    print("Database initialized and seeded from data/services.json (Neon Postgres)")

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Trend Clip pipeline additions (Postgres/Neon — matches get_conn() pattern)
# ---------------------------------------------------------------------------

def save_trend_cache(results_json):
    """
    Overwrites the single cached trend-search result set. Stored in Neon
    (not local SQLite) so it survives Render sleep/restart cycles -- an
    in-memory-only cache resets every time the free-tier service spins
    down, which defeats the point of caching to protect YouTube quota.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trend_cache (
            id INTEGER PRIMARY KEY DEFAULT 1,
            results_json TEXT NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    cur.execute("""
        INSERT INTO trend_cache (id, results_json, fetched_at)
        VALUES (1, %s, now())
        ON CONFLICT (id) DO UPDATE SET results_json = EXCLUDED.results_json, fetched_at = EXCLUDED.fetched_at
    """, (results_json,))


def get_trend_cache(max_age_hours=3):
    """
    Returns the cached (keyword, topic_title, ...) results list if it
    exists and is younger than max_age_hours, else None.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trend_cache (
            id INTEGER PRIMARY KEY DEFAULT 1,
            results_json TEXT NOT NULL,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    cur.execute("""
        SELECT results_json, fetched_at FROM trend_cache
        WHERE id = 1 AND fetched_at > now() - (%s || ' hours')::interval
    """, (max_age_hours,))
    row = cur.fetchone()
    if not row:
        return None
    return row["results_json"] if isinstance(row, dict) else row[0]


def create_clip_job(topic_id, topic_title, keyword):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO clip_jobs (topic_id, topic_title, keyword)
           VALUES (%s, %s, %s)
           ON CONFLICT (topic_id) DO NOTHING""",
        (topic_id, topic_title, keyword),
    )


def update_clip_job(topic_id, **fields):
    """update_clip_job('abc123', seo_title='...', status='seo_ready')"""
    conn = get_conn()
    cur = conn.cursor()
    cols = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [topic_id]
    cur.execute(f"UPDATE clip_jobs SET {cols} WHERE topic_id = %s", values)


def get_clip_job(topic_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clip_jobs WHERE topic_id = %s", (topic_id,))
    row = cur.fetchone()
    return dict(row) if row else None
