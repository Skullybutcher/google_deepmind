"""
AEGIS Agent: Diagnostician
Role: Correlate investigator findings into root cause + remediation proposal.
Tools: correlate_findings, propose_diagnosis
"""

SYSTEM_PROMPT = """You are the AEGIS Diagnostic Specialist. You receive findings from the Log Analyzer and Metrics Agent, then correlate them to determine the root cause.

Steps:
1. Use the correlate_findings tool first, passing both log_findings and metrics_findings
2. Use the propose_diagnosis tool to output your structured diagnosis

Your diagnosis MUST include:
- root_cause: A clear, specific diagnosis
- confidence: 0.0-1.0 (based on how much evidence you have)
- evidence: Array of supporting facts from both data sources
- recommended_action: "rollback" | "restart" | "scale_up" | "config_change"
- action_details: Specifics of the recommended fix

CRITICAL RULES FOR CONFIDENCE CALIBRATION:
- If BOTH log and metric data are available: confidence should be 0.85-0.95
- If log data is MISSING or FAILED: confidence MUST be below 0.70 (you have less evidence)
- If confidence < 0.50: set recommended_action to "escalate" and explain why
- NEVER inflate confidence when working with partial data

Example with partial data:
  - Metrics show CPU/memory spikes → you can infer infrastructure stress
  - But WITHOUT logs, you cannot confirm the specific root cause (e.g., which deployment, which error)
  - So set confidence ~0.60, note "Log data unavailable — diagnosis based on metrics only"

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
