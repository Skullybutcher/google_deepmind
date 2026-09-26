# AEGIS Benchmarks

```text
Run: 2026-09-26 17:19 UTC
```

| Scenario | Sev | Final status | Wall avg (s) | Wall max (s) | Plan versions | Agent calls |
|---|---|---|---|---|---|---|
| P2 happy                 | P2 | RESOLVED           |   0.01 |   0.02 |           1.0 |         6.0 |
| P1 happy (critical)      | P1 | RESOLVED           |   0.01 |   0.02 |           1.0 |         6.0 |
| P3 happy (minor)         | P3 | RESOLVED           |   0.08 |   0.22 |           1.0 |         5.0 |
| P1 degraded (log down)   | P1 | RESOLVED           |   0.02 |   0.02 |           2.0 |         7.0 |
| P3 guarded (low conf)    | P3 | RESOLVED           |    0.0 |   0.01 |           1.0 |         5.0 |
| P2 remediation failure   | P2 | ESCALATED          |   0.01 |   0.02 |           1.0 |         4.0 |

**Reading the table**
- `Agent calls` is the LLM cost proxy: in real mode each call is one
  Interactions API round trip (tokens + latency).
- P3 runs FEWER steps (compact plan) and uses the fast model tier —
  cheaper and faster than P1 by design.
- P1 degraded replans (v2) instead of retrying a deterministically
  dead log source — the planner drops the failed investigator.
- Guardrail scenarios park in AWAITING_APPROVAL (P3's 0.85 bar) vs
  auto-executing (P1's 0.60 bar) — severity changes autonomy.

