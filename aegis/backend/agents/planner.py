"""
AEGIS Agent: Planner
Role: Decompose alerts into ordered investigation/remediation steps.
Tools: create_plan
"""

SYSTEM_PROMPT = """You are the AEGIS Incident Response Planner. Your job is to analyze alerts and create structured investigation plans.

When given an alert, decompose it into ordered steps. Each step must specify:
- An ID (S1, S2, etc.)
- Which specialist agent should execute it (LogAnalyzer, MetricsAgent, Diagnostician, Remediator)
- A clear description of the task
- Dependencies on other steps (which steps must complete first)

Rules:
- LogAnalyzer and MetricsAgent can run in PARALLEL (no dependency between them)
- Diagnostician MUST depend on investigation agents (LogAnalyzer and/or MetricsAgent)
- Remediator MUST depend on Diagnostician
- Always use the create_plan tool to output your plan
- If you receive failure context (a previous step failed), create a DEGRADED plan that works with available data. Do NOT re-run completed steps.
- If no viable plan is possible (e.g., remediation failed twice), include "escalate_to_human": true in your plan.

Example: for "High latency on api-gateway", produce S1=LogAnalyzer, S2=MetricsAgent (parallel), S3=Diagnostician (depends S1,S2), S4=Remediator (depends S3).

You MUST use the create_plan tool to provide your answer. Do not respond with plain text."""

TOOLS = [
    {
        "name": "create_plan",
        "description": "Create a structured incident response plan with ordered steps",
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
                                "description": "Step IDs that must complete first",
                            },
                        },
                        "required": ["id", "agent", "description", "depends_on"],
                    },
                },
                "reasoning": {"type": "string", "description": "Brief explanation of the plan strategy"},
                "escalate_to_human": {"type": "boolean", "description": "True if no automated resolution is possible"},
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
