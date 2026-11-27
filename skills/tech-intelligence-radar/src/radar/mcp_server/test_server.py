import sys
from pathlib import Path

# Ensure 'src' is on sys.path
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import asyncio
import json
from radar.mcp_server.storage.db import init_db
from radar.mcp_server.server import mcp

async def test_mcp_components():
    print("1. Initializing Database...")
    await init_db()
    print("Database initialized successfully.")

    print("\n2. Testing registered MCP Tools...")
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    print(f"Registered Tools ({len(tool_names)}):", tool_names)
    assert "github_search_trending" in tool_names
    assert "hn_search_discussions" in tool_names
    assert "web_extract_markdown" in tool_names
    assert "db_persist_intel" in tool_names
    assert "db_query_history" in tool_names

    print("\n3. Testing registered MCP Resources...")
    resources = await mcp.list_resources()
    resource_uris = [str(r.uri) for r in resources]
    print(f"Registered Resources ({len(resource_uris)}):", resource_uris)

    print("\n4. Testing Hacker News search tool...")
    hn_res = await mcp.call_tool("hn_search_discussions", {"query": "model context protocol", "days_back": 180, "limit": 3})
    # FastMCP/MCPServer returns CallToolResult or content list
    print("HN Tool Call Result preview:")
    if hasattr(hn_res, "content"):
        content_text = hn_res.content[0].text if hn_res.content else ""
        parsed = json.loads(content_text)
        print(f"  Found {len(parsed.get('items', []))} items. First title: {parsed.get('items', [{}])[0].get('title', 'N/A')}")
    else:
        print("  Raw result:", hn_res)

    print("\n5. Testing DB Persist & Query History tool...")
    sample_persist = await mcp.call_tool(
        "db_persist_intel",
        {
            "source_type": "github",
            "entity_name": "modelcontextprotocol/servers",
            "source_url": "https://github.com/modelcontextprotocol/servers",
            "category": "Tools",
            "novelty_score": 9.5,
            "velocity_score": 9.0,
            "summary": "Official reference MCP servers repository.",
            "key_takeaways": "Covers filesystem, sqlite, github, memory, and postgres integrations.",
            "verified_metrics": {"stars": 12500, "forks": 1100}
        }
    )
    print("Persist result:", sample_persist)

    history_res = await mcp.call_tool("db_query_history", {"query": "modelcontextprotocol", "limit": 5})
    print("Query History result:")
    if hasattr(history_res, "content"):
        print(history_res.content[0].text)
    else:
        print(history_res)

    print("\nALL MCP COMPONENT TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_mcp_components())
