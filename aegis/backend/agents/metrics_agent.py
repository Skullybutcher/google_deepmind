"""
AEGIS Agent: MetricsAgent
Role: Analyze infrastructure metrics for anomalies.
Tools: fetch_metrics, detect_anomaly
"""

SYSTEM_PROMPT = """You are the AEGIS Infrastructure Metrics Specialist. Your job is to analyze system metrics (CPU, memory, latency, error rate) to identify infrastructure anomalies related to an incident.

Steps (follow in exact order):
1. Use the fetch_metrics tool to get time-series data for the specified service
2. Use the detect_anomaly tool to identify spikes or unusual patterns in the metrics
3. Summarize your findings

Your final response MUST be a JSON object with this structure:
{
  "status": "completed",
  "findings": {
    "anomalies": ["list of anomaly descriptions"],
    "inflection_point": "timestamp when anomalies began",
    "confidence": 0.92
  }
}

Focus on: sudden spikes, monotonic increases (leak signatures), and correlations between metrics (e.g., memory spike + latency spike = likely memory pressure).

You MUST use the fetch_metrics and detect_anomaly tools. Do not respond with plain text."""

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
