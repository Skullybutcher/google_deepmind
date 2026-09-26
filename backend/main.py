"""FastAPI entrypoint — owned by Muse Spark.

Routes per ARCHITECTURE.md §2. FreeBuff swaps `get_backend` to return the
real Interactions-API backend; orchestrator + routes stay identical.
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from itertools import count

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from . import state as store
from .orchestrator import StubBackend, run_incident_safe as run_incident

load_dotenv("D:/dmh/.env")
load_dotenv()  # also try local .env

_subscribers: set[asyncio.Queue] = set()


async def _broadcast(event: dict):
    # sse-starlette expects either a str (default "message" event) or a dict
    # with event/data keys. Passing our raw payload dict previously caused
    # a pydantic ValidationError -> HTTP 500 on every /api/events connect.
    await _broadcast_raw({"event": "state_update", "data": json.dumps(event)})


async def _broadcast_raw(chunk: dict):
    global _seq_counter
    # SSE-native id field (NOT a custom key — sse-starlette passes dict entries
    # as ServerSentEvent kwargs, and unknown keys raise TypeError).
    chunk["id"] = str(next(_seq_counter))
    for q in list(_subscribers):
        await q.put(chunk)


def get_backend():
    """USE_REAL=1 -> RealBackend (Interactions API). Default StubBackend.
    FreeBuff/Person B: nothing to change here; implement tools/simulated.py
    dispatch() and prompts flow through automatically."""
    if os.environ.get("USE_REAL") == "1":
        from .agents.base import RealBackend
        st = store.get_state()
        return RealBackend(getattr(st, "get", lambda k, d=None: d)("active_failures", [])
                           if isinstance(st, dict) else [])
    return StubBackend()


class TriggerReq(BaseModel):
    alert_type: str = "HIGH_LATENCY"
    service: str = "api-gateway"
    severity: str = "P1"  # P1|P2|P3 — drives the severity profile (see severity.py)


class WebhookAlert(BaseModel):
    """PagerDuty/Opsgenie-style ingestion: tolerate extra fields, map common
    aliases. Extra JSON fields are accepted (model_config) and ignored."""
    model_config = {"extra": "allow"}
    alert_type: str | None = None
    service: str | None = None
    severity: str | None = None
    alert_name: str | None = None      # PagerDuty alias
    component: str | None = None       # Opsgenie alias
    source: str = "webhook"


class FailureReq(BaseModel):
    failure_type: str = Field(pattern="^(LOG_SOURCE_UNAVAILABLE|REMEDIATION_FAILED|NONE)$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="AEGIS Orchestrator")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])

_seq_counter = count(1)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "aegis-orchestrator"}


@app.get("/api/debug/env")
def debug_env():
    """Deployment diagnostics. NEVER returns the key value — only presence
    and length — so it's safe to expose while debugging Render env vars."""
    k = os.environ.get("GEMINI_API_KEY", "")
    return {
        "USE_REAL": os.environ.get("USE_REAL", "<unset>"),
        "GEMINI_API_KEY_present": bool(k),
        "GEMINI_API_KEY_length": len(k),
        "GEMINI_API_KEY_prefix_ok": k.startswith("AIza"),
        "python": os.sys.version.split()[0],
    }


@app.post("/api/trigger-incident")
async def trigger(req: TriggerReq):
    st = store.new_incident(req.alert_type, req.service, req.severity)
    backend = get_backend()
    asyncio.create_task(run_incident(st["incident_id"], backend, _broadcast))
    return {"incident_id": st["incident_id"], "status": "PLANNING",
            "severity": st["alert"]["severity"],
            "message": "Incident created. Planner Agent activated."}


@app.post("/api/webhooks/alert")
async def webhook_alert(req: WebhookAlert):
    """Real-world ingestion seam: monitoring tools (PagerDuty, Opsgenie,
    Grafana) POST alerts here. Maps their common field aliases, then runs
    the exact same pipeline as the dashboard trigger."""
    alert_type = req.alert_type or req.alert_name or "GENERIC_ALERT"
    service = req.service or req.component or "unknown-service"
    severity = (req.severity or "P2").upper()
    # tolerate severity spellings like "critical" / "sev1"
    if severity.startswith("CRIT") or severity in ("SEV1", "1"):
        severity = "P1"
    elif severity.startswith("WARN") or severity in ("SEV3", "3"):
        severity = "P3"
    elif severity.startswith("SEV2") or severity in ("2", "MAJOR"):
        severity = "P2"
    st = store.new_incident(alert_type, service, severity)
    store.add_history(st["incident_id"], "WEBHOOK_INGESTED",
                      f"alert received from {req.source}")
    backend = get_backend()
    asyncio.create_task(run_incident(st["incident_id"], backend, _broadcast))
    return {"incident_id": st["incident_id"], "status": "PLANNING",
            "severity": severity,
            "message": f"Webhook alert ingested from {req.source}."}


