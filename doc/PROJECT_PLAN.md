# Project Plan: AEGIS — Autonomous Emergency Grid for Incident Response & Self-healing

> **Codename**: AEGIS  
> **Track**: Autonomous Orchestration with Managed Agents  
> **Stack**: Antigravity Agent (`antigravity-preview-09-2026`) via the Interactions API  
> **Team Size**: 3 people × 5 hours  
> **Repo**: Public GitHub  
> **Demo**: Hosted web app (Vercel / Cloudflare Pages + serverless backend)

---

## 1. Concrete Project Concept

### The Problem We Solve

When a production system alert fires (server down, latency spike, failing health checks), a human SRE must:
1. **Triage** — read the alert, decide what logs/metrics to pull.
2. **Investigate** — query multiple systems (logs, metrics, recent deploys, config changes).
3. **Diagnose** — correlate findings into a root-cause hypothesis.
4. **Remediate** — apply a fix (rollback, restart, scale up).
5. **Verify** — confirm the fix worked; if not, try something else.

This is a *perfect* multi-agent use case because each step is a distinct capability, the state is complex (multiple parallel data streams converge into a diagnosis), failures are common (a log source is unreachable, a rollback fails), and retry-without-thinking is dangerous.

### What We Build (Scoped for 5 Hours)

**AEGIS** is a live incident-response orchestration system. The user clicks **"Trigger Incident"** on a web dashboard. The system:

1. **Planner Agent** receives the alert, decomposes it into investigation subtasks.
2. **Log Analyzer Agent** fetches and analyzes simulated application logs.
3. **Metrics Agent** fetches and analyzes simulated infrastructure metrics (CPU, memory, latency).
4. **Diagnostician Agent** synthesizes findings from both investigators into a root-cause hypothesis.
5. **Remediator Agent** executes the proposed fix in a simulated environment.
6. **Orchestrator** tracks state across all agents, detects failures, and re-plans.

The entire flow runs live in ~30–60 seconds, with state transitions visible on the dashboard in real time.

### Why This Use Case Wins

| Judging Criterion | How AEGIS Demonstrates It |
|---|---|
| **Multi-step planning** | Planner decomposes alert into 3–4 subtasks with dependencies |
| **Delegation across distinct agents** | 4 specialist agents with different system prompts, tools, and responsibilities |
| **State tracking over long horizon** | Incident state object persists through all phases; dashboard shows full history |
| **Failure detection & recovery** | Injected failures (log source timeout, failed remediation) trigger re-planning, not blind retry |
| **Not "3 prompts with if/else"** | Agents communicate through shared state + Interactions API message passing; Orchestrator dynamically routes based on agent outputs |

### The 2-Minute Demo Script

1. **0:00** — Dashboard loads. Shows "All Systems Normal."
2. **0:10** — User clicks **"Trigger Incident: High Latency on API Gateway."**
3. **0:15** — Planner Agent activates, posts plan: "Investigate logs, check metrics, correlate findings, remediate."
4. **0:20** — Log Analyzer and Metrics Agent run in parallel. Live status chips update.
5. **0:30** — Diagnostician synthesizes: "Root cause: memory leak from deploy v2.3.1."
6. **0:35** — Remediator proposes: "Rollback to v2.3.0." Executes in sandbox.
7. **0:40** — Verification passes. Incident marked **RESOLVED**. Full timeline visible.
8. **0:45** — User clicks **"Trigger Failure: Log Source Unavailable"** (a button that injects failure).
9. **0:50** — Log Analyzer fails. Orchestrator detects, updates state to "DEGRADED_INVESTIGATION."
10. **0:55** — Orchestrator re-plans: "Skip detailed logs, use Metrics Agent + heuristic diagnosis."
11. **1:05** — Diagnostician runs with partial data, proposes best-effort fix.
12. **1:10** — Remediation attempt fails (injected). Orchestrator escalates: "REQUIRES_HUMAN — insufficient data for automated fix."
13. **1:15** — Dashboard shows full incident timeline with both failures, recovery attempts, and escalation. Demo complete.

---

## 2. System Architecture

### Agent Roster (5 agents + 1 orchestrator)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AEGIS ORCHESTRATOR                          │
│  (Main process — NOT an LLM agent. Pure state machine + router.)   │
│                                                                    │
│  State Store: In-memory JSON object (persisted to file each step)  │
│  Communication: Interactions API sessions per agent                │
└──────────┬──────────┬──────────┬──────────┬──────────┬─────────────┘
           │          │          │          │          │
      ┌────▼───┐ ┌────▼───┐ ┌───▼────┐ ┌──▼───┐ ┌───▼────────┐
      │PLANNER │ │LOG     │ │METRICS │ │DIAG  │ │REMEDIATOR  │
      │AGENT   │ │ANALYZER│ │AGENT   │ │AGENT │ │AGENT       │
      └────────┘ └────────┘ └────────┘ └──────┘ └────────────┘
