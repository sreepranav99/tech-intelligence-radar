import re
from typing import List, Dict, Any
from radar.orchestrator.agents.base import BaseAgent
from radar.orchestrator.state import RadarState

class CoordinatorAgent(BaseAgent):
    """Decomposes the research topic into search matrices and sets pipeline parameters."""

    def __init__(self, mcp_client):
        super().__init__(
            name="CoordinatorAgent",
            role="Research Planning & Topic Decomposition",
            mcp_client=mcp_client
        )

    async def execute(self, state: RadarState) -> None:
        # Respect an explicit multi-stream search plan if already provided (e.g. Morning Briefing)
        if "_search_plan" in state.__dict__ and state.__dict__["_search_plan"]:
            plan = state.__dict__["_search_plan"]
            state.log(f"[{self.name}] Using multi-stream search plan: {plan.get('primary_topics', [])}")
            return

        state.log(f"[{self.name}] Analyzing topic: '{state.topic_query}'")
        
        # Split comma/and-separated multi-topic strings into clean sub-phrases
        raw_parts = re.split(r"[,;]|\band\b", state.topic_query, flags=re.IGNORECASE)
        phrases = []
        for part in raw_parts:
            clean_part = re.sub(r"[^\w\s-]", " ", part).strip()
            clean_part = re.sub(r"\s+", " ", clean_part)
            if len(clean_part) >= 2:
                phrases.append(clean_part)

        if not phrases:
            phrases = [state.topic_query.strip()]

        # Deduplicate while preserving order
        unique_phrases = list(dict.fromkeys(phrases))
        
        plan = {
            "primary_topics": unique_phrases[:4],
            "github_queries": unique_phrases[:3],
            "hn_queries": unique_phrases[:3]
        }
        
        state.log(f"[{self.name}] Formulated search plan: {plan['primary_topics']}")
        state.__dict__["_search_plan"] = plan
