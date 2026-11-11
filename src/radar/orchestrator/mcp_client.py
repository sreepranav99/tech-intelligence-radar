import json
from typing import Dict, Any, List, Optional
from radar.mcp_server.server import mcp
from radar.orchestrator.external_mcp import ExternalMCPBridge

class RadarMCPClient:
    """Client adapter for interacting with internal and external MCP Servers."""

    def __init__(self):
        self.external_bridge = ExternalMCPBridge()

    @staticmethod
    def _parse_tool_result(result: Any) -> Any:
        """Extract JSON payload from MCP CallToolResult or raw response."""
        if hasattr(result, "content") and result.content:
            text = result.content[0].text
            try:
                return json.loads(text)
            except Exception:
                return text
        elif isinstance(result, str):
            try:
                return json.loads(result)
            except Exception:
                return result
        return result

    async def search_github(
        self,
        topic: str,
        days_back: int = 7,
        min_stars: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Call github_search_trending MCP tool."""
        res = await mcp.call_tool(
            "github_search_trending",
            {"topic": topic, "days_back": days_back, "min_stars": min_stars, "limit": limit}
        )
        parsed = self._parse_tool_result(res)
        if isinstance(parsed, dict):
            return parsed.get("items", [])
        return []

    async def verify_github_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Call github_verify_repo MCP tool to inspect live repo statistics."""
        res = await mcp.call_tool(
            "github_verify_repo",
            {"owner": owner, "repo": repo}
        )
        parsed = self._parse_tool_result(res)
        if isinstance(parsed, dict):
            return parsed.get("data", parsed)
        return {"exists": False, "error": "Invalid response"}

    async def search_hackernews(
        self,
        query: str,
        days_back: int = 7,
        min_points: int = 15,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Call hn_search_discussions MCP tool."""
        res = await mcp.call_tool(
            "hn_search_discussions",
            {"query": query, "days_back": days_back, "min_points": min_points, "limit": limit}
        )
        parsed = self._parse_tool_result(res)
        if isinstance(parsed, dict):
            return parsed.get("items", [])
        return []

    async def extract_web(self, url: str, max_chars: int = 6000) -> Dict[str, Any]:
        """Call web_extract_markdown MCP tool."""
        res = await mcp.call_tool(
            "web_extract_markdown",
            {"url": url, "max_chars": max_chars}
        )
        parsed = self._parse_tool_result(res)
        if isinstance(parsed, dict):
            return parsed.get("data", parsed)
        return {}

    async def search_arxiv(self, query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Call arxiv_search_papers MCP tool."""
        res = await mcp.call_tool(
            "arxiv_search_papers",
            {"query": query, "limit": limit}
        )
        parsed = self._parse_tool_result(res)
        if isinstance(parsed, dict):
            return parsed.get("items", [])
        return []

    async def search_reddit(self, query: str, subreddit: str = "LocalLLaMA", limit: int = 8) -> List[Dict[str, Any]]:
        """Call reddit_search_discussions MCP tool."""
        res = await mcp.call_tool(
            "reddit_search_discussions",
            {"query": query, "subreddit": subreddit, "limit": limit}
        )
        parsed = self._parse_tool_result(res)
        if isinstance(parsed, dict):
            return parsed.get("items", [])
        return []

    async def query_history(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Call db_query_history MCP tool to check for prior coverage."""
        res = await mcp.call_tool(
            "db_query_history",
            {"query": query, "limit": limit}
        )
        parsed = self._parse_tool_result(res)
        if isinstance(parsed, dict):
            return parsed.get("items", [])
        return []

    async def persist_intel(
        self,
        source_type: str,
        entity_name: str,
        source_url: str,
        category: str,
        novelty_score: float,
        velocity_score: float,
        summary: str,
        key_takeaways: str,
        verified_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call db_persist_intel MCP tool."""
        res = await mcp.call_tool(
            "db_persist_intel",
            {
                "source_type": source_type,
                "entity_name": entity_name,
                "source_url": source_url,
                "category": category,
                "novelty_score": novelty_score,
                "velocity_score": velocity_score,
                "summary": summary,
                "key_takeaways": key_takeaways,
                "verified_metrics": verified_metrics
            }
        )
        return self._parse_tool_result(res)

    async def save_briefing(
        self,
        run_id: str,
        topic_query: str,
        briefing_markdown: str,
        verified_items_count: int,
        sources_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call db_save_briefing MCP tool."""
        res = await mcp.call_tool(
            "db_save_briefing",
            {
                "run_id": run_id,
                "topic_query": topic_query,
                "briefing_markdown": briefing_markdown,
                "verified_items_count": verified_items_count,
                "sources_summary": sources_summary
            }
        )
        return self._parse_tool_result(res)

    async def get_velocity_delta(self, source_url: str) -> Dict[str, Any]:
        """Call db_get_velocity_delta MCP tool to check growth delta over time."""
        res = await mcp.call_tool(
            "db_get_velocity_delta",
            {"source_url": source_url}
        )
        parsed = self._parse_tool_result(res)
        if isinstance(parsed, dict):
            return parsed
        return {"has_history": False, "delta_stars": 0, "badge": "New"}

    async def list_external_servers(self) -> List[Dict[str, Any]]:
        """List third-party MCP servers configured in mcp_servers.json."""
        return await self.external_bridge.list_available_external_servers()

    async def call_external_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on an external third-party MCP server."""
        return await self.external_bridge.call_external_server_tool(server_name, tool_name, arguments)
