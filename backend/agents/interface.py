"""Agent interface contract — owned by Muse Spark, implemented by FreeBuff.

The Orchestrator talks ONLY through the AgentBackend protocol below.
FreeBuff's real Interactions-API backend (agents/base.py) must implement
the same async method signatures. Until then, orchestrator.py ships a
StubBackend with identical signatures so the API + SSE run end-to-end.

Rule: change a signature here ONLY with both AIs agreeing in AGENTS_SYNC.md.
"""
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class PlanStep:
    id: str
    agent: str  # LogAnalyzer | MetricsAgent | Diagnostician | Remediator
    description: str
    depends_on: list = field(default_factory=list)
    status: str = "PENDING"  # PENDING | IN_PROGRESS | COMPLETED | FAILED
    output_summary: str = ""


@dataclass
class AgentResult:
    ok: bool
    agent: str
    summary: str
    data: dict = field(default_factory=dict)
    error_code: Optional[str] = None
    error: Optional[str] = None
    interaction_id: Optional[str] = None


@dataclass
class PlanResult:
    steps: list  # list[PlanStep]
    reasoning: str
    version: int = 1
    interaction_id: Optional[str] = None


class AgentBackend(Protocol):
    """FreeBuff implements this with real Interactions API calls."""

    async def create_plan(self, alert: dict, context: str = "") -> PlanResult:
        ...

    async def analyze_logs(
        self, service: str, time_window_minutes: int = 30
    ) -> AgentResult:
        ...

    async def analyze_metrics(
        self, service: str, metrics: Optional[list] = None
    ) -> AgentResult:
        ...

    async def diagnose(
        self, log_findings: dict, metrics_findings: dict
    ) -> AgentResult:
        ...

    async def remediate(
        self, action_type: str, service: str, details: Optional[dict] = None
    ) -> AgentResult:
        ...

    async def verify(self, service: str, check_type: str = "HEALTH_CHECK") -> AgentResult:
        ...


def safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Walk nested dicts without KeyError — orchestrator uses this on all
    agent outputs (Risk 2: never trust raw LLM JSON shape)."""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur
