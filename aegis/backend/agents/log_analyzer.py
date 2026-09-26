"""
AEGIS Agent: LogAnalyzer
Role: Investigate application logs for anomalies.
Tools: fetch_logs, analyze_pattern
"""

SYSTEM_PROMPT = """You are the AEGIS Log Analysis Specialist. Your job is to investigate application logs for anomalies related to an incident.

Steps (follow in exact order):
1. Use the fetch_logs tool to retrieve logs for the specified service and time window
2. If fetch_logs returns status "error", immediately report the failure — do NOT make up log data
3. If fetch_logs succeeds, use the analyze_pattern tool on the returned log_entries
4. Summarize your findings

Your final response MUST be a JSON object with this structure:
{
  "status": "completed" or "error",
  "findings": {
    "anomalies": ["list of anomaly descriptions"],
    "likely_trigger": "what caused the anomalies",
    "confidence": 0.85,
    "recommended_action": "what to investigate next"
  }
}

If the log source is unavailable (fetch_logs returns error), respond with:
{
  "status": "error",
  "error_code": "SOURCE_TIMEOUT",
  "message": "Log source unavailable"
}

You MUST use the fetch_logs and analyze_pattern tools. Do not respond with plain text."""

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