@app.post("/api/approve-fix")
async def approve_fix():
    """Human-in-the-loop: resume an incident parked in AWAITING_APPROVAL.
    The parked orchestrator task wakes, re-checks the guardrail (now with
    human override recorded in history) and executes the fix."""
    st = store.get_state()
    if not st:
        raise HTTPException(404, "no active incident")
    if st["status"] != "AWAITING_APPROVAL":
        raise HTTPException(400, f"incident is {st['status']}, not AWAITING_APPROVAL")
    resolved = store.resolve_approval(st["incident_id"], approved=True)
    if not resolved:
        raise HTTPException(409, "no pending approval object (incident may have timed out)")
    store.add_history(st["incident_id"], "APPROVED",
                      "human approved remediation via dashboard")
    await _broadcast({"event_type": "APPROVED", "incident_id": st["incident_id"],
                      "data": {"status": "REMEDIATING",
                               "plan_version": st["plan"]["version"],
                               "steps": st["plan"]["steps"],
                               "message": "Human approved. Executing fix..."}})
    return {"status": "ok", "incident_id": st["incident_id"],
            "message": "Approval recorded; remediation resuming."}


@app.post("/api/deny-fix")
async def deny_fix():
    """Deny: the parked task wakes, sees approved=False, escalates."""
    st = store.get_state()
    if not st or st["status"] != "AWAITING_APPROVAL":
        raise HTTPException(400, "no incident awaiting approval")
    store.resolve_approval(st["incident_id"], approved=False)
    store.add_history(st["incident_id"], "DENIED",
                      "human denied remediation via dashboard")
    return {"status": "ok", "incident_id": st["incident_id"],
            "message": "Denial recorded; incident will escalate."}


@app.post("/api/inject-failure")
async def inject(req: FailureReq):
    st = store.get_state()
    if not st:
        # No active incident (e.g. fresh server): STILL accept the flags into
        # the module-level holder — the demo script is "inject -> trigger",
        # and the first trigger after a restart must honor pre-injected
        # failures. (Verified bug: this used to 400 and silently skip.)
        if req.failure_type == "NONE":
            store._store["_injected_failures"] = []
        else:
            holder = store._store.setdefault("_injected_failures", [])
            if req.failure_type not in holder:
                holder.append(req.failure_type)
        return {"status": "ok",
                "active_failures": list(store._store["_injected_failures"]),
                "note": "no active incident; flags will apply to next trigger"}
    def _fn(s):
        if req.failure_type == "NONE":
            s["active_failures"] = []
        elif req.failure_type not in s["active_failures"]:
            s["active_failures"].append(req.failure_type)
    store._update(st["incident_id"], _fn)
    # Mirror into the module-level holder so NEW incidents inherit the flags
    # (demo flow: inject -> trigger -> degraded run).
    current = store.get_state(st["incident_id"])["active_failures"]
    store._store["_injected_failures"] = list(current)
    return {"status": "ok", "active_failures": current}


@app.get("/api/state")
def full_state():
    st = store.get_state()
    if not st:
        raise HTTPException(404, "no incident yet")
    return st


@app.get("/api/events")
async def events():
    q: asyncio.Queue = asyncio.Queue()
    # Heal late subscribers: replay a full snapshot immediately on connect, so
    # a dashboard joining after POST /trigger-incident still renders all state
    # (verified E2E: every _emit sends complete plan/steps/status).
    st = store.get_state()
    if st:
        seq = next(_seq_counter)
        q.put_nowait({"event": "state_update", "id": str(seq), "data": json.dumps({
            "event_type": "STATE_SNAPSHOT", "incident_id": st["incident_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"status": st["status"], "plan_version": st["plan"]["version"],
                     "steps": st["plan"]["steps"], "history": st["history"],
                     "message": "snapshot on connect"}})})
    _subscribers.add(q)

    async def gen():
        try:
            while True:
                item = await q.get()
                yield item
        finally:
            _subscribers.discard(q)

    return EventSourceResponse(gen())


@app.get("/", response_class=HTMLResponse)
def root():
    return ("<h1>AEGIS Orchestrator</h1><p>POST /api/trigger-incident to start. "
            "GET /api/events for SSE. Frontend served separately.</p>")
