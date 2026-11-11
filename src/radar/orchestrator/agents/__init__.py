"""Agents module."""
from radar.orchestrator.agents.base import BaseAgent
from radar.orchestrator.agents.coordinator import CoordinatorAgent
from radar.orchestrator.agents.scouts import (
    GitHubScoutAgent,
    HackerNewsScoutAgent,
    ArxivScoutAgent,
    RedditScoutAgent,
    ScoutPool
)
from radar.orchestrator.agents.analyst import SignalAnalystAgent
from radar.orchestrator.agents.verifier import FactCheckerAgent
from radar.orchestrator.agents.editor import ExecutiveEditorAgent

__all__ = [
    "BaseAgent",
    "CoordinatorAgent",
    "GitHubScoutAgent",
    "HackerNewsScoutAgent",
    "ArxivScoutAgent",
    "RedditScoutAgent",
    "ScoutPool",
    "SignalAnalystAgent",
    "FactCheckerAgent",
    "ExecutiveEditorAgent"
]
