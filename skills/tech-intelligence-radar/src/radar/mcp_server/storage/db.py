import json
import aiosqlite
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from radar.config import DB_PATH

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS intelligence_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    source_url TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    novelty_score REAL NOT NULL,
    velocity_score REAL NOT NULL,
    summary TEXT NOT NULL,
    key_takeaways TEXT NOT NULL,
    verified_metrics_json TEXT NOT NULL,
    first_detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_url ON intelligence_items(source_url);
CREATE INDEX IF NOT EXISTS idx_entity_name ON intelligence_items(entity_name);

CREATE TABLE IF NOT EXISTS briefings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    run_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    topic_query TEXT NOT NULL,
    briefing_markdown TEXT NOT NULL,
    verified_items_count INTEGER NOT NULL,
    sources_summary_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    stars INTEGER DEFAULT 0,
    forks INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_snapshot_url ON entity_snapshots(source_url, recorded_at);
"""

async def init_db(db_path: Path = DB_PATH) -> None:
    """Initialize SQLite database tables and indices."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(CREATE_TABLES_SQL)
        await db.commit()

async def persist_intelligence_item(
    source_type: str,
    entity_name: str,
    source_url: str,
    category: str,
    novelty_score: float,
    velocity_score: float,
    summary: str,
    key_takeaways: str,
    verified_metrics: Dict[str, Any],
    db_path: Path = DB_PATH
) -> int:
    """Insert or update an intelligence item in the database."""
    metrics_json = json.dumps(verified_metrics)
    now = datetime.now(timezone.utc).isoformat()
    
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO intelligence_items (
                source_type, entity_name, source_url, category,
                novelty_score, velocity_score, summary, key_takeaways,
                verified_metrics_json, first_detected_at, last_verified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_url) DO UPDATE SET
                entity_name=excluded.entity_name,
                novelty_score=excluded.novelty_score,
                velocity_score=excluded.velocity_score,
                summary=excluded.summary,
                key_takeaways=excluded.key_takeaways,
                verified_metrics_json=excluded.verified_metrics_json,
                last_verified_at=excluded.last_verified_at
            """,
            (
                source_type, entity_name, source_url, category,
                novelty_score, velocity_score, summary, key_takeaways,
                metrics_json, now, now
            )
        )
        await db.commit()
        item_id = cursor.lastrowid or 0

    # Record snapshot for velocity tracking
    stars = int(verified_metrics.get("verified_stars", verified_metrics.get("stars", 0)))
    forks = int(verified_metrics.get("verified_forks", verified_metrics.get("forks", 0)))
    points = int(verified_metrics.get("points", 0))
    comments = int(verified_metrics.get("comments", 0))
    await record_metric_snapshot(
        entity_name=entity_name,
        source_url=source_url,
        stars=stars,
        forks=forks,
        points=points,
        comments=comments,
        db_path=db_path
    )

    return item_id

async def query_history(
    query: str,
    limit: int = 10,
    db_path: Path = DB_PATH
) -> List[Dict[str, Any]]:
    """Search historical items to check for duplicates or previous coverage."""
    search_term = f"%{query}%"
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, source_type, entity_name, source_url, category,
                   novelty_score, summary, key_takeaways, first_detected_at
            FROM intelligence_items
            WHERE entity_name LIKE ? OR summary LIKE ? OR source_url LIKE ?
            ORDER BY first_detected_at DESC
            LIMIT ?
            """,
            (search_term, search_term, search_term, limit)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def check_url_exists(source_url: str, db_path: Path = DB_PATH) -> bool:
    """Check if a specific source URL has already been processed."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute(
            "SELECT 1 FROM intelligence_items WHERE source_url = ?",
            (source_url,)
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None

async def save_briefing(
    run_id: str,
    topic_query: str,
    briefing_markdown: str,
    verified_items_count: int,
    sources_summary: Dict[str, Any],
    db_path: Path = DB_PATH
) -> int:
    """Save a generated markdown briefing into the briefings table."""
    sources_json = json.dumps(sources_summary)
    now = datetime.now(timezone.utc).isoformat()
    
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO briefings (
                run_id, run_timestamp, topic_query, briefing_markdown,
                verified_items_count, sources_summary_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, now, topic_query, briefing_markdown, verified_items_count, sources_json)
        )
        await db.commit()
        return cursor.lastrowid or 0

async def get_latest_briefing(db_path: Path = DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent briefing."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, run_id, run_timestamp, topic_query, briefing_markdown,
                   verified_items_count, sources_summary_json
            FROM briefings
            ORDER BY id DESC
            LIMIT 1
            """
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_all_tracked_entities(db_path: Path = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve all tracked intelligence items for resource exposure."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT id, entity_name, category, source_url, novelty_score,
                   velocity_score, first_detected_at, last_verified_at
            FROM intelligence_items
            ORDER BY last_verified_at DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

async def record_metric_snapshot(
    entity_name: str,
    source_url: str,
    stars: int = 0,
    forks: int = 0,
    points: int = 0,
    comments: int = 0,
    db_path: Path = DB_PATH
) -> int:
    """Store a timestamped snapshot of an entity's traction metrics."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute(
            """
            INSERT INTO entity_snapshots (
                entity_name, source_url, stars, forks, points, comments, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (entity_name, source_url, stars, forks, points, comments, now)
        )
        await db.commit()
        return cursor.lastrowid or 0

async def get_velocity_delta(
    source_url: str,
    db_path: Path = DB_PATH
) -> Dict[str, Any]:
    """Calculate the velocity delta (growth change) between the two most recent snapshots."""
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT stars, forks, points, comments, recorded_at
            FROM entity_snapshots
            WHERE source_url = ?
            ORDER BY recorded_at DESC
            LIMIT 2
            """,
            (source_url,)
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return {"has_history": False, "delta_stars": 0, "stars_per_day": 0.0, "badge": "New Entry"}

    latest = dict(rows[0])
    if len(rows) == 1:
        # First observation
        return {
            "has_history": False,
            "current_stars": latest["stars"],
            "current_points": latest["points"],
            "delta_stars": 0,
            "stars_per_day": 0.0,
            "badge": f"Baseline: {latest['stars']} stars" if latest['stars'] > 0 else "Baseline"
        }

    previous = dict(rows[1])
    try:
        t_latest = datetime.fromisoformat(latest["recorded_at"])
        t_prev = datetime.fromisoformat(previous["recorded_at"])
        hours_elapsed = max(0.1, (t_latest - t_prev).total_seconds() / 3600.0)
    except Exception:
        hours_elapsed = 24.0

    days_elapsed = round(hours_elapsed / 24.0, 1)
    delta_stars = latest["stars"] - previous["stars"]
    delta_points = latest["points"] - previous["points"]

    stars_per_day = round((delta_stars / hours_elapsed) * 24.0, 1)

    pct_growth = 0.0
    if previous["stars"] > 0:
        pct_growth = round((delta_stars / previous["stars"]) * 100.0, 1)

    # Format human-readable acceleration badge
    if delta_stars > 100:
        badge = f"🔥 Viral Surge: +{delta_stars} stars in {days_elapsed}d (+{pct_growth}%)"
    elif delta_stars > 20:
        badge = f"📈 Steady Acceleration: +{delta_stars} stars (+{stars_per_day}/day)"
    elif delta_stars > 0:
        badge = f"🌱 Growing: +{delta_stars} stars"
    elif delta_points > 10:
        badge = f"💬 Discussion Spike: +{delta_points} points on HN"
    else:
        badge = "Stable"

    return {
        "has_history": True,
        "current_stars": latest["stars"],
        "previous_stars": previous["stars"],
        "delta_stars": delta_stars,
        "delta_points": delta_points,
        "days_elapsed": days_elapsed,
        "stars_per_day": stars_per_day,
        "percentage_growth": pct_growth,
        "badge": badge
    }

