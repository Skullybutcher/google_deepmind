# AEGIS — Hour-by-Hour Timeline

> 5 hours total. 3 people in parallel. All times are wall-clock offsets from kickoff.

---

## Hour 0:00 – 0:30 | SPIKE & CONTRACTS (All 3 Together)

**Goal**: Validate the Interactions API works, lock all integration contracts, assign roles.

| Person | Task | Output |
|---|---|---|
| **A** | Interactions API spike: auth, create agent session, send message, get response | Working code snippet; paste in Slack/Discord |
| **B** | (With A) Test tool registration, system prompt attachment, structured output | Confirmed: tools work / don't work; fallback plan if needed |
| **C** | Set up repo (GitHub), create folder structure (`/backend`, `/frontend`, `/docs`), init `index.html` with Google Fonts loaded | Repo URL shared with team |
| **All** | Lock SSE event format, agent I/O contracts, hosting choice | Shared doc / pinned message with schemas |

> **🚨 GATE**: By 0:30, the team must have a working agent "hello world" OR activate fallback (direct SDK calls).

---

## Hour 0:30 – 1:00 | FOUNDATION BUILD (Parallel)

| Person A (Orchestrator) | Person B (Agents) | Person C (Frontend) |
|---|---|---|
| FastAPI skeleton: `/api/trigger-incident`, `/api/events` (SSE), `/api/inject-failure` | Planner Agent: system prompt, `create_plan` tool, test with "HIGH_LATENCY" alert | HTML scaffold: background gradient (soft mint→gray), glassmorphism main card, Google Fonts (Playfair Display + Inter) |
| In-memory state dict, stub agent functions returning mock data | Test Planner produces valid JSON plan with subtask IDs, agent assignments, dependencies | Basic layout: centered glass card, heading with serif font, body area for status |

---

## Hour 1:00 – 1:30 | CORE BUILD (Parallel)

| Person A (Orchestrator) | Person B (Agents) | Person C (Frontend) |
|---|---|---|
| State transition logic: PLANNING → INVESTIGATING → DIAGNOSING → REMEDIATING → RESOLVED | LogAnalyzer Agent: `fetch_logs` tool (with hardcoded realistic log data), `analyze_pattern` tool | Agent status panel inside glass card: 5 rows (one per agent), status chips (⏳→🔄→✅→❌) |
| JSON file persistence: write state to disk after each transition | Test LogAnalyzer in isolation: receives log query, returns structured anomaly report | "Trigger Incident" primary pill button (high-contrast, solid fill) |
| SSE event emitter: push state updates to connected clients | | |

---

## Hour 1:30 – 2:00 | CORE BUILD (Continued)

| Person A (Orchestrator) | Person B (Agents) | Person C (Frontend) |
|---|---|---|
| Orchestrator flow: Planner → parallel (LogAnalyzer + MetricsAgent) → Diagnostician → Remediator | MetricsAgent: `fetch_metrics` tool (simulated CPU/memory/latency time-series), `detect_anomaly` tool | Failure injection buttons: "Inject: Log Failure" + "Inject: Remediation Failure" (outline style, secondary) |
| (Still using stubs, but flow logic is complete) | Diagnostician Agent: `correlate_findings` tool, takes combined findings as input | Tech credibility strip: "Powered by Antigravity Agent · Interactions API · FastAPI · SSE" |

> **🔄 MINI-INTEGRATION CHECK at 2:00**: Person A runs orchestrator with one real agent (Planner). Person C tests SSE connection to Person A's local server. 5-minute check — if broken, identify the gap and continue building.

---

## Hour 2:00 – 2:30 | WIRING (Parallel)

| Person A (Orchestrator) | Person B (Agents) | Person C (Frontend) |
|---|---|---|
| Replace Planner stub with real Interactions API call | Remediator Agent: `execute_fix` tool (simulated sandbox), `verify_fix` tool | SSE integration: `EventSource` in JS, parse events, update status chips in real-time |
| Replace LogAnalyzer stub with real API call | Add failure injection hooks to `fetch_logs` and `execute_fix` tools | Animate status transitions: fade-in new status, color change (gray→blue→green / red) |
| Replace MetricsAgent stub with real API call | | |

---

## Hour 2:30 – 3:00 | WIRING + FEATURES (Parallel)

| Person A (Orchestrator) | Person B (Agents) | Person C (Frontend) |
|---|---|---|
| Replace Diagnostician + Remediator stubs | Test all 5 agents end-to-end through orchestrator (happy path) | Incident timeline: scrollable log below main card, color-coded events |
| Implement parallel execution (asyncio.gather for Log + Metrics) | Fix any prompt issues (agents returning bad JSON, wrong format) | Each timeline entry: timestamp, event type badge, detail text |
| `/api/inject-failure` endpoint (sets flags) | | |

