# AEGIS — Autonomous Emergency Grid for Incident Response & Self-healing

> **Hackathon track**: Autonomous Orchestration with Managed Agents
> **Stack**: Antigravity Agent (`antigravity-preview-09-2026`) · FastAPI · React + Vite
> **Deploy**: Render (backend) + Netlify (frontend) — or Cloud Run + Firebase Hosting (GCP)

---

## What It Does

AEGIS is a live incident-response system. A user clicks **"Trigger Incident"** on the dashboard; five specialist AI agents coordinate to investigate, diagnose, and fix the problem autonomously — replanning when something fails and escalating to a human when the system reaches its safety limits.

```
Browser  ──SSE──►  Firebase Hosting  ──/api/**──►  Cloud Run (FastAPI)
                                                         │
                                                   Orchestrator
                                                   (state machine)
                                              ┌─────────┼─────────┐
                                              ▼         ▼         ▼
                                         Planner  LogAnalyzer  MetricsAgent
                                                         │
                                                   Diagnostician
                                                         │
                                                    Remediator ◄── Guardrail
```

### The Five Agents

| Agent | Capability | Tools |
|---|---|---|
| **Planner** | Multi-turn planning loop | `create_plan` |
| **LogAnalyzer** | Code execution (Python sandbox) | `fetch_logs`, `run_python_analysis`, `analyze_pattern` |
| **MetricsAgent** | Code execution (Python sandbox) | `fetch_metrics`, `run_python_analysis`, `detect_anomaly` |
| **Diagnostician** | Multi-turn + web search | `correlate_findings`, `web_search`, `propose_diagnosis` |
| **Remediator** | Sandbox + file management | `execute_fix`, `run_bash_command`, `write_fix_report`, `verify_fix` |

All tools return **simulated data** — no external APIs required. Failure scenarios are injected on demand via dashboard buttons.

---

## Repo Structure

```
google_deepmind/
├── backend/                  Python / FastAPI backend
│   ├── main.py               FastAPI routes: /api/trigger-incident, /api/events (SSE),
│   │                         /api/inject-failure, /api/state, /api/approve-fix
│   ├── orchestrator.py       Deterministic state machine — NOT an LLM
│   ├── state.py              Incident state store + telemetry fields
│   ├── guardrails.py         Hard code-enforced Remediator safety gate
│   ├── requirements.txt
│   ├── agents/
│   │   ├── interface.py      AgentBackend protocol (PlanStep, AgentResult, PlanResult)
│   │   └── base.py           RealBackend — Interactions API implementation
│   ├── tools/
│   │   └── simulated.py      All tool handlers + failure injection dispatch table
│   └── eval/
│       ├── run_eval.py       Golden-scenario eval harness (82/82 checks)
│       └── fixtures/         8 JSON scenario fixtures
├── frontend/                 React + Vite + Tailwind dashboard
│   ├── src/App.jsx           Main dashboard component
│   └── src/components/       LightRays and other UI components
├── doc/                      Architecture, project plan, handover docs, deployment guide
│   ├── AGENTS.md             Master agent instructions (paste into every AI session)
│   ├── ARCHITECTURE.md       Full system spec + integration contracts
│   ├── DEPLOYMENT.md         Cloud Run + Firebase Hosting deployment guide
│   ├── HANDOVER_PERSON_A.md  Orchestrator + backend
│   ├── HANDOVER_PERSON_B.md  Agent swarm + tools + eval + guardrails
│   └── HANDOVER_PERSON_C.md  Frontend + demo
└── for-submission/
    └── writeup.md            Kaggle competition writeup (~1450 words)
```

---

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
# or: source .venv/bin/activate                  # macOS/Linux
pip install -r requirements.txt

# Copy and fill in your API key
cp .env.example .env   # set ANTIGRAVITY_API_KEY (or GOOGLE_API_KEY)

# Run with stub backend (no API key needed)
uvicorn backend.main:app --reload --port 8000

# Run with real Interactions API
USE_REAL=1 uvicorn backend.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

### Run the eval harness

```bash
# From repo root — no API key needed, runs against StubBackend
python -m backend.eval.run_eval

# Against a live server
python -m backend.eval.run_eval --live

# Single scenario
python -m backend.eval.run_eval --fixture sc04
```

