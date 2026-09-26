# AEGIS — Architecture Deep Dive & Integration Contracts

> This document contains the detailed technical specs that all 3 team members reference during build.
> **Lock this at minute 30. No changes after that without all-team agreement.**

---

## 1. System Architecture Diagram

```
                              ┌──────────────────────┐
                              │     WEB DASHBOARD     │
                              │  (index.html + JS)    │
                              │                       │
                              │  EventSource(/events) │
                              │  POST /trigger        │
                              │  POST /inject-failure │
                              └──────────┬────────────┘
                                         │ SSE + REST
                                         ▼
                              ┌──────────────────────┐
                              │   FASTAPI BACKEND     │
                              │                       │
                              │  ┌────────────────┐   │
                              │  │  ORCHESTRATOR   │   │
                              │  │  (State Machine)│   │
                              │  └───────┬────────┘   │
                              │          │             │
                              │  ┌───────▼────────┐   │
                              │  │  STATE STORE    │   │
                              │  │  (in-mem + JSON)│   │
                              │  └────────────────┘   │
                              └──────────┬────────────┘
                                         │ Interactions API
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
           ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
           │   PLANNER    │    │ LOG ANALYZER  │    │   METRICS    │
           │   AGENT      │    │    AGENT      │    │    AGENT     │
           │              │    │              │     │              │
           │ Tools:       │    │ Tools:       │     │ Tools:       │
           │ create_plan  │    │ fetch_logs   │     │ fetch_metrics│
           │              │    │ analyze_pat  │     │ detect_anom  │
           └──────────────┘    └──────────────┘     └──────────────┘
                                         │
                              ┌──────────▼───────────┐
                              │   DIAGNOSTICIAN      │
                              │      AGENT           │
                              │                      │
                              │ Tools:               │
                              │ correlate_findings   │
                              │ propose_diagnosis    │
                              └──────────┬───────────┘
                                         │
                              ┌──────────▼───────────┐
                              │    REMEDIATOR        │
                              │      AGENT           │
                              │                      │
                              │ Tools:               │
                              │ execute_fix          │
                              │ verify_fix           │
                              └──────────────────────┘
```

---

## 2. REST API Contract (Backend ↔ Frontend)

### POST `/api/trigger-incident`

Triggers a new incident response flow.

**Request:**
```json
{
  "alert_type": "HIGH_LATENCY",
  "service": "api-gateway",
  "severity": "P1"
}
```

**Response:**
```json
{
  "incident_id": "INC-20260926-001",
  "status": "PLANNING",
  "message": "Incident created. Planner Agent activated."
}
```

### POST `/api/inject-failure`

Injects a failure scenario for the next (or current) incident run.

**Request:**
```json
{
  "failure_type": "LOG_SOURCE_UNAVAILABLE"
}
```

Valid `failure_type` values:
- `"LOG_SOURCE_UNAVAILABLE"` — LogAnalyzer's `fetch_logs` will return an error
- `"REMEDIATION_FAILED"` — Remediator's `execute_fix` will return a failure
- `"NONE"` — Clear all injected failures

**Response:**
```json
{
  "status": "ok",
  "active_failures": ["LOG_SOURCE_UNAVAILABLE"]
}
```

### GET `/api/events` (SSE)

Server-Sent Events stream for live incident updates.

**Event format:**
```
event: state_update
data: {"event_type":"AGENT_STARTED","timestamp":"2026-09-26T10:05:00Z","incident_id":"INC-20260926-001","data":{"status":"INVESTIGATING","active_agent":"LogAnalyzer","plan_version":1,"steps":[...],"history":[...],"message":"LogAnalyzer is scanning application logs..."}}

event: state_update
data: {"event_type":"AGENT_COMPLETED","timestamp":"...","incident_id":"...","data":{...}}
```

**Event types** (the `event_type` field):

| Event Type | When Emitted | Key Data |
|---|---|---|
| `INCIDENT_CREATED` | Incident triggered | alert details |
| `PLAN_CREATED` | Planner produces plan | steps array |
| `AGENT_STARTED` | An agent begins work | agent name, step ID |
| `AGENT_COMPLETED` | An agent finishes successfully | agent name, output summary |
| `AGENT_FAILED` | An agent encountered an error | agent name, error message |
| `REPLAN_TRIGGERED` | Orchestrator initiates replanning | failure reason, old plan version |
| `PLAN_UPDATED` | Planner produces new plan | new steps array, new plan version |
| `RESOLVED` | Incident fully resolved | final diagnosis, remediation action |
| `ESCALATED` | System cannot resolve, needs human | failure history, reason |

