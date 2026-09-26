# AEGIS — Master Handover Document

> **How to use this file**: Read this FIRST for the full picture. Then read YOUR person-specific handover file
> (`HANDOVER_PERSON_A.md`, `HANDOVER_PERSON_B.md`, or `HANDOVER_PERSON_C.md`) for your exact tasks.
> Share this file + the person-specific file with your AI agents as context.

---

## Quick Status Board

| Stream | Owner | Delivers | Depends On |
|---|---|---|---|
| **Orchestrator + Backend** | Person A | FastAPI server, state machine, SSE, deployment | Interactions API access (spike at 0:00) |
| **All 5 Agents + Tools** | Person B | Agent definitions, system prompts, tools, simulated data, writeup | API spike results from Person A |
| **Frontend Dashboard** | Person C | HTML/CSS/JS dashboard, SSE consumption, demo recording | SSE event format (locked at 0:30) |

---

## Critical Milestones (Everyone Must Know)

| Time | Milestone | Who | Gate? |
|---|---|---|---|
| **0:30** | API spike complete, contracts locked | A + B | 🚨 YES — if API fails, activate fallback |
| **2:00** | Mini-integration: 1 real agent + SSE test | A + B + C | 🔄 5-min check |
| **3:00** | Feature freeze — NO new features | ALL | 🚨 YES — enforced |
| **3:30** | Full integration + deploy | A + C | 🚨 YES — if deploy fails, re-run `gcloud run deploy` |
| **3:45** | Writeup draft started | B | Non-negotiable |
| **4:00** | Demo video recording started | C | Non-negotiable |
| **4:50** | All deliverables submitted | ALL | Final |

---

## What Each Person Delivers to the Others

### Person A → Person B
- Working `base.py` agent wrapper (Interactions API call function) — **by hour 1:00**
- Orchestrator with stub agent functions (so B can test agents in isolation first) — **by hour 1:30**
- Live orchestrator accepting real agent calls — **by hour 2:00**

### Person A → Person C
- SSE endpoint running at `localhost:8000/api/events` — **by hour 1:30**
- Mock SSE events emitting every 3 seconds for frontend testing — **by hour 1:30**
- Deployed public URL — **by hour 3:30**

### Person B → Person A
- API spike findings (exact SDK calls, auth method, tool registration) — **by hour 0:30**
- Agent definition files (`planner.py`, etc.) with system prompts and tool schemas — **by hour 3:00**
- `tools/simulated.py` with all mock tool responses + failure injection hooks — **by hour 3:00**

### Person B → Person C
- Nothing directly (all agent output flows through Person A's orchestrator/SSE)
- But: agent names, status values, and output formats are in `AGENTS.md` — use those for mock data

### Person C → Person A
- Nothing until integration at hour 3:30 (frontend is standalone until then)
- Frontend files (`index.html`, `style.css`, `app.js`) for static serving — **by hour 3:30**

### Person C → Person B
- Demo video — **by hour 4:15** (B embeds link in writeup)

---

## Integration Sequence (Hour 3:30)

```
Step 1: Person A deploys backend to Cloud Run
Step 2: Person A shares Firebase Hosting URL with Person C
Step 3: Person C builds React app (`npm run build`) and deploys via `firebase deploy`
Step 4: Firebase Hosting rewrites `/api/**` to Cloud Run (same origin — no CORS issues)
Step 5: Everyone tests:
         - Happy path (Trigger Incident → all agents → RESOLVED)
         - Failure 1 (Inject Log Failure → replan → degraded resolution)
         - Failure 2 (Inject Remediation Failure → retry → escalation)
Step 6: Person C records demo video
Step 7: Person B finishes writeup with demo link + repo link
```

---

## Fallback Plan (If Integration Breaks at 3:30)

| Problem | Fallback | Owner |
|---|---|---|
| Backend won't deploy | Re-run `gcloud run deploy --source .` (usually faster than debugging) | A |
| SSE not working through proxy | Verify Firebase rewrite; fallback to polling (`GET /api/state` every 2s) | C |
| Agents returning garbage | Hardcode agent responses for demo | B |
| Frontend can't connect to backend | Replay mode (canned SSE events from JSON file) | C |
| Time running out (past 4:00) | Use whatever works, record video of current state | C |

---

## Communication Protocol During Build

- **Slack/Discord channel** for quick messages
- **"BLOCKER"** prefix for anything that's blocking progress
- **"HEADS UP"** prefix for non-blocking FYI
- **At hour 2:00**: Everyone stops for 5-minute sync (mini-integration check)
- **At hour 3:00**: Everyone stops for 2-minute sync (feature freeze confirmation)

---

## File/Folder Structure (Create This at Kickoff)

```
aegis/
├── backend/
│   ├── main.py              # Person A
│   ├── orchestrator.py      # Person A
│   ├── state.py             # Person A
│   ├── agents/
│   │   ├── __init__.py      # Person B
│   │   ├── base.py          # Person A (shared)
│   │   ├── planner.py       # Person B
│   │   ├── log_analyzer.py  # Person B
│   │   ├── metrics_agent.py # Person B
│   │   ├── diagnostician.py # Person B
│   │   └── remediator.py    # Person B
│   ├── tools/
│   │   ├── __init__.py      # Person B
│   │   └── simulated.py     # Person B
│   ├── requirements.txt     # Person A
│   └── Procfile             # Person A
├── frontend/
│   ├── index.html           # Person C
│   ├── style.css            # Person C
│   └── app.js               # Person C
├── README.md                # Person A
└── .gitignore               # Person A
```
