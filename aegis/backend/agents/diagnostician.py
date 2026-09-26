"""
AEGIS Agent: Diagnostician
Role: Correlate investigator findings into root cause + remediation proposal.
Tools: correlate_findings, propose_diagnosis
"""

SYSTEM_PROMPT = """You are the AEGIS Diagnostic Specialist. You receive findings from the Log Analyzer and Metrics Agent, then correlate them to determine the root cause.

Your output MUST include:
- root_cause: A clear, specific diagnosis
- confidence: 0.0-1.0 (based on how much evidence you have)
- evidence: Array of supporting facts from both data sources
- recommended_action: "rollback" | "restart" | "scale_up" | "config_change"
- action_details: Specifics of the recommended fix

If you only have PARTIAL data (e.g., logs unavailable), you MUST lower your confidence and note which data source was missing. If log data is missing, your confidence MUST be below 0.7. If confidence < 0.5, recommend escalation.

You MUST use the correlate_findings and propose_diagnosis tools to provide your answer. Do not respond with plain text."""

TOOLS = [
    {
        "name": "correlate_findings",
        "description": "Correlate log and metric findings into joint evidence",
        "parameters": {
            "type": "object",
            "properties": {
                "log_findings": {"type": "object"},
                "metrics_findings": {"type": "object"},
            },
            "required": ["metrics_findings"],
        },
    },
    {
        "name": "propose_diagnosis",
        "description": "Propose root cause and remediation action",
        "parameters": {
            "type": "object",
            "properties": {
                "root_cause": {"type": "string"},
                "confidence": {"type": "number"},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "recommended_action": {"type": "string", "enum": ["rollback", "restart", "scale_up", "config_change"]},
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
        "recommended_action": "restart",
        "action_details": {},
    },
}

AGENT_NAME = "Diagnostician"
