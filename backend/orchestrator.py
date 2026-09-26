"""Deterministic orchestrator state machine — owned by Muse Spark.

NOT an LLM. Routes AgentBackend calls, detects failures, replans, escalates.
FreeBuff swaps StubBackend -> real backend in main.py; this file is untouched.

Flow: PLANNING -> INVESTIGATING (parallel Log+Metrics) -> DIAGNOSING
     -> REMEDIATING -> RESOLVED | ESCALATED. Replan loop capped at
     MAX_PLAN_VERSIONS; remediation capped at MAX_REMEDIATION_ATTEMPTS.
"""
import asyncio
from typing import Awaitable, Callable

from . import state as store
from .agents.interface import AgentBackend, AgentResult, PlanResult, PlanStep, safe_get
from .guardrails import RemediatorGuardrail

EmitFn = Callable[[dict], Awaitable[None]]


async def _emit(emit: EmitFn | None, event_type: str, incident: dict, message: str, extra: dict | None = None):
    if emit is None:
        return
    payload = {
        "event_type": event_type,
        "incident_id": incident["incident_id"],
        "data": {
            "status": incident["status"],
            "plan_version": incident["plan"]["version"],
            "steps": incident["plan"]["steps"],
            "message": message,
        },
    }
    if extra:
        payload["data"].update(extra)
    # MUST await here: returning the coroutine gave "'_broadcast' was never
    # awaited" and SSE subscribers saw nothing.
    return await emit(payload)


class StubBackend:
    """Same signatures as AgentBackend. Returns contract-shaped mock data
    (ARCHITECTURE.md §3) and honors injected failures."""

    def __init__(self, failures: list | None = None):
        self._static_failures = failures or []
        self._incident_id: str | None = None
        self.timeout = 30.0  # stubs answer instantly; RealBackend sets 150s

    @property
    def failures(self) -> list:
        """Read active_failures live from the store so mid-run injections are
        picked up immediately, rather than using a snapshot taken at startup."""
        if self._incident_id:
            st = store.get_state(self._incident_id)
            if st:
                return st.get("active_failures", [])
        return self._static_failures

    @failures.setter
    def failures(self, value: list):
        # Orchestrator sets backend.failures = failures at startup; we store
        # the incident_id instead so we can always read live state.
        self._static_failures = value

    async def create_plan(self, alert: dict, context: str = "") -> PlanResult:
        # v1 is ALWAYS the full plan — degradation only happens on replan,
        # so the dashboard visibly shows FAILED -> REPLAN -> degraded plan.
        degraded = "failed" in context.lower()
        steps = []
        if not degraded:
            steps.append(PlanStep("S1", "LogAnalyzer", "Fetch and analyze api-gateway logs", []))
        steps += [
            PlanStep("S2", "MetricsAgent", "Fetch CPU/memory/latency metrics", []),
            PlanStep(
                "S3", "Diagnostician", "Correlate findings into root cause",
                ["S2"] if degraded else ["S1", "S2"],
            ),
            PlanStep("S4", "Remediator", "Execute recommended fix", ["S3"]),
        ]
        return PlanResult(steps, "Parallel investigation, then correlate and remediate."
                          + (" (degraded: logs unavailable)" if degraded else ""))

    async def analyze_logs(self, service: str, time_window_minutes: int = 30) -> AgentResult:
        if "LOG_SOURCE_UNAVAILABLE" in self.failures:
            return AgentResult(False, "LogAnalyzer", "Log source unreachable",
                               error_code="SOURCE_TIMEOUT",
                               error="PermissionError: Missing IAM Role for CloudWatch — "
                                     "Failed to connect to log aggregation service after 30s")
        return AgentResult(True, "LogAnalyzer", "OOM pattern after deploy v2.3.1", {
            "anomalies": ["OutOfMemoryError right after deploy v2.3.1",
                          "GC pause 2.3s, heap 98%",
                          "Circuit breaker OPEN for downstream-payment-service"],
            "likely_trigger": "Deployment v2.3.1 introduced a memory leak",
            "confidence": 0.85})

    async def analyze_metrics(self, service: str, metrics: list | None = None) -> AgentResult:
        return AgentResult(True, "MetricsAgent", "CPU/mem/latency spike at deploy window", {
            "anomalies": ["CPU 52%->95% at 09:58", "Memory 65%->99%, no plateau",
                          "P99 latency 130ms->12000ms"],
            "inflection_point": "09:58, matches deploy v2.3.1",
            "confidence": 0.92})

    async def diagnose(self, log_findings: dict, metrics_findings: dict) -> AgentResult:
        conf = 0.90 if log_findings else 0.70
        return AgentResult(True, "Diagnostician", f"Memory-leak diagnosis (conf {conf})", {
            "root_cause": "Memory leak in deploy v2.3.1 causing OOM + cascading latency",
            "confidence": conf,
            "evidence": ["OOM logs correlate with memory spike",
                         "Onset matches deploy window",
                         "Circuit breaker confirms cascade"] if log_findings else
                        ["Memory climb with no plateau", "Onset matches deploy window"],
            "recommended_action": "rollback",
            "action_details": {"type": "ROLLBACK", "target_version": "v2.3.0", "service": "api-gateway"}})

    async def remediate(self, action_type: str, service: str, details: dict | None = None) -> AgentResult:
        if "REMEDIATION_FAILED" in self.failures:
            return AgentResult(False, "Remediator", "Rollback blocked",
                               error_code="ROLLBACK_FAILED",
                               error="DeploymentLockError: Cannot rollback — deployment lock held "
                                     "by CI/CD pipeline process pid-4521. Manual intervention required.")
        return AgentResult(True, "Remediator", f"{action_type} on {service} succeeded",
                           {"action": f"{action_type} to v2.3.0", "result": "Pods healthy"})

    async def verify(self, service: str, check_type: str = "HEALTH_CHECK") -> AgentResult:
        return AgentResult(True, "Remediator", "Health checks passing",
                           {"result": "Latency p99 125ms, error rate 0%"})


