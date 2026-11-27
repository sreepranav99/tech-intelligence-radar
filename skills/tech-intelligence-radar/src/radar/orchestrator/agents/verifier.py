import re
from datetime import datetime, timezone
from typing import List, Dict, Any
from radar.orchestrator.agents.base import BaseAgent
from radar.orchestrator.state import RadarState, VerifiedIntel

def _clean_sentence_truncate(text: str, max_len: int = 280) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_len:
        return text
    clipped = text[:max_len]
    # Try cutting at last sentence end if at least half filled
    for sep in (". ", "! ", "? "):
        idx = clipped.rfind(sep)
        if idx >= max_len // 2:
            return clipped[: idx + 1].strip()
    # Otherwise cut at last word boundary
    last_space = clipped.rfind(" ")
    if last_space > 20:
        clipped = clipped[:last_space]
    return clipped.rstrip(",;:- ") + "..."

def _extract_readable_excerpt(raw_text: str, max_len: int = 280) -> str:
    """Extract a crisp plain-English summary from scraped HTML/Markdown content."""
    if not raw_text:
        return ""
    # Remove untrusted wrapper tags if present
    text = re.sub(r"</?untrusted_web_content[^>]*>", "", raw_text)
    boilerplate_terms = (
        "skip to content", "skip to main", "cookie", "accept all", "privacy policy",
        "sign in", "log in", "create account", "subscribe", "javascript is disabled",
        "enable javascript", "table of contents", "navigation", "terms of service",
        "all rights reserved", "menu", "search", "newsletter", "enter your email",
        "sign you up", "join for quick access"
    )
    good_lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("```", "---", "===", "|", "![")):
            continue
        # Strip markdown headings, blockquotes, list bullets, and links
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^[-*>]\s+", "", line)
        line = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
        line = re.sub(r"https?://\S+", "", line)
        line = re.sub(r"[`*_~]", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) < 45:
            continue
        low = line.lower()
        if any(term in low for term in boilerplate_terms) and len(line) < 120:
            continue
        # Require mostly prose letters (avoid nav bars of single tokens)
        if sum(c.isalpha() for c in line) < len(line) * 0.55:
            continue
        good_lines.append(line)
        if sum(len(x) for x in good_lines) >= max_len:
            break

    if not good_lines:
        return ""
    return _clean_sentence_truncate(" ".join(good_lines), max_len=max_len)