### GET `/api/state`

Returns the current full incident state object (for polling fallback if SSE fails).

**Response:** The full Incident State Object JSON (see PROJECT_PLAN.md § Architecture).

---

## 3. Agent I/O Contracts (Orchestrator ↔ Agents via Interactions API)

### 3.1 Planner Agent

**System Prompt** (summary):
> You are the incident response planner. Given an alert (and optionally, context about previous failed attempts), produce a structured investigation and remediation plan. Each step must specify: an ID, the agent to execute it, a description of what to do, and any dependencies on other steps.

**Input message from Orchestrator:**
```
ALERT: High latency detected on api-gateway service. P1 severity.
Current time: 2026-09-26T10:00:00Z.

CONTEXT (if replanning):
Previous plan version: 1
Completed steps: [S1: LogAnalyzer - COMPLETED, S2: MetricsAgent - COMPLETED]
Failed steps: [S4: Remediator - FAILED, error: ROLLBACK_FAILED]
Available agents: Planner, LogAnalyzer, MetricsAgent, Diagnostician, Remediator

Please create a plan. Use the create_plan tool.
```

**Tool: `create_plan`**
```json
{
  "name": "create_plan",
  "description": "Create a structured incident response plan",
  "parameters": {
    "type": "object",
    "properties": {
      "steps": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "id": { "type": "string", "description": "Step ID, e.g. S1, S2" },
            "agent": { "type": "string", "enum": ["LogAnalyzer", "MetricsAgent", "Diagnostician", "Remediator"] },
            "description": { "type": "string" },
            "depends_on": { "type": "array", "items": { "type": "string" } }
          },
          "required": ["id", "agent", "description", "depends_on"]
        }
      },
      "reasoning": { "type": "string", "description": "Brief explanation of the plan" }
    },
    "required": ["steps", "reasoning"]
  }
}
```

**Expected output (tool call result):**
```json
{
  "steps": [
    {"id": "S1", "agent": "LogAnalyzer", "description": "Fetch and analyze API gateway logs for error patterns", "depends_on": []},
    {"id": "S2", "agent": "MetricsAgent", "description": "Fetch CPU, memory, and latency metrics for api-gateway", "depends_on": []},
    {"id": "S3", "agent": "Diagnostician", "description": "Correlate log anomalies and metric spikes to determine root cause", "depends_on": ["S1", "S2"]},
    {"id": "S4", "agent": "Remediator", "description": "Execute recommended fix based on diagnosis", "depends_on": ["S3"]}
  ],
  "reasoning": "Parallel investigation via logs and metrics, followed by correlation and remediation."
}
```

---

### 3.2 LogAnalyzer Agent

**System Prompt** (summary):
> You are a log analysis specialist. Use the fetch_logs tool to retrieve application logs, then use analyze_pattern to identify anomalies. Report structured findings.

**Input from Orchestrator:**
```
TASK: Analyze application logs for service "api-gateway" to identify error patterns related to high latency.
Time window: last 30 minutes.
Use the fetch_logs tool first, then analyze_pattern.
```

**Tool: `fetch_logs`**
```json
{
  "name": "fetch_logs",
  "description": "Fetch application logs for a given service and time window",
  "parameters": {
    "type": "object",
    "properties": {
      "service": { "type": "string" },
      "time_window_minutes": { "type": "integer" },
      "log_level": { "type": "string", "enum": ["ALL", "ERROR", "WARN", "INFO"] }
    },
    "required": ["service", "time_window_minutes"]
  }
}
```

**Simulated tool response (happy path):**
```json
{
  "status": "success",
  "log_entries": [
    {"timestamp": "10:02:15", "level": "ERROR", "message": "OutOfMemoryError: Java heap space in /api/v2/orders"},
    {"timestamp": "10:02:16", "level": "WARN", "message": "GC pause 2.3s, heap usage 98%"},
    {"timestamp": "10:02:18", "level": "ERROR", "message": "Request timeout: /api/v2/orders after 30000ms"},
    {"timestamp": "10:01:00", "level": "INFO", "message": "Deployment v2.3.1 completed successfully"},
    {"timestamp": "10:02:20", "level": "ERROR", "message": "Circuit breaker OPEN for downstream-payment-service"}
  ]
}
```

**Simulated tool response (FAILURE INJECTED):**
```json
{
  "status": "error",
  "error_code": "SOURCE_TIMEOUT",
  "message": "Failed to connect to log aggregation service: connection timed out after 30s"
}
```

