# AEGIS — Risk Register & Mitigation Playbook

> Top 5 risks for the 5-hour build, ordered by likelihood × impact.
> Each risk has a concrete mitigation and a "when to trigger fallback" decision point.

---

## Risk 1: Interactions API Unfamiliarity / Auth Issues

| Attribute | Detail |
|---|---|
| **Likelihood** | HIGH — new API, no prior experience assumed |
| **Impact** | CRITICAL — blocks all agent work; nothing works without it |
| **Detection** | First 15 minutes of API spike |

### Mitigation
- Persons A + B spend the first 30 minutes exclusively on an API spike.
- Goal: create one agent session, register one tool, send one message, get one response.
- Document the exact code snippet and share with the team.

### Fallback (trigger at 0:30 if spike fails)
- **Option A**: If the Interactions API works but is slow/flaky → add aggressive timeouts + caching of responses.
- **Option B**: If the Interactions API is fundamentally inaccessible → fall back to direct Antigravity Agent SDK calls (non-managed agents). The architecture changes from "managed agents via Interactions API" to "direct agent calls with manual session management." The orchestrator pattern still works.
- **Option C**: If no Antigravity API works at all → pivot to OpenAI/Anthropic API with the same architecture. Document in writeup that "we designed for Antigravity but had to substitute due to access issues." This is a last resort.

### Decision Owner
Person A (backend lead) makes the call at 0:30.

---

## Risk 2: Agent Output Format Inconsistency

| Attribute | Detail |
|---|---|
| **Likelihood** | MEDIUM-HIGH — LLMs don't always return valid JSON even with tool calling |
| **Impact** | HIGH — orchestrator can't parse responses → state machine breaks |
| **Detection** | During agent testing (hours 1–2) |

### Mitigation
- All agent interactions use **tool calling / function calling** (structured output), NOT free-text responses.
- Orchestrator wraps every agent response in `safe_parse()`:
  ```python
  def safe_parse(response, schema, retries=1):
      try:
          parsed = json.loads(response)
          validate(parsed, schema)
          return parsed
      except (JSONDecodeError, ValidationError):
          if retries > 0:
              # Re-prompt agent: "Your output was not valid JSON. Please try again using the tool."
              return retry_agent_call(...)
          else:
              return DEFAULT_FALLBACK_RESPONSE
  ```
- Each agent has a `DEFAULT_FALLBACK_RESPONSE` that's valid for the orchestrator to continue (e.g., LogAnalyzer fallback = "No anomalies detected, confidence 0.0").

### Fallback (trigger if agent consistently fails after 3 tests)
- Simplify the agent's tool schema (fewer fields, flatter structure).
- Add stronger constraints in the system prompt: "You MUST call the tool. Do not respond with plain text."
- If still failing: hardcode the agent's response for the demo and note in writeup that "structured output consistency was a challenge."

### Decision Owner
Person B (agent owner) tests each agent in isolation and flags issues by hour 2:00.

---

## Risk 3: Live Demo Flakiness / Hosting Issues

| Attribute | Detail |
|---|---|
| **Likelihood** | LOW — Cloud Run is reliable; `--min-instances=1` eliminates cold-start during judging |
| **Impact** | CRITICAL — judges can't see the demo = instant fail |
| **Detection** | During deployment at hour 3:30 |

### Mitigation
- **Three layers of redundancy**:
  1. **Primary**: Deployed on Cloud Run with `--min-instances=1` during judging slot + Firebase Hosting rewrites `/api/**` to Cloud Run (same-origin, no CORS issues).
  2. **Backup 1**: Re-run `gcloud run deploy --source .` (usually faster than debugging; keep ngrok as last resort only if Cloud Run itself is down).
  3. **Backup 2**: Pre-recorded 2-minute screen recording uploaded to YouTube (unlisted).
- Person C records the demo video at hour 4:00 regardless of hosting status.
- All three backup URLs are included in the writeup and README.

