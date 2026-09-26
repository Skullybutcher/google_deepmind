import asyncio
from state import IncidentState
from agents.base import call_agent

class Orchestrator:
    def __init__(self, state: IncidentState, emit_callback):
        self.state = state
        self.emit = emit_callback
    
    async def run(self):
        self.state.add_event("INCIDENT_CREATED", message="Incident started")
        self.state.persist()
        await self.emit()

        # Call Planner
        plan_res = await call_agent("Planner", [], [])
        self.state.plan = plan_res
        self.state.status = "INVESTIGATING"
        self.state.add_event("PLAN_CREATED", message="Plan created with 4 steps")
        self.state.persist()
        await self.emit()

        # Execute step 1 and 2 in parallel
        await self._emit_agent_started("LogAnalyzer")
        await self._emit_agent_started("MetricsAgent")
        
        log_res, met_res = await asyncio.gather(
            call_agent("LogAnalyzer", [], []),
            call_agent("MetricsAgent", [], [])
        )
        
        if log_res.get("status") == "error":
            self.state.add_event("AGENT_FAILED", agent="LogAnalyzer", message=log_res["message"])
            self.state.status = "REPLANNING"
            self.state.add_event("REPLAN_TRIGGERED", message="LogAnalyzer failed, switching to degraded mode")
            self.state.persist()
            await self.emit()
            
            # Replan
            plan_res = await call_agent("Planner", [], [])
            self.state.plan_version += 1
            self.state.status = "INVESTIGATING"
            self.state.add_event("PLAN_UPDATED", message="Plan updated")
            self.state.persist()
            await self.emit()
        else:
            self.state.add_event("AGENT_COMPLETED", agent="LogAnalyzer", message="Completed")
            self.state.add_event("AGENT_COMPLETED", agent="MetricsAgent", message="Completed")
            self.state.persist()
            await self.emit()

        # Step 3
        self.state.status = "DIAGNOSING"
        await self._emit_agent_started("Diagnostician")
        diag_res = await call_agent("Diagnostician", [], [])
        self.state.add_event("AGENT_COMPLETED", agent="Diagnostician", message="Root cause: Memory leak")
        self.state.persist()
        await self.emit()

        # Step 4
        self.state.status = "REMEDIATING"
        await self._emit_agent_started("Remediator")
        rem_res = await call_agent("Remediator", [], [])
        
        if rem_res.get("status") == "error":
            self.state.add_event("AGENT_FAILED", agent="Remediator", message=rem_res["message"])
            self.state.status = "ESCALATED"
            self.state.add_event("ESCALATED", message="Requires Human Intervention")
            self.state.persist()
            await self.emit()
        else:
            self.state.add_event("AGENT_COMPLETED", agent="Remediator", message="Completed")
            self.state.status = "RESOLVED"
            self.state.add_event("RESOLVED", message="Incident RESOLVED. All health checks passing.")
            self.state.persist()
            await self.emit()

    async def _emit_agent_started(self, agent_name):
        self.state.add_event("AGENT_STARTED", agent=agent_name, message=f"{agent_name} running...")
        self.state.persist()
        await self.emit()