Expected output: **82/82 checks passing**

---

## API Reference

| Method | Endpoint | Body | Description |
|---|---|---|---|
| `POST` | `/api/trigger-incident` | `{"alert_type": "HIGH_LATENCY", "service": "api-gateway", "severity": "P1"}` | Start a new incident |
| `GET` | `/api/events` | — | SSE stream of orchestration events |
| `GET` | `/api/state` | — | Full incident state snapshot (polling fallback) |
| `POST` | `/api/inject-failure` | `{"failure_type": "LOG_SOURCE_UNAVAILABLE"}` | Inject a failure scenario |
| `POST` | `/api/approve-fix` | — | Human approval for guardrail-blocked actions |
| `GET` | `/api/health` | — | Liveness check |

**Failure types**: `LOG_SOURCE_UNAVAILABLE` · `REMEDIATION_FAILED` · `NONE` (clears all)

---

## Differentiating Features

### 1. Remediator Guardrails — [`backend/guardrails.py`](backend/guardrails.py)

Hard, code-enforced safety gate before every `execute_fix` call. **Not a prompt instruction** — deterministic Python that cannot be overridden by agent output.

Two rules (in order):
- **Action allowlist**: only `rollback` and `restart` may auto-execute. Any other action (`config_change`, `scale_up`, etc.) requires a human to click "Approve Fix?" in the UI.
- **Confidence threshold**: diagnosis confidence must be `≥ 0.70`. Below this, the system halts at `AWAITING_APPROVAL` and waits for human approval (5-minute timeout, then escalates).

```python
guard = RemediatorGuardrail()
result = guard.check(action="config_change", confidence=0.95)
# → {"allowed": False, "reason": "action_not_in_allowlist", ...}
```

### 2. Golden-Scenario Eval Harness — [`backend/eval/`](backend/eval/)

8 scripted scenarios replay every orchestration path against `StubBackend` and assert **82 specific conditions** — final status, tool call sequence, event presence, confidence bounds, plan version count, and guardrail behaviour.

```
python -m backend.eval.run_eval
# Result: 82/82 checks | ALL PASSING
```

Scenarios covered:

| ID | Scenario | Final Status |
|---|---|---|
| SC-01 | Happy path — HIGH_LATENCY | RESOLVED |
| SC-02 | Happy path — OOM_CRASH | RESOLVED |
| SC-03 | Log source unavailable (degraded replan) | RESOLVED |
| SC-04 | Remediation fails (max attempts) | ESCALATED |
| SC-05 | Both failures (degraded + failed remediation) | ESCALATED |
| SC-06 | P3 minor alert | RESOLVED |
| SC-07 | Guardrail: disallowed action | AWAITING_APPROVAL |
| SC-08 | Guardrail: low-confidence diagnosis | AWAITING_APPROVAL |

### 3. Per-Incident Telemetry — [`backend/state.py`](backend/state.py)

Every SSE event includes a `telemetry` object the frontend renders as a live cost/latency panel:

```json
{
  "telemetry": {
    "started_at": "2026-09-26T09:01:00Z",
    "total_wall_clock_ms": 4231,
    "agent_timings": {
      "LogAnalyzer": {"wall_clock_ms": 1240},
      "MetricsAgent": {"wall_clock_ms": 1180}
    },
    "plan_versions": 2,
    "guardrail_triggered": false
  }
}
```

### 4. Thinking-Mode Switch

Planner and Diagnostician have dual system prompts selected at runtime:
- **P1/P2** (critical) → multi-turn planning loop + mandatory web search
- **P3/P4** (minor) → single-shot fast mode

```python
from backend.agents import set_thinking_mode
set_thinking_mode(severity="P1")  # → {"Planner": True, "Diagnostician": True}
```

### 5. Deterministic Orchestrator

The orchestrator is a plain Python `async` state machine with hard-coded limits:

| Limit | Value | Where enforced |
|---|---|---|
| Max plan versions | 3 | `state.py:MAX_PLAN_VERSIONS` |
| Max remediation attempts | 2 | `state.py:MAX_REMEDIATION_ATTEMPTS` |
| Incident wall-clock limit | 240s | `orchestrator.py:INCIDENT_WALL_CLOCK_LIMIT` |
| Agent timeout | 30s (stub) / 150s (real) | `orchestrator.py:_call()` |