class FactCheckerAgent(BaseAgent):
    """Adversarial Auditor: Verifies candidates against live endpoints to enforce Zero-Hallucination."""

    def __init__(self, mcp_client):
        super().__init__(
            name="FactChecker",
            role="Zero-Hallucination Verification & Live Auditing",
            mcp_client=mcp_client
        )

    async def _audit_github_candidate(self, candidate) -> VerifiedIntel:
        full_name = candidate.signal.external_id
        if "/" not in full_name:
            return VerifiedIntel(
                candidate=candidate,
                is_verified=False,
                verified_metrics={},
                fact_check_notes="Rejected: Invalid GitHub repository name format."
            )

        owner, repo = full_name.split("/", 1)
        # Probe live MCP tool
        live_data = await self.mcp.verify_github_repo(owner, repo)

        if not live_data.get("exists", False):
            return VerifiedIntel(
                candidate=candidate,
                is_verified=False,
                verified_metrics={},
                fact_check_notes=f"Rejected: Repository '{full_name}' does not exist on GitHub (HTTP 404)."
            )

        if live_data.get("archived", False):
            return VerifiedIntel(
                candidate=candidate,
                is_verified=False,
                verified_metrics=live_data,
                fact_check_notes="Rejected: Repository is archived and abandoned."
            )

        live_stars = live_data.get("stars", 0)
        claimed_stars = candidate.signal.metrics.get("stars", 0)
        is_unconfirmed = bool(live_data.get("is_unconfirmed"))

        # Apply star tolerance check: if live count is more than 10% lower than claimed, reject
        if claimed_stars > 0 and not is_unconfirmed and live_stars < (claimed_stars * 0.9):
            return VerifiedIntel(
                candidate=candidate,
                is_verified=False,
                verified_metrics={"claimed_stars": claimed_stars, "live_stars": live_stars},
                fact_check_notes=f"Rejected: Live stars ({live_stars}) are >10% lower than claimed ({claimed_stars})."
            )

        verified_metrics = {
            "verified_stars": live_stars,
            "verified_forks": live_data.get("forks", 0),
            "language": candidate.signal.metrics.get("language") or "Unknown",
            "created_at": live_data.get("created_at") or candidate.signal.metrics.get("created_at"),
            "last_push": live_data.get("last_push"),
            "license": live_data.get("license") or "None",
            "archived": live_data.get("archived", False),
            "is_unconfirmed": is_unconfirmed
        }

        if is_unconfirmed:
            notes = (
                f"Unconfirmed: Direct GitHub API rate-limited; metrics ({live_stars} stars) inferred from cache/search fallback."
            )
        else:
            notes = (
                f"Verified live on GitHub. Confirmed {live_stars:,} stars, "
                f"active push at {live_data.get('last_push', 'N/A')}, license: {verified_metrics['license']}."
            )

        return VerifiedIntel(
            candidate=candidate,
            is_verified=True,
            verified_metrics=verified_metrics,
            fact_check_notes=notes
        )

    async def _audit_web_candidate(self, candidate) -> VerifiedIntel:
        url = candidate.signal.url
        if not url.startswith("http"):
            return VerifiedIntel(
                candidate=candidate,
                is_verified=False,
                verified_metrics={},
                fact_check_notes="Rejected: Invalid URL format."
            )

        # Helper to enrich sparse HN/Reddit snippets from verified content
        def _maybe_enrich_snippet(raw_text: str, page_title: str = "") -> None:
            sig = candidate.signal
            is_sparse = (not sig.raw_snippet.strip()) or sig.raw_snippet.startswith("HN Story with ")
            if sig.source_type != "arxiv" and is_sparse:
                excerpt = _extract_readable_excerpt(raw_text)
                if excerpt:
                    sig.raw_snippet = excerpt
                elif page_title and page_title not in ("Live Page", "Untitled Page"):
                    sig.raw_snippet = f"{page_title} — community-highlighted release/article on {sig.source_type.upper()}."

        # 1. Prefer External MCP Fetch Server (Official Anthropic Server) if configured & active
        ext_res = await self.mcp.call_external_tool("external_fetch", "fetch", {"url": url})
        if isinstance(ext_res, str) and len(ext_res) > 30 and "error" not in ext_res[:30].lower():
            _maybe_enrich_snippet(ext_res)
            verified_metrics = {
                "source": "External MCP Server (mcp_server_fetch)",
                "status_code": 200,
                "content_length": len(ext_res)
            }
            if candidate.signal.source_type == "hackernews":
                verified_metrics["points"] = candidate.signal.metrics.get("points", 0)
                verified_metrics["comments"] = candidate.signal.metrics.get("comments", 0)
            elif candidate.signal.source_type == "reddit":
                verified_metrics["score"] = candidate.signal.metrics.get("score", 0)
                verified_metrics["comments"] = candidate.signal.metrics.get("comments", 0)
            return VerifiedIntel(
                candidate=candidate,
                is_verified=True,
                verified_metrics=verified_metrics,
                fact_check_notes="Verified live via Official External MCP Fetch Server."
            )

        # 2. Fallback to our custom internal web_extract_markdown MCP tool
        page_data = await self.mcp.extract_web(url, max_chars=1800)
        status = page_data.get("status_code", 0)

        if status != 200:
            return VerifiedIntel(
                candidate=candidate,
                is_verified=False,
                verified_metrics={"status_code": status},
                fact_check_notes=f"Rejected: Target URL returned HTTP status {status}."
            )

        _maybe_enrich_snippet(page_data.get("cleaned_text", ""), page_data.get("title", ""))
        verified_metrics = {
            "status_code": status,
            "page_title": page_data.get("title", "Live Page"),
            "content_length": page_data.get("char_length", 0)
        }
        if candidate.signal.source_type == "hackernews":
            verified_metrics["points"] = candidate.signal.metrics.get("points", 0)
            verified_metrics["comments"] = candidate.signal.metrics.get("comments", 0)
        elif candidate.signal.source_type == "reddit":
            verified_metrics["score"] = candidate.signal.metrics.get("score", 0)
            verified_metrics["comments"] = candidate.signal.metrics.get("comments", 0)

        return VerifiedIntel(
            candidate=candidate,
            is_verified=True,
            verified_metrics=verified_metrics,
            fact_check_notes=f"Verified live webpage. Title: '{verified_metrics['page_title']}'."
        )

    async def execute(self, state: RadarState) -> None:
        state.log(f"[{self.name}] Initiating adversarial audit on {len(state.shortlisted_candidates)} candidates...")
        
        verified_items: List[VerifiedIntel] = []

        for candidate in state.shortlisted_candidates:
            if candidate.signal.source_type == "github":
                audit_result = await self._audit_github_candidate(candidate)
            else:
                audit_result = await self._audit_web_candidate(candidate)

            if audit_result.is_verified:
                verified_items.append(audit_result)
                state.log(f"[{self.name}] [VERIFIED] {candidate.signal.title[:50]}... -> Passed live checks.")
            else:
                state.log(f"[{self.name}] [REJECTED] {candidate.signal.title[:50]}... -> {audit_result.fact_check_notes}")

        state.verified_items = verified_items
        state.log(f"[{self.name}] Audit complete: {len(state.verified_items)} candidates successfully verified.")
