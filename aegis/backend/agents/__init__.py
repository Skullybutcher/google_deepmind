"""AEGIS agent exports (Person B)."""
from . import diagnostician as _diag_module
from . import planner as _planner_module
from .diagnostician import AGENT_NAME as DIAGNOSTICIAN_NAME
from .diagnostician import DEFAULT_FALLBACK as DIAGNOSTICIAN_FALLBACK
from .diagnostician import OUTPUT_SCHEMA as DIAGNOSTICIAN_SCHEMA
from .diagnostician import SYSTEM_PROMPT as DIAGNOSTICIAN_PROMPT
from .diagnostician import TOOLS as DIAGNOSTICIAN_TOOLS
from .log_analyzer import AGENT_NAME as LOG_ANALYZER_NAME
from .log_analyzer import DEFAULT_FALLBACK as LOG_ANALYZER_FALLBACK
from .log_analyzer import OUTPUT_SCHEMA as LOG_ANALYZER_SCHEMA
from .log_analyzer import SYSTEM_PROMPT as LOG_ANALYZER_PROMPT
from .log_analyzer import TOOLS as LOG_ANALYZER_TOOLS
from .metrics_agent import AGENT_NAME as METRICS_NAME
from .metrics_agent import DEFAULT_FALLBACK as METRICS_FALLBACK
from .metrics_agent import OUTPUT_SCHEMA as METRICS_SCHEMA
from .metrics_agent import SYSTEM_PROMPT as METRICS_PROMPT
from .metrics_agent import TOOLS as METRICS_TOOLS
from .planner import AGENT_NAME as PLANNER_NAME
from .planner import DEFAULT_FALLBACK as PLANNER_FALLBACK
from .planner import OUTPUT_SCHEMA as PLANNER_SCHEMA
from .planner import SYSTEM_PROMPT as PLANNER_PROMPT
from .planner import TOOLS as PLANNER_TOOLS
from .remediator import AGENT_NAME as REMEDIATOR_NAME
from .remediator import DEFAULT_FALLBACK as REMEDIATOR_FALLBACK
from .remediator import OUTPUT_SCHEMA as REMEDIATOR_SCHEMA
from .remediator import SYSTEM_PROMPT as REMEDIATOR_PROMPT
from .remediator import TOOLS as REMEDIATOR_TOOLS


# ─── Thinking-mode switch ─────────────────────────────────────────────────────
# Severity map used by the orchestrator to auto-switch modes:
#   P1/P2 (critical/high) → THINKING_MODE = True  (multi-turn loop + web search)
#   P3/P4 (minor/info)    → THINKING_MODE = False (single-shot, faster)
#
# Usage in orchestrator.py:
#   from agents import set_thinking_mode
#   set_thinking_mode(severity=state.alert.get("severity", "P1"))
#
# Or override manually for testing:
#   set_thinking_mode(force=False)  # always fast
#   set_thinking_mode(force=True)   # always thinking

_THINKING_SEVERITIES = {"P1", "P2"}


def set_thinking_mode(severity: str | None = None, force: bool | None = None) -> dict[str, bool]:
    """
    Set THINKING_MODE on Planner and Diagnostician based on incident severity.

    Args:
        severity: Alert severity string ("P1", "P2", "P3", "P4").
                  P1/P2 → thinking=True, P3/P4 → thinking=False.
        force:    If provided, overrides severity and sets both agents explicitly.

    Returns:
        Dict of {"Planner": bool, "Diagnostician": bool} showing the mode set.
    """
    if force is not None:
        thinking = force
    elif severity is not None:
        thinking = severity.upper() in _THINKING_SEVERITIES
    else:
        thinking = True  # default to thinking mode if no info

    _planner_module.THINKING_MODE = thinking
    _diag_module.THINKING_MODE = thinking

    return {"Planner": thinking, "Diagnostician": thinking}


def get_prompt(agent_name: str) -> str:
    """
    Get the active system prompt for a given agent, respecting THINKING_MODE.

    Args:
        agent_name: "Planner" or "Diagnostician" (others always return SYSTEM_PROMPT)

    Returns:
        The correct system prompt string for the current mode.
    """
    if agent_name == "Planner":
        return _planner_module.get_prompt()
    if agent_name == "Diagnostician":
        return _diag_module.get_prompt()
    # Code-execution agents (LogAnalyzer, MetricsAgent, Remediator) don't have thinking modes
    from .log_analyzer import SYSTEM_PROMPT as LA_PROMPT
    from .metrics_agent import SYSTEM_PROMPT as MA_PROMPT
    from .remediator import SYSTEM_PROMPT as R_PROMPT
    return {"LogAnalyzer": LA_PROMPT, "MetricsAgent": MA_PROMPT, "Remediator": R_PROMPT}.get(agent_name, "")


__all__ = [
    # Agent names
    "PLANNER_NAME", "LOG_ANALYZER_NAME", "METRICS_NAME", "DIAGNOSTICIAN_NAME", "REMEDIATOR_NAME",
    # Prompts (active-mode aliases — use get_prompt() for mode-aware access)
    "PLANNER_PROMPT", "LOG_ANALYZER_PROMPT", "METRICS_PROMPT", "DIAGNOSTICIAN_PROMPT", "REMEDIATOR_PROMPT",
    # Tools
    "PLANNER_TOOLS", "LOG_ANALYZER_TOOLS", "METRICS_TOOLS", "DIAGNOSTICIAN_TOOLS", "REMEDIATOR_TOOLS",
    # Schemas
    "PLANNER_SCHEMA", "LOG_ANALYZER_SCHEMA", "METRICS_SCHEMA", "DIAGNOSTICIAN_SCHEMA", "REMEDIATOR_SCHEMA",
    # Fallbacks
    "PLANNER_FALLBACK", "LOG_ANALYZER_FALLBACK", "METRICS_FALLBACK", "DIAGNOSTICIAN_FALLBACK", "REMEDIATOR_FALLBACK",
    # Mode switch helpers
    "set_thinking_mode", "get_prompt",
]
