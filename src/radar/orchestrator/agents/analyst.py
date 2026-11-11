import re
from typing import List
from radar.config import BRIEFING_ITEMS_LIMIT
from radar.orchestrator.agents.base import BaseAgent
from radar.orchestrator.state import RadarState, ScoredCandidate
from radar.orchestrator.llm import LLMClient

def _clean_truncate(text: str, max_len: int = 240) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    if len(cleaned) <= max_len:
        return cleaned
    clipped = cleaned[:max_len]
    for sep in (". ", "! ", "? "):
        idx = clipped.rfind(sep)
        if idx >= max_len // 2:
            return clipped[: idx + 1].strip()
    last_space = clipped.rfind(" ")
    if last_space > 20:
        clipped = clipped[:last_space]
    return clipped.rstrip(",;:- ") + "..."

class SignalAnalystAgent(BaseAgent):
    """Filters noise, checks historical persistence, and scores candidate novelty & velocity."""

    def __init__(self, mcp_client):
        super().__init__(
            name="SignalAnalyst",
            role="Signal Filtering, Deduplication & Scoring",
            mcp_client=mcp_client
        )
        self.llm = LLMClient()

    def _determine_category(self, title: str, snippet: str, source_type: str) -> str:
        if source_type == "arxiv":
            return "Research / Paper"
        text = f"{title} {snippet}".lower()
        if any(w in text for w in ["framework", "sdk", "library", "client"]):
            return "Framework / SDK"
        elif any(w in text for w in ["server", "mcp-server", "cli", "extension", "plugin", "tool"]):
            return "Developer Tool"
        elif any(w in text for w in ["spec", "protocol", "architecture", "standard", "rfc"]):
            return "Protocol / Spec"
        elif any(w in text for w in ["benchmark", "paper", "research", "eval"]):
            return "Research / Evaluation"
        return "Ecosystem Discussion"

    def _compute_velocity_score(self, signal) -> float:
        """Calculate momentum based on stars or discussion activity."""
        metrics = signal.metrics
        if signal.source_type == "github":
            stars = metrics.get("stars", 0)
            if stars > 1000:
                return 9.5
            elif stars > 300:
                return 8.5
            elif stars > 100:
                return 7.5
            elif stars > 30:
                return 6.5
            return 5.0
        elif signal.source_type == "hackernews":
            points = metrics.get("points", 0)
            comments = metrics.get("comments", 0)
            score = min(9.5, (points * 0.015) + (comments * 0.025) + 4.5)
            return round(score, 1)
        elif signal.source_type == "reddit":
            score_val = metrics.get("score", 0)
            comments = metrics.get("comments", 0)
            score = min(9.2, (score_val * 0.02) + (comments * 0.03) + 4.5)
            return round(score, 1)
        elif signal.source_type == "arxiv":
            return 7.4  # Fresh academic preprint momentum without crowding out live GitHub/HN tools
        return 5.0

    def _build_takeaway(self, signal, category: str, velocity: float, novelty: float, velocity_delta: dict, is_breakout: bool) -> str:
        """Synthesize a crisp 'Why You Should Care' engineering takeaway distinct from raw description."""
        m = signal.metrics or {}
        if is_breakout:
            badge = velocity_delta.get("badge", "Surge Detected")
            return f"⚡ {badge}. Rapid ecosystem adoption signals active production experimentation in {category}."

        if signal.source_type == "github":
            stars = int(m.get("stars", 0))
            forks = int(m.get("forks", 0))
            lang = m.get("language") or "Multi-language"
            return (
                f"Active {lang} open-source {category.lower()} with {stars:,} GitHub stars and {forks:,} forks "
                f"(Velocity {velocity}/10, Novelty {novelty}/10) — worth evaluating for your AI workflow stack."
            )
        elif signal.source_type == "hackernews":
            pts = int(m.get("points", 0))
            cmts = int(m.get("comments", 0))
            return (
                f"Sparked high-signal developer debate on Hacker News ({pts:,} points, {cmts:,} comments), "
                f"indicating strong practitioner interest in this {category.lower()}."
            )
        elif signal.source_type == "reddit":
            sc = int(m.get("score", 0))
            cmts = int(m.get("comments", 0))
            sub = m.get("subreddit", "LocalLLaMA")
            return (
                f"Practitioner discussion in r/{sub} ({sc:,} upvotes, {cmts:,} comments) highlighting hands-on benchmarks, "
                f"trade-offs, or real-world deployment patterns."
            )
        elif signal.source_type == "arxiv":
            return (
                f"Recent research preprint advancing formal architectures or safety/evaluation methods for autonomous AI systems "
                f"(Novelty {novelty}/10)."
            )
        return f"Verified emerging signal in {category} (Velocity {velocity}/10, Novelty {novelty}/10)."

    def _compute_novelty_score(self, signal, is_past_duplicate: bool) -> float:
        if is_past_duplicate:
            return 3.0  # Penalize already known items
        
        text = f"{signal.title} {signal.raw_snippet}".lower()
        # Bonus for high-signal technical indicators
        bonus = 0.0
        if any(k in text for k in ["autonomous", "mcp", "protocol", "agent", "orchestration", "zero-shot"]):
            bonus += 1.5
        if len(signal.raw_snippet) > 40:
            bonus += 0.5
            
        base = 6.0
        return min(10.0, round(base + bonus, 1))

    async def execute(self, state: RadarState) -> None:
        state.log(f"[{self.name}] Analyzing {len(state.raw_signals)} raw signals...")
        
        candidates: List[ScoredCandidate] = []
        backfill_candidates: List[ScoredCandidate] = []

        for signal in state.raw_signals:
            # Query MCP storage for duplicate check & historical velocity delta
            past_hits = await self.mcp.query_history(query=signal.external_id, limit=3)
            is_duplicate = len(past_hits) > 0
            
            # Check time-series velocity delta from snapshots
            velocity_delta = await self.mcp.get_velocity_delta(signal.url)
            delta_stars = velocity_delta.get("delta_stars", 0)
            is_breakout = velocity_delta.get("has_history", False) and (delta_stars >= 30)

            category = self._determine_category(signal.title, signal.raw_snippet, signal.source_type)
            velocity = self._compute_velocity_score(signal)
            
            # If it's a breakout surge, override duplicate penalty and boost scores!
            if is_breakout:
                velocity = min(10.0, velocity + 1.5)
                novelty = 9.0  # High novelty for active surges
            else:
                novelty = self._compute_novelty_score(signal, is_duplicate)

            # Store velocity delta info in signal metrics for Editor
            signal.metrics["velocity_delta"] = velocity_delta
            justification = self._build_takeaway(signal, category, velocity, novelty, velocity_delta, is_breakout)

            # Include if novel and fresh, OR if an existing project is having a viral surge!
            if (novelty >= 5.5 and not is_duplicate) or is_breakout:
                candidates.append(
                    ScoredCandidate(
                        signal=signal,
                        category=category,
                        novelty_score=novelty,
                        velocity_score=velocity,
                        is_duplicate=is_duplicate and not is_breakout,
                        justification=justification
                    )
                )
            elif velocity >= 7.0:
                backfill_novelty = max(6.5, novelty)
                backfill_candidates.append(
                    ScoredCandidate(
                        signal=signal,
                        category=category,
                        novelty_score=backfill_novelty,
                        velocity_score=velocity,
                        is_duplicate=True,
                        justification=self._build_takeaway(signal, category, velocity, backfill_novelty, velocity_delta, False) + " (Continued top momentum)"
                    )
                )

        # Sort candidates by combined score (velocity + novelty) descending
        score_fn = lambda c: (c.velocity_score * 0.55 + c.novelty_score * 0.45)
        candidates.sort(key=score_fn, reverse=True)
        target_pool = BRIEFING_ITEMS_LIMIT + 3

        # Ensure balanced source diversity across GitHub, HN, arXiv, Reddit (cap single source to 4 first, then fill remainder)
        diversified: List[ScoredCandidate] = []
        overflow: List[ScoredCandidate] = []
        source_counts = {}
        max_per_source = max(4, (BRIEFING_ITEMS_LIMIT + 1) // 2)
        for cand in candidates:
            st = cand.signal.source_type
            if source_counts.get(st, 0) < max_per_source:
                diversified.append(cand)
                source_counts[st] = source_counts.get(st, 0) + 1
            else:
                overflow.append(cand)

        if len(diversified) < target_pool and overflow:
            diversified.extend(overflow[: target_pool - len(diversified)])

        if len(diversified) < target_pool and backfill_candidates:
            backfill_candidates.sort(key=lambda c: c.velocity_score, reverse=True)
            needed = target_pool - len(diversified)
            diversified.extend(backfill_candidates[:needed])

        # Shortlist enough top candidates to guarantee hitting the target after fact-checking
        top_candidates = diversified[:target_pool]

        # Optional LLM reasoning enrichment for technical differentiators
        if self.llm.is_available:
            state.log(f"[{self.name}] Enriching top candidates with LLM architectural differentiation...")
            for cand in top_candidates[:3]:
                diff = await self.llm.analyze_technical_differentiator(
                    cand.signal.title, cand.signal.raw_snippet, cand.category
                )
                if diff:
                    cand.justification = f"{diff} (Score: {cand.novelty_score}/10, Velocity: {cand.velocity_score}/10)"

        state.shortlisted_candidates = top_candidates

        state.log(
            f"[{self.name}] Filtered down to {len(state.shortlisted_candidates)} high-potential candidates."
        )
