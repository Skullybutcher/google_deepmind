import asyncio
from tools import simulated

async def call_agent(agent_name, messages, tools, previous_interaction_id=None):
    await asyncio.sleep(1)
    
    if agent_name == "Planner":
        from agents.planner import DEFAULT_FALLBACK
        return DEFAULT_FALLBACK
    
    elif agent_name == "LogAnalyzer":
        res = simulated.fetch_logs("api-gateway")
        if res.get("status") == "error":
            return {"status": "error", "error_code": res["error_code"], "message": res["message"]}
        return {"status": "completed", "output": "Log anomalies found"}
        
    elif agent_name == "MetricsAgent":
        return {"status": "completed", "output": "Metrics anomalies found"}
        
    elif agent_name == "Diagnostician":
        return {"status": "completed", "diagnosis": {"root_cause": "Memory leak from deploy v2.3.1"}}
        
    elif agent_name == "Remediator":
        res = simulated.execute_fix("ROLLBACK", "api-gateway")
        if res.get("status") == "error":
            return {"status": "error", "error_code": res["error_code"], "message": res["message"]}
        return {"status": "completed", "action": "Rollback completed"}
    
    return {}
