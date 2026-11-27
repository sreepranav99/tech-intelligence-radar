import asyncio
import html
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from rich.console import Console
from rich.panel import Panel

from radar.config import (
    CORE_TOPICS,
    INCLUDE_TRENDING_AI,
    BRIEFING_RECIPIENT,
    GMAIL_USER,
    BRIEFING_ITEMS_LIMIT,
    DATA_DIR,
)
from radar.mcp_server.storage.db import init_db
from radar.orchestrator.agents.analyst import _clean_truncate
from radar.orchestrator.engine import RadarEngine
from radar.ui.generator import generate_radar_html_from_state, classify_ring
from radar.orchestrator.notifier import send_briefing_email, format_morning_briefing_html, is_smtp_configured

console = Console()
LOG_PATH = DATA_DIR / "morning_scheduler.log"

def _log_file(message: str) -> None:
    """Append timestamped execution trace to data/morning_scheduler.log."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {message}\n")
    except Exception:
        pass

def _build_morning_plan() -> Dict[str, List[str]]:
    """Build combined Watchlist (Option 3) + Trending AI Discovery (Option 2) search plan."""
    github_queries = list(CORE_TOPICS)
    hn_queries: List[str] = []
    arxiv_queries: List[str] = []
    reddit_queries: List[str] = []

    # Map verbose core topics into crisp platform-specific queries
    for topic in CORE_TOPICS:
        low = topic.lower()
        if "model context protocol" in low:
            hn_queries.append("MCP")
            arxiv_queries.append("Model Context Protocol LLM")
            reddit_queries.append("MCP")
        elif "ai agent" in low:
            hn_queries.append("AI agent")
            arxiv_queries.append("AI Agents")
            reddit_queries.append("AI agent")
        else:
            hn_queries.append(topic)
            arxiv_queries.append(topic)
            reddit_queries.append(topic)

    if INCLUDE_TRENDING_AI:
        # Broad ecosystem discovery queries without triggering unauthenticated GitHub rate limits
        for q in ["llm", "mcp server"]:
            if q.lower() not in [x.lower() for x in github_queries]:
                github_queries.append(q)
        for q in ["LLM", "AI agent", "MCP"]:
            if q.lower() not in [x.lower() for x in hn_queries]:
                hn_queries.append(q)
            if q.lower() not in [x.lower() for x in reddit_queries]:
                reddit_queries.append(q)
        for q in ["autonomous LLM agents", "local llm inference"]:
            if q.lower() not in [x.lower() for x in arxiv_queries]:
                arxiv_queries.append(q)

    primary_topics = list(dict.fromkeys(CORE_TOPICS + ["large language model agents", "local llm inference"]))

    return {
        "primary_topics": primary_topics,
        "github_queries": github_queries[:4],
        "hn_queries": list(dict.fromkeys(hn_queries))[:4],
        "arxiv_queries": list(dict.fromkeys(arxiv_queries))[:3],
        "reddit_queries": list(dict.fromkeys(reddit_queries))[:3],
    }

async def run_morning_cycle(send_email: bool = True) -> Dict[str, Any]:
    """Execute the combined morning intelligence cycle across Core Topics and Trending AI."""
    _log_file("=== Starting Morning AI Intelligence Cycle ===")

    console.print(Panel(
        "🌅 [bold cyan]Starting Daily Morning AI Intelligence Cycle[/bold cyan]\n"
        f"🎯 Core Watchlist: [bold green]{', '.join(CORE_TOPICS)}[/bold green]\n"
        f"⚡ Trending AI Discovery: [bold green]{'Enabled' if INCLUDE_TRENDING_AI else 'Disabled'}[/bold green]\n"
        f"✉️ Recipient: [bold yellow]{BRIEFING_RECIPIENT or GMAIL_USER or 'Not Configured'}[/bold yellow]",
        border_style="cyan"
    ))

    try:
        await init_db()
        engine = RadarEngine()

        combined_topic = f"{', '.join(CORE_TOPICS)} & Trending AI"
        initial_plan = _build_morning_plan()
        _log_file(f"Search plan: GitHub={initial_plan['github_queries']}, HN={initial_plan['hn_queries']}")

        console.print("\n[dim]Launching Multi-Agent Swarm across GitHub, Hacker News, arXiv, and Reddit...[/dim]")
        
        def on_step(step_name: str, state):
            console.print(f"  [cyan]›[/cyan] {step_name}")

        state = await engine.run(topic=combined_topic, on_step=on_step, initial_plan=initial_plan)

        # Regenerate local visual radar file
        latest_html_path = generate_radar_html_from_state(state)
        console.print(f"\n[green]✓[/green] Updated Interactive Visual Radar: [cyan]{latest_html_path}[/cyan]")

        # Extract verified items for email format
        verified_payload = []
        for item in state.verified_items:
            cand = item.candidate
            sig = cand.signal
            verified_payload.append({
                "title": sig.title,
                "url": sig.url,
                "category": cand.category,
                "ring": classify_ring(cand.novelty_score, cand.velocity_score, item.verified_metrics, item.fact_check_notes),
                "novelty_score": cand.novelty_score,
                "velocity_score": cand.velocity_score,
                "summary": _clean_truncate(sig.raw_snippet or cand.justification, max_len=320),
                "verified_metrics": item.verified_metrics,
                "velocity_delta": sig.metrics.get("velocity_delta", {}),
                "justification": cand.justification,
                "fact_check_notes": item.fact_check_notes
            })

        # Limit to configured number of top verified items (e.g. 8)
        verified_payload = verified_payload[:BRIEFING_ITEMS_LIMIT]
        _log_file(f"Pipeline finished: {len(state.raw_signals)} raw signals -> {len(state.verified_items)} verified -> {len(verified_payload)} selected for email.")

        # Build clean human-readable executive summary (no raw markdown tokens)
        safe_topics = html.escape(", ".join(CORE_TOPICS))
        if verified_payload:
            top_title = html.escape(verified_payload[0]["title"])
            top_cat = html.escape(verified_payload[0]["category"])
            executive_summary = (
                f"Over the last cycle, your autonomous swarm scouted {len(state.raw_signals)} live signals across "
                f"GitHub, Hacker News, arXiv, and Reddit covering {safe_topics} and breakout AI repositories. "
                f"{len(state.verified_items)} projects passed strict zero-hallucination endpoint verification. "
                f"Top momentum today is led by <strong>{top_title}</strong> ({top_cat})."
            )
        else:
            executive_summary = (
                f"Your autonomous swarm scouted {len(state.raw_signals)} signals across {safe_topics}, "
                "but no candidates cleared the strict live verification barrier in this window."
            )

        email_status = {"sent": False, "message": "Email sending skipped."}

        if send_email:
            if not is_smtp_configured():
                console.print("\n[yellow]⚠️ Gmail SMTP credentials not configured in .env. Skipping email dispatch.[/yellow]")
                console.print("[dim]Edit .env with your GMAIL_USER and GMAIL_APP_PASSWORD, then run 'radar test-email'.[/dim]")
                email_status = {"sent": False, "error": "SMTP not configured"}
                _log_file("Email skipped: SMTP not configured in .env.")
            else:
                console.print("\n[bold yellow]✉️ Generating and dispatching morning email briefing...[/bold yellow]")
                subject = f"📡 Daily AI Radar: {len(verified_payload)} Verified Breakthroughs ({datetime.now().strftime('%d %b')})"
                html_body = format_morning_briefing_html(
                    topic="AI Agents, MCP & Trending AI",
                    verified_items=verified_payload,
                    executive_summary=executive_summary,
                    run_id=state.run_id[:8]
                )
                result = send_briefing_email(subject=subject, html_body=html_body)
                if result.get("success"):
                    console.print(f"[bold green]✓ Morning Briefing Email successfully delivered to {result.get('recipient')}![/bold green]")
                    email_status = {"sent": True, "recipient": result.get("recipient")}
                    _log_file(f"SUCCESS: Email sent to {result.get('recipient')}.")
                else:
                    console.print(f"[bold red]✗ Failed to send email: {result.get('error')}[/bold red]")
                    email_status = {"sent": False, "error": result.get("error")}
                    _log_file(f"ERROR sending email: {result.get('error')}")

        return {
            "run_id": state.run_id,
            "items_count": len(verified_payload),
            "email_status": email_status
        }

    except Exception as e:
        import traceback
        err_trace = traceback.format_exc()
        _log_file(f"FATAL EXCEPTION in morning cycle: {str(e)}\n{err_trace}")
        console.print(f"[bold red]✗ Morning cycle failed: {str(e)}[/bold red]")
        raise
