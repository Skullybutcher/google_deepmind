# AEGIS — Kaggle Writeup Outline (≤1500 Words)

> Draft this section-by-section. Person B owns the draft. Expand bullet points into prose.

---

## Title
**AEGIS: Autonomous Emergency Grid for Incident Self-healing**

## Subtitle
*A stateful multi-agent orchestration system for automated incident response, powered by Antigravity managed agents via the Interactions API*

---

## Section 1: Introduction & Problem (150 words)

- Production incidents require coordinated investigation across logs, metrics, recent deploys — a multi-step, multi-system task.
- Single-prompt LLM wrappers fail here: they can't track state across investigation phases, can't recover when a data source is unreachable, and can't re-plan when a fix fails.
- AEGIS demonstrates that a **stateful multi-agent system** with explicit planning, delegation, state tracking, and failure recovery can automate incident response end-to-end.
- Brief thesis: "We built a 5-agent system orchestrated by a deterministic state machine that plans investigations, delegates to specialist agents, tracks state across the full incident lifecycle, and dynamically re-plans when failures occur."
- **Credibility anchor**: Draw explicit parallel to the decentralized supervisor pattern used in TruthGuard AI (where a supervisor agent intercepts uncertain claims before they corrupt the knowledge graph) and the asynchronous multi-agent orchestration experience from Agentathon 2025. Frame AEGIS as the natural evolution of those patterns — same core insight (agents need a supervisor that tracks state and routes failures), applied to the incident response domain with Antigravity's native Interactions API for session management.

---

## Section 2: Architecture Overview (350 words)

- **High-level diagram** (embed the ASCII art or a rendered image):
  - Orchestrator (deterministic, not LLM) at the center
  - 5 managed agents: Planner, LogAnalyzer, MetricsAgent, Diagnostician, Remediator
  - Interactions API as the communication backbone
  - SSE to the frontend for live visualization

- **Why a deterministic orchestrator** (not an LLM orchestrator):
  - Reliability: routing decisions should be deterministic, not hallucinated
  - Speed: no LLM call needed for "which agent runs next?"
  - Testability: state machine is fully predictable
  - The *agents* do the intelligent work; the orchestrator does traffic control
  - Cite: this pattern is used in production systems (CrewAI, AutoGen, LangGraph all use graph-based orchestration)

- **Agent roles and tools** (table format):
  - Each agent has a distinct system prompt, distinct tools, and a distinct responsibility
  - Emphasize: these are NOT "three prompts glued together" — each agent has its own Interactions API session, its own tool definitions, and produces independently structured output

- **State persistence**:
  - Incident State Object (JSON) persisted to disk after every transition
  - Full event history maintained for audit/debugging
  - Plan versioning: when the system re-plans, old plans are preserved, not overwritten

- **Interactions API usage**:
  - Each agent is a managed agent created via the Interactions API
  - Sessions are created per-incident, per-agent
  - Tool definitions are registered with each agent at creation time
  - The orchestrator sends context-rich messages and receives structured responses
  - `previous_interaction_id` chains agent context natively — no fragile prompt concatenation

- **Prior Art & Design Lineage** (proof of engineering depth):
  - **TruthGuard AI parallel**: AEGIS's Orchestrator→Diagnostician→Remediator pipeline mirrors the TruthGuard supervisor model where a Verifier agent intercepts uncertain entity extractions before they reach the knowledge graph. In AEGIS, the Diagnostician plays the same gatekeeper role — it must validate the root-cause hypothesis before the Remediator is allowed to act.
  - **Agentathon 2025 parallel**: The asynchronous agent swarm pattern (multiple specialist agents running concurrently with a coordinator collecting results) was validated during Agentathon 2025. AEGIS applies the same pattern with `asyncio.gather` for parallel investigation, but adds failure-aware replanning that Agentathon projects typically lacked.
  - **Why this matters for judges**: These are not theoretical references — they demonstrate a track record of designing, debugging, and shipping multi-agent architectures. The design choices in AEGIS (deterministic orchestrator, bounded retries, native API state management) are direct lessons learned from those prior systems.

---

## Section 3: Multi-Agent Collaboration in Action (250 words)

- Walk through the **happy path** step by step:
  1. Alert received → Planner decomposes into subtasks with dependencies
  2. LogAnalyzer and MetricsAgent run **in parallel** (genuine concurrent delegation)
  3. Diagnostician receives **combined findings** from both — true inter-agent data flow
  4. Remediator executes the proposed fix in a sandboxed simulation
  5. Orchestrator verifies and marks RESOLVED

