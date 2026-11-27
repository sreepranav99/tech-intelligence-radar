import uuid
from datetime import datetime, timezone
from typing import Callable, Optional, List, Any, Awaitable, Dict
from radar.orchestrator.state import RadarState, ScoredCandidate
from radar.orchestrator.mcp_client import RadarMCPClient
from radar.orchestrator.agents.coordinator import CoordinatorAgent
from radar.orchestrator.agents.scouts import ScoutPool
from radar.orchestrator.agents.analyst import SignalAnalystAgent
from radar.orchestrator.agents.verifier import FactCheckerAgent
from radar.orchestrator.agents.editor import ExecutiveEditorAgent

class RadarEngine:
    """Master workflow orchestrator managing the multi-agent pipeline and state transitions."""

    def __init__(self, mcp_client: Optional[RadarMCPClient] = None):
        self.mcp = mcp_client or RadarMCPClient()
        self.coordinator = CoordinatorAgent(self.mcp)
        self.scout_pool = ScoutPool(self.mcp)
        self.analyst = SignalAnalystAgent(self.mcp)
        self.verifier = FactCheckerAgent(self.mcp)
        self.editor = ExecutiveEditorAgent(self.mcp)

    async def run(
        self,
        topic: str,
        on_step: Optional[Callable[[str, RadarState], None]] = None,
        interactive: bool = False,
        on_human_selection: Optional[Callable[[List[ScoredCandidate]], Any]] = None,
        initial_plan: Optional[Dict[str, Any]] = None
    ) -> RadarState:
        """Execute a full intelligence cycle on the specified topic."""
        run_id = str(uuid.uuid4())
        state = RadarState(run_id=run_id, topic_query=topic)
        if initial_plan:
            state.__dict__["_search_plan"] = initial_plan
        state.log(f"Initiated intelligence cycle for topic: '{topic}' [Run: {run_id[:8]}]")

        def notify(step_name: str):
            if on_step:
                on_step(step_name, state)

        # Stage 1: Topic Decomposition & Planning
        notify("Coordinator: Formulating Search Strategy")
        await self.coordinator.execute(state)

        # Stage 2: Parallel Scouting (GitHub & Hacker News via MCP)
        notify("Scout Swarm: Harvesting Raw Signals via MCP")
        await self.scout_pool.execute(state)

        # Stage 3: Deduplication, Filtering & Scoring
        notify("Signal Analyst: Deduplicating & Scoring Novelty")
        await self.analyst.execute(state)

        # Human-in-the-Loop Steering Hook
        if interactive and on_human_selection and state.shortlisted_candidates:
            notify("Human-in-the-Loop: Awaiting User Candidate Selection")
            user_selected = on_human_selection(state.shortlisted_candidates)
            if hasattr(user_selected, "__await__"):
                user_selected = await user_selected
            if user_selected:
                state.shortlisted_candidates = user_selected
                state.log(f"Human operator narrowed candidates to {len(state.shortlisted_candidates)} items.")

        # Stage 4: Live Verification & Fact-Checking (Zero Hallucination Barrier)
        notify("Fact-Checker: Live Endpoint Auditing")
        await self.verifier.execute(state)

        # Stage 5: Synthesis & Persistence
        notify("Executive Editor: Synthesizing Briefing & Saving")
        await self.editor.execute(state)

        state.completed_at = datetime.now(timezone.utc).isoformat()
        state.log("Intelligence cycle successfully completed.")
        notify("Pipeline Complete")

        return state