The orchestrator never makes LLM calls and never hallucinates a routing decision.

---

## Incident Lifecycle

```
PLANNING
   │
   ▼ Planner Agent
INVESTIGATING ──► [parallel] LogAnalyzer + MetricsAgent
   │                              │
   │  log fails?                  │
   ├──────────────► REPLANNING ──►┤
   │                              │
   ▼                              ▼
DIAGNOSING ◄── Diagnostician (correlates both findings)
   │
   │  confidence < 0.70 OR action not in allowlist?
   ├──────────────────────────────► AWAITING_APPROVAL ──► (human click) ──► REMEDIATING
   │
   ▼
REMEDIATING ── Remediator (execute_fix → verify_fix)
   │
   │  fix fails?
   ├──────────────► REPLANNING ──► REMEDIATING (attempt 2)
   │                                   │
   │                            still fails?
   │                                   ▼
   │                               ESCALATED
   ▼
RESOLVED
```

---

## Deployment

Two options are both configured in the repo:

### Option A — Render + Netlify (free tier, fastest)

Config files: [`render.yaml`](render.yaml), [`netlify.toml`](netlify.toml)

1. **Backend → Render**: connect the GitHub repo at [render.com](https://render.com), pick "New Web Service" — `render.yaml` is auto-detected. Set `GEMINI_API_KEY` in the Render dashboard. `USE_REAL=1` is already in the config.

2. **Frontend → Netlify**: connect the repo at [netlify.com](https://netlify.com) — `netlify.toml` is auto-detected. After Render gives you a URL, update the proxy target in `netlify.toml`:
   ```toml
   to = "https://aegis-backend-xxxx.onrender.com/api/:splat"
   ```
   Redeploy — `/api/*` proxies to Render, no CORS issues.

### Option B — Cloud Run + Firebase Hosting (GCP)

Config files: [`Dockerfile`](Dockerfile), [`firebase.json`](firebase.json), [`doc/DEPLOYMENT.md`](doc/DEPLOYMENT.md)

```bash
# Backend → Cloud Run
gcloud run deploy aegis-backend \
  --source . \
  --region us-central1 \
  --set-env-vars USE_REAL=1 \
  --set-secrets GEMINI_API_KEY=aegis-api-key:latest \
  --allow-unauthenticated

# Frontend → Firebase (firebase.json rewrites /api/** to Cloud Run — no CORS needed)
cd frontend && npm run build
firebase deploy --only hosting
```

See [`doc/DEPLOYMENT.md`](doc/DEPLOYMENT.md) for the full GCP setup guide.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes (real mode) | Antigravity / Google AI API key |
| `USE_REAL` | No | Set to `1` to use `RealBackend` (Interactions API). Default: `StubBackend` |
| `PORT` | No | HTTP port (injected by Cloud Run / Render). Default: `8000` |

Copy `.env.example` to `.env` for local development (never commit `.env`).

---

## Development Notes

- **StubBackend vs RealBackend**: `main.py` reads `USE_REAL=1` env var to select the backend. Everything else is identical — the orchestrator only calls the `AgentBackend` protocol defined in [`backend/agents/interface.py`](backend/agents/interface.py).
- **Adding a new tool**: add to `backend/tools/simulated.py:_HANDLERS`, update the relevant agent's `TOOLS` list, add a fixture assertion in `backend/eval/fixtures/`.
- **Adjusting guardrail thresholds**: edit `ALLOWED_ACTIONS` or `AUTO_EXECUTE_THRESHOLD` in [`backend/guardrails.py`](backend/guardrails.py). The eval harness (SC-07, SC-08) will catch regressions automatically.

---

## Team

| Person | Role | Deliverables |
|---|---|---|
| **A** | Orchestrator + Backend | `backend/orchestrator.py`, `backend/state.py`, `backend/main.py`, `backend/agents/base.py`, deployment |
| **B** | Agent Swarm + Eval + Safety | `backend/guardrails.py`, `backend/eval/`, agent prompts + tool schemas, `for-submission/writeup.md` |
| **C** | Frontend + Demo | `frontend/`, demo video, screenshots |