- **Why this is genuine multi-agent collaboration**:
  - Agents produce outputs that feed into other agents' inputs
  - The Diagnostician cannot function without data from both investigators
  - The Remediator acts on the Diagnostician's hypothesis, not a pre-determined script
  - Parallel execution of LogAnalyzer + MetricsAgent is real concurrency, not sequential

- **Long-horizon state tracking**:
  - The incident state object accumulates data across 5+ agent interactions
  - The history array provides a full audit trail
  - Plan versioning shows the system's evolving understanding of the problem

---

## Section 4: Failure Recovery — Not Just Retry (250 words)

- **Failure Scenario 1: Log Source Unavailable**
  - LogAnalyzer's `fetch_logs` tool returns an error (simulated 503/timeout)
  - Orchestrator **detects** the failure (not a crash — an intentional error check)
  - Orchestrator **does not blindly retry** — it calls the Planner with failure context
  - Planner produces a **new plan** (Plan v2): skip log analysis, use metrics-only diagnosis
  - This is *intelligent adaptation*, not mechanical retry
  - State object records both plans, the failure event, and the replan event

- **Failure Scenario 2: Remediation Failed**
  - Remediator's `execute_fix` tool returns "ROLLBACK_FAILED"
  - Orchestrator detects, calls Planner: "Propose alternative or escalate"
  - Planner may propose a different fix (service restart vs. rollback)
  - If second attempt fails, Orchestrator **escalates to human** (status: ESCALATED)
  - This demonstrates *bounded autonomy* — the system knows when to stop and ask for help

- **Why this matters for the judging bar**:
  - Both failures are injectable on-demand via dashboard buttons
  - Recovery is visible in the UI: timeline shows failure → replan → new plan → continue
  - The system's behavior is qualitatively different with and without failures — it's not a script

---

## Section 5: Technical Challenges Overcome (200 words)

- **Challenge 1: Structured output consistency**
  - LLM agents don't always return valid JSON
  - Solution: tool definitions with strict schemas + `safe_parse()` wrapper with one retry
  - Fallback: hardcoded default response if agent produces garbage (logged as anomaly)

- **Challenge 2: Concurrent agent execution**
  - Running LogAnalyzer and MetricsAgent in parallel via `asyncio.gather`
  - Handling the case where one completes and the other fails — partial results must be preserved
  - Solution: individual try/except per agent call, state updated incrementally

- **Challenge 3: Replan coherence**
  - When the Planner is asked to re-plan, it must understand what already happened
  - Solution: send the full incident state (including history and previous plan) as context
  - The Planner's system prompt instructs it to reference completed steps and avoid re-running them

- **Challenge 4: Live UI updates**
  - SSE for real-time state streaming to the dashboard
  - Handling reconnection on network hiccups (EventSource auto-reconnect)

---

## Section 6: Design & Demo Experience (150 words)

- **Glassmorphism UI**: Frosted-glass panel for the main incident dashboard — modern, not prototypy
- **Live agent status visualization**: Each agent has a status chip that updates in real-time
- **Incident timeline**: Full event history scrollable below the main card
- **Failure injection buttons**: Judges can trigger failures on-demand and watch recovery happen live
- **Typography**: Playfair Display (headline) + Inter (body) for professional contrast
- **Why this design approach**: 
  - The UI is the primary way judges evaluate the system — it must make the orchestration *visible*
  - Every state transition, every agent handoff, every failure and recovery is rendered as a visual event
  - The system's intelligence is demonstrated through its UI, not just its code

---

## Section 7: Conclusion (100 words)

- AEGIS demonstrates that genuine multi-agent orchestration — with real planning, real delegation, real state tracking, and real failure recovery — is achievable with Antigravity managed agents and the Interactions API.
- The system handles incidents that would break single-prompt wrappers: multi-source investigation, parallel data gathering, adaptive diagnosis under partial failure, and bounded autonomous remediation.
- We believe this pattern (deterministic orchestrator + specialist LLM agents + persistent state + dynamic replanning) is the right foundation for production multi-agent systems.
- Future work: real log/metric integrations, multi-incident handling, learning from past incidents.

---

## Word Count Budget

| Section | Target Words |
|---|---|
| Introduction & Problem | 150 |
| Architecture Overview | 350 |
| Multi-Agent Collaboration | 250 |
| Failure Recovery | 250 |
| Technical Challenges | 200 |
| Design & Demo | 150 |
| Conclusion | 100 |
| **Total** | **~1450** (leaves 50-word buffer) |

---

## Embedded Assets to Include

- [ ] Architecture diagram (ASCII or rendered)
- [ ] Screenshot of the dashboard in happy-path resolved state
- [ ] Screenshot of the dashboard showing failure → replan → recovery
- [ ] Link to live demo
- [ ] Link to GitHub repo
- [ ] Link to demo video (YouTube unlisted)
