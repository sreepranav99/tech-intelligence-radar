"""MCP Tools module."""
from radar.mcp_server.tools.github import search_trending_repositories, get_repository_details
from radar.mcp_server.tools.hackernews import search_hackernews_discussions
from radar.mcp_server.tools.web import extract_web_markdown
from radar.mcp_server.tools.arxiv import search_arxiv_papers
from radar.mcp_server.tools.reddit import search_reddit_discussions

__all__ = [
    "search_trending_repositories",
    "get_repository_details",
    "search_hackernews_discussions",
    "extract_web_markdown",
    "search_arxiv_papers",
    "search_reddit_discussions"
]
