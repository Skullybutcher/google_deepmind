# AEGIS — Master Agent Instructions

> **How to use this file**: This is the top-level instruction set for ALL AI coding agents working on this project.
> Paste this file (or reference it) as context when starting ANY new agent session across the team.
> For person-specific agent instructions, see: `HANDOVER_PERSON_A.md`, `HANDOVER_PERSON_B.md`, `HANDOVER_PERSON_C.md`.

---

## Project Identity

- **Project**: AEGIS — Autonomous Emergency Grid for Incident Response & Self-healing
- **Track**: Autonomous Orchestration with Managed Agents (Hackathon)
- **Stack**: Antigravity Agent (`antigravity-preview-09-2026`) via Interactions API
- **Deadline**: 5 hours from kickoff. Every minute counts.
- **Repo structure**: `aegis/backend/`, `aegis/frontend/`, `docs/`

---

## What We're Building

A **multi-agent incident response system** with a web dashboard. When a user clicks "Trigger Incident":

1. **Planner Agent** decomposes the alert into subtasks
2. **LogAnalyzer Agent** + **MetricsAgent** investigate in parallel
3. **Diagnostician Agent** correlates findings into a root cause
4. **Remediator Agent** executes the fix in a simulated sandbox
5. **Orchestrator** (deterministic Python state machine, NOT an LLM) tracks state, detects failures, and triggers re-planning

All tools return **simulated data** — no external APIs. Failures are injected via dashboard buttons.

---

## Architecture Summary

```
Frontend (HTML/JS) ──SSE──► FastAPI Backend
                              │
                         Orchestrator (state machine)
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
               Planner   LogAnalyzer  MetricsAgent
                              │
                         Diagnostician
                              │
                         Remediator
```

- **Communication**: Orchestrator ↔ Agents via Interactions API
- **State**: In-memory Python dict + JSON file persistence
- **Live updates**: Server-Sent Events (SSE) from backend to frontend
- **Failure injection**: Boolean flags checked by simulated tools

---

## Coding Standards (ALL Agents Must Follow)

### Python (Backend)
- Python 3.11+, FastAPI, asyncio
- Type hints on all functions
- `async def` for all agent-calling functions
- JSON responses with consistent schemas
- Error handling: never crash — catch, log, and return structured error

### JavaScript (Frontend)
- Vanilla JS — NO frameworks, NO build tools
- Single `index.html` + `style.css` + `app.js`
- `EventSource` for SSE, `fetch()` for REST
- All DOM updates via `document.getElementById()` or `querySelector()`

### Shared Conventions
- UTC timestamps everywhere: `datetime.utcnow().isoformat() + "Z"`
- Incident IDs: `INC-YYYYMMDD-NNN` format
- Agent names: `Planner`, `LogAnalyzer`, `MetricsAgent`, `Diagnostician`, `Remediator` (exact case)
- Status values: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `ESCALATED`, `RESOLVED`

---

## Integration Contracts (DO NOT CHANGE WITHOUT TEAM AGREEMENT)

### SSE Event Format (Backend → Frontend)
```json
{
  "event_type": "STATE_UPDATE",
  "timestamp": "2026-09-26T10:05:00Z",
  "incident_id": "INC-20260926-001",
  "data": {
    "status": "INVESTIGATING",
    "active_agent": "LogAnalyzer",
    "plan_version": 1,
    "steps": [
      {"id": "S1", "agent": "LogAnalyzer", "status": "IN_PROGRESS", "description": "...", "output": null},
      {"id": "S2", "agent": "MetricsAgent", "status": "PENDING", "description": "...", "output": null}
    ],
    "history": [
      {"timestamp": "...", "event": "PLAN_CREATED", "detail": "..."}
    ],
    "message": "LogAnalyzer is scanning application logs..."
  }
}
```

### Event Types
`INCIDENT_CREATED` | `PLAN_CREATED` | `AGENT_STARTED` | `AGENT_COMPLETED` | `AGENT_FAILED` | `REPLAN_TRIGGERED` | `PLAN_UPDATED` | `RESOLVED` | `ESCALATED`

### REST Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/trigger-incident` | Start a new incident |
| POST | `/api/inject-failure` | Inject a failure scenario |
| GET | `/api/events` | SSE stream |
| GET | `/api/state` | Current state (polling fallback) |
| GET | `/api/health` | Health check |

---

## Hard Limits (Orchestrator Constants)

```python
MAX_PLAN_VERSIONS = 3
MAX_AGENT_RETRIES = 2
MAX_REMEDIATION_ATTEMPTS = 2
AGENT_TIMEOUT_SECONDS = 30
MAX_INCIDENT_DURATION = 120
SAFE_PARSE_RETRIES = 1
```

---

## Key Files Reference

| File | Owner | Purpose |
|---|---|---|
| `backend/main.py` | Person A | FastAPI app, routes, SSE |
| `backend/orchestrator.py` | Person A | State machine, agent routing |
| `backend/state.py` | Person A | State model, persistence |
| `backend/agents/base.py` | Person A + B | Base agent wrapper |
| `backend/agents/planner.py` | Person B | Planner agent definition |
| `backend/agents/log_analyzer.py` | Person B | LogAnalyzer agent |
| `backend/agents/metrics_agent.py` | Person B | MetricsAgent |
| `backend/agents/diagnostician.py` | Person B | Diagnostician agent |
| `backend/agents/remediator.py` | Person B | Remediator agent |
| `backend/tools/simulated.py` | Person B | All simulated tool responses |
| `frontend/index.html` | Person C | Dashboard HTML |
| `frontend/style.css` | Person C | All styles |
| `frontend/app.js` | Person C | SSE handling, DOM updates |

---

## Do NOT Do

- ❌ Add external API dependencies (everything is simulated)
- ❌ Use a database (JSON file persistence only)
- ❌ Add npm/webpack/build tooling to frontend
- ❌ Change the SSE event format without team agreement
- ❌ Add features after hour 3:00
- ❌ Make the Orchestrator an LLM agent (it's a deterministic state machine)
- ❌ Use `time.sleep()` — use `asyncio.sleep()` for any delays
