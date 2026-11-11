import re
import json
import httpx
import hashlib
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from radar.config import CACHE_DIR, USER_AGENT

def _get_cache_path(url: str) -> Path:
    hashed = hashlib.sha256(url.encode()).hexdigest()
    return CACHE_DIR / f"web_{hashed}.json"

def _sanitize_untrusted_text(text: str) -> str:
    """Strip dangerous control characters, zero-width spaces, and excess whitespace."""
    # Remove zero-width spaces and control characters except newlines/tabs
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\u200B-\u200D\uFEFF]", "", text)
    # Collapse 3+ newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces into single
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()

async def extract_web_markdown(url: str, max_chars: int = 6000) -> Dict[str, Any]:
    """Fetch external web page, clean boilerplate, and return safe markdown."""
    cache_path = _get_cache_path(url)
    if cache_path.exists():
        try:
            cached_data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_time = datetime.fromisoformat(cached_data["_cached_at"])
            if datetime.now(timezone.utc) - cached_time < timedelta(hours=12):
                return {"source": "cache", "data": cached_data["payload"]}
        except Exception:
            pass

    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        async with httpx.AsyncClient(headers=headers, timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {
                    "url": url,
                    "status_code": resp.status_code,
                    "error": f"HTTP status {resp.status_code}",
                    "content": ""
                }
            
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # Remove noisy tags
            for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg", "form"]):
                tag.decompose()

            title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled Page"

            # Prefer main article container if available
            main_element = soup.find("main") or soup.find("article") or soup.find("body") or soup
            raw_text = main_element.get_text(separator="\n")
            cleaned_text = _sanitize_untrusted_text(raw_text)

            # Truncate to avoid context window explosion
            if len(cleaned_text) > max_chars:
                cleaned_text = cleaned_text[:max_chars] + "\n\n...[Content truncated for length]..."

            # Wrap in untrusted delimiter for safety
            safe_payload = {
                "url": url,
                "title": title,
                "status_code": resp.status_code,
                "cleaned_text": f"<untrusted_web_content url=\"{url}\">\n{cleaned_text}\n</untrusted_web_content>",
                "char_length": len(cleaned_text)
            }

            try:
                cache_path.write_text(json.dumps({
                    "_cached_at": datetime.now(timezone.utc).isoformat(),
                    "payload": safe_payload
                }, indent=2), encoding="utf-8")
            except Exception:
                pass

            return {"source": "live", "data": safe_payload}

    except Exception as e:
        return {
            "url": url,
            "error": str(e),
            "content": ""
        }
