"""
AEGIS Golden-Scenario Eval Harness
====================================
Replays scripted incidents against StubBackend (no API key needed) and
checks every assertion in the fixture. Prints a pass/fail table and exits
non-zero on any failure.

Usage:
    cd google_deepmind
    python -m backend.eval.run_eval                     # all fixtures
    python -m backend.eval.run_eval --fixture sc03      # single fixture
    python -m backend.eval.run_eval --live              # against http://localhost:8000

Exit codes:  0 = all pass,  1 = failures
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

# ── colour helpers ───────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def _pass(msg: str) -> str:  return f"{GREEN}PASS{RESET} {msg}"
def _fail(msg: str) -> str:  return f"{RED}FAIL{RESET} {msg}"

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── thin mock that drives StubBackend directly ───────────────────────────────

class _EvalState:
    """Minimal incident state tracker for the eval harness."""
    def __init__(self):
        self.status = "PLANNING"
        self.plan_version = 1
        self.history: list[dict] = []
        self.tools_called: list[str] = []
        self.diagnosis: dict | None = None
        self.guardrail_triggered = False
        self.guardrail_reason: str | None = None

    def event(self, ev: str, **kw):
        self.history.append({"event": ev, **kw})


async def _run_fixture_mock(fixture: dict) -> _EvalState:
    """Drive StubBackend through the full orchestrator flow."""
    # Import here so path setup isn't needed at module level
    import sys, os
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

    from backend.orchestrator import StubBackend
    from backend.guardrails import RemediatorGuardrail
    from backend.agents.interface import safe_get

    failures = fixture.get("inject_failures", [])
    override = fixture.get("_sim_override", {})
    alert    = fixture["alert"]
    service  = alert.get("service", "api-gateway")

    backend = StubBackend(failures=failures)
    st = _EvalState()
    st.event("INCIDENT_CREATED")

    # ── Plan ──────────────────────────────────────────────────────────────
    plan = await backend.create_plan(alert)
    st.event("PLAN_CREATED")

    # ── Investigate (parallel) ────────────────────────────────────────────
    st.tools_called.extend(["fetch_logs", "fetch_metrics"])
    log_res, met_res = await asyncio.gather(
        backend.analyze_logs(service),
        backend.analyze_metrics(service),
    )

    log_ok = log_res.ok
    if log_ok:
        st.tools_called.extend(["correlate_findings"])
        st.event("AGENT_COMPLETED", agent="LogAnalyzer")
        st.event("AGENT_COMPLETED", agent="MetricsAgent")
    else:
        st.event("AGENT_FAILED", agent="LogAnalyzer",
                 error_code=log_res.error_code)
        st.event("AGENT_COMPLETED", agent="MetricsAgent")
        st.event("REPLAN_TRIGGERED", message="degraded mode")
        st.plan_version += 1
        await backend.create_plan(alert, context="failed: LogAnalyzer")
        st.event("PLAN_UPDATED")

    # ── Diagnose ──────────────────────────────────────────────────────────
    log_find = log_res.data if log_ok else {}
    met_find = met_res.data

    # Allow confidence override for SC-08
    diag_res = await backend.diagnose(log_find, met_find)
    diag_data = dict(diag_res.data)
    if "diagnosis_confidence" in override:
        diag_data["confidence"] = override["diagnosis_confidence"]
    if "diagnosis_action" in override:
        diag_data["recommended_action"] = override["diagnosis_action"]
        if "action_details" in diag_data:
            diag_data["action_details"]["type"] = override["diagnosis_action"].upper()

    st.diagnosis = diag_data
    st.tools_called.extend(["correlate_findings", "propose_diagnosis"])
    st.event("AGENT_COMPLETED", agent="Diagnostician")

    # ── Guardrail check ───────────────────────────────────────────────────
    action     = safe_get(diag_data, "recommended_action", default="rollback")
    confidence = safe_get(diag_data, "confidence", default=0.0)
    action_type = str((safe_get(diag_data, "action_details", default={}) or {}).get(
        "type", action)).upper()

    guard = RemediatorGuardrail()
    g = guard.check(action=action_type, confidence=confidence)
    if not g["allowed"]:
        st.guardrail_triggered = True
        st.guardrail_reason    = g["reason"]
        st.status = "AWAITING_APPROVAL"
        st.event("AWAITING_APPROVAL", reason=g["reason"])
        return st

    # ── Remediate ─────────────────────────────────────────────────────────
    for attempt in range(1, 3):
        st.tools_called.append("execute_fix")
        fix = await backend.remediate(action_type, service)

        if not fix.ok:
            st.event("AGENT_FAILED", agent="Remediator", error=fix.error)
            if attempt < 2:
                continue
            st.status = "ESCALATED"
            st.event("ESCALATED", message="max attempts")
            return st

        st.tools_called.append("verify_fix")
        verify = await backend.verify(service)
        st.event("AGENT_COMPLETED", agent="Remediator")
        st.status = "RESOLVED"
        st.event("RESOLVED")
        return st

    return st


# ── assertion engine ─────────────────────────────────────────────────────────

def _check(fixture: dict, state: _EvalState) -> list[tuple[bool, str]]:
    exp = fixture.get("expect", {})
    results: list[tuple[bool, str]] = []

    def chk(cond: bool, label: str):
        results.append((cond, label))

    if "final_status" in exp:
        chk(state.status == exp["final_status"],
            f"final_status: want={exp['final_status']} got={state.status}")

    if "escalated" in exp:
        escalated = any(e["event"] == "ESCALATED" for e in state.history)
        chk(escalated == exp["escalated"],
            f"escalated: want={exp['escalated']} got={escalated}")

    for tool in exp.get("tools_called", []):
        chk(tool in state.tools_called, f"tool_called: {tool}")

    event_types = {e["event"] for e in state.history}
    for ev in exp.get("events_must_include", []):
        chk(ev in event_types, f"event_present: {ev}")

    diag_exp = exp.get("diagnosis", {})
    if diag_exp and state.diagnosis:
        conf = state.diagnosis.get("confidence", 0.0)
        if "recommended_action" in diag_exp:
            chk(state.diagnosis.get("recommended_action") == diag_exp["recommended_action"],
                f"diagnosis.recommended_action: want={diag_exp['recommended_action']} got={state.diagnosis.get('recommended_action')}")
        if "confidence_min" in diag_exp:
            chk(conf >= diag_exp["confidence_min"],
                f"diagnosis.confidence >= {diag_exp['confidence_min']}: got={conf:.2f}")
        if "confidence_max" in diag_exp:
            chk(conf <= diag_exp["confidence_max"],
                f"diagnosis.confidence <= {diag_exp['confidence_max']}: got={conf:.2f}")

    if "plan_versions" in exp:
        chk(state.plan_version == exp["plan_versions"],
            f"plan_versions: want={exp['plan_versions']} got={state.plan_version}")

    if "guardrail_triggered" in exp:
        chk(state.guardrail_triggered == exp["guardrail_triggered"],
            f"guardrail_triggered: want={exp['guardrail_triggered']} got={state.guardrail_triggered}")

    if "guardrail_reason" in exp:
        chk(state.guardrail_reason == exp["guardrail_reason"],
            f"guardrail_reason: want={exp['guardrail_reason']} got={state.guardrail_reason}")

    return results


# ── runner ───────────────────────────────────────────────────────────────────

async def run_fixture(fixture: dict, live: bool = False) -> tuple[int, int, float]:
    t0 = time.monotonic()

    if live:
        import httpx
        base = "http://localhost:8000"
        for f in fixture.get("inject_failures", []):
            async with httpx.AsyncClient() as c:
                await c.post(f"{base}/api/inject-failure", json={"failure_type": f})
        async with httpx.AsyncClient() as c:
            await c.post(f"{base}/api/trigger-incident",
                         json={"alert_type": fixture["alert"]["type"],
                               "service": fixture["alert"]["service"],
                               "severity": fixture["alert"]["severity"]},
                         timeout=30)
        terminal = {"RESOLVED", "ESCALATED", "AWAITING_APPROVAL"}
        data: dict = {}
        for _ in range(120):
            await asyncio.sleep(1)
            async with httpx.AsyncClient() as c:
                r = await c.get(f"{base}/api/state")
                data = r.json()
            if data.get("status") in terminal:
                break

        class _APIState:
            def __init__(self, d):
                self.status             = d.get("status", "")
                self.plan_version       = d.get("plan", {}).get("version", 1)
                self.history            = d.get("history", [])
                self.tools_called       = d.get("tools_called", [])
                self.diagnosis          = d.get("diagnosis")
                self.guardrail_triggered = bool(d.get("guardrail"))
                self.guardrail_reason   = (d.get("guardrail") or {}).get("reason")
        state = _APIState(data)
    else:
        state = await _run_fixture_mock(fixture)

    elapsed = time.monotonic() - t0
    checks = _check(fixture, state)
    passed = sum(1 for ok, _ in checks if ok)
    total  = len(checks)

    sc_id  = fixture.get("id", "?")
    desc   = fixture.get("description", "")
    badge  = f"{GREEN}PASS{RESET}" if passed == total else f"{RED}FAIL{RESET}"
    print(f"\n{BOLD}[{sc_id}] {desc}{RESET}  {badge}  ({passed}/{total})  {elapsed:.1f}s")
    for ok, label in checks:
        print(f"  {_pass(label) if ok else _fail(label)}")

    return passed, total, elapsed


async def main(args: argparse.Namespace):
    fixtures = sorted(FIXTURES_DIR.glob("*.json"))
    if args.fixture:
        fixtures = [f for f in fixtures if args.fixture.lower() in f.stem.lower()]
        if not fixtures:
            print(f"{RED}No fixtures match '{args.fixture}'{RESET}")
            sys.exit(1)

    grand_pass = grand_total = 0
    total_time = 0.0

    print(f"\n{BOLD}AEGIS Golden-Scenario Eval Harness{RESET}  ({len(fixtures)} scenarios)")
    print("=" * 60)

    for fpath in fixtures:
        with open(fpath) as fh:
            fixture = json.load(fh)
        p, t, elapsed = await run_fixture(fixture, live=args.live)
        grand_pass += p
        grand_total += t
        total_time += elapsed

    print("\n" + "=" * 60)
    verdict = f"{GREEN}ALL PASSING{RESET}" if grand_pass == grand_total else f"{RED}FAILURES DETECTED{RESET}"
    print(f"{BOLD}Result: {grand_pass}/{grand_total} checks  |  {verdict}  |  {total_time:.1f}s total{RESET}\n")
    sys.exit(0 if grand_pass == grand_total else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AEGIS eval harness")
    parser.add_argument("--fixture", help="Filter by ID prefix (e.g. sc03)")
    parser.add_argument("--live", action="store_true",
                        help="Run against a live server at http://localhost:8000")
    asyncio.run(main(parser.parse_args()))
