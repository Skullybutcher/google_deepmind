# AEGIS: Autonomous Emergency Grid for Incident Self-healing

*A stateful multi-agent orchestration system for automated incident response, powered by Antigravity managed agents via the Interactions API.*

**Repo**: https://github.com/Skullybutcher/google_deepmind  
**Eval**: 82/82 golden-scenario checks passing (`python -m backend.eval.run_eval`)

---

## 1. Introduction & Problem (150 words)

Production incidents demand coordinated investigation across logs, metrics, recent deploys, and config changes — a multi-step, multi-system task under time pressure. A human SRE triages the alert, queries several systems in parallel, correlates findings into a hypothesis, applies a fix, and verifies it, retrying intelligently when something fails.

Single-prompt LLM wrappers collapse here: they cannot track state across investigation phases, cannot recover when a data source is unreachable, and cannot re-plan when a fix fails. Retry-without-thinking is actively dangerous in incident response — an LLM that blindly retries a failed rollback may destroy a production deployment.

AEGIS demonstrates a stateful multi-agent alternative: five specialist agents (Planner, LogAnalyzer, MetricsAgent, Diagnostician, Remediator) orchestrated by a deterministic state machine that plans investigations, delegates to specialists, tracks state across the full incident lifecycle, and dynamically re-plans on failure. This mirrors proven supervisor patterns from TruthGuard AI and the async swarm experience of Agentathon 2025 — same core insight (agents need a supervisor that tracks state and routes failures), applied to incident response with Antigravity's native session management.

---

## 2. Architecture Overview (350 words)

At the center sits the Orchestrator: a deterministic Python/FastAPI state machine, explicitly not an LLM. It owns the Incident State Object (JSON, persisted to disk every transition), routes data between agents, detects failures, triggers re-planning, and streams Server-Sent Events to the dashboard. Routing is deterministic because routing must never hallucinate; the agents do the intelligent work, the orchestrator does traffic control. This matches production practice in CrewAI, AutoGen, and LangGraph, all of which use graph-based orchestration under the hood.

The five managed agents each hold their own Interactions API session, system prompt, and tool definitions. Each agent has a distinct capability mode reflecting real SRE tooling:

| Agent | Capability | Tools |
|---|---|---|
| Planner | Multi-turn planning loop | `create_plan` |
| LogAnalyzer | Code execution (Python sandbox) | `fetch_logs`, `run_python_analysis`, `analyze_pattern` |
| MetricsAgent | Code execution (Python sandbox) | `fetch_metrics`, `run_python_analysis`, `detect_anomaly` |
| Diagnostician | Multi-turn + web search | `correlate_findings`, `web_search`, `propose_diagnosis` |
| Remediator | Sandbox + file management | `execute_fix`, `run_bash_command`, `write_fix_report`, `verify_fix` |

These are not glued prompts. Each agent has an independent session, independent tool schemas, and independently structured output. LogAnalyzer and MetricsAgent run concurrently via `asyncio.gather`; their outputs converge as joint input to the Diagnostician, which gates the Remediator exactly as TruthGuard's verifier gates knowledge-graph writes.

State persistence is the long-horizon backbone: `incident_id`, `status`, versioned `plan` with per-step statuses, `findings`, `diagnosis`, `remediation`, full `history`, `plan_version_history`, and a `telemetry` object tracking wall-clock time and cost per agent. Re-plans create new versions; old plans are preserved, never overwritten.

Context chains natively via `previous_interaction_id`. When the Planner re-plans after a failure, the orchestrator passes the prior interaction ID — the API resumes conversational context server-side instead of concatenating history into a bloated prompt. Token cost stays flat per turn; the state object stores interaction IDs for audit.

```
Frontend (React/Tailwind)  ──SSE──►  FastAPI (Cloud Run / Render)
                                            │
                                      Orchestrator (state machine)
                                            │
                             ┌──────────────┼──────────────┐
                             ▼              ▼              ▼
                          Planner    LogAnalyzer    MetricsAgent
                                            │
                                      Diagnostician ◄── web_search
                                            │
                                       Remediator ◄── Guardrail gate
```

*[Architecture diagram — full version in doc/ARCHITECTURE.md]*

---

## 3. Multi-Agent Collaboration in Action (250 words)

Happy path: the user clicks "Trigger Incident: High Latency on api-gateway." The Orchestrator creates incident `INC-YYYYMMDD-HHMMSS` and calls the Planner, which returns four steps — S1 LogAnalyzer and S2 MetricsAgent with no dependencies (parallel), S3 Diagnostician depending on S1+S2, S4 Remediator depending on S3.

LogAnalyzer fetches five log lines (OOM errors post-deploy v2.3.1, 2.3s GC pause, circuit breaker open), then executes Python in a sandbox to compute error rates and rapid-onset patterns, reporting anomalies at 0.85 confidence pointing at the deploy. Concurrently, MetricsAgent fetches CPU/memory/latency series showing 52%→95% CPU and 130ms→12000ms p99 at 09:58, runs numerical analysis to detect the inflection point and confirm a monotonically increasing memory leak signature, reporting 0.92 confidence. Neither agent knows about the other; collaboration happens through the orchestrator's state.

The Diagnostician receives both finding objects, calls `web_search` to validate the OOM + deploy pattern against real-world knowledge ("OutOfMemoryError Java heap space after deployment — Stack Overflow"), correlates findings, and proposes `rollback` to v2.3.0 at 0.90 confidence with cited evidence. The Remediator executes the rollback in a sandboxed Linux environment, runs `kubectl rollout` bash verification, writes a structured fix report to `/tmp/`, and calls `verify_fix` (p99 back to 125ms, error rate 0%). The Orchestrator marks the incident RESOLVED in roughly 30–60 seconds end-to-end.

