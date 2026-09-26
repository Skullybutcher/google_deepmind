# 🔧 Person A — Orchestrator Swarm Handover

> **How to use this file**: You are Person A. This file contains EVERYTHING you need to build your part.
> 1. Read `AGENTS.md` first for project-wide coding standards and contracts.
> 2. Read THIS file for your exact tasks, deliverables, and timeline.
> 3. Paste `AGENTS.md` + this file as context into your AI coding agents.
> 4. You can run multiple agents in parallel — assign each one a file/task from the table below.

---

## Your Role

**Orchestrator Swarm Lead** — You own the backend server, the deterministic state machine, SSE streaming, failure detection, and deployment. You are also the **integration lead** — you coordinate the merge at hour 3:30.

---

## Your Files (You Create These)

| File | Purpose | Priority |
|---|---|---|
| `backend/main.py` | FastAPI app: routes, SSE endpoint, CORS, static file serving | P0 |
| `backend/orchestrator.py` | State machine: agent routing, failure detection, replan logic | P0 |
| `backend/state.py` | IncidentState model, JSON persistence, history logging | P0 |
| `backend/agents/base.py` | Base agent wrapper: Interactions API call function | P0 |
| `backend/requirements.txt` | Dependencies: `fastapi`, `uvicorn`, `httpx`, `sse-starlette` | P0 |
| `backend/Dockerfile` | Cloud Run container: `FROM python:3.11-slim`, `CMD uvicorn` | P1 |
| `README.md` | Project description, setup instructions, demo link | P1 |
| `.gitignore` | `.env`, `__pycache__`, `state_*.json`, `node_modules` | P2 |

---

## Hour-by-Hour Tasks

### Hour 0:00–0:30 — API Spike (With Person B)

**Goal**: Validate the Interactions API works. This is the most critical 30 minutes.

- [ ] Get API key / auth token set up
- [ ] Create a test agent session via the Interactions API
- [ ] Register a test tool with the agent
- [ ] Send a message, get a structured response
- [ ] Document the exact Python code that works
- [ ] Share the working snippet with Person B immediately
- [ ] Identify: Does `previous_interaction_id` work as expected?

**If API fails**: See RISKS.md Risk 1 — decide on fallback by 0:30.

**Share with team by 0:30**:
```python
# WORKING EXAMPLE — paste this in the team channel
import httpx

async def call_agent(agent_id, messages, tools, previous_interaction_id=None):
    response = await client.post(
        f"{API_BASE}/interactions",
        json={
            "agent_id": agent_id,
            "model": "antigravity-preview-09-2026",
            "messages": messages,
            "tools": tools,
            "previous_interaction_id": previous_interaction_id,
        },
        headers={"Authorization": f"Bearer {API_KEY}"}
    )
    return response.json()
```

### Hour 0:30–1:30 — Orchestrator Skeleton

**Goal**: Working FastAPI server with all endpoints, SSE streaming, and stub agent calls.

**`main.py`** must have:
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="AEGIS")

# CORS — allow all origins for hackathon
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Routes
@app.post("/api/trigger-incident")      # → starts orchestrator flow
@app.post("/api/inject-failure")         # → sets failure flags
@app.get("/api/events")                  # → SSE stream
@app.get("/api/state")                   # → current state JSON
@app.get("/api/health")                  # → {"status": "ok"}

# Static files (for serving frontend later)
# app.mount("/", StaticFiles(directory="../frontend", html=True))
```

**SSE streaming pattern**:
```python
async def event_generator(request: Request):
    while True:
        if await request.is_disconnected():
            break
        if state_has_new_events():
            event = get_latest_event()
            yield {
                "event": "state_update",
                "data": json.dumps(event)
            }
        await asyncio.sleep(0.5)

@app.get("/api/events")
async def sse_events(request: Request):
    return EventSourceResponse(event_generator(request))
```

**Stub agent calls** (return mock data until Person B's agents are ready):
```python
async def call_planner(alert):
    # STUB — replace with real Interactions API call at hour 2:00
    return {
        "steps": [
            {"id": "S1", "agent": "LogAnalyzer", "description": "Analyze logs", "depends_on": []},
            {"id": "S2", "agent": "MetricsAgent", "description": "Check metrics", "depends_on": []},
            {"id": "S3", "agent": "Diagnostician", "description": "Correlate findings", "depends_on": ["S1", "S2"]},
            {"id": "S4", "agent": "Remediator", "description": "Execute fix", "depends_on": ["S3"]}
        ],
        "reasoning": "Standard investigation plan"
    }
```

### Hour 1:30–2:00 — State Management

**`state.py`** must implement:
```python
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json

