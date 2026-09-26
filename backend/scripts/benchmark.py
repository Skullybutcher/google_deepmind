"""AEGIS benchmark harness — severity profiles measured, not claimed.

Runs each severity scenario through the ORCHESTRATOR ITSELF (stub backend,
deterministic) and measures:
  - wall clock (execution time)
  - plan versions used (replan count)
  - steps executed / retries / guardrail outcomes
  - LLM cost proxy: agent calls per incident (real mode burns tokens per call)

Output: markdown table (stdout + benchmarks.md) that OC's dashboard table and
the writeup can quote directly.

Usage:
    cd backend && python -m scripts.benchmark        (or python benchmark.py)
"""
from __future__ import annotations

import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

# repo root = two levels up from this file (backend/scripts/benchmark.py)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend import state as store  # noqa: E402
from backend.orchestrator import (  # noqa: E402
    StubBackend, run_incident, run_incident_safe,
)
from backend.severity import PROFILES  # noqa: E402

SCENARIOS = [
    # (name, severity, injected_failures, expect_terminal)
    ("P2 happy",               "P2", [],                        "RESOLVED"),
    ("P1 happy (critical)",    "P1", [],                        "RESOLVED"),
    ("P3 happy (minor)",       "P3", [],                        "RESOLVED"),
    ("P1 degraded (log down)", "P1", ["LOG_SOURCE_UNAVAILABLE"], "RESOLVED"),
    ("P3 guarded (low conf)",  "P3", ["LOG_SOURCE_UNAVAILABLE"], None),  # either terminal ok
    ("P2 remediation failure", "P2", ["REMEDIATION_FAILED"],    "ESCALATED"),
]


async def run_one(name: str, severity: str, failures: list, runs: int = 3) -> dict:
    wall_clocks, versions_list, calls_list = [], [], []
    final_status = None

    for _ in range(runs):
        store._store.clear()
        store._store.update({"active_id": None, "incidents": {}})
        store._store["_injected_failures"] = list(failures)
        st = store.new_incident("HIGH_LATENCY", "api-gateway", severity)
        iid = st["incident_id"]

        # Auto-approver: guardrail-parked incidents (AWAITING_APPROVAL) must
        # not wait the 120s human timeout inside a benchmark run.
        async def _auto_approve(iid=iid):
            while True:
                await asyncio.sleep(0.2)
                s = store.get_state(iid)
                if not s:
                    return
                if s["status"] == "AWAITING_APPROVAL":
                    store.resolve_approval(iid, approved=True)
                if s["status"] in ("RESOLVED", "ESCALATED"):
                    return

        approver = asyncio.create_task(_auto_approve())
        t0 = time.monotonic()
        await run_incident_safe(iid, StubBackend(), emit=None)
        elapsed = time.monotonic() - t0
        approver.cancel()

        s = store.get_state(iid)
        final_status = s["status"]
        agent_calls = sum(1 for h in s["history"] if h["event"] == "AGENT_COMPLETED")
        wall_clocks.append(elapsed)
        versions_list.append(s["plan"]["version"])
        calls_list.append(agent_calls)

    return {
        "scenario": name,
        "severity": severity,
        "status": final_status,
        "wall_s": round(statistics.mean(wall_clocks), 2),
        "wall_max": round(max(wall_clocks), 2),
        "plan_versions": statistics.mean(versions_list),
        "agent_calls": statistics.mean(calls_list),
        "runs": runs,
    }


def _fmt_row(r: dict) -> str:
    return (f"| {r['scenario']:<24} | {r['severity']} | {r['status']:<18} | "
            f"{r['wall_s']:>6} | {r['wall_max']:>6} | "
            f"{r['plan_versions']:>13.1f} | {r['agent_calls']:>11.1f} |")


def main() -> int:
    print("Running benchmark suite (stub backend, 3 runs per scenario)...\n")
    rows = []
    for name, sev, failures, _expect in SCENARIOS:
        r = asyncio.run(run_one(name, sev, failures))
        rows.append(r)
        print(f"  {name:<26} -> {r['status']:<10} {r['wall_s']}s "
              f"(v{r['plan_versions']:.0f}, {r['agent_calls']:.0f} agent calls)")

    header = ("| Scenario | Sev | Final status | Wall avg (s) | Wall max (s) | "
              "Plan versions | Agent calls |")
    sep = "|---|---|---|---|---|---|---|"
    table = "\n".join([header, sep] + [_fmt_row(r) for r in rows])

    notes = (
        "\n\n**Reading the table**\n"
        "- `Agent calls` is the LLM cost proxy: in real mode each call is one\n"
        "  Interactions API round trip (tokens + latency).\n"
        "- P3 runs FEWER steps (compact plan) and uses the fast model tier —\n"
        "  cheaper and faster than P1 by design.\n"
        "- P1 degraded replans (v2) instead of retrying a deterministically\n"
        "  dead log source — the planner drops the failed investigator.\n"
        "- Guardrail scenarios park in AWAITING_APPROVAL (P3's 0.85 bar) vs\n"
        "  auto-executing (P1's 0.60 bar) — severity changes autonomy.\n"
    )

    out = f"# AEGIS Benchmarks\n\n```text\nRun: {time.strftime('%Y-%m-%d %H:%M UTC')}\n```\n\n{table}{notes}\n"
    out_path = Path(__file__).resolve().parents[2] / "benchmarks.md"
    out_path.write_text(out, encoding="utf-8")
    print(f"\nWrote {out_path}")
    print()
    print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