```

### Agent Definitions

| Agent | Role | Tools / Capabilities | Model |
|---|---|---|---|
| **Planner** | Receives raw alert, outputs ordered subtask list with dependencies | `create_plan` tool (structured output) | `antigravity-preview-09-2026` |
| **LogAnalyzer** | Fetches & parses application logs for anomalies | `fetch_logs` tool (returns simulated log data), `analyze_pattern` | `antigravity-preview-09-2026` |
| **MetricsAgent** | Fetches & interprets infrastructure metrics | `fetch_metrics` tool (returns simulated time-series), `detect_anomaly` | `antigravity-preview-09-2026` |
| **Diagnostician** | Correlates findings from investigators, proposes root cause | `correlate_findings` tool, `propose_diagnosis` | `antigravity-preview-09-2026` |
| **Remediator** | Executes proposed fix in simulated sandbox | `execute_fix` tool, `verify_fix` tool | `antigravity-preview-09-2026` |

### Orchestrator (NOT an LLM — deterministic state machine)

The Orchestrator is the backbone. It is **not** an LLM agent — it is a deterministic Python/Node.js process that:
1. Manages the **Incident State Object** (see below).
2. Creates and manages **Interactions API sessions** for each agent.
3. Routes data between agents based on the current plan and state.
4. Detects failures (timeouts, error responses, failed verifications).
5. Triggers re-planning by calling the Planner Agent with updated context.
6. Emits **Server-Sent Events (SSE)** to the frontend for live updates.

> **Key design decision**: The Orchestrator is deterministic, not LLM-based, because:
> - It's faster and more reliable (no hallucination in routing logic).
> - The *agents* do the intelligent work; the orchestrator does traffic control.
> - This is a legitimate and common pattern in production multi-agent systems.
> - It makes failure detection and state tracking predictable and testable.

### Incident State Object (the "long-horizon state")

```json
{
  "incident_id": "INC-20260926-001",
  "status": "INVESTIGATING",
  "alert": {
    "type": "HIGH_LATENCY",
    "service": "api-gateway",
    "severity": "P1",
    "timestamp": "2026-09-26T10:00:00Z"
  },
  "plan": {
    "version": 1,
    "steps": [
      {"id": "S1", "agent": "LogAnalyzer", "status": "COMPLETED", "output": "..."},
      {"id": "S2", "agent": "MetricsAgent", "status": "COMPLETED", "output": "..."},
      {"id": "S3", "agent": "Diagnostician", "status": "IN_PROGRESS", "depends_on": ["S1", "S2"]},
      {"id": "S4", "agent": "Remediator", "status": "PENDING", "depends_on": ["S3"]}
    ]
  },
  "findings": {
    "log_analysis": { "anomalies": ["..."], "confidence": 0.85 },
    "metrics_analysis": { "anomalies": ["..."], "confidence": 0.92 }
  },
  "diagnosis": null,
  "remediation": { "action": null, "result": null },
  "history": [
    {"timestamp": "...", "event": "PLAN_CREATED", "detail": "..."},
    {"timestamp": "...", "event": "AGENT_STARTED", "agent": "LogAnalyzer"},
    {"timestamp": "...", "event": "AGENT_COMPLETED", "agent": "LogAnalyzer", "output_summary": "..."},
    {"timestamp": "...", "event": "FAILURE_DETECTED", "agent": "LogAnalyzer", "error": "SOURCE_TIMEOUT"},
    {"timestamp": "...", "event": "REPLAN_TRIGGERED", "reason": "LogAnalyzer failed, switching to degraded mode"}
  ],
  "plan_version_history": []
}
```

**Persistence**: JSON file on disk, updated after every state transition. Simplest thing that demonstrably works and is visible in the demo.

### Communication Flow via Interactions API

```
User clicks "Trigger Incident"
    │
    ▼
Orchestrator creates Incident State Object
    │
    ▼
Orchestrator → Interactions API → Planner Agent session
    │  (sends: alert details)
    │  (receives: structured plan with subtask list)
    ▼
Orchestrator updates state with plan, starts parallel agent sessions:
    ├── Interactions API → LogAnalyzer session (sends: log query params)
    └── Interactions API → MetricsAgent session (sends: metric query params)
    │
    │  (both run concurrently; Orchestrator polls/awaits both)
    ▼