### Fallback (trigger at 3:30 if deploy fails)
- Re-run `gcloud run deploy --source .` (often fixes transient Cloud Build issues).
- If Cloud Run itself is down (rare): fall back to local machine + ngrok tunnel.
- If ngrok also fails: the pre-recorded video IS the demo. Writeup says "live demo available at [Firebase URL], recorded demo at [YouTube URL]."

### Decision Owner
Person A (deploy owner) makes the call at 3:30.

---

## Risk 4: Integration Failures at Hour 3:30

| Attribute | Detail |
|---|---|
| **Likelihood** | MEDIUM — three people building in parallel always has integration risk |
| **Impact** | HIGH — 90 minutes of debugging instead of polishing |
| **Detection** | Integration checkpoint at hour 3:30 |

### Mitigation
- **Contracts locked at 0:30**: SSE event format + agent I/O schemas agreed before building.
- **Mock data everywhere**: Person C builds frontend against mock SSE events. Person A builds orchestrator with stub agents. Both can test independently.
- **Mini-integration at 2:00**: 5-minute smoke test:
  - Person A runs orchestrator with one real agent (Planner).
  - Person C connects EventSource to Person A's local server.
  - If this works → on track. If not → identify the gap immediately.

### Fallback (trigger at 3:30 if integration is broken)
- **Frontend fallback**: Person C switches to a "replay mode" — a pre-recorded sequence of SSE events stored in a JSON array, replayed with `setTimeout()`. The UI looks identical; the data is just canned instead of live.
  ```javascript
  // Replay mode: read events from mock_events.json, emit them with delays
  const mockEvents = await fetch('mock_events.json').then(r => r.json());
  for (const event of mockEvents) {
    await sleep(event.delay);
    handleEvent(event);
  }
  ```
- **Backend fallback**: If agents work but SSE is broken, switch to polling (`setInterval` + `GET /api/state` every 2 seconds).

### Decision Owner
Person A (integration lead) coordinates the checkpoint at 2:00 and makes the 3:30 call.

---

## Risk 5: Scope Creep / Running Out of Time

| Attribute | Detail |
|---|---|
| **Likelihood** | MEDIUM — hackathon adrenaline, "one more feature" syndrome |
| **Impact** | HIGH — nothing is finished properly |
| **Detection** | Continuous; enforced by timeline gates |

### Mitigation
- **Hard rule: NO NEW FEATURES after 3:00.** This is non-negotiable.
- **Descope order pre-agreed** (see TIMELINE.md):
  1. Cut UI polish (P3): animations, font pairing
  2. Cut UI flair (P2): floating avatars, credibility strip
  3. Cut Failure 2 if Failure 1 works reliably
  4. Cut MetricsAgent (simplify to 3 agents) if agents are taking too long
  5. Cut timeline view (P1) — just show current status
- **Person B starts writeup at 3:45 regardless** — even if code isn't perfect.
- **Person C records demo at 4:00 regardless** — even if not all features work.
- Writeup and demo recording are NOT optional — they ARE deliverables.

### Decision Owner
All three people enforce collectively. Person B is the "time cop" — calls out scope creep.

---

## Risk 6: Infinite Retry Loops / Context Window Exhaustion

| Attribute | Detail |
|---|---|
| **Likelihood** | MEDIUM — multi-agent systems can easily get stuck in argue-retry loops |
| **Impact** | HIGH — demo hangs, token budget burns, or agents produce degrading output as context fills |
| **Detection** | During integration testing (hours 3–4); hard to catch in unit tests |

### Token & Loop Budget (Hardcoded in `orchestrator.py`)

```python
# orchestrator.py — HARD LIMITS (non-negotiable)
MAX_PLAN_VERSIONS = 3          # Planner can replan at most 3 times per incident
MAX_AGENT_RETRIES = 2          # Each agent gets at most 2 retry attempts on failure
MAX_REMEDIATION_ATTEMPTS = 2   # Remediator gets at most 2 fix attempts
AGENT_TIMEOUT_SECONDS = 30     # Any agent call that exceeds 30s is killed
MAX_INCIDENT_DURATION = 120    # Entire incident auto-escalates after 2 minutes
SAFE_PARSE_RETRIES = 1         # Re-prompt agent once for malformed output, then use fallback
```