The history array accumulates every handoff, giving judges a full audit trail: plan created, two agents started/completed in parallel, diagnosis proposed with web evidence, fix executed and bash-verified — genuine inter-agent data flow, not a script.

---

## 4. Failure Recovery — Not Just Retry (250 words)

**Failure 1 — Log Source Unavailable**: `fetch_logs` returns `SOURCE_TIMEOUT` (`PermissionError: Missing IAM Role for CloudWatch`). The Orchestrator marks S1 FAILED, records `AGENT_FAILED`, and calls the Planner with failure context. The Planner returns Plan v2 in degraded mode: skip log analysis, diagnose from metrics only. The Diagnostician runs on partial data, drops confidence to 0.70 (the minimum threshold for auto-execution), and notes the missing source. If confidence falls below 0.70, the Remediator **cannot self-execute** — the system halts at `AWAITING_APPROVAL` and surfaces an "Approve Fix?" button for the SRE. Resolution continues on degraded evidence — intelligent adaptation, fully visible as FAILED → REPLAN → degraded plan → continue or halt for human.

**Failure 2 — Remediation Failed**: `execute_fix` returns `ROLLBACK_FAILED` (deployment lock held by CI/CD pid-4521). The Orchestrator marks remediation FAILED, increments the attempt counter, and retries with an alternative action (RESTART instead of ROLLBACK). After `MAX_REMEDIATION_ATTEMPTS = 2` with `MAX_PLAN_VERSIONS = 3`, the Orchestrator sets status ESCALATED with a timestamped reason — bounded autonomy, knowing when to stop.

Both failures inject on demand via dashboard buttons (`LOG_SOURCE_UNAVAILABLE`, `REMEDIATION_FAILED` flags in state), so judges trigger them deterministically mid-demo. Recovery is qualitatively different from retry: plans change shape, confidence recalibrates, and every step is timestamped in state.

*[TODO: screenshot — failure → replan → recovery timeline — Person C]*

---

## 5. Technical Challenges Overcome (200 words)

**Structured output consistency**: LLMs return free text instead of tool calls. Fix: every system prompt ends with "You MUST use the [tool] tool…", tool schemas stay flat, and the `safe_get` wrapper on all agent outputs means a bad JSON shape never crashes the orchestrator — a `DEFAULT_FALLBACK` is logged as an anomaly and the pipeline continues.

**Concurrent execution**: `asyncio.gather` runs investigators in parallel, but one may fail while the other succeeds. Fix: per-agent try/except with incremental state updates, so partial results survive and the join gate routes to diagnosis or replanning based on individual statuses.

**Hard safety gate (not a prompt)**: the Remediator guardrail (`backend/guardrails.py`) is deterministic Python — `ALLOWED_ACTIONS = {rollback, restart}` and `AUTO_EXECUTE_THRESHOLD = 0.70`. Agent output cannot override it. Verified by SC-07 and SC-08 in the eval harness.

**Replan coherence**: replan messages carry completed/failed step summaries plus the prior plan version; `previous_interaction_id` supplies full conversational context without prompt bloat. Completed steps are never re-run.

**Live UI updates**: SSE streaming with `EventSource` auto-reconnect, plus a `GET /api/state` polling fallback every 2s if a proxy breaks the stream. `asyncio.sleep` throughout — never `time.sleep`.

**Eval confidence**: 82 assertions across 8 golden scenarios cover every state transition — final status, tool call sequence, event presence, confidence bounds, plan version count, and guardrail behaviour. The harness runs against `StubBackend` in under 1 second; `--live` mode runs it against the deployed server.

---

## 6. Design & Demo Experience (150 words)

The dashboard is a dark-mode incident console built in React + Tailwind CSS. A live flowchart visualises the five-agent pipeline in real time — each node transitions from pending (grey) → in-progress (pulsing) → completed (green) / failed (red) as SSE events arrive. Ambient LightRays background animation signals system activity. A timeline panel below the flowchart logs every orchestration event with timestamps. A separate telemetry panel shows wall-clock time per agent, estimated API cost, and plan version count — directly visible to judges.

Failure-injection buttons sit alongside the "Trigger Incident" button. Judges click "Inject: Log Source Unavailable" mid-run and watch the flowchart show S1 fail, S3 replan, and the degraded plan continue — the system's intelligence is demonstrated through the UI, not just in a terminal.

*[TODO: screenshot — happy-path RESOLVED dashboard — Person C]*
*[TODO: screenshot — failure → replan flowchart — Person C]*

---

## 7. Conclusion (100 words)

AEGIS shows genuine multi-agent orchestration — real planning, delegation, state tracking, failure recovery, and hard safety guarantees — is achievable with Antigravity managed agents and the Interactions API. It handles what breaks single-prompt wrappers: multi-source parallel investigation, adaptive diagnosis under partial failure, bounded autonomous remediation, and a code-enforced human-approval gate before any destructive action. The deterministic-orchestrator plus specialist-agents plus persistent-state plus dynamic-replanning plus guardrails pattern is, we believe, the right foundation for production multi-agent systems. The 82-check eval harness means every claim in this writeup is mechanically verified, not just observed in a demo run. Next: real log/metric integrations, multi-incident handling, and learning from past incidents.

---

*Word budget: ~1500. Assets still pending: architecture diagram (Person A), 2 screenshots (Person C).*
