import asyncio
import json
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from state import IncidentState
from orchestrator import Orchestrator
from tools.simulated import set_failures

app = FastAPI(title="AEGIS")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

events_queue = asyncio.Queue()
current_state = None

async def emit_state():
    global current_state
    if current_state:
        event_data = {
            "event_type": current_state.history[-1]["event"] if current_state.history else "STATE_UPDATE",
            "timestamp": current_state.history[-1]["timestamp"] if current_state.history else "",
            "incident_id": current_state.incident_id,
            "data": {
                "status": current_state.status,
                "steps": _get_steps(),
                "message": current_state.history[-1].get("message", "") if current_state.history else ""
            }
        }
        await events_queue.put(event_data)

def _get_steps():
    if not current_state or not current_state.plan: return []
    steps = current_state.plan.get("steps", [])
    history = current_state.history
    
    for step in steps:
        step["status"] = "PENDING"
        for h in history:
            if h.get("agent") == step["agent"]:
                if h["event"] == "AGENT_STARTED":
                    step["status"] = "IN_PROGRESS"
                elif h["event"] == "AGENT_COMPLETED":
                    step["status"] = "COMPLETED"
                elif h["event"] == "AGENT_FAILED":
                    step["status"] = "FAILED"
    return steps

@app.post("/api/trigger-incident")
async def trigger_incident(background_tasks: BackgroundTasks):
    global current_state
    current_state = IncidentState(incident_id="INC-20260926-001")
    orchestrator = Orchestrator(current_state, emit_state)
    background_tasks.add_task(orchestrator.run)
    return {"incident_id": current_state.incident_id, "status": "PLANNING"}

@app.post("/api/inject-failure")
async def inject_failure(req: dict):
    failures = [req.get("failure_type")]
    set_failures(failures)
    return {"status": "ok", "active_failures": failures}

@app.get("/api/events")
async def sse_events(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(events_queue.get(), timeout=1.0)
                yield {
                    "event": "state_update",
                    "data": json.dumps(event)
                }
            except asyncio.TimeoutError:
                pass
    return EventSourceResponse(event_generator())