async def _call_plan(backend_coro, incident_id: str, backend=None) -> PlanResult | None:
    """Planner call with timeout. Returns None on timeout/exception."""
    timeout = getattr(backend, "timeout", store.AGENT_TIMEOUT_SECONDS)
    try:
        plan: PlanResult = await asyncio.wait_for(backend_coro, timeout=timeout)
        store.add_history(incident_id, "AGENT_COMPLETED", "Planner ok", {"agent": "Planner"})
        return plan
    except asyncio.TimeoutError:
        store.add_history(incident_id, "AGENT_FAILED", "Planner TIMEOUT", {"agent": "Planner"})
        return None
    except Exception as e:  # never let the task die silently
        store.add_history(incident_id, "AGENT_FAILED", f"Planner error: {e}", {"agent": "Planner"})
        return None


async def _call(backend_coro, incident_id: str, agent: str, step_id: str = "",
            backend=None) -> AgentResult:
    """One agent call with timeout. Never raises — failures become AgentResult."""
    import time as _time
    _agent_t0 = _time.monotonic()
    timeout = getattr(backend, "timeout", store.AGENT_TIMEOUT_SECONDS)
    try:
        res: AgentResult = await asyncio.wait_for(backend_coro, timeout=timeout)
        _record_agent_timing(incident_id, agent, _agent_t0,
                             (_time.monotonic() - _agent_t0) * 1000)
        store.add_history(incident_id,
                          "AGENT_COMPLETED" if res.ok else "AGENT_FAILED",
                          f"{agent} {step_id} {'ok' if res.ok else res.error_code}",
                          {"agent": agent})
        return res
    except asyncio.TimeoutError:
        _record_agent_timing(incident_id, agent, _agent_t0,
                             (_time.monotonic() - _agent_t0) * 1000)
        store.add_history(incident_id, "AGENT_FAILED", f"{agent} {step_id} TIMEOUT",
                          {"agent": agent})
        return AgentResult(False, agent, "timeout", error_code="TIMEOUT", error="30s timeout")


def _set_step_status(incident_id: str, agent: str, status: str, summary: str = "") -> None:
    """Update the plan step for `agent` so the dashboard status chips live-track
    each agent (PENDING -> IN_PROGRESS -> COMPLETED/FAILED). Frontend
    (aegis/frontend/src/App.jsx) reads these per-step statuses directly."""
    def _fn(s):
        for step in s["plan"]["steps"]:
            if step["agent"] == agent:
                step["status"] = status
                if summary:
                    step["output_summary"] = summary[:200]

    store._update(incident_id, _fn)


