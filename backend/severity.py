"""Severity profiles — how incident levels change the loop itself.

This is the "incidents behave differently by severity" feature the team asked
for: not just a label, but different ORCHESTRATION per level.

  P1 (critical): default (heavy) model everywhere, full parallel investigation,
                 generous replan budget, LOW guardrail threshold (act fast,
                 approve less) — minutes matter more than perfect confidence.
  P2 (major):    fast model tier everywhere, standard budgets, standard
                 guardrail (0.70 confidence to auto-execute).
  P3 (minor):    fast model, compact plan (Planner instructed to keep it
                 minimal), tight replan budget, HIGH guardrail bar (don't
                 touch production for minor incidents without high
                 confidence) — cheap to run, safe to auto-execute.

Benchmarks (scripts/benchmark.py) measure wall-clock + plan versions +
escalation behavior per profile so the differences are EVIDENCE, not claims.
"""
from __future__ import annotations

from .agents.base import FAST_MODEL, DEFAULT_MODEL

PROFILES: dict[str, dict] = {
    "P1": {
        "label": "Critical",
        "model_tier": "default",          # AEGIS_MODEL_TIER override per incident
        "max_plan_versions": 3,           # generous replan budget
        "max_retries": 2,
        "guardrail_threshold": 0.60,      # act fast: approve less
        "plan_hint": ("Full parallel investigation (LogAnalyzer + MetricsAgent "
                      "concurrently), then Diagnostician, then Remediator. "
                      "Use every available agent."),
        "compact": False,
    },
    "P2": {
        "label": "Major",
        "model_tier": "fast",
        "max_plan_versions": 2,
        "max_retries": 2,
        "guardrail_threshold": 0.70,
        "plan_hint": ("Standard investigation; parallel where possible; keep "
                      "the plan to 3-4 steps."),
        "compact": True,
    },
    "P3": {
        "label": "Minor",
        "model_tier": "fast",
        "max_plan_versions": 2,
        "max_retries": 1,
        "guardrail_threshold": 0.85,      # high bar: production actions need certainty
        "plan_hint": ("COMPACT plan: at most 3 steps. A single investigator "
                      "plus Diagnostician plus Remediator is enough for minor "
                      "incidents. Skip redundant data gathering."),
        "compact": True,
    },
}

DEFAULT_PROFILE = "P2"


def get_profile(severity: str | None) -> tuple[str, dict]:
    sev = (severity or DEFAULT_PROFILE).upper()
    if sev not in PROFILES:
        sev = DEFAULT_PROFILE
    return sev, PROFILES[sev]