> **🚨 NO NEW FEATURES AFTER 3:00. Only integration, testing, fixing, polish.**

---

## Hour 3:00 – 3:30 | FAILURE HANDLING + INTEGRATION

| Person A (Orchestrator) | Person B (Agents) | Person C (Frontend) |
|---|---|---|
| Implement failure detection: timeout handler, error response parser | Support Person A with replan prompt engineering: "Given LogAnalyzer failed, create a degraded plan..." | Floating agent avatars (if time): small cards around main panel with agent name + emoji + status |
| Implement replan flow: on failure → call Planner with failure context → new plan → continue | Test replan scenario: Planner produces valid degraded plan | If no time for avatars: skip (P2 descope) |
| Implement escalation: after 2 failed remediations → ESCALATED status | Test escalation scenario: Planner returns "escalate to human" | Wire failure injection buttons to `/api/inject-failure` endpoint |
| | | Final responsive check |

---

## Hour 3:30 – 4:00 | FULL INTEGRATION + DEPLOY

| Person A | Person B | Person C |
|---|---|---|
| Deploy backend to Railway/Render | Test full happy path through deployed backend | Test full UI against deployed backend |
| Configure CORS for frontend domain | Test Failure 1 (log source) end-to-end | Fix any visual bugs from real data (text overflow, long agent outputs) |
| Verify SSE works through deployed URL | Test Failure 2 (remediation) end-to-end | Deploy frontend (serve from same backend OR Vercel) |
| **Fallback**: If deploy fails, set up ngrok tunnel | | **Fallback**: If SSE flaky, implement polling fallback (fetch state every 2s) |

> **🚨 GATE at 4:00**: Demo must work end-to-end through a public URL. If not:
> - **Backup 1**: ngrok tunnel to local
> - **Backup 2**: Pre-recorded video (record NOW)

---

## Hour 4:00 – 4:30 | DEMO RECORDING + WRITEUP

| Person A | Person B | Person C |
|---|---|---|
| Monitor backend stability, fix any last bugs | **WRITE THE KAGGLE WRITEUP** (1500 words, see outline) | **RECORD THE DEMO VIDEO** (2-minute screen recording) |
| Prepare README.md for GitHub repo | Include: architecture explanation, technical challenges, design justification | Record: happy path → failure 1 → recovery → failure 2 → escalation |
| Add architecture diagram to README | | Upload video to YouTube (unlisted) or embed in writeup |
| Push final code to GitHub | | |

---

## Hour 4:30 – 5:00 | FINAL SUBMISSION

| Person A | Person B | Person C |
|---|---|---|
| Final GitHub push, verify repo is public | Finalize writeup, proofread, submit to Kaggle | Verify hosted demo is reachable, do one final run-through |
| Add demo link + video link to README | Add repo link + demo link to writeup | |
| **Everyone**: Final review of all 3 deliverables | | |

> **SUBMIT by 4:50. Last 10 minutes = buffer for upload issues.**

---

## Descope Order (If Behind Schedule)

Execute these cuts in order, from least to most impactful:

| When to Cut | What to Cut | Impact |
|---|---|---|
| Behind at 2:30 | P3: Micro-animations, font pairing | Minimal — still looks good |
| Behind at 3:00 | P2: Floating agent avatars, credibility strip | Moderate — less visual flair |
| Behind at 3:00 | Failure 2 (remediation failure) — keep Failure 1 only | Reduces demo impressiveness but saves 30 min |
| Behind at 3:30 | P1: Incident timeline — just show current status | Judges see less state history, but core demo works |
| Behind at 3:30 | MetricsAgent — use LogAnalyzer only (simplify to 3 agents) | Reduces "multi-agent" impression but still demonstrates pattern |
| Behind at 4:00 | Polish writeup — submit bullet points, not prose | Judges may dock points but at least it's submitted |

---

## Critical Path Visualization

```
HOUR  0    0:30   1:00   1:30   2:00   2:30   3:00   3:30   4:00   4:30   5:00
      |      |      |      |      |      |      |      |      |      |      |
  A:  [SPIKE ][--Orchestrator Skeleton--][Wire Real Agents---][Failure][DEPLOY][README]
  B:  [SPIKE ][Planner][LogAn][Metrics][Diag ][Remed][Tune  ][------WRITEUP------]
  C:  [SETUP ][--HTML/CSS/Design-------][--SSE+Buttons--][Timeline][Float][RECORD]
      |      |      |      |      |      |      |      |      |      |      |
              ↑                          ↑               ↑            ↑
          CONTRACTS                MINI-CHECK       NO NEW        DEPLOY
           LOCKED                  (5 min)         FEATURES        GATE
```
