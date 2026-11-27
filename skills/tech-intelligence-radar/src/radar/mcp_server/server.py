import json
import asyncio
from typing import Dict, Any, List
from mcp.server.mcpserver import MCPServer

from radar.mcp_server.storage.db import (
    init_db,
    persist_intelligence_item,
    query_history,
    save_briefing,
    get_latest_briefing,
    get_all_tracked_entities,
    get_velocity_delta
)
from radar.mcp_server.tools.github import search_trending_repositories, get_repository_details
from radar.mcp_server.tools.hackernews import search_hackernews_discussions
from radar.mcp_server.tools.web import extract_web_markdown
from radar.mcp_server.tools.arxiv import search_arxiv_papers
from radar.mcp_server.tools.reddit import search_reddit_discussions

# Initialize MCP Server instance
mcp = MCPServer("radar-mcp", description="Autonomous Market & Tech Intelligence Radar Server")

@mcp.tool()
async def github_search_trending(
    topic: str,
    days_back: int = 7,
    min_stars: int = 30,
    limit: int = 10
) -> str:
    """Search for recently created or active repositories matching topic on GitHub."""
    result = await search_trending_repositories(topic, days_back, min_stars, limit)
    return json.dumps(result, indent=2)

@mcp.tool()
async def github_verify_repo(owner: str, repo: str) -> str:
    """Verify live status, stars, forks, and last commit date of a GitHub repository."""
    result = await get_repository_details(owner, repo)
    return json.dumps(result, indent=2)

@mcp.tool()
async def hn_search_discussions(
    query: str,
    days_back: int = 7,
    min_points: int = 15,
    limit: int = 15
) -> str:
    """Search Hacker News for community discussions, launches, and comments."""
    result = await search_hackernews_discussions(query, days_back, min_points, limit)
    return json.dumps(result, indent=2)

@mcp.tool()
async def web_extract_markdown(url: str, max_chars: int = 6000) -> str:
    """Fetch external web page, clean HTML, and return safe markdown with untrusted content wrapper."""
    result = await extract_web_markdown(url, max_chars)
    return json.dumps(result, indent=2)

@mcp.tool()
async def arxiv_search_papers(query: str, limit: int = 8) -> str:
    """Search arXiv for recent scientific and architectural research preprints."""
    result = await search_arxiv_papers(query, limit)
    return json.dumps(result, indent=2)

@mcp.tool()
async def reddit_search_discussions(query: str, subreddit: str = "LocalLLaMA", limit: int = 8) -> str:
    """Search developer communities on Reddit for discussions, benchmarks, and community sentiment."""
    result = await search_reddit_discussions(query, subreddit, limit)
    return json.dumps(result, indent=2)

@mcp.tool()
async def db_persist_intel(
    source_type: str,
    entity_name: str,
    source_url: str,
    category: str,
    novelty_score: float,
    velocity_score: float,
    summary: str,
    key_takeaways: str,
    verified_metrics: Dict[str, Any]
) -> str:
    """Persist a verified intelligence item to the local SQLite database."""
    item_id = await persist_intelligence_item(
        source_type=source_type,
        entity_name=entity_name,
        source_url=source_url,
        category=category,
        novelty_score=novelty_score,
        velocity_score=velocity_score,
        summary=summary,
        key_takeaways=key_takeaways,
        verified_metrics=verified_metrics
    )
    return json.dumps({"status": "persisted", "id": item_id})

@mcp.tool()
async def db_query_history(query: str, limit: int = 10) -> str:
    """Query past intelligence items to prevent duplicates and check for historical coverage."""
    items = await query_history(query, limit)
    return json.dumps({"count": len(items), "items": items}, indent=2)

@mcp.tool()
async def db_save_briefing(
    run_id: str,
    topic_query: str,
    briefing_markdown: str,
    verified_items_count: int,
    sources_summary: Dict[str, Any]
) -> str:
    """Save the final generated markdown briefing to database."""
    briefing_id = await save_briefing(
        run_id=run_id,
        topic_query=topic_query,
        briefing_markdown=briefing_markdown,
        verified_items_count=verified_items_count,
        sources_summary=sources_summary
    )
    return json.dumps({"status": "saved", "briefing_id": briefing_id})

@mcp.tool()
async def db_get_velocity_delta(source_url: str) -> str:
    """Calculate the velocity delta (growth change) between the two most recent metric snapshots."""
    delta_info = await get_velocity_delta(source_url)
    return json.dumps(delta_info, indent=2)

# MCP Resources
@mcp.resource("radar://briefings/latest")
async def get_latest_briefing_resource() -> str:
    """Expose the latest generated intelligence briefing."""
    briefing = await get_latest_briefing()
    if not briefing:
        return "# No Briefings Generated Yet\n\nRun the radar CLI to generate your first briefing."
    return briefing["briefing_markdown"]

@mcp.resource("radar://entities/tracked")
async def get_tracked_entities_resource() -> str:
    """Expose list of all tracked technologies and repositories."""
    entities = await get_all_tracked_entities()
    return json.dumps({"count": len(entities), "entities": entities}, indent=2)

# MCP Prompts
@mcp.prompt()
def fact_check_rubric(candidate_json: str) -> str:
    """Prompt template for auditing a technology candidate against live metrics."""
    return f"""You are the Fact-Checker & Verifier Agent.
Your objective is zero hallucinations.
Evaluate this candidate:
{candidate_json}

Strict Audit Checklist:
1. Verify repository exists and URL is live.
2. Verify stars and commit velocity are within 10% of claimed numbers.
3. Check if claimed architectural features are verified by docs.
4. If false or unverified, reject completely.
"""

@mcp.prompt()
def executive_brief_template(topic: str, verified_items_json: str) -> str:
    """Prompt template for writing the executive intelligence briefing."""
    return f"""Synthesize an actionable Executive Intelligence Briefing on '{topic}'.
Verified items:
{verified_items_json}

Include:
- 3 Key Executive Takeaways
- Deep Dives (Problem, Architecture, Why It Matters, Verified Stats)
- Tech Radar Classification (Adopt, Trial, Assess, Hold)
"""

def run_server():
    """Run the MCP server over standard I/O (stdio)."""
    asyncio.run(init_db())
    mcp.run()

def main():
    run_server()

if __name__ == "__main__":
    main()
