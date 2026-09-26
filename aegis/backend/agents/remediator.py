"""
AEGIS Agent: Remediator
Role: Execute recommended fix in sandbox and verify.
Tools: execute_fix, verify_fix
"""

SYSTEM_PROMPT = """You are the AEGIS Remediation Specialist. You receive a diagnosis and execute the recommended fix in a sandboxed environment.

Steps:
1. Use execute_fix to apply the recommended action
2. Use verify_fix to confirm the fix resolved the issue
3. Report the result

If execute_fix fails, report the failure clearly — do NOT retry on your own. The Orchestrator will handle retries and replanning.

You MUST use the execute_fix and verify_fix tools to provide your answer. Do not respond with plain text."""

TOOLS = [
    {
        "name": "execute_fix",
        "description": "Execute a remediation action in a sandboxed environment",
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "enum": ["ROLLBACK", "RESTART", "SCALE_UP", "CONFIG_CHANGE"]},
                "target_service": {"type": "string"},
                "details": {"type": "object"},
            },
            "required": ["action_type", "target_service"],
        },
    },
    {
        "name": "verify_fix",
        "description": "Verify the applied fix resolved the incident",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "check_type": {"type": "string", "enum": ["HEALTH_CHECK", "LATENCY_CHECK", "ERROR_RATE_CHECK"]},
            },
            "required": ["service", "check_type"],
        },
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
    },
    "required": ["status"],
}

DEFAULT_FALLBACK = {
    "status": "completed",
    "remediation": {
        "action": "RESTART",
        "result": "Fallback action — agent output was unparseable. Attempted generic restart.",
        "verified": False,
        "note": "Agent output was unparseable; orchestrator should consider escalation.",
    },
}

AGENT_NAME = "Remediator"
