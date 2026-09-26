"""
AEGIS Agent: MetricsAgent
Role: Analyze infrastructure metrics for anomalies.
Tools: fetch_metrics, detect_anomaly
"""

SYSTEM_PROMPT = """You are the AEGIS Infrastructure Metrics Specialist. Your job is to analyze system metrics (CPU, memory, latency) to identify infrastructure anomalies.

Steps:
1. Use the fetch_metrics tool to get time-series data
2. Use the detect_anomaly tool to identify spikes or unusual patterns
3. Return structured findings with anomalies, inflection point, and confidence.

You MUST use the fetch_metrics and detect_anomaly tools to provide your answer. Do not respond with plain text."""

TOOLS = [
    {
        "name": "fetch_metrics",
        "description": "Fetch infrastructure metrics for a service",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "metrics": {"type": "array", "items": {"type": "string"}},
                "time_window_minutes": {"type": "integer"},
            },
            "required": ["service", "metrics"],
        },
    },
    {
        "name": "detect_anomaly",
        "description": "Detect spikes or unusual patterns in metric time-series",
        "parameters": {
            "type": "object",
            "properties": {
                "metrics": {"type": "object"},
                "sensitivity": {"type": "string"},
            },
            "required": ["metrics"],
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

AGENT_NAME = "MetricsAgent"
