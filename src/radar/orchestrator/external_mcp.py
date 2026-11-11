import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from radar.config import PROJECT_ROOT

CONFIG_PATH = PROJECT_ROOT / "mcp_servers.json"

DEFAULT_SAMPLE_CONFIG = {
    "mcpServers": {
        "example_filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
            "description": "Example: Connect to local filesystem MCP server",
            "enabled": False
        }
    }
}

class ExternalMCPBridge:
    """Discovers, connects to, and invokes tools from external third-party MCP servers."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self._ensure_config()

    def _ensure_config(self) -> None:
        """Create sample config if not exists."""
        if not self.config_path.exists():
            try:
                self.config_path.write_text(json.dumps(DEFAULT_SAMPLE_CONFIG, indent=2), encoding="utf-8")
            except Exception:
                pass

    def load_config(self) -> Dict[str, Any]:
        """Load external MCP server configurations."""
        if not self.config_path.exists():
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8")).get("mcpServers", {})
        except Exception:
            return {}

    def _resolve_server_params(self, name: str, cfg: Dict[str, Any]) -> Tuple[Optional[StdioServerParameters], Optional[str]]:
        """Validate command availability cross-platform and build stdio server parameters."""
        cmd = cfg.get("command") or ""
        args = cfg.get("args", [])

        if cmd and not Path(cmd).exists() and shutil.which(cmd) is None:
            if "python" in cmd.lower() and name == "external_fetch":
                cmd = sys.executable
            else:
                return None, f"Executable '{cmd}' for external MCP server '{name}' not found on this host"

        if "mcp_server_fetch" in args and importlib.util.find_spec("mcp_server_fetch") is None:
            return None, "Optional Python module 'mcp_server_fetch' is not installed on this host"

        return StdioServerParameters(command=cmd, args=args, env=cfg.get("env")), None

    async def list_available_external_servers(self) -> List[Dict[str, Any]]:
        """List configured external servers and their status."""
        servers = self.load_config()
        results = []
        for name, cfg in servers.items():
            results.append({
                "name": name,
                "command": cfg.get("command"),
                "args": cfg.get("args", []),
                "enabled": cfg.get("enabled", True),
                "description": cfg.get("description", "External MCP Server")
            })
        return results

    async def list_all_external_tools(self) -> List[Dict[str, Any]]:
        """Connect to each enabled external MCP server and list all their exposed tools."""
        servers = self.load_config()
        all_tools = []
        for name, cfg in servers.items():
            if not cfg.get("enabled", True):
                continue
            server_params, err = self._resolve_server_params(name, cfg)
            if err or not server_params:
                all_tools.append({
                    "server": name,
                    "name": "[Unavailable]",
                    "description": err or "Unavailable"
                })
                continue
            try:
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()
                        for t in tools_result.tools:
                            all_tools.append({
                                "server": name,
                                "name": t.name,
                                "description": t.description or "No description provided"
                            })
            except Exception as e:
                all_tools.append({
                    "server": name,
                    "name": "[Connection Error]",
                    "description": str(e)
                })
        return all_tools

    async def call_external_server_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Connect to an external MCP server via stdio, call the tool, and return the result."""
        servers = self.load_config()
        if server_name not in servers:
            return {"error": f"Server '{server_name}' not configured in mcp_servers.json"}

        cfg = servers[server_name]
        if not cfg.get("enabled", True):
            return {"error": f"Server '{server_name}' is disabled in configuration"}

        server_params, err = self._resolve_server_params(server_name, cfg)
        if err or not server_params:
            return {"error": err or f"Unable to resolve '{server_name}'"}

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tool_res = await session.call_tool(tool_name, arguments)
                    if hasattr(tool_res, "content") and tool_res.content:
                        return tool_res.content[0].text
                    return tool_res
        except Exception as e:
            return {"error": f"Failed calling external MCP server '{server_name}': {str(e)}"}
