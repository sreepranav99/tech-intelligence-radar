from abc import ABC, abstractmethod
from radar.orchestrator.state import RadarState
from radar.orchestrator.mcp_client import RadarMCPClient

class BaseAgent(ABC):
    """Abstract Base Class for Multi-Agent Swarm participants."""

    def __init__(self, name: str, role: str, mcp_client: RadarMCPClient):
        self.name = name
        self.role = role
        self.mcp = mcp_client

    @abstractmethod
    async def execute(self, state: RadarState) -> None:
        """Execute agent-specific logic and update the shared RadarState."""
        pass
