import httpx
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from radar.config import CACHE_DIR, USER_AGENT

HN_API_BASE = "https://hn.algolia.com/api/v1"

def _get_cache_path(key: str) -> Path:
    hashed = hashlib.sha256(key.encode()).hexdigest()
    return CACHE_DIR / f"hn_{hashed}.json"

def _read_cache(cache_path: Path, max_age_hours: int = 4) -> Optional[Any]:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        cached_time = datetime.fromisoformat(data["_cached_at"])
        if datetime.now(timezone.utc) - cached_time < timedelta(hours=max_age_hours):
            return data["payload"]
    except Exception:
        return None
    return None

def _write_cache(cache_path: Path, payload: Any) -> None:
    try:
        data = {
            "_cached_at": datetime.now(timezone.utc).isoformat(),
            "payload": payload
        }
        cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

async def search_hackernews_discussions(
    query: str,
    days_back: int = 7,
    min_points: int = 15,
    limit: int = 15
) -> Dict[str, Any]:
    """Search Hacker News stories and discussions matching query within time window."""
    since_timestamp = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())
    cache_key = f"hn:{query}:{days_back}:{min_points}:{limit}"
    cache_path = _get_cache_path(cache_key)

    cached = _read_cache(cache_path)
    if cached is not None:
        return {"source": "cache", "items": cached}

    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{since_timestamp},points>={min_points}",
        "hitsPerPage": min(limit * 2, 40)
    }

    try:
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(headers=headers, timeout=12.0) as client:
            resp = await client.get(f"{HN_API_BASE}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            items = []
            for hit in data.get("hits", []):
                story_id = hit.get("objectID")
                title = hit.get("title") or "Untitled"
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={story_id}"
                hn_item_url = f"https://news.ycombinator.com/item?id={story_id}"
                
                items.append({
                    "id": story_id,
                    "title": title,
                    "url": story_url,
                    "discussion_url": hn_item_url,
                    "points": hit.get("points", 0),
                    "comments": hit.get("num_comments", 0),
                    "author": hit.get("author", "unknown"),
                    "created_at": hit.get("created_at")
                })
                if len(items) >= limit:
                    break

            _write_cache(cache_path, items)
            return {"source": "live", "items": items}

    except Exception as e:
        return {"error": str(e), "items": []}
