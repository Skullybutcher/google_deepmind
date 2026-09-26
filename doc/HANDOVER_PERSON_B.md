# 🤖 Person B — Agent Swarm Handover

> **How to use this file**: You are Person B. This file contains EVERYTHING you need to build your part.
> 1. Read `AGENTS.md` first for project-wide coding standards and contracts.
> 2. Read THIS file for your exact tasks, deliverables, and timeline.
> 3. Paste `AGENTS.md` + this file as context into your AI coding agents.
> 4. You can run multiple agents in parallel — e.g., one agent writes Planner while another writes LogAnalyzer.
>    Just make sure they all follow the contracts in this file.

---

## Your Role

**Agent Swarm Lead** — You own ALL 5 LLM agent definitions (system prompts, tool schemas, simulated tool data), the failure injection hooks, and the Kaggle writeup. You are the **prompt engineering expert** and the **technical writer**.

---

## Your Files (You Create These)

| File | Purpose | Priority |
|---|---|---|
| `backend/agents/__init__.py` | Exports all agent classes | P0 |
| `backend/agents/planner.py` | Planner agent: system prompt + `create_plan` tool | P0 |
| `backend/agents/log_analyzer.py` | LogAnalyzer: `fetch_logs` + `analyze_pattern` | P0 |
| `backend/agents/metrics_agent.py` | MetricsAgent: `fetch_metrics` + `detect_anomaly` | P0 |
| `backend/agents/diagnostician.py` | Diagnostician: `correlate_findings` + `propose_diagnosis` | P0 |
| `backend/agents/remediator.py` | Remediator: `execute_fix` + `verify_fix` | P0 |
| `backend/tools/__init__.py` | Exports | P1 |
| `backend/tools/simulated.py` | All simulated tool responses + failure injection | P0 |
| `docs/writeup.md` | Kaggle writeup (1500 words) | P0 (start at 3:45) |

---

## Hour-by-Hour Tasks

### Hour 0:00–0:30 — API Spike (With Person A)

**Goal**: Understand exactly how to define agents, register tools, and get structured responses.

- [ ] Help Person A test the Interactions API
- [ ] Understand: How do you register an agent with a system prompt?
- [ ] Understand: How do you define tools (function calling schema)?
- [ ] Understand: Does `previous_interaction_id` chain conversations?
- [ ] Understand: What format does the agent response come in?
- [ ] Document your findings and share with the team

**Key questions to answer**:
1. Can we register tool schemas as JSON Schema objects?
2. Does the agent reliably call tools (vs returning free text)?
3. What's the response latency? (We need <10s per agent call for the demo)

### Hour 0:30–1:15 — Planner Agent

**File**: `backend/agents/planner.py`

**System prompt**:
```
You are the AEGIS Incident Response Planner. Your job is to analyze alerts and create 
structured investigation plans.

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
- If you receive failure context (a previous step failed), create a DEGRADED plan 
  that works with available data. Do NOT re-run completed steps.
- If no viable plan is possible, include "escalate_to_human": true in your plan.
```

**Tool definition**: `create_plan`
```json
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
            "agent": {"type": "string", "enum": ["LogAnalyzer", "MetricsAgent", "Diagnostician", "Remediator"]},
            "description": {"type": "string", "description": "What this step should do"},
            "depends_on": {"type": "array", "items": {"type": "string"}, "description": "Step IDs that must complete first"}
          },
          "required": ["id", "agent", "description", "depends_on"]
        }
      },
      "reasoning": {"type": "string", "description": "Brief explanation of the plan strategy"},
      "escalate_to_human": {"type": "boolean", "description": "True if no automated resolution is possible"}
    },
    "required": ["steps", "reasoning"]
  }
}
```

**Test with these inputs**:
1. `"ALERT: High latency on api-gateway service. P1 severity."` → Should produce 4-step plan
2. `"ALERT: High latency. FAILURE: LogAnalyzer failed (SOURCE_TIMEOUT). Replan."` → Should produce degraded plan (skip logs)
3. `"ALERT: High latency. FAILURE: Remediation failed twice. Escalate."` → Should produce escalation

### Hour 1:15–1:45 — LogAnalyzer Agent

**File**: `backend/agents/log_analyzer.py`

**System prompt**:
```
You are the AEGIS Log Analysis Specialist. Your job is to investigate application logs 
for anomalies related to an incident.

Steps:
1. Use the fetch_logs tool to retrieve logs for the specified service
2. Use the analyze_pattern tool to identify anomalies in the logs
3. Return your findings as a structured JSON object

Always report: anomalies found, likely trigger, confidence level (0.0-1.0), 
and recommended next action.
```