@dataclass
class IncidentState:
    incident_id: str
    status: str = "PLANNING"  # PLANNING|INVESTIGATING|DIAGNOSING|REMEDIATING|RESOLVED|ESCALATED
    alert: dict = field(default_factory=dict)
    plan: dict = field(default_factory=dict)
    plan_version: int = 1
    findings: dict = field(default_factory=dict)
    diagnosis: dict = None
    remediation: dict = None
    history: list = field(default_factory=list)
    plan_version_history: list = field(default_factory=list)
    interaction_ids: dict = field(default_factory=dict)  # agent_name → last interaction_id

    def add_event(self, event_type: str, **kwargs):
        self.history.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event_type,
            **kwargs
        })

    def persist(self):
        with open(f"state_{self.incident_id}.json", "w") as f:
            json.dump(asdict(self), f, indent=2, default=str)
```

### Hour 2:00–3:00 — Wire Real Agent Calls

- [ ] Replace `call_planner()` stub with real Interactions API call
- [ ] Replace `call_log_analyzer()` stub
- [ ] Replace `call_metrics_agent()` stub
- [ ] Replace `call_diagnostician()` stub
- [ ] Replace `call_remediator()` stub
- [ ] Implement parallel execution: `asyncio.gather(call_log_analyzer(), call_metrics_agent())`
- [ ] Implement `safe_parse()` wrapper for all agent responses

### Hour 3:00–3:30 — Failure Detection + Recovery

**`orchestrator.py`** failure logic:
```python
# Constants
MAX_PLAN_VERSIONS = 3
MAX_AGENT_RETRIES = 2
MAX_REMEDIATION_ATTEMPTS = 2
AGENT_TIMEOUT_SECONDS = 30

async def run_agent_with_timeout(agent_call, timeout=AGENT_TIMEOUT_SECONDS):
    try:
        return await asyncio.wait_for(agent_call, timeout=timeout)
    except asyncio.TimeoutError:
        return {"status": "error", "error_code": "TIMEOUT", "message": f"Agent timed out after {timeout}s"}

async def handle_agent_failure(state, failed_agent, error):
    state.add_event("AGENT_FAILED", agent=failed_agent, error=str(error))
    if state.plan_version < MAX_PLAN_VERSIONS:
        state.add_event("REPLAN_TRIGGERED", reason=f"{failed_agent} failed: {error}")
        new_plan = await call_planner_replan(state)
        state.plan_version += 1
        state.plan = new_plan
        state.add_event("PLAN_UPDATED", plan_version=state.plan_version)
    else:
        state.status = "ESCALATED"
        state.add_event("ESCALATED", reason="Max replan attempts exceeded")
```

### Hour 3:30–4:00 — Integration + Deploy (Cloud Run + Firebase)

- [ ] Create `Dockerfile` in `backend/` (see `DEPLOYMENT.md`)
- [ ] Deploy backend: `gcloud run deploy aegis-backend --source . --region us-central1 --allow-unauthenticated --set-secrets ANTIGRAVITY_API_KEY=ANTIGRAVITY_API_KEY:latest --min-instances=1 --timeout=300`
- [ ] Set env vars: `ANTIGRAVITY_API_BASE_URL`, `CORS_ORIGINS=*`
- [ ] Verify `/api/health` returns 200 on the Cloud Run URL
- [ ] Person C builds React: `npm run build` → `firebase deploy --only hosting`
- [ ] Verify Firebase rewrite (`/api/**` → Cloud Run) works with SSE
- [ ] Share Firebase Hosting URL (`your-project.web.app`) with team
- [ ] **Fallback**: If Cloud Run deploy fails, re-run `gcloud run deploy --source .` (usually faster than debugging). Keep ngrok as last resort.

### Hour 4:00–4:30 — Testing + README

- [ ] Run happy path end-to-end through public URL
- [ ] Run Failure 1 (Log Source Unavailable) end-to-end
- [ ] Run Failure 2 (Remediation Failed) end-to-end
- [ ] Write README.md (description, architecture, setup, demo link)
- [ ] Final `git push`

---

## What You Receive From Others

| From | What | When |
|---|---|---|
| Person B | API spike findings (auth method, SDK calls) | 0:30 |
| Person B | Agent files (`planner.py`, `log_analyzer.py`, etc.) | 2:00–3:00 (rolling) |
| Person B | `tools/simulated.py` with mock data + failure hooks | 2:30 |
| Person C | Frontend files for React build + Firebase deploy | 3:30 |

## What You Deliver To Others

| To | What | When |
|---|---|---|
| Person B | Working `base.py` agent wrapper | 1:00 |
| Person B | Orchestrator with stubs (for agent testing) | 1:30 |
| Person C | SSE endpoint emitting mock events | 1:30 |
| Person C | Deployed Cloud Run URL + Firebase Hosting URL | 3:30 |
| ALL | README.md with demo link | 4:30 |