**Tool: `analyze_pattern`**
```json
{
  "name": "analyze_pattern",
  "description": "Analyze log entries for anomaly patterns",
  "parameters": {
    "type": "object",
    "properties": {
      "log_entries": { "type": "array" },
      "focus_area": { "type": "string" }
    },
    "required": ["log_entries"]
  }
}
```

**Expected agent output** (final message back to orchestrator):
```json
{
  "status": "completed",
  "findings": {
    "anomalies": [
      "OutOfMemoryError detected immediately after deployment v2.3.1",
      "GC pause of 2.3s indicates memory pressure",
      "Circuit breaker opened for downstream service"
    ],
    "likely_trigger": "Deployment v2.3.1 introduced a memory leak",
    "confidence": 0.85,
    "recommended_action": "Investigate memory consumption in v2.3.1 changes"
  }
}
```

---

### 3.3 MetricsAgent

**System Prompt** (summary):
> You are an infrastructure metrics specialist. Use fetch_metrics to get time-series data, then detect_anomaly to identify spikes or unusual patterns.

**Tool: `fetch_metrics`**
```json
{
  "name": "fetch_metrics",
  "description": "Fetch infrastructure metrics for a service",
  "parameters": {
    "type": "object",
    "properties": {
      "service": { "type": "string" },
      "metrics": { "type": "array", "items": { "type": "string" } },
      "time_window_minutes": { "type": "integer" }
    },
    "required": ["service", "metrics"]
  }
}
```

**Simulated response:**
```json
{
  "status": "success",
  "metrics": {
    "cpu_percent": [45, 48, 52, 78, 95, 99, 99, 99],
    "memory_percent": [60, 62, 65, 80, 92, 97, 98, 99],
    "latency_p99_ms": [120, 125, 130, 450, 2300, 5000, 8000, 12000],
    "timestamps": ["09:55", "09:56", "09:57", "09:58", "09:59", "10:00", "10:01", "10:02"]
  }
}
```

**Tool: `detect_anomaly`** — similar structure. Returns structured anomaly report.

**Expected output:**
```json
{
  "status": "completed",
  "findings": {
    "anomalies": [
      "CPU spike from 52% to 95% at 09:58 (correlates with deployment window)",
      "Memory climbing from 65% to 99% — no plateau, suggests leak",
      "P99 latency 100x increase: 130ms → 12000ms"
    ],
    "inflection_point": "09:58 — consistent with deployment v2.3.1 at 10:01",
    "confidence": 0.92
  }
}
```

---

### 3.4 Diagnostician Agent

**System Prompt** (summary):
> You are a diagnostic specialist. Given findings from log analysis and metrics analysis, correlate them to determine the root cause and propose a remediation action.

**Input from Orchestrator:**
```
TASK: Correlate the following findings to determine root cause and propose remediation.

LOG ANALYSIS FINDINGS:
{...LogAnalyzer output...}

METRICS ANALYSIS FINDINGS:
{...MetricsAgent output...}

Use correlate_findings and then propose_diagnosis.
```

**Expected output:**
```json
{
  "status": "completed",
  "diagnosis": {
    "root_cause": "Memory leak introduced in deployment v2.3.1 causing OOM errors and cascading latency",
    "confidence": 0.90,
    "evidence": [
      "OOM errors in logs correlate with memory spike in metrics",
      "Both anomalies begin at deployment time (09:58-10:01)",
      "Circuit breaker activation confirms cascading failure"
    ],
    "recommended_action": "rollback",
    "action_details": {
      "type": "ROLLBACK",
      "target_version": "v2.3.0",
      "service": "api-gateway"
    }
  }
}
```

---

### 3.5 Remediator Agent

**System Prompt** (summary):
> You are a remediation specialist. Execute the proposed fix in a sandboxed environment and verify it works.

**Tool: `execute_fix`**
```json
{
  "name": "execute_fix",
  "description": "Execute a remediation action in a sandboxed environment",
  "parameters": {
    "type": "object",
    "properties": {
      "action_type": { "type": "string", "enum": ["ROLLBACK", "RESTART", "SCALE_UP", "CONFIG_CHANGE"] },
      "target_service": { "type": "string" },
      "details": { "type": "object" }
    },
    "required": ["action_type", "target_service"]
  }
}
```

**Simulated response (happy path):**
```json
{
  "status": "success",
  "action": "ROLLBACK to v2.3.0",
  "result": "Deployment rolled back successfully. New pods healthy.",
  "verification_needed": true
}
```