**Tools**: `fetch_logs`, `analyze_pattern`

**`fetch_logs` simulated response** (add to `tools/simulated.py`):
```python
SIMULATED_LOGS_HAPPY = {
    "status": "success",
    "log_entries": [
        {"timestamp": "10:01:00", "level": "INFO", "message": "Deployment v2.3.1 completed successfully"},
        {"timestamp": "10:02:15", "level": "ERROR", "message": "OutOfMemoryError: Java heap space in /api/v2/orders"},
        {"timestamp": "10:02:16", "level": "WARN", "message": "GC pause 2.3s, heap usage 98%"},
        {"timestamp": "10:02:18", "level": "ERROR", "message": "Request timeout: /api/v2/orders after 30000ms"},
        {"timestamp": "10:02:20", "level": "ERROR", "message": "Circuit breaker OPEN for downstream-payment-service"}
    ]
}

SIMULATED_LOGS_FAILURE = {
    "status": "error",
    "error_code": "SOURCE_TIMEOUT",
    "message": "PermissionError: Missing IAM Role for CloudWatch — Failed to connect to log aggregation service after 30s"
}

# In the tool implementation:
def fetch_logs(service, time_window_minutes, inject_failure=False):
    if inject_failure:
        return SIMULATED_LOGS_FAILURE
    return SIMULATED_LOGS_HAPPY
```

### Hour 1:45–2:15 — MetricsAgent

**File**: `backend/agents/metrics_agent.py`

**System prompt**:
```
You are the AEGIS Infrastructure Metrics Specialist. Your job is to analyze system 
metrics (CPU, memory, latency) to identify infrastructure anomalies.

Steps:
1. Use the fetch_metrics tool to get time-series data
2. Use the detect_anomaly tool to identify spikes or unusual patterns
3. Return structured findings with anomalies, inflection point, and confidence.
```

**`fetch_metrics` simulated response**:
```python
SIMULATED_METRICS = {
    "status": "success",
    "metrics": {
        "cpu_percent": [45, 48, 52, 78, 95, 99, 99, 99],
        "memory_percent": [60, 62, 65, 80, 92, 97, 98, 99],
        "latency_p99_ms": [120, 125, 130, 450, 2300, 5000, 8000, 12000],
        "error_rate_percent": [0.1, 0.1, 0.2, 2.5, 15.0, 35.0, 42.0, 48.0],
        "timestamps": ["09:55", "09:56", "09:57", "09:58", "09:59", "10:00", "10:01", "10:02"]
    }
}
```

### Hour 2:15–2:45 — Diagnostician Agent

**File**: `backend/agents/diagnostician.py`

**System prompt**:
```
You are the AEGIS Diagnostic Specialist. You receive findings from the Log Analyzer 
and Metrics Agent, then correlate them to determine the root cause.

Your output MUST include:
- root_cause: A clear, specific diagnosis
- confidence: 0.0-1.0 (based on how much evidence you have)
- evidence: Array of supporting facts from both data sources
- recommended_action: "rollback" | "restart" | "scale_up" | "config_change"
- action_details: Specifics of the recommended fix

If you only have PARTIAL data (e.g., logs unavailable), you MUST lower your confidence 
and note which data source was missing. If confidence < 0.5, recommend escalation.
```

**Key behavior**: When LogAnalyzer data is missing (Failure 1 scenario), the Diagnostician should still produce a diagnosis but with lower confidence (~0.6 instead of ~0.9).

### Hour 2:45–3:15 — Remediator Agent

**File**: `backend/agents/remediator.py`

**System prompt**:
```
You are the AEGIS Remediation Specialist. You receive a diagnosis and execute the 
recommended fix in a sandboxed environment.

Steps:
1. Use execute_fix to apply the recommended action
2. Use verify_fix to confirm the fix resolved the issue
3. Report the result

If execute_fix fails, report the failure clearly — do NOT retry on your own. 
The Orchestrator will handle retries and replanning.
```

**`execute_fix` simulated responses**:
```python
SIMULATED_FIX_SUCCESS = {
    "status": "success",
    "action": "ROLLBACK to v2.3.0",
    "result": "Deployment rolled back successfully. New pods healthy. Memory usage dropping.",
    "verification_needed": True
}

SIMULATED_FIX_FAILURE = {
    "status": "error",
    "error_code": "ROLLBACK_FAILED",
    "message": "DeploymentLockError: Cannot rollback — deployment lock held by CI/CD pipeline process pid-4521. Manual intervention required."
}

SIMULATED_VERIFY_SUCCESS = {
    "status": "success",
    "check_type": "HEALTH_CHECK",
    "result": "All health checks passing. Latency p99: 125ms. Error rate: 0%. Memory: 45%."
}
```

