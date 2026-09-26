"""
AEGIS Agent: Diagnostician
Role: Correlate investigator findings into root cause + remediation proposal.
Capability: Multi-turn loop + Web Search — the model reasons iteratively across findings,
            then uses Google Search to look up known error signatures and validate the
            root cause hypothesis against real-world knowledge before proposing a fix.
Tools: correlate_findings, web_search, propose_diagnosis
"""

# This agent runs in MULTI-TURN + WEB_SEARCH mode by default.
# Switch to fast single-shot for P3/minor incidents:
#   import agents.diagnostician as diag_agent
#   diag_agent.THINKING_MODE = (severity in ("P1", "P2"))
CAPABILITY = "multi_turn_web_search"

# ─── Mode Switch ──────────────────────────────────────────────────────────────
# THINKING_MODE = True  → multi-turn loop + mandatory web search (P1/P2)
# THINKING_MODE = False → single-shot: correlate → diagnose, no web search (P3)
THINKING_MODE: bool = True


def get_prompt() -> str:
    """Return the correct system prompt based on current THINKING_MODE."""
    return SYSTEM_PROMPT_THINKING if THINKING_MODE else SYSTEM_PROMPT_FAST


# ─── Fast prompt (single-shot, no web search) ──────────────────────────────
# For P3/minor incidents. Two tool calls, one response.
SYSTEM_PROMPT_FAST = """You are the AEGIS Diagnostic Specialist. Correlate findings and diagnose in a single response.

Steps (do both in one turn):
1. Use correlate_findings with log_findings and metrics_findings
2. Use propose_diagnosis with your root cause and recommended action

CONFIDENCE RULES:
- BOTH data sources available → confidence 0.85-0.95
- Log data MISSING → confidence 0.50-0.70
- Only one source AND inconclusive → confidence < 0.50 → recommended_action = "escalate"

You MUST call correlate_findings then propose_diagnosis. Do not respond with plain text."""

# ─── Thinking prompt (multi-turn + web search) ─────────────────────────────
# For P1/P2 incidents. Iterates across turns and validates via Google Search.
SYSTEM_PROMPT_THINKING = """You are the AEGIS Diagnostic Specialist. You correlate findings from multiple investigation agents and use web search to validate your root cause hypothesis before proposing a fix.

Your workflow (multi-turn):

Turn 1 — Correlate:
  Use the correlate_findings tool, passing both log_findings and metrics_findings.
  If log_findings is missing or has status "error": note this — you have partial data only.

Turn 2 — Search (ALWAYS do this):
  Use web_search to look up the most specific error signature from the log findings.
  Example searches:
  - "OutOfMemoryError Java heap space api-gateway cause rollback"
  - "circuit breaker OPEN memory leak JVM 2024"
  - "kubernetes deployment memory leak signature monotonic increase"
  This grounds your diagnosis in real-world knowledge, not just the data you were given.

Turn 3 — Diagnose:
  Use propose_diagnosis with your final structured root cause, informed by both the correlation
  AND the web search results.

CONFIDENCE CALIBRATION RULES (strictly enforced):
  - BOTH log + metric data available + web search confirms pattern → confidence 0.85-0.95
  - Log data MISSING but metric data available → confidence 0.50-0.70
  - Only one data source AND web search inconclusive → confidence < 0.50 → recommended_action = "escalate"
  - NEVER inflate confidence when working with partial data
  - NEVER skip web search — it is mandatory for every diagnosis

You MUST use correlate_findings → web_search → propose_diagnosis in that order."""

# Legacy alias so any code referencing SYSTEM_PROMPT still works
SYSTEM_PROMPT = SYSTEM_PROMPT_THINKING


TOOLS = [
    {
        "name": "correlate_findings",
        "description": "Correlate log and metric findings into joint evidence set",
        "parameters": {
            "type": "object",
            "properties": {
                "log_findings": {"type": "object", "description": "Output from LogAnalyzer (may be None if failed)"},
                "metrics_findings": {"type": "object", "description": "Output from MetricsAgent"},
            },
            "required": ["metrics_findings"],
        },
    },
    {
        "name": "web_search",
        "description": "Google Search to look up real-world knowledge about the error signature",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — use specific error messages + technology + 'root cause' or 'fix'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "propose_diagnosis",
        "description": "Propose the root cause and recommended remediation action",
        "parameters": {
            "type": "object",
            "properties": {
                "root_cause": {"type": "string", "description": "Specific, evidence-backed root cause statement"},
                "confidence": {"type": "number", "description": "0.0-1.0, calibrated per the rules above"},
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of supporting facts from logs, metrics, AND web search",
                },
                "web_search_summary": {
                    "type": "string",
                    "description": "What web search revealed about this error pattern",
                },
                "recommended_action": {
                    "type": "string",
                    "enum": ["rollback", "restart", "scale_up", "config_change", "escalate"],
                },
                "action_details": {"type": "object"},
            },
            "required": ["root_cause", "confidence", "evidence", "recommended_action"],
        },
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "diagnosis": {"type": "object"},
    },
    "required": ["status"],
}

DEFAULT_FALLBACK = {
    "status": "completed",
    "diagnosis": {
        "root_cause": "Unknown — agent output unparseable",
        "confidence": 0.0,
        "evidence": [],
        "web_search_summary": "Not available",
        "recommended_action": "escalate",
        "action_details": {},
    },
}

AGENT_NAME = "Diagnostician"
