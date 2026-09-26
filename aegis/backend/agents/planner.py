"""
AEGIS Agent: Planner
Role: Decompose alerts into ordered investigation/remediation steps.
Capability: Multi-turn planning loop — the model iterates across multiple reasoning turns to
            produce a well-structured plan before returning. Uses the model's built-in planning
            loop rather than a single-shot call.
Tools: create_plan
"""

# This agent runs in MULTI-TURN mode by default.
# The orchestrator can switch to single-shot for minor incidents:
#   import agents.planner as planner_agent
#   planner_agent.THINKING_MODE = (severity in ("P1", "P2"))
CAPABILITY = "multi_turn_planning"

# ─── Mode Switch ──────────────────────────────────────────────────────────────
# THINKING_MODE = True  → multi-turn planning loop (best for P1/P2 incidents)
# THINKING_MODE = False → single-shot response  (best for P3/minor incidents)
THINKING_MODE: bool = True


def get_prompt() -> str:
    """Return the correct system prompt based on current THINKING_MODE."""
    return SYSTEM_PROMPT_THINKING if THINKING_MODE else SYSTEM_PROMPT_FAST

# ─── Fast prompt (single-shot) ─────────────────────────────────────────────
# Used for P3/minor incidents. One call, one structured JSON response. Fast.
SYSTEM_PROMPT_FAST = """You are the AEGIS Incident Response Planner. Analyze the alert and produce an investigation plan in a SINGLE response.

Rules:
- LogAnalyzer and MetricsAgent run in PARALLEL (no depends_on between them)
- Diagnostician depends on both investigation agents
- Remediator depends on Diagnostician
- If a step already COMPLETED (shown in context), skip it in your plan
- If a step FAILED (shown in context), build a degraded plan without it
- If remediation failed twice, set escalate_to_human: true

You MUST call create_plan exactly once. Do not respond with plain text."""

# ─── Thinking prompt (multi-turn) ──────────────────────────────────────────
# Used for P1/P2 incidents. The model iterates across multiple turns.
SYSTEM_PROMPT_THINKING = """You are the AEGIS Incident Response Planner. Your job is to analyze production alerts and create structured investigation plans.

You have access to a planning loop — use it. Think step by step across multiple turns if needed before producing your final plan.

Turn 1: Read the alert carefully. Ask yourself:
  - What type of incident is this? (latency, memory, crash, config, unknown?)
  - What data sources need to be checked? (always check logs AND metrics in parallel)
  - Is this a replan scenario? (if so, which steps already completed and what failed?)

Turn 2+: Reason about agent dependencies:
  - LogAnalyzer and MetricsAgent can run in PARALLEL (no dependency between them)
  - Diagnostician MUST depend on all investigation agents
  - Remediator MUST depend on Diagnostician
  - If a previous step failed (context says "FAILURE"), create a DEGRADED plan that skips unavailable data
  - If remediation failed twice, set escalate_to_human: true

Final turn: Call create_plan with your structured plan. This is your only output.

Rules:
  - NEVER re-run steps already marked COMPLETED in context
  - NEVER produce a plan with zero steps
  - If no plan is viable, produce a single-step escalation plan

You MUST use the create_plan tool to provide your final answer."""

# Legacy alias so any code referencing SYSTEM_PROMPT still works
SYSTEM_PROMPT = SYSTEM_PROMPT_THINKING

TOOLS = [
    {
        "name": "create_plan",
        "description": "Create a structured incident response plan with ordered steps and dependency graph",
        "parameters": {
            "type": "object",
            "properties": {
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "Step ID (S1, S2, etc.)"},
                            "agent": {
                                "type": "string",
                                "enum": ["LogAnalyzer", "MetricsAgent", "Diagnostician", "Remediator"],
                            },
                            "description": {"type": "string", "description": "What this step should do"},
                            "depends_on": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Step IDs that must complete first (empty for parallel steps)",
                            },
                        },
                        "required": ["id", "agent", "description", "depends_on"],
                    },
                },
                "reasoning": {
                    "type": "string",
                    "description": "Explain your plan strategy and any degradation decisions",
                },
                "escalate_to_human": {
                    "type": "boolean",
                    "description": "True if automated resolution is impossible",
                },
            },
            "required": ["steps", "reasoning"],
        },
    }
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {"type": "array"},
        "reasoning": {"type": "string"},
        "escalate_to_human": {"type": "boolean"},
    },
    "required": ["steps", "reasoning"],
}

DEFAULT_FALLBACK = {
    "steps": [
        {"id": "S1", "agent": "LogAnalyzer", "description": "Fetch and analyze service logs", "depends_on": []},
        {"id": "S2", "agent": "MetricsAgent", "description": "Fetch CPU, memory, latency metrics", "depends_on": []},
        {"id": "S3", "agent": "Diagnostician", "description": "Correlate findings into root cause", "depends_on": ["S1", "S2"]},
        {"id": "S4", "agent": "Remediator", "description": "Execute recommended fix", "depends_on": ["S3"]},
    ],
    "reasoning": "Fallback standard plan (agent output unparseable).",
    "escalate_to_human": False,
}

AGENT_NAME = "Planner"
