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
| **Likelihood** | MEDIUM — free-tier hosting (Railway/Render) can be slow on cold starts |
| **Impact** | CRITICAL — judges can't see the demo = instant fail |
| **Detection** | During deployment at hour 3:30 |

### Mitigation
- **Three layers of redundancy**:
  1. **Primary**: Deployed on Railway/Render with a keep-alive cron ping every 5 minutes.
  2. **Backup 1**: Local machine running the app + ngrok/Cloudflare tunnel for public URL.
  3. **Backup 2**: Pre-recorded 2-minute screen recording uploaded to YouTube (unlisted).
- Person C records the demo video at hour 4:00 regardless of hosting status.
- All three backup URLs are included in the writeup and README.

### Fallback (trigger at 3:30 if deploy fails)
- Immediately activate ngrok tunnel.
- If ngrok also fails: the pre-recorded video IS the demo. Writeup says "live demo available at [ngrok URL], recorded demo at [YouTube URL]."

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

## Quick Reference: Decision Points

| Time | Decision | Owner | Options |
|---|---|---|---|
| 0:15 | API works? | A | Continue / investigate / fallback |
| 0:30 | Contracts locked? | All | Lock or 5-min discussion |
| 2:00 | Mini-integration passes? | A | Continue / identify gap |
| 2:00 | All agents produce valid output? | B | Continue / simplify schema / hardcode |
| 3:00 | Feature freeze | All | Enforced — no exceptions |
| 3:30 | Deploy works? | A | Railway / ngrok / pre-recorded video |
| 3:30 | Frontend integration works? | C | Live SSE / polling / replay mode |
| 3:45 | Writeup started? | B | Must start — non-negotiable |
| 4:00 | Demo recorded? | C | Must record — non-negotiable |
| 4:50 | Everything submitted? | All | Submit what we have — buffer over |

---

## First-30-Minute Decisions (Must Lock Before Building)

These decisions CANNOT be deferred. Discuss and lock in the first standup:

1. **Backend language**: Python (FastAPI) — recommended. Override only if team strongly prefers Node.
2. **Hosting platform**: Railway — recommended. Override only if team has existing Render/Replit setup.
3. **SSE vs WebSocket**: SSE — recommended. Simpler, sufficient for one-way updates.
4. **Frontend framework**: None (vanilla HTML/CSS/JS) — recommended. No build tools = no build failures.
5. **Number of agents**: 5 (Planner + LogAnalyzer + MetricsAgent + Diagnostician + Remediator). Descope to 3 if needed (cut MetricsAgent, merge Diagnostician into Planner).
6. **Failure scenarios**: 2 (log source + remediation). Descope to 1 if needed.
7. **Demo format**: Hosted web app (primary) + pre-recorded video (backup). Both are prepared regardless.
