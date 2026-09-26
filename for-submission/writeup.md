# AEGIS: Autonomous Emergency Grid for Incident Self-healing

*A stateful multi-agent orchestration system for automated incident response, powered by Antigravity managed agents via the Interactions API.*

## 1. Introduction & Problem (150 words)

Production incidents demand coordinated investigation across logs, metrics, recent deploys, and config changes — a multi-step, multi-system task under time pressure. A human SRE triages the alert, queries several systems in parallel, correlates findings into a hypothesis, applies a fix, and verifies it, retrying intelligently when something fails.

Single-prompt LLM wrappers collapse here: they cannot track state across investigation phases, cannot recover when a data source is unreachable, and cannot re-plan when a fix fails. Retry-without-thinking is actively dangerous in incident response.

AEGIS demonstrates a stateful multi-agent alternative: five specialist agents (Planner, LogAnalyzer, MetricsAgent, Diagnostician, Remediator) orchestrated by a deterministic state machine that plans investigations, delegates to specialists, tracks state across the full incident lifecycle, and dynamically re-plans on failure. This mirrors proven supervisor patterns from TruthGuard AI and the async swarm experience of Agentathon 2025 — same core insight (agents need a supervisor that tracks state and routes failures), applied to incident response with Antigravity's native session management.

## 2. Architecture Overview (350 words)

At the center sits the Orchestrator: a deterministic Python/FastAPI state machine, explicitly not an LLM. It owns the Incident State Object (JSON, persisted to disk every transition), routes data between agents, detects failures, triggers re-planning, and streams Server-Sent Events to the dashboard. Routing is deterministic because routing must never hallucinate; the agents do the intelligent work, the orchestrator does traffic control. This matches production practice in CrewAI, AutoGen, and LangGraph, all of which use graph-based orchestration under the hood.

The five managed agents each hold their own Interactions API session, system prompt, and tool definitions:

| Agent | Responsibility | Tools |
|---|---|---|
| Planner | Decomposes alerts into ordered steps with dependencies | `create_plan` |
| LogAnalyzer | Fetches and analyzes application logs | `fetch_logs`, `analyze_pattern` |
| MetricsAgent | Analyzes CPU/memory/latency time-series | `fetch_metrics`, `detect_anomaly` |
| Diagnostician | Correlates findings into root cause + action | `correlate_findings`, `propose_diagnosis` |
| Remediator | Executes and verifies the fix in simulation | `execute_fix`, `verify_fix` |

These are not glued prompts. Each agent has an independent session, independent tool schemas, and independently structured output validated by a `safe_parse` wrapper. LogAnalyzer and MetricsAgent run concurrently via `asyncio.gather`; their outputs converge as joint input to the Diagnostician, which gates the Remediator exactly as TruthGuard's verifier gates knowledge-graph writes.

State persistence is the long-horizon backbone: `incident_id`, `status`, versioned `plan` with per-step statuses, `findings`, `diagnosis`, `remediation`, full `history`, and `plan_version_history`. Re-plans create new versions; old plans are preserved, never overwritten.

Crucially, context chains natively via `previous_interaction_id`. When the Planner re-plans after a failure, the orchestrator passes the prior interaction ID — the API resumes conversational context server-side instead of us concatenating history into a bloated prompt. Token cost stays flat per turn; the state object stores interaction IDs for audit.

```
[TODO: architecture diagram — Person A to export from ARCHITECTURE.md]
```

## 3. Multi-Agent Collaboration in Action (250 words)

Happy path: the user clicks "Trigger Incident: High Latency on api-gateway." The Orchestrator creates incident `INC-YYYYMMDD-NNN` and calls the Planner, which returns four steps — S1 LogAnalyzer and S2 MetricsAgent with no dependencies (parallel), S3 Diagnostician depending on S1+S2, S4 Remediator depending on S3.

LogAnalyzer fetches five log lines (OOM errors post-deploy v2.3.1, 2.3s GC pause, circuit breaker open) and reports anomalies at 0.85 confidence pointing at the deploy. Concurrently, MetricsAgent fetches CPU/memory/latency series showing 52%→95% CPU and 130ms→12000ms p99 at 09:58, reporting 0.92 confidence with the same inflection point. Neither agent knows about the other; the collaboration happens through the orchestrator's state.

