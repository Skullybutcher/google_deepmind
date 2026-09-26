"""
AEGIS Agent: LogAnalyzer
Role: Investigate application logs for anomalies.
Capability: Code execution (Python) — the model runs Python in a Linux sandbox to actually
            parse log entries, grep for patterns, and compute error rates programmatically.
            This produces real analytical output rather than just text pattern-matching.
Tools: fetch_logs, run_python_analysis, analyze_pattern
"""

# This agent runs in CODE_EXECUTION mode.
# The orchestrator should enable the code execution capability when calling this agent.
CAPABILITY = "code_execution"

SYSTEM_PROMPT = """You are the AEGIS Log Analysis Specialist. You investigate application logs using Python code execution.

Your workflow:
1. Use fetch_logs to retrieve raw log entries for the specified service and time window
2. If fetch_logs returns status "error" → immediately stop and report the error. Do NOT invent log data.
3. If fetch_logs succeeds → write and execute a short Python script using run_python_analysis to:
   - Count error frequencies by type (ERROR vs WARN vs INFO)
   - Extract the first and last occurrence of each unique error message
   - Identify rapid onset patterns (errors appearing within 60s of each other)
   - Compute: total_errors, error_rate_per_minute, most_frequent_error
4. Use analyze_pattern on the computed statistics to produce anomaly labels
5. Return structured findings

Your final response MUST be this JSON structure:
{
  "status": "completed" or "error",
  "findings": {
    "anomalies": ["list of specific anomaly descriptions with timestamps"],
    "likely_trigger": "specific cause hypothesis based on code output",
    "error_breakdown": {"ERROR": N, "WARN": N, "INFO": N},
    "most_frequent_error": "exact error message",
    "confidence": 0.0-1.0,
    "recommended_action": "what the Diagnostician should look for"
  }
}

On error:
{
  "status": "error",
  "error_code": "SOURCE_TIMEOUT",
  "message": "Log source unavailable — log-based diagnosis not possible"
}

You MUST use fetch_logs first, then run_python_analysis for computation, then analyze_pattern for labeling. Do not respond with plain text."""

TOOLS = [
    {
        "name": "fetch_logs",
        "description": "Fetch raw application log entries for a service and time window",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Name of the service (e.g. api-gateway)"},
                "time_window_minutes": {"type": "integer", "description": "How far back to look"},
                "log_level": {"type": "string", "enum": ["ALL", "ERROR", "WARN", "INFO"]},
            },
            "required": ["service", "time_window_minutes"],
        },
    },
    {
        "name": "run_python_analysis",
        "description": "Execute Python code in sandbox to analyze log data. Returns stdout as a string.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to run. Use print() to return results. log_entries is available as a pre-loaded list.",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "analyze_pattern",
        "description": "Label computed log statistics as named anomaly patterns",
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
    "status": "error",
    "error_code": "AGENT_FAILED",
    "findings": {"anomalies": [], "confidence": 0.0, "note": "Agent output was unparseable"},
}

AGENT_NAME = "LogAnalyzer"