### Graceful Degradation Protocol

When any limit is hit, the Orchestrator does NOT crash or silently retry. It follows this protocol:

1. **Log the limit hit** in the state history:
   ```json
   {"event": "LIMIT_REACHED", "limit": "MAX_PLAN_VERSIONS", "value": 3, "action": "ESCALATING"}
   ```
2. **Set incident status to `ESCALATED`** with a human-readable reason:
   ```json
   {"status": "ESCALATED", "reason": "Exhausted 3 replan attempts. Root cause unclear with available data. Handing diagnostic report to human operator."}
   ```
3. **Emit the full diagnostic report** as the final SSE event, including:
   - All plans attempted (v1, v2, v3) and why each was insufficient
   - All agent outputs collected (even partial)
   - All errors encountered with timestamps
   - A machine-generated "best guess" summary from the last Diagnostician call

4. **Dashboard renders the ESCALATED state** with a distinct visual treatment (amber warning banner) so judges see this is intentional bounded autonomy, not a crash.

### Why This Matters

| Without Limits | With AEGIS Limits |
|---|---|
| Agent A fails → replan → Agent B fails → replan → Agent A fails → replan → ∞ | Max 3 replans → graceful escalation with full diagnostic context |
| Each replan re-sends entire history → context window fills → output quality degrades | `previous_interaction_id` manages context server-side; each message is compact |
| Demo hangs for 5+ minutes while agents argue | Hard 2-minute ceiling; demo always completes in a bounded time |
| Token costs spiral unpredictably | Predictable worst-case: 5 agents × 2 retries × ~1K tokens = ~10K tokens per incident |

### Fallback
- If during testing agents still loop despite limits: reduce `MAX_PLAN_VERSIONS` to 2 and `MAX_AGENT_RETRIES` to 1. The demo gets simpler but always terminates.
- If `AGENT_TIMEOUT_SECONDS = 30` causes false positives (agent is slow but working): increase to 45s, but never above 60s.

### Decision Owner
Person A (orchestrator) implements the limits. Person B validates agents complete within timeout during testing at hour 3:00.

## Quick Reference: Decision Points

| Time | Decision | Owner | Options |
|---|---|---|---|
| 0:15 | API works? | A | Continue / investigate / fallback |
| 0:30 | Contracts locked? | All | Lock or 5-min discussion |
| 2:00 | Mini-integration passes? | A | Continue / identify gap |
| 2:00 | All agents produce valid output? | B | Continue / simplify schema / hardcode |
| 3:00 | Feature freeze | All | Enforced — no exceptions |
| 3:30 | Deploy works? | A | Cloud Run + Firebase / re-deploy / pre-recorded video |
| 3:30 | Frontend integration works? | C | Live SSE / polling / replay mode |
| 3:45 | Writeup started? | B | Must start — non-negotiable |
| 4:00 | Demo recorded? | C | Must record — non-negotiable |
| 4:50 | Everything submitted? | All | Submit what we have — buffer over |

---

## First-30-Minute Decisions (Must Lock Before Building)

These decisions CANNOT be deferred. Discuss and lock in the first standup:

1. **Backend language**: Python (FastAPI) — recommended. Override only if team strongly prefers Node.
2. **Hosting platform**: Cloud Run (backend) + Firebase Hosting (frontend) — on-brand for Google hackathon. See `DEPLOYMENT.md` for full setup.
3. **SSE vs WebSocket**: SSE — recommended. Simpler, sufficient for one-way updates.
4. **Frontend framework**: None (vanilla HTML/CSS/JS) — recommended. No build tools = no build failures.
5. **Number of agents**: 5 (Planner + LogAnalyzer + MetricsAgent + Diagnostician + Remediator). Descope to 3 if needed (cut MetricsAgent, merge Diagnostician into Planner).
6. **Failure scenarios**: 2 (log source + remediation). Descope to 1 if needed.
7. **Demo format**: Hosted web app (primary) + pre-recorded video (backup). Both are prepared regardless.
