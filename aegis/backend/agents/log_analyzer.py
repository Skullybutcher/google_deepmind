"""
AEGIS Agent: LogAnalyzer
Role: Investigate application logs for anomalies.
Tools: fetch_logs, analyze_pattern
"""

SYSTEM_PROMPT = """You are the AEGIS Log Analysis Specialist. Your job is to investigate application logs for anomalies related to an incident.

Steps:
1. Use the fetch_logs tool to retrieve logs for the specified service
2. Use the analyze_pattern tool to identify anomalies in the logs
3. Return your findings as a structured JSON object

Always report: anomalies found, likely trigger, confidence level (0.0-1.0), and recommended next action.

You MUST use the fetch_logs and analyze_pattern tools to provide your answer. Do not respond with plain text."""

TOOLS = [
    {
        "name": "fetch_logs",
        "description": "Fetch application logs for a given service and time window",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "time_window_minutes": {"type": "integer"},
                "log_level": {"type": "string", "enum": ["ALL", "ERROR", "WARN", "INFO"]},
            },
            "required": ["service", "time_window_minutes"],
        },
    },
    {
        "name": "analyze_pattern",
        "description": "Analyze log entries for anomaly patterns",
        "parameters": {
            "type": "object",
            "properties": {
                "log_entries": {"type": "array"},
                "focus_area": {"type": "string"},
            },
            "required": ["log_entries"],
        },
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "findings": {"type": "object"},
    },
    "required": ["status"],
}

DEFAULT_FALLBACK = {
    "status": "completed",
    "findings": {"anomalies": [], "confidence": 0.0, "note": "Agent output was unparseable"},
}

AGENT_NAME = "LogAnalyzer"
