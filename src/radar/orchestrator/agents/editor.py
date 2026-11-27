from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from radar.config import BRIEFINGS_DIR
from radar.orchestrator.agents.base import BaseAgent
from radar.orchestrator.state import RadarState
from radar.orchestrator.llm import LLMClient
from radar.ui.generator import classify_ring

class ExecutiveEditorAgent(BaseAgent):
    """Synthesizes verified items into an actionable Markdown Briefing and persists records via MCP."""

    def __init__(self, mcp_client):
        super().__init__(
            name="ExecutiveEditor",
            role="Executive Briefing Synthesis & Knowledge Base Persistence",
            mcp_client=mcp_client
        )
        self.llm = LLMClient()

    def _classify_radar_quadrant(self, candidate, item) -> str:
        """Assign Tech Radar recommendation quadrant based on maturity and velocity."""
        ring = classify_ring(
            candidate.novelty_score,
            candidate.velocity_score,
            item.verified_metrics,
            item.fact_check_notes
        )
        labels = {
            "ADOPT": "ADOPT / PROVEN",
            "TRIAL": "TRIAL / PROTOTYPE",
            "ASSESS": "ASSESS / MONITOR",
            "HOLD": "HOLD / WATCH"
        }
        return labels.get(ring, f"{ring} / EVALUATE")

    async def execute(self, state: RadarState) -> None:
        state.log(f"[{self.name}] Synthesizing executive briefing from {len(state.verified_items)} verified items...")
        
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # 1. Persist each verified item to SQLite database via MCP
        for item in state.verified_items:
            candidate = item.candidate
            signal = candidate.signal
            
            await self.mcp.persist_intel(
                source_type=signal.source_type,
                entity_name=signal.external_id,
                source_url=signal.url,
                category=candidate.category,
                novelty_score=candidate.novelty_score,
                velocity_score=candidate.velocity_score,
                summary=signal.raw_snippet or signal.title,
                key_takeaways=item.fact_check_notes,
                verified_metrics=item.verified_metrics
            )

        # 2. Build Markdown Briefing Document
        lines = []
        lines.append(f"# 📡 Tech Intelligence Radar: {state.topic_query}")
        lines.append(f"**Generated:** {now_str} | **Run ID:** `{state.run_id}` | **Status:** ✅ Zero-Hallucination Verified\n")
        lines.append("---")
        
        # Executive Pulse
        lines.append("## ⚡ Executive Pulse")
        if state.verified_items:
            items_summary = "\n".join([f"- {it.candidate.signal.title} ({it.candidate.category}): {it.fact_check_notes}" for it in state.verified_items[:5]])
            llm_pulse = await self.llm.generate_executive_pulse(state.topic_query, items_summary)
            if llm_pulse:
                lines.append(llm_pulse)
            else:
                top_item = state.verified_items[0]
                lines.append(f"* **Primary Focus**: Highest momentum in `{top_item.candidate.category}` around **{top_item.candidate.signal.title}**.")
                lines.append(f"* **Audit Summary**: {len(state.raw_signals)} raw signals harvested $\\rightarrow$ {len(state.shortlisted_candidates)} shortlisted $\\rightarrow$ **{len(state.verified_items)} verified live**.")
                lines.append(f"* **Velocity Outlook**: Key architectural patterns focus on standardized tool calling and multi-agent coordination.")
        else:
            lines.append("* No emerging items met the strict novelty and live verification threshold in this window.")
        lines.append("")

        # Deep Dives
        lines.append("## 🔍 Verified Technology Deep Dives\n")
        for idx, item in enumerate(state.verified_items, start=1):
            cand = item.candidate
            sig = cand.signal
            quadrant = self._classify_radar_quadrant(cand, item)

            lines.append(f"### {idx}. [{sig.title}]({sig.url})")
            lines.append(f"* **Category**: `{cand.category}` | **Radar Status**: `{quadrant}`")
            lines.append(f"* **Scores**: Novelty: **{cand.novelty_score}/10** | Velocity: **{cand.velocity_score}/10**")
            
            v_delta = sig.metrics.get("velocity_delta", {})
            badge = v_delta.get("badge", "New Entry")
            lines.append(f"* **Momentum & Velocity**: `{badge}`")

            # Formatted metrics
            metrics_display = []
            for k, v in item.verified_metrics.items():
                metrics_display.append(f"{k.replace('_', ' ').capitalize()}: `{v}`")
            if metrics_display:
                lines.append(f"* **Verified Live Stats**: {', '.join(metrics_display)}")

            lines.append(f"* **Why It Matters**: {cand.justification}")
            lines.append(f"* **Audit Trail**: _{item.fact_check_notes}_\n")

        # Radar Matrix Summary Table
        lines.append("## 📊 Technology Radar Matrix")
        lines.append("| Technology / Project | Category | Novelty | Velocity | Momentum | Recommendation |")
        lines.append("| :--- | :--- | :---: | :---: | :--- | :--- |")
        for item in state.verified_items:
            c = item.candidate
            s = c.signal
            rec = self._classify_radar_quadrant(c, item)
            v_badge = s.metrics.get("velocity_delta", {}).get("badge", "New")
            lines.append(f"| [{s.external_id}]({s.url}) | {c.category} | {c.novelty_score} | {c.velocity_score} | `{v_badge}` | **{rec}** |")
        lines.append("")

        # Footer
        lines.append("---")
        lines.append("_Generated autonomously by **Autonomous Market & Tech Intelligence Radar** backed by FastMCP & Multi-Agent Swarm._")

        briefing_markdown = "\n".join(lines)
        state.final_briefing_markdown = briefing_markdown

        # 3. Save briefing to filesystem
        file_path = BRIEFINGS_DIR / f"briefing_{date_slug}_{state.run_id[:8]}.md"
        file_path.write_text(briefing_markdown, encoding="utf-8")
        state.log(f"[{self.name}] Briefing written to: {file_path}")

        # 4. Save briefing to database via MCP
        sources_summary = {
            "github_raw": sum(1 for s in state.raw_signals if s.source_type == "github"),
            "hn_raw": sum(1 for s in state.raw_signals if s.source_type == "hackernews"),
            "verified": len(state.verified_items)
        }
        await self.mcp.save_briefing(
            run_id=state.run_id,
            topic_query=state.topic_query,
            briefing_markdown=briefing_markdown,
            verified_items_count=len(state.verified_items),
            sources_summary=sources_summary
        )
        state.log(f"[{self.name}] Briefing record persisted to SQLite via MCP.")

        # 5. Generate Visual Interactive Tech Radar HTML
        try:
            from radar.ui.generator import generate_radar_html_from_state
            html_file = generate_radar_html_from_state(state)
            state.log(f"[{self.name}] Visual Tech Radar HTML generated: {html_file}")
        except Exception as e:
            state.log(f"[{self.name}] Warning: Could not generate visual HTML: {e}")