The Diagnostician receives both finding objects, correlates the OOM errors with the memory curve and the shared deploy-window onset, and proposes `rollback` to v2.3.0 at 0.90 confidence with cited evidence. The Remediator executes the rollback in simulation, runs a health check (p99 back to 125ms, error rate 0%), and the Orchestrator marks the incident RESOLVED in roughly 30–60 seconds.

The history array accumulates every handoff, giving judges a full audit trail: plan created, two agents started/completed in parallel, diagnosis proposed, fix executed and verified — genuine inter-agent data flow, not a script.

## 4. Failure Recovery — Not Just Retry (250 words)

Failure 1 — Log Source Unavailable: `fetch_logs` returns `SOURCE_TIMEOUT` (`PermissionError: Missing IAM Role for CloudWatch`). The Orchestrator marks S1 FAILED, records `AGENT_FAILED`, and calls the Planner with failure context instead of retrying blindly. The Planner returns Plan v2 in degraded mode: skip log analysis, diagnose from metrics plus heuristics. The Diagnostician runs on partial data, drops confidence to ~0.6 (contractually below 0.7), and notes the missing source. Resolution continues on degraded evidence — intelligent adaptation, fully visible as failed → replan → new plan → continue.

Failure 2 — Remediation Failed: `execute_fix` returns `ROLLBACK_FAILED` (deployment lock held by CI/CD pid-4521). The Orchestrator marks remediation FAILED and asks the Planner for an alternative or escalation. The Planner proposes Plan v3 (restart instead of rollback). After two failed remediation attempts (`MAX_REMEDIATION_ATTEMPTS = 2`, `MAX_PLAN_VERSIONS = 3`), the Orchestrator sets status ESCALATED with a "requires human" reason — bounded autonomy, knowing when to stop.

Both failures inject on demand via dashboard buttons setting flags in `ACTIVE_FAILURES`, so judges trigger them deterministically. Recovery is qualitatively different from retry: plans change shape, confidence recalibrates, and every step is timestamped in state. That is the judging bar this section targets.

```
[TODO: screenshot — failure → replan → recovery timeline — Person C]
```

## 5. Technical Challenges Overcome (200 words)

Structured output consistency: LLMs return free text instead of tool calls. Fix: every system prompt ends with "You MUST use the [tool] tool…", tool schemas stay flat, and a `safe_parse` wrapper retries once before falling back to a hardcoded `DEFAULT_FALLBACK` logged as an anomaly — the pipeline never crashes.

Concurrent execution: `asyncio.gather` runs investigators in parallel, but one may fail while the other succeeds. Fix: per-agent try/except with incremental state updates, so partial results survive and the join gate routes to diagnosis or replanning based on individual statuses.

Replan coherence: the Planner must not re-run completed steps. Fix: replan messages carry completed/failed step summaries plus prior plan version, and the prompt instructs degraded planning; `previous_interaction_id` supplies full conversational context without prompt bloat.

Live UI updates: SSE streaming with `EventSource` auto-reconnect, plus a `GET /api/state` polling fallback every 2s if the proxy breaks the stream. Never `time.sleep` — `asyncio.sleep` throughout.

## 6. Design & Demo Experience (150 words)

The dashboard is a glassmorphism incident console: central frosted card with live status, per-agent status chips (pending → in-progress → completed/failed), primary "Trigger Incident" pill, secondary outline failure-injection buttons, and a scrollable color-coded timeline below. Playfair Display headlines with Inter body keep it professional, not prototypy.

Every orchestration event renders visually — the system's intelligence is demonstrated through the UI, not just code. Judges watch planning, parallel investigation, correlation, remediation, failure, replan, and escalation happen live.

```
[TODO: screenshot — happy-path RESOLVED dashboard — Person C]
[TODO: demo video link (YouTube unlisted) — Person C, due 4:15]
[TODO: live demo URL + repo URL — Person A, due 3:30]
```

## 7. Conclusion (100 words)

AEGIS shows genuine multi-agent orchestration — real planning, delegation, state tracking, and failure recovery — is achievable with Antigravity managed agents and the Interactions API. It handles what breaks single-prompt wrappers: multi-source parallel investigation, adaptive diagnosis under partial failure, and bounded autonomous remediation. The deterministic-orchestrator plus specialist-agents plus persistent-state plus dynamic-replanning pattern is, we believe, the right foundation for production multi-agent systems. Next: real log/metric integrations, multi-incident handling, and learning from past incidents.

---
*Word budget: ~1450 excl. placeholders. Assets pending: architecture diagram (A), 2 screenshots + video (C), demo/repo links (A).*
