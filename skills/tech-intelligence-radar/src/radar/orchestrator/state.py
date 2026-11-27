from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class RawSignal(BaseModel):
    """Raw data gathered by scout agents from external sources."""
    source_type: str                  # 'github', 'hackernews', 'web'
    external_id: str                  # repo full_name, story id, or url
    title: str
    url: str
    raw_snippet: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    detected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ScoredCandidate(BaseModel):
    """Signal filtered, deduplicated, and scored by the Analyst Agent."""
    signal: RawSignal
    category: str                     # 'Framework', 'Tool', 'Architecture', 'Paper'
    novelty_score: float              # 1.0 to 10.0
    velocity_score: float             # 1.0 to 10.0
    is_duplicate: bool = False
    justification: str

class VerifiedIntel(BaseModel):
    """Item verified by the Fact-Checker agent to ensure zero hallucinations."""
    candidate: ScoredCandidate
    is_verified: bool
    live_verification_timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verified_metrics: Dict[str, Any]
    fact_check_notes: str

class RadarState(BaseModel):
    """Typed shared blackboard state passed across the multi-agent pipeline."""
    run_id: str
    topic_query: str
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    
    # State transitions
    raw_signals: List[RawSignal] = Field(default_factory=list)
    shortlisted_candidates: List[ScoredCandidate] = Field(default_factory=list)
    verified_items: List[VerifiedIntel] = Field(default_factory=list)
    
    # Final outputs
    final_briefing_markdown: Optional[str] = None
    execution_logs: List[str] = Field(default_factory=list)

    def log(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self.execution_logs.append(f"[{timestamp}] {message}")
