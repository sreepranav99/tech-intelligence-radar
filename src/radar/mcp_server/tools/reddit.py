import httpx
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from radar.config import CACHE_DIR, USER_AGENT

REDDIT_BASE = "https://www.reddit.com"

def _get_cache_path(key: str) -> Path:
    hashed = hashlib.sha256(key.encode()).hexdigest()
    return CACHE_DIR / f"reddit_{hashed}.json"

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

async def search_reddit_discussions(
    query: str,
    subreddit: str = "LocalLLaMA",
    limit: int = 8
) -> Dict[str, Any]:
    """Search developer communities on Reddit for discussions, benchmarks, and feedback."""
    cache_key = f"reddit:{subreddit}:{query}:{limit}"
    cache_path = _get_cache_path(cache_key)

    cached = _read_cache(cache_path)
    if cached is not None:
        return {"source": "cache", "items": cached}

    # Custom unique User-Agent required by Reddit API guidelines
    headers = {
        "User-Agent": f"windows:tech.intelligence.radar:v1.0 (by /u/TechRadarAgent)"
    }
    
    url = f"{REDDIT_BASE}/r/{subreddit}/search.json"
    params = {
        "q": query,
        "restrict_sr": 1,
        "sort": "relevance",
        "t": "month",
        "limit": min(limit, 15)
    }

    try:
        async with httpx.AsyncClient(headers=headers, timeout=12.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return {"source": "reddit", "items": [], "warning": f"HTTP {resp.status_code}"}
            
            data = resp.json()
            children = data.get("data", {}).get("children", [])

            items = []
            for child in children:
                post = child.get("data", {})
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                permalink = post.get("permalink", "")
                post_url = f"{REDDIT_BASE}{permalink}" if permalink else post.get("url", "")
                
                score = post.get("score", 0)
                comments = post.get("num_comments", 0)

                items.append({
                    "id": post.get("id"),
                    "title": title,
                    "url": post_url,
                    "snippet": selftext[:300] + "..." if len(selftext) > 300 else selftext,
                    "score": score,
                    "comments": comments,
                    "subreddit": post.get("subreddit"),
                    "author": post.get("author")
                })

                if len(items) >= limit:
                    break

            _write_cache(cache_path, items)
            return {"source": "live", "items": items}

    except Exception as e:
        return {"error": str(e), "items": []}
