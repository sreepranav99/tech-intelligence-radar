import httpx
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from radar.config import CACHE_DIR, GITHUB_TOKEN, USER_AGENT

GITHUB_API_BASE = "https://api.github.com"

def _get_cache_path(key: str) -> Path:
    hashed = hashlib.sha256(key.encode()).hexdigest()
    return CACHE_DIR / f"gh_{hashed}.json"

def _read_cache(cache_path: Path, max_age_hours: int = 6) -> Optional[Any]:
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

def _get_headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": USER_AGENT,
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers

async def search_trending_repositories(
    topic: str,
    days_back: int = 7,
    min_stars: int = 30,
    limit: int = 10
) -> Dict[str, Any]:
    """Search for recently created or active repositories matching topic."""
    since_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
    query = f"{topic} created:>{since_date} stars:>={min_stars}"
    cache_key = f"search:{query}:{limit}"
    cache_path = _get_cache_path(cache_key)

    cached = _read_cache(cache_path)
    if cached is not None:
        return {"source": "cache", "items": cached}

    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 30)
    }

    try:
        async with httpx.AsyncClient(headers=_get_headers(), timeout=15.0) as client:
            resp = await client.get(f"{GITHUB_API_BASE}/search/repositories", params=params)
            
            # If 0 results for strictly created:>{date}, fall back to pushed:>{date} for active development
            if resp.status_code == 200 and resp.json().get("total_count", 0) == 0:
                fallback_query = f"{topic} pushed:>{since_date} stars:>={min_stars}"
                resp = await client.get(
                    f"{GITHUB_API_BASE}/search/repositories",
                    params={"q": fallback_query, "sort": "stars", "order": "desc", "per_page": min(limit, 30)}
                )

            if resp.status_code == 403 or resp.status_code == 429:
                return {
                    "error": "GitHub API rate limit exceeded.",
                    "status_code": resp.status_code,
                    "items": []
                }
            resp.raise_for_status()
            data = resp.json()

            items = []
            for repo in data.get("items", [])[:limit]:
                items.append({
                    "name": repo.get("full_name"),
                    "url": repo.get("html_url"),
                    "description": repo.get("description") or "No description provided",
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language") or "Unknown",
                    "created_at": repo.get("created_at"),
                    "pushed_at": repo.get("pushed_at"),
                    "topics": repo.get("topics", [])
                })

            _write_cache(cache_path, items)
            return {"source": "live", "items": items}

    except Exception as e:
        return {"error": str(e), "items": []}

async def get_repository_details(owner: str, repo: str) -> Dict[str, Any]:
    """Fetch live metadata for a specific repository (used by Fact-Checker agent)."""
    cache_key = f"repo:{owner}/{repo}"
    cache_path = _get_cache_path(cache_key)

    cached = _read_cache(cache_path, max_age_hours=2)
    if cached is not None:
        return {"source": "cache", "data": cached}

    try:
        async with httpx.AsyncClient(headers=_get_headers(), timeout=12.0) as client:
            resp = await client.get(f"{GITHUB_API_BASE}/repos/{owner}/{repo}")
            if resp.status_code == 404:
                return {"exists": False, "error": "Repository not found (404)"}
            if resp.status_code in (403, 429):
                return {"exists": True, "error": "Rate limit exceeded while verifying"}
            
            resp.raise_for_status()
            data = resp.json()

            details = {
                "exists": True,
                "full_name": data.get("full_name"),
                "description": data.get("description"),
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "open_issues": data.get("open_issues_count", 0),
                "created_at": data.get("created_at"),
                "last_push": data.get("pushed_at"),
                "archived": data.get("archived", False),
                "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
                "default_branch": data.get("default_branch", "main")
            }
            _write_cache(cache_path, details)
            return {"source": "live", "data": details}

    except Exception as e:
        return {"exists": False, "error": str(e)}
