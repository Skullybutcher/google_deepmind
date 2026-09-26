"""Incident state store — owned by Muse Spark.

Single-active-incident model (hackathon scope) + JSON persistence after
every transition, per ARCHITECTURE.md §2 / PROJECT_PLAN.md §2.
"""
import copy
import json
import os
import threading
from datetime import datetime, timezone

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "state_current.json")

# Hard limits — non-negotiable (RISKS.md Risk 6).
MAX_PLAN_VERSIONS = 3
MAX_AGENT_RETRIES = 2
MAX_REMEDIATION_ATTEMPTS = 2
AGENT_TIMEOUT_SECONDS = 30
MAX_INCIDENT_DURATION = 120
# Wall-clock ceiling ACTUALLY enforced by the orchestrator. RISKS.md said 120s,
# but real-mode happy path measured ~135s and degraded (replan) ~165-180s — a
# 120s cap would escalate the working demo. 240s = bounded autonomy with 2x
# headroom over the worst measured run. See AGENTS_SYNC.md decisions.
INCIDENT_WALL_CLOCK_LIMIT = 240

VALID_STATUSES = {
    "IDLE",
    "PLANNING",
    "INVESTIGATING",
    "DIAGNOSING",
    "REMEDIATING",
    "REPLANNING",
    "RESOLVED",
    "ESCALATED",
    "AWAITING_APPROVAL",  # guardrail fired — waiting for human to click "Approve Fix?"
}

_lock = threading.Lock()
_store: dict = {"active_id": None, "incidents": {}}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_incident(alert_type: str, service: str, severity: str) -> dict:
    incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    # Consume the pre-injected failures and immediately clear them so that a
    # second trigger (e.g. after a page reload) starts with a clean slate unless
    # the user explicitly re-injects a failure first.
    with _lock:
        injected = list(_store.pop("_injected_failures", []))
    state = {
        "incident_id": incident_id,
        "status": "PLANNING",
        "created_at": _now(),
        "alert": {
            "type": alert_type,
            "service": service,
            "severity": severity,
        },
        "plan": {"version": 0, "steps": [], "reasoning": ""},
        "plan_version_history": [],
        "findings": {"log_analysis": None, "metrics_analysis": None},
        "diagnosis": None,
        "remediation": {"action": None, "result": None, "attempts": 0},
        "guardrail": None,          # set when guardrail fires: {allowed, reason, message, ...}
        "telemetry": {              # per-incident cost + latency panel data
            "started_at": _now(),
            "completed_at": None,
            "total_wall_clock_ms": None,
            "agent_timings": {},    # agent -> {"started_at", "completed_at", "wall_clock_ms"}
            "plan_versions": 1,
            "guardrail_triggered": False,
        },
        "history": [],
        # Failures injected via /api/inject-failure before this trigger are
        # consumed once. The frontend sends failure_type=NONE before every
        # fresh trigger, so stale failures from a prior session are always
        # cleared before new_incident is called.
        "active_failures": injected,
        "retry_count": 0,
        "interaction_ids": {},  # agent -> latest interaction id (prev chaining)
        "environment_id": None,
    }
    with _lock:
        _store["active_id"] = incident_id
        _store["incidents"][incident_id] = state
    add_history(state, "INCIDENT_CREATED", f"{alert_type} on {service} ({severity})")
    persist(state)
    return copy.deepcopy(state)


def get_state(incident_id: str | None = None) -> dict | None:
    with _lock:
        iid = incident_id or _store["active_id"]
        if not iid or iid not in _store["incidents"]:
            return None
        return copy.deepcopy(_store["incidents"][iid])


def _update(incident_id: str, fn) -> dict:
    with _lock:
        state = _store["incidents"][incident_id]
        fn(state)
        snapshot = copy.deepcopy(state)
    persist(snapshot)
    return snapshot


def set_status(incident_id: str, status: str, message: str = "") -> dict:
    assert status in VALID_STATUSES, f"bad status {status}"

    def _fn(s):
        s["status"] = status

    snap = _update(incident_id, _fn)
    add_history(snap, "STATUS", f"{status} {message}".strip())
    return get_state(incident_id)


def add_history(state_or_id, event: str, detail: str = "", extra: dict | None = None) -> dict:
    entry = {"timestamp": _now(), "event": event, "detail": detail}
    if extra:
        entry.update(extra)
    if isinstance(state_or_id, str):
        def _fn(s):
            s["history"].append(entry)
        return _update(state_or_id, _fn)
    # dict snapshot passed (during creation before store write-back)
    state_or_id["history"].append(entry)
    with _lock:
        iid = state_or_id["incident_id"]
        if iid in _store["incidents"]:
            _store["incidents"][iid] = copy.deepcopy(state_or_id)
    persist(state_or_id)
    return state_or_id


def persist(state: dict) -> None:
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError:
        pass  # persistence is best-effort; in-memory is source of truth