Orchestrator collects outputs, updates state, starts:
    └── Interactions API → Diagnostician session (sends: combined findings)
    │
    ▼
Orchestrator receives diagnosis, updates state, starts:
    └── Interactions API → Remediator session (sends: diagnosis + proposed fix)
    │
    ▼
Orchestrator receives remediation result:
    ├── SUCCESS → mark RESOLVED, emit final SSE event
    └── FAILURE → re-plan (call Planner again with failure context) or ESCALATE
```

### Tech Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Agents** | Antigravity Agent via Interactions API | Required by challenge |
| **Orchestrator** | Python (FastAPI) | Best async support, team likely comfortable |
| **State** | JSON file + in-memory dict | Simplest possible; no DB setup time |
| **Frontend** | Single HTML page + vanilla JS + CSS | Fastest to build; no build tools needed |
| **Live updates** | Server-Sent Events (SSE) | Simpler than WebSockets; native browser support |
| **Hosting** | Backend: Railway / Render | Free tier, fast deploy |
| **Demo recording** | Screen capture (OBS / browser ext) | Backup if live demo flakes |

> **Assumption**: The Interactions API provides a way to create an agent session, send messages, and receive responses (synchronous or streaming). We assume Python SDK availability. If only REST, we use `httpx` directly. **This must be validated in the first 15 minutes.**

---

## 3. Failure-Injection Design

### Failure 1: "Log Source Unavailable" (Investigation-Phase Failure)

- **What happens**: The `fetch_logs` tool in LogAnalyzer returns an error (simulated timeout / 503).
- **How injected**: Boolean flag `INJECT_LOG_FAILURE` set via dashboard button. The simulated `fetch_logs` tool checks this flag and returns an error response.
- **Orchestrator detection**: LogAnalyzer session returns an error output or times out (30s timeout).
- **Recovery behavior**:
  1. Orchestrator marks step S1 (LogAnalyzer) as `FAILED` in state.
  2. Orchestrator calls Planner Agent with updated context: "LogAnalyzer failed due to source unavailability. Replan with available data only."
  3. Planner produces Plan v2: skip log analysis, proceed with Metrics-only diagnosis (degraded mode).
  4. State object records the replan event, increments plan version.
  5. Dashboard shows: ❌ LogAnalyzer failed → 🔄 Replanning → ✅ New plan created → continues.
- **Build time**: ~30 minutes.

### Failure 2: "Remediation Failed" (Action-Phase Failure)

- **What happens**: The `execute_fix` tool in Remediator returns "ROLLBACK_FAILED — deployment lock held by another process."
- **How injected**: Boolean flag `INJECT_REMEDIATION_FAILURE` set via a second dashboard button.
- **Orchestrator detection**: Remediator session returns a failure result.
- **Recovery behavior**:
  1. Orchestrator marks remediation as `FAILED` in state.
  2. Orchestrator calls Planner Agent: "Remediation failed. Propose alternative fix or escalate."
  3. Planner may propose: "Try service restart instead of rollback" (Plan v3).
  4. If second remediation also fails (max retries = 2), Orchestrator sets status to `ESCALATED` and emits "Requires Human Intervention."
  5. Dashboard shows the full failure chain with timestamps.
- **Build time**: ~30 minutes.

### Why These Two Are Sufficient

- **Failure 1** = recovery during *investigation* (mid-pipeline).
- **Failure 2** = recovery during *action* (end-of-pipeline).
- Together they show recovery at any stage, not just one hardcoded point.
- Both are **on-demand** via buttons for reliable judge demos.

---

## 4. Three-Person Work Breakdown

### Person A — "Orchestrator Swarm" (Backend + State + Integration Lead)

| Deliverable | Hour | Details |
|---|---|---|
| Interactions API spike | 0:00–0:30 | Validate API auth, test agent session, share findings with B. |
| Orchestrator skeleton | 0:30–1:30 | FastAPI: `/api/trigger-incident`, SSE `/api/events`, in-memory state, stub agent calls. |
| State management | 1:30–2:00 | Incident State Object, JSON persistence, transitions, history logging. |
| Wire real agent calls | 2:00–3:00 | Replace stubs with Interactions API calls. Parallel execution for Log+Metrics. |
| Failure detection + recovery | 3:00–3:30 | Timeout detection, error handling, replan trigger, failure flags. |
| Integration + deploy | 3:30–4:00 | Wire frontend SSE, deploy to Railway/Render. |
| Testing + buffer | 4:00–4:30 | E2E testing: happy path + both failure scenarios. |

### Person B — "Agent Swarm" (All LLM Agents + Tools + Prompts)

| Deliverable | Hour | Details |
|---|---|---|
| API spike (with A) | 0:00–0:30 | Validate Interactions API. Understand agent registration, tools, system prompts. |
| Planner Agent | 0:30–1:15 | System prompt + `create_plan` tool. Structured JSON output. Test with 2–3 alerts. |
| LogAnalyzer Agent | 1:15–1:45 | System prompt + `fetch_logs` (simulated data) + `analyze_pattern`. Failure hook. |
| MetricsAgent | 1:45–2:15 | System prompt + `fetch_metrics` (simulated data) + `detect_anomaly`. |
| Diagnostician Agent | 2:15–2:45 | System prompt + `correlate_findings` + `propose_diagnosis`. |
| Remediator Agent | 2:45–3:15 | System prompt + `execute_fix` + `verify_fix`. Failure hook. |
| Prompt tuning | 3:15–3:45 | Test all agents through Orchestrator. Tune for consistent structured output. |
| Writeup drafting | 3:45–4:30 | Draft the Kaggle writeup (technical sections). |

### Person C — "Frontend Swarm" (Dashboard + Visual Design + Demo)

| Deliverable | Hour | Details |
|---|---|---|
| HTML scaffold + design | 0:00–0:45 | `index.html` + `style.css` + `app.js`. Background gradient, glassmorphism card, fonts. |
| Agent status panel | 0:45–1:30 | Central glass card: incident status, plan steps, live status chips. Mock data first. |
| CTA buttons + failure UI | 1:30–2:00 | Primary "Trigger Incident" pill. Secondary failure inject buttons. Tech strip. |
| SSE integration | 2:00–2:30 | Connect to `/api/events`. Parse events, update UI live. Animate transitions. |
| Incident timeline | 2:30–3:00 | Scrollable timeline below main card with color-coded event history. |
| Floating agent avatars | 3:00–3:30 | Asymmetric floating elements around central card. Layered depth. |
| Integration + polish | 3:30–4:00 | Final integration, responsive check, visual bug fixes. |
| Demo recording | 4:00–4:30 | Record 2-min demo. Ensure hosted version stable. |

### UI Priority / Descope Order

| Priority | Element | Time | Cut Impact |
|---|---|---|---|
| **P0** | Glassmorphism card + status + plan steps + CTAs | 45 min | Can't demo without it |
| **P0** | SSE integration (live updates) | 30 min | Can't demo without it |
| **P1** | Incident timeline / history | 30 min | Judges lose state visibility |
| **P1** | Failure injection buttons | 15 min | Can use API calls instead |
| **P2** | Floating agent avatars | 30 min | Visual flair only |
| **P2** | Credibility strip | 10 min | Easy late add |
| **P3** | Micro-animations, hover effects | 20 min | Pure polish |
| **P3** | Serif/sans-serif font pairing | 10 min | Falls back to system font |

---

## 5. Key Decisions to Lock at 0:30

| Decision | Options | Recommendation |
|---|---|---|
| Backend language | Python (FastAPI) vs Node.js | Python — better async |
| Interactions API auth | API key vs OAuth | Determine from docs |
| Hosting platform | Railway vs Render vs Replit | Railway — fastest free deploy |
| SSE event format | Lock JSON schema | See below |
| Agent I/O contracts | Lock input/output JSON | See Architecture section |

### Proposed SSE Event Format

```json
{
  "event_type": "STATE_UPDATE",
  "timestamp": "2026-09-26T10:05:00Z",
  "incident_id": "INC-20260926-001",
  "data": {
    "status": "INVESTIGATING",
    "active_agent": "LogAnalyzer",
    "plan_version": 1,
    "steps": [],
    "history": [],
    "message": "LogAnalyzer is scanning application logs for anomalies..."
  }
}
```

---

## 6. "Done" Checklist at Hour 5:00

- [ ] GitHub repo is public with README, architecture diagram, setup instructions, demo link
- [ ] Hosted demo loads, "Trigger Incident" works, happy-path completes in <60s
- [ ] "Inject Log Failure" triggers visible failure → replan → degraded resolution
- [ ] "Inject Remediation Failure" triggers visible failure → retry → escalation
- [ ] Dashboard shows live agent statuses, incident timeline, state transitions
- [ ] 2-minute demo video recorded and uploaded
- [ ] Kaggle writeup submitted (≤1500 words)
- [ ] All three members can explain any part to a judge
