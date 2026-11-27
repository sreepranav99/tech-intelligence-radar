import httpx
import json
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import warnings
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from radar.config import CACHE_DIR, USER_AGENT

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

ARXIV_API_BASE = "https://export.arxiv.org/api/query"

def _get_cache_path(key: str) -> Path:
    hashed = hashlib.sha256(key.encode()).hexdigest()
    return CACHE_DIR / f"arxiv_{hashed}.json"

def _read_cache(cache_path: Path, max_age_hours: int = 12) -> Optional[Any]:
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

async def search_arxiv_papers(query: str, limit: int = 8) -> Dict[str, Any]:
    """Search arXiv scientific preprints for breakthrough papers matching query."""
    cache_key = f"arxiv:{query}:{limit}"
    cache_path = _get_cache_path(cache_key)

    cached = _read_cache(cache_path)
    if cached is not None:
        return {"source": "cache", "items": cached}

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": min(limit, 20),
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }

    try:
        headers = {"User-Agent": USER_AGENT}
        async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
            resp = await client.get(ARXIV_API_BASE, params=params)
            resp.raise_for_status()
            xml_content = resp.text

            soup = BeautifulSoup(xml_content, "html.parser")
            entries = soup.find_all("entry")

            items = []
            for entry in entries:
                title_elem = entry.find("title")
                title = title_elem.get_text().strip().replace("\n", " ") if title_elem else "Untitled Paper"

                summary_elem = entry.find("summary")
                summary = summary_elem.get_text().strip().replace("\n", " ") if summary_elem else ""

                id_elem = entry.find("id")
                url = id_elem.get_text().strip() if id_elem else ""

                published_elem = entry.find("published")
                published = published_elem.get_text().strip() if published_elem else ""

                authors = [a.get_text().strip() for a in entry.find_all("name")]

                items.append({
                    "id": url,
                    "title": title,
                    "url": url,
                    "summary": summary[:400] + "..." if len(summary) > 400 else summary,
                    "published": published,
                    "authors": authors[:3]
                })

                if len(items) >= limit:
                    break

            _write_cache(cache_path, items)
            return {"source": "live", "items": items}

    except Exception as e:
        return {"error": str(e), "items": []}
