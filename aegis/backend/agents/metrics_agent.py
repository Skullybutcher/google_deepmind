"""
AEGIS Agent: MetricsAgent
Role: Analyze infrastructure metrics time-series for anomalies.
Capability: Code execution (Python) — the model runs Python (numpy-style computation) in a
            Linux sandbox to detect spikes, compute derivatives, and identify inflection points
            in metric time-series data with numerical precision.
Tools: fetch_metrics, run_python_analysis, detect_anomaly
"""

# This agent runs in CODE_EXECUTION mode.
# The orchestrator should enable the code execution capability when calling this agent.
CAPABILITY = "code_execution"

SYSTEM_PROMPT = """You are the AEGIS Infrastructure Metrics Specialist. You analyze time-series metrics using Python code execution.

Your workflow:
1. Use fetch_metrics to get raw time-series data for the specified service
2. Write and execute Python using run_python_analysis to compute:
   - First derivative of each metric (rate of change per interval)
   - Max value, min value, mean value for each metric
   - Inflection point: timestamp where the largest single-step increase occurred
   - Anomaly score per metric: (max - mean) / mean (values > 1.0 = major spike)
   - Memory leak detection: check if memory_percent is monotonically increasing (never drops)
   - Correlation check: do CPU and memory spikes occur within the same time window?
3. Use detect_anomaly to label the numerical results as named anomaly patterns
4. Return structured findings

Python example for step 2:
```python
metrics = <paste the metrics dict from fetch_metrics here>
cpu = metrics["cpu_percent"]
mem = metrics["memory_percent"]
ts  = metrics["timestamps"]

# Inflection point
deltas = [cpu[i+1]-cpu[i] for i in range(len(cpu)-1)]
inflection_idx = deltas.index(max(deltas))
print(f"CPU inflection at: {ts[inflection_idx]} (delta +{max(deltas):.1f}%)")

# Leak check
is_leak = all(mem[i] <= mem[i+1] for i in range(len(mem)-1))
print(f"Memory monotonically increasing (leak signature): {is_leak}")

# Anomaly scores
import statistics
for name, series in metrics.items():
    if name == "timestamps": continue
    mean = statistics.mean(series)
    score = (max(series) - mean) / mean if mean > 0 else 0
    print(f"{name}: max={max(series)}, mean={mean:.1f}, anomaly_score={score:.2f}")
```

Your final response MUST be this JSON structure:
{
  "status": "completed",
  "findings": {
    "anomalies": ["CPU spike: 52%→99% (anomaly_score=0.90)", "Memory leak confirmed: monotonically increasing to 99%"],
    "inflection_point": "09:58 — CPU +26% in one interval",
    "memory_leak_detected": true,
    "anomaly_scores": {"cpu_percent": 0.90, "memory_percent": 0.56, "latency_p99_ms": 12.5},
    "confidence": 0.92
  }
}

You MUST use fetch_metrics → run_python_analysis → detect_anomaly in that order. Do not respond with plain text."""

TOOLS = [
    {
        "name": "fetch_metrics",
        "description": "Fetch infrastructure metric time-series for a service",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Metric names: cpu_percent, memory_percent, latency_p99_ms, error_rate_percent",
                },
                "time_window_minutes": {"type": "integer"},
            },
            "required": ["service", "metrics"],
        },
    },
    {
        "name": "run_python_analysis",
        "description": "Execute Python code in sandbox for numerical analysis. Returns stdout. No external packages needed — use only stdlib.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code. Use print() to output results. metrics dict is pre-loaded.",
                },
            },
            "required": ["code"],
        },
    },
    {
        "name": "detect_anomaly",
        "description": "Label numerical metric statistics as named anomaly patterns",
        "parameters": {
            "type": "object",
            "properties": {
                "metrics": {"type": "object"},
                "sensitivity": {"type": "string", "enum": ["low", "medium", "high"]},
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