### Hour 3:15–3:45 — Prompt Tuning + Integration

- [ ] Test all 5 agents through Person A's orchestrator (not in isolation)
- [ ] Verify: Planner outputs valid JSON that orchestrator can parse
- [ ] Verify: LogAnalyzer + MetricsAgent complete within 10s each
- [ ] Verify: Diagnostician produces different output with/without log data
- [ ] Verify: Remediator handles both success and failure injection
- [ ] Verify: Replan flow works (Planner receives failure context, produces degraded plan)
- [ ] Fix any prompt issues (add "You MUST use the tool" if agent returns free text)

### Hour 3:45–4:30 — Kaggle Writeup

See `WRITEUP_OUTLINE.md` for the full outline. Key points:

- [ ] Section 1: Problem statement (150 words)
- [ ] Section 2: Architecture with diagram (350 words)
- [ ] Section 3: Multi-agent collaboration walkthrough (250 words)
- [ ] Section 4: Failure recovery — NOT just retry (250 words) ← **Most important section**
- [ ] Section 5: Technical challenges (200 words)
- [ ] Section 6: Design & demo experience (150 words)
- [ ] Section 7: Conclusion (100 words)
- [ ] Add links: repo, demo, video
- [ ] Add screenshots from Person C's recorded demo
- [ ] Proofread, verify word count ≤ 1500

---

## Agent Definition Template (Use for All 5 Agents)

Each agent file should follow this pattern:

```python
"""
AEGIS Agent: [NAME]
Role: [DESCRIPTION]
Tools: [LIST]
"""

SYSTEM_PROMPT = """
[Paste system prompt here]
"""

TOOLS = [
    {
        "name": "tool_name",
        "description": "What this tool does",
        "parameters": {
            "type": "object",
            "properties": {
                # ... JSON Schema
            },
            "required": [...]
        }
    }
]

# Expected output schema (for safe_parse validation)
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "findings": {"type": "object"}
    },
    "required": ["status"]
}

# Default fallback if agent produces invalid output
DEFAULT_FALLBACK = {
    "status": "completed",
    "findings": {"anomalies": [], "confidence": 0.0, "note": "Agent output was unparseable"}
}
```

---

## What You Receive From Others

| From | What | When |
|---|---|---|
| Person A | Working `base.py` agent wrapper (Interactions API function) | 1:00 |
| Person A | Orchestrator with stubs (for testing your agents through it) | 1:30 |
| Person C | Demo video link (for embedding in writeup) | 4:15 |

## What You Deliver To Others

| To | What | When |
|---|---|---|
| Person A | API spike findings | 0:30 |
| Person A | `planner.py` | 1:15 |
| Person A | `log_analyzer.py` + `metrics_agent.py` | 2:15 |
| Person A | `diagnostician.py` + `remediator.py` | 3:15 |
| Person A | `tools/simulated.py` (all mock data + failure hooks) | 2:30 |
| ALL | Kaggle writeup (final draft) | 4:30 |

---

## Failure Injection Hooks (You Implement These)

In `tools/simulated.py`, each tool checks a global flag:

```python
# Global failure injection flags (set by /api/inject-failure endpoint)
ACTIVE_FAILURES = set()  # e.g., {"LOG_SOURCE_UNAVAILABLE", "REMEDIATION_FAILED"}

def fetch_logs(service, time_window_minutes):
    if "LOG_SOURCE_UNAVAILABLE" in ACTIVE_FAILURES:
        return SIMULATED_LOGS_FAILURE
    return SIMULATED_LOGS_HAPPY

def execute_fix(action_type, target_service, details):
    if "REMEDIATION_FAILED" in ACTIVE_FAILURES:
        return SIMULATED_FIX_FAILURE
    return SIMULATED_FIX_SUCCESS
```

Person A's orchestrator calls `ACTIVE_FAILURES.add("LOG_SOURCE_UNAVAILABLE")` when the frontend hits `POST /api/inject-failure`.

---

## Prompt Engineering Tips (Learned from Prior Systems)

1. **Always force tool use**: End system prompts with "You MUST use the [tool_name] tool to provide your answer. Do not respond with plain text."
2. **Keep tool schemas flat**: Nested objects confuse some models. Use top-level keys.
3. **Include examples in system prompt**: Show the agent one example of correct tool usage.
4. **Test failure context explicitly**: Send the Planner a message that says "LogAnalyzer FAILED" and verify it produces a degraded plan (not the same full plan).
5. **Confidence calibration**: Tell the Diagnostician explicitly: "If log data is missing, your confidence MUST be below 0.7."