**Simulated response (FAILURE INJECTED):**
```json
{
  "status": "error",
  "error_code": "ROLLBACK_FAILED",
  "message": "Cannot rollback: deployment lock held by CI/CD pipeline process pid-4521. Manual intervention required."
}
```

**Tool: `verify_fix`**
```json
{
  "name": "verify_fix",
  "description": "Verify the applied fix resolved the incident",
  "parameters": {
    "type": "object",
    "properties": {
      "service": { "type": "string" },
      "check_type": { "type": "string", "enum": ["HEALTH_CHECK", "LATENCY_CHECK", "ERROR_RATE_CHECK"] }
    },
    "required": ["service", "check_type"]
  }
}
```

**Simulated response:**
```json
{
  "status": "success",
  "check_type": "HEALTH_CHECK",
  "result": "All health checks passing. Latency p99 back to 125ms. Error rate: 0%."
}
```

---

## 4. State Machine Transitions

```
                    ┌──────────┐
                    │  IDLE    │
                    └────┬─────┘
                         │ trigger-incident
                         ▼
                    ┌──────────┐
              ┌─────│ PLANNING │
              │     └────┬─────┘
              │          │ plan_created
              │          ▼
              │    ┌──────────────┐
              │    │INVESTIGATING │◄──────────────────┐
              │    └──┬───────┬───┘                   │
              │       │       │                       │
              │       │       │ (parallel)            │
              │       ▼       ▼                       │
              │   ┌──────┐ ┌──────┐                   │
              │   │ Logs │ │Metrics│                   │
              │   └──┬───┘ └──┬───┘                   │
              │      │        │                       │
              │      │ (one fails?)                   │
              │      ├────────┤                       │
              │      │ YES    │ NO                    │
              │      ▼        ▼                       │
              │  ┌────────┐  all done                 │
              │  │REPLAN  │──────┐                    │
              │  └────────┘      │                    │
              │                  ▼                    │
              │           ┌───────────┐               │
              │           │DIAGNOSING │               │
              │           └─────┬─────┘               │
              │                 │                     │
              │                 ▼                     │
              │          ┌────────────┐               │
              │          │REMEDIATING │               │
              │          └──┬──────┬──┘               │
              │             │      │                  │
              │          success  failure              │
              │             │      │                  │
              │             ▼      ▼                  │
              │       ┌────────┐ ┌────────┐           │
              │       │RESOLVED│ │REPLAN  │───(retry?)┘
              │       └────────┘ └────┬───┘
              │                       │ (max retries exceeded)
              │                       ▼
              │                 ┌──────────┐
              └────────────────►│ESCALATED │
                                └──────────┘
```

---

## 5. File / Folder Structure

```
aegis/
├── backend/
│   ├── main.py              # FastAPI app, routes, SSE endpoint
│   ├── orchestrator.py      # State machine, agent routing, failure detection
│   ├── state.py             # Incident state model, persistence, history
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py          # Base agent wrapper (Interactions API calls)
│   │   ├── planner.py       # Planner agent: system prompt, tools, I/O
│   │   ├── log_analyzer.py  # LogAnalyzer agent
│   │   ├── metrics_agent.py # MetricsAgent
│   │   ├── diagnostician.py # Diagnostician agent
│   │   └── remediator.py    # Remediator agent
│   ├── tools/
│   │   ├── __init__.py
│   │   └── simulated.py     # All simulated tool implementations (fetch_logs, etc.)
│   ├── requirements.txt
│   └── Procfile             # For Railway/Render deployment
├── frontend/
│   ├── index.html           # Single-page app
│   ├── style.css            # All styles (glassmorphism, layout, typography)
│   └── app.js               # SSE handling, DOM updates, button handlers
├── docs/
│   └── architecture.png     # Rendered architecture diagram (optional)
├── README.md
└── .gitignore
```

---

## 6. Environment Variables

```env
ANTIGRAVITY_API_KEY=<your-api-key>
ANTIGRAVITY_API_BASE_URL=<interactions-api-base-url>
PORT=8000
CORS_ORIGINS=*
```

---

## 7. Deployment Checklist

- [ ] Backend deployed to Railway/Render with env vars set
- [ ] Frontend served from backend (FastAPI static files mount) OR deployed to Vercel
- [ ] CORS configured to allow frontend origin
- [ ] SSE endpoint accessible from public URL
- [ ] Health check endpoint (`GET /api/health`) returns 200
- [ ] `.gitignore` excludes `.env`, `__pycache__`, `state_*.json`
- [ ] README has: description, architecture diagram, setup instructions, demo link, video link