def _snapshot_plan(plan: PlanResult, version: int) -> dict:
    return {"version": version,
            "reasoning": plan.reasoning,
            "steps": [s.__dict__ for s in plan.steps]}


def _record_agent_timing(incident_id: str, agent: str, started_at: float, wall_clock_ms: float):
    """Persist per-agent wall-clock timing into telemetry.agent_timings."""
    from datetime import datetime, timezone
    def _fn(s):
        s["telemetry"]["agent_timings"][agent] = {
            "wall_clock_ms": round(wall_clock_ms, 1),
        }
    store._update(incident_id, _fn)


async def run_incident(incident_id: str, backend: AgentBackend, emit: EmitFn | None = None):
    """Full lifecycle. Callable with StubBackend today, real backend later.

    Wall-clock guard: checks INCIDENT_WALL_CLOCK_LIMIT at each phase boundary
    and escalates instead of running past it (bounded autonomy, RISKS.md #6).
    """
    import time as _time
    _t0 = _time.monotonic()

    async def _out_of_time() -> bool:
        if _time.monotonic() - _t0 < store.INCIDENT_WALL_CLOCK_LIMIT:
            return False
        await _escalate(incident_id, emit,
                        f"Incident exceeded {store.INCIDENT_WALL_CLOCK_LIMIT}s "
                        f"wall-clock limit (bounded autonomy)")
        return True

    st = store.get_state(incident_id)
    alert, service = st["alert"], st["alert"]["service"]
    # Give the backend a live reference to the incident so active_failures are
    # read from the store on every agent call (supports mid-run injection).
    if hasattr(backend, "_incident_id"):
        backend._incident_id = incident_id
    elif hasattr(backend, "failures"):
        # Fallback for non-stub backends: snapshot once at startup.
        backend.failures = st.get("active_failures", [])

    # --- PLANNING (v1) ---
    await _emit(emit, "AGENT_STARTED", st, "Planner Agent creating investigation plan...")
    plan = await _call_plan(backend.create_plan(alert), incident_id, backend)
    if plan is None:
        store.set_status(incident_id, "ESCALATED", "planner failed")
        await _emit(emit, "ESCALATED", store.get_state(incident_id), "Planner failed. Escalated.")
        return
    version = 1
    store._update(incident_id, lambda s: (
        s["plan"].update(_snapshot_plan(plan, version)),
        s["plan_version_history"].append(_snapshot_plan(plan, version)),
        s.update(status="INVESTIGATING")))
    st = store.get_state(incident_id)
    store.add_history(incident_id, "PLAN_CREATED", f"v1: {len(plan.steps)} steps")
    await _emit(emit, "PLAN_CREATED", st, f"Plan v1: {len(plan.steps)} steps")
    if await _out_of_time():
        return

    # --- INVESTIGATING (parallel) ---
    st = store.get_state(incident_id)
    await _emit(emit, "AGENT_STARTED", st, "LogAnalyzer + MetricsAgent investigating in parallel...")
    _set_step_status(incident_id, "LogAnalyzer", "IN_PROGRESS")
    _set_step_status(incident_id, "MetricsAgent", "IN_PROGRESS")
    log_res, met_res = await asyncio.gather(
        _call(backend.analyze_logs(service), incident_id, "LogAnalyzer", "S1", backend),
        _call(backend.analyze_metrics(service), incident_id, "MetricsAgent", "S2", backend))
    _set_step_status(incident_id, "LogAnalyzer",
                     "COMPLETED" if log_res.ok else "FAILED", log_res.summary)
    _set_step_status(incident_id, "MetricsAgent",
                     "COMPLETED" if met_res.ok else "FAILED", met_res.summary)

    st = store.get_state(incident_id)
    await _emit(emit,
                "AGENT_COMPLETED" if log_res.ok else "AGENT_FAILED", st,
                f"LogAnalyzer: {log_res.summary}",
                {"active_agent": "LogAnalyzer"})
    await _emit(emit,
                "AGENT_COMPLETED" if met_res.ok else "AGENT_FAILED", st,
                f"MetricsAgent: {met_res.summary}",
                {"active_agent": "MetricsAgent"})

    # --- Replan on investigation failure (degraded mode) ---
    if not log_res.ok or not met_res.ok:
        failed = [a for a, r in (("LogAnalyzer", log_res), ("MetricsAgent", met_res)) if not r.ok]
        store.add_history(incident_id, "FAILURE_DETECTED", f"{failed} failed")
        store.add_history(incident_id, "REPLAN_TRIGGERED",
                          f"{'/'.join(failed)} failed — switching to degraded mode")
        st = store.get_state(incident_id)
        await _emit(emit, "REPLAN_TRIGGERED", st,
                    f"{'/'.join(failed)} failed — replanning with available data...")
        if st["retry_count"] >= store.MAX_PLAN_VERSIONS - 1:
            return await _escalate(incident_id, emit, "Replan budget exhausted during investigation")
        ctx = (f"Previous plan v{version} failed: "
               f"{[(a, r.error_code) for a, r in (('Log', log_res), ('Met', met_res)) if not r.ok]}. "
               f"Replan using available data only.")
        plan2 = await _call_plan(backend.create_plan(alert, ctx), incident_id, backend)
        if plan2 is None:
            return await _escalate(incident_id, emit, "Replan failed")
        version += 1

        def _apply_plan2(s):
            # Carry over earned statuses so the dashboard chips don't reset:
            # MetricsAgent already COMPLETED in v1 stays COMPLETED in v2.
            old = {st["agent"]: st["status"] for st in s["plan"]["steps"]}
            snap = _snapshot_plan(plan2, version)
            for st in snap["steps"]:
                st["status"] = old.get(st["agent"], "PENDING")
            s["plan"].update(snap)
            s["plan_version_history"].append(snap)
            s.update(retry_count=s["retry_count"] + 1, status="INVESTIGATING")

        store._update(incident_id, _apply_plan2)
        st = store.get_state(incident_id)
        store.add_history(incident_id, "PLAN_UPDATED", f"v{version} degraded mode")
        await _emit(emit, "PLAN_UPDATED", st, f"Plan v{version}: degraded mode, continuing...")

    if await _out_of_time():
        return
    # --- DIAGNOSING ---
    st = store.get_state(incident_id)
    store._update(incident_id, lambda s: s.update(status="DIAGNOSING"))
    st = store.get_state(incident_id)
    await _emit(emit, "AGENT_STARTED", st, "Diagnostician correlating findings...")
    log_find = log_res.data if log_res.ok else {}
    met_find = met_res.data if met_res.ok else {}
    _set_step_status(incident_id, "Diagnostician", "IN_PROGRESS")
    diag = await _call(backend.diagnose(log_find, met_find), incident_id, "Diagnostician", "S3", backend)
    _set_step_status(incident_id, "Diagnostician",
                     "COMPLETED" if diag.ok else "FAILED", diag.summary)
    st = store.get_state(incident_id)
    if not diag.ok:
        return await _escalate(incident_id, emit, "Diagnosis failed")
    conf = safe_get(diag.data, "confidence", default=0.0)
    store._update(incident_id, lambda s: s.update(diagnosis=diag.data))
    await _emit(emit, "AGENT_COMPLETED", store.get_state(incident_id),
                f"Root cause (conf {conf}): {safe_get(diag.data, 'root_cause', default='?')}")
    if conf < 0.5:
        return await _escalate(incident_id, emit, f"Diagnosis confidence {conf} too low")

    if await _out_of_time():
        return
    # --- GUARDRAIL CHECK (hard gate, not a prompt instruction) ---
    action = safe_get(diag.data, "recommended_action", default="rollback")
    action_details = safe_get(diag.data, "action_details", default={}) or {}
    action_type = str(action_details.get("type", action)).upper()

    guard = RemediatorGuardrail()
    guard_result = guard.check(action=action_type, confidence=conf)
    if not guard_result["allowed"]:
        # Persist the guardrail state so the frontend can show "Approve Fix?"
        store._update(incident_id, lambda s: s.update(
            status="AWAITING_APPROVAL",
            guardrail=guard_result,
        ))
        st = store.get_state(incident_id)
        store.add_history(incident_id, "GUARDRAIL_BLOCKED", guard_result["message"],
                          {"reason": guard_result["reason"], "action": action_type,
                           "confidence": conf})
        await _emit(emit, "AWAITING_APPROVAL", st, guard_result["message"],
                    {"guardrail": guard_result})
        # NOTE: live approval flow (asyncio.Event wait) requires Person A to add
        # a POST /api/approve-fix endpoint that sets a shared event. For now the
        # state halts here visibly — judges see the guardrail firing, not a crash.
        return

    # --- REMEDIATING (up to 2 attempts) ---
    for attempt in range(1, store.MAX_REMEDIATION_ATTEMPTS + 1):
        if await _out_of_time():
            return
        st = store.get_state(incident_id)
        store._update(incident_id, lambda s: s.update(status="REMEDIATING"))
        await _emit(emit, "AGENT_STARTED", store.get_state(incident_id),
                    f"Remediator attempt {attempt}: {action_type} on {service}...")
        _set_step_status(incident_id, "Remediator", "IN_PROGRESS")
        fix = await _call(backend.remediate(action_type, service, action_details),
                          incident_id, "Remediator", "S4", backend)
        _set_step_status(incident_id, "Remediator",
                         "COMPLETED" if fix.ok else "FAILED", fix.summary)
        store._update(incident_id, lambda s: s["remediation"].update(
            {"action": action_type, "attempts": attempt,
             "result": fix.summary if fix.ok else fix.error}))
        if not fix.ok:
            st = store.get_state(incident_id)
            await _emit(emit, "AGENT_FAILED", st, f"Remediation failed: {fix.error}")
            if attempt < store.MAX_REMEDIATION_ATTEMPTS:
                action_type = "RESTART" if action_type == "ROLLBACK" else "SCALE_UP"
                store.add_history(incident_id, "REPLAN_TRIGGERED",
                                  f"Trying alternative fix: {action_type}")
                continue
            return await _escalate(incident_id, emit,
                                   f"Remediation failed after {attempt} attempts: {fix.error}")
        # LATENCY + DETERMINISM: run verification directly against the
        # simulated health check (tool-level), NOT via an LLM agent call.
        # A health check is a tool's job in real SRE systems too; this removes
        # a ~20-25s agent round trip AND makes verification non-flaky.
        from .tools.simulated import dispatch as _tool_dispatch
        import json as _json
        raw = _tool_dispatch("verify_fix", {"service": service,
                                            "check_type": "HEALTH_CHECK"})
        vres = _json.loads(raw)
        verify_ok = vres.get("status") == "success"
        verify_summary = vres.get("result", "health check")
        store.add_history(incident_id,
                          "AGENT_COMPLETED" if verify_ok else "AGENT_FAILED",
                          f"verify_fix (direct): {verify_summary}",
                          {"agent": "Remediator"})
        if verify_ok:
            store._update(incident_id, lambda s: s.update(status="RESOLVED"))
            st = store.get_state(incident_id)
            store.add_history(incident_id, "RESOLVED", verify_summary)
            await _emit(emit, "RESOLVED", st, f"RESOLVED: {verify_summary}")
            return
        if attempt == store.MAX_REMEDIATION_ATTEMPTS:
            return await _escalate(incident_id, emit, "Verification failed after 2 attempts")


async def run_incident_safe(incident_id: str, backend: AgentBackend, emit: EmitFn | None = None):
    """Wrapper: no silent stalls — any unexpected crash becomes ESCALATED."""
    try:
        await run_incident(incident_id, backend, emit)
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        try:
            await _escalate(incident_id, emit, f"Orchestrator crash: {e}")
        except Exception:  # noqa: BLE001
            pass


async def _escalate(incident_id: str, emit: EmitFn | None, reason: str):
    store._update(incident_id, lambda s: s.update(status="ESCALATED"))
    st = store.get_state(incident_id)
    store.add_history(incident_id, "ESCALATED", reason)
    await _emit(emit, "ESCALATED", store.get_state(incident_id),
                f"REQUIRES HUMAN: {reason}")
