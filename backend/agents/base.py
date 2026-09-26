"""Real Interactions-API backend — implements AgentBackend (interface.py).

Teammate contract (Person B):
  await call_agent(messages, tools=None, previous_interaction_id=None,
                   environment_id=None, timeout=90.0) -> dict
  returns {"interaction_id", "environment_id", "output_text",
           "steps": [...raw step dicts...],
           "function_calls": [{"call_id","name","arguments"}]}

Auth: explicit api_key read from D:/dmh/.env (GEMINI_API_KEY). NEVER rely on
  env vars — this machine has a stale/invalid GOOGLE_API_KEY that the SDK
  would otherwise prefer, causing 400 API_KEY_INVALID.

Spike-proven facts (2026-09-26, SDK google-genai 2.25.0):
  - client.interactions.create(agent="antigravity-preview-09-2026",
      input=..., environment="remote") -> interaction (.id, .environment_id,
      .output_text, .steps). Fresh sandbox call ~11-17s; chained ~6-8s.
  - Custom tools: tools=[{"type":"function","name":...,"description":...,
      "parameters":{JSON schema}}]. Agent does NOT execute them — it returns
      steps=[{type:function_call, id, name, arguments}] with EMPTY output_text.
  - Orchestrator executes the tool LOCALLY, then follows up with
      input=[{"type":"function_result","call_id":id,"name":name,"result":str}],
      previous_interaction_id=<id>, environment=<env_id>, tools=[same].
      Repeat until no function_call steps (cap 4 turns), then read output_text.
  - previous_interaction_id chaining confirmed working (context retained).
  - Structured output: parse the REPORT tool's call args (not output_text —
      the agent writes prose there). Prompts force a final report_* call.
  - Timeouts: 90s+ (NOT 30s) — sandbox provisioning alone exceeds 10s.
"""
import asyncio
import json
import os

from .interface import AgentResult, PlanResult, PlanStep
from .. import state as store  # live failure-flag reads (OC's mid-run inject)

AGENT_ID = "antigravity-preview-09-2026"
AGENT_TIMEOUT = 120.0
MAX_TOOL_TURNS = 5
_ENV_PATH = os.environ.get("AEGIS_ENV_PATH", "D:/dmh/.env")

_VALID_AGENTS = ("LogAnalyzer", "MetricsAgent", "Diagnostician", "Remediator")


def _api_key() -> str:
    # 1) AEGIS_ENV_PATH file (default points at this machine's D:/dmh/.env),
    # 2) plain GEMINI_API_KEY env var (teammates / deployment).
    env_key = os.environ.get("GEMINI_API_KEY", "")
    try:
        with open(_ENV_PATH) as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    if env_key:
        return env_key
    raise RuntimeError("GEMINI_API_KEY not found: set the env var or create "
                       f"{_ENV_PATH}")


def _client():
    # PROD BUG FIXED: this used to os.environ.pop GEMINI_API_KEY, deleting the
    # key from the running process on the FIRST agent call. Harmless locally
    # (D:/dmh/.env file fallback saved us), fatal on Render (no file). We only
    # pass api_key EXPLICITLY below, so the SDK never needs env-var probing;
    # popping is unnecessary and destructive. (GOOGLE_API_KEY note: the SDK
    # would prefer it over nothing, but we always pass api_key explicitly.)
    from google import genai
    return genai.Client(api_key=_api_key())


def tool_def(name: str, description: str, properties: dict, required: list) -> dict:
    return {"type": "function", "name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required}}


_STEP_SCHEMA = {"type": "object",
    "properties": {
        "id": {"type": "string", "description": "Step ID like S1, S2"},
        "agent": {"type": "string", "enum": list(_VALID_AGENTS)},
        "description": {"type": "string"},
        "depends_on": {"type": "array", "items": {"type": "string"}}},
    "required": ["id", "agent", "description", "depends_on"]}

TOOL_DEFS = {
    "create_plan": tool_def("create_plan", "Create a structured incident response plan",
        {"steps": {"type": "array", "items": _STEP_SCHEMA},
         "reasoning": {"type": "string"}}, ["steps", "reasoning"]),
    "fetch_logs": tool_def("fetch_logs", "Fetch application logs for a service",
        {"service": {"type": "string"}, "time_window_minutes": {"type": "integer"},
         "log_level": {"type": "string"}}, ["service"]),
    "analyze_pattern": tool_def("analyze_pattern", "Analyze log entries for anomalies",
        {"log_entries": {"type": "array"}, "focus_area": {"type": "string"}}, ["log_entries"]),
    "fetch_metrics": tool_def("fetch_metrics", "Fetch infrastructure metrics",
        {"service": {"type": "string"},
         "metrics": {"type": "array", "items": {"type": "string"}},
         "time_window_minutes": {"type": "integer"}}, ["service"]),
    "detect_anomaly": tool_def("detect_anomaly", "Detect anomalies in metric series",
        {"metrics": {"type": "object"}}, ["metrics"]),
    "correlate_findings": tool_def("correlate_findings", "Correlate log+metric findings",
        {"log_findings": {"type": "object"}, "metrics_findings": {"type": "object"}}, []),
    "propose_diagnosis": tool_def("propose_diagnosis", "Propose root cause + fix",
        {"evidence": {"type": "array"}, "hypothesis": {"type": "string"}}, ["hypothesis"]),
    "execute_fix": tool_def("execute_fix", "Execute a remediation action in sandbox",
        {"action_type": {"type": "string"}, "target_service": {"type": "string"},
         "details": {"type": "object"}}, ["action_type", "target_service"]),
    "verify_fix": tool_def("verify_fix", "Verify the fix resolved the incident",
        {"service": {"type": "string"}, "check_type": {"type": "string"}}, ["service"]),
    # Report tools: the agent's FINAL call. Structured output is parsed from
    # these call args — never from prose output_text.
    "report_log_findings": tool_def("report_log_findings", "Submit final log analysis",
        {"anomalies": {"type": "array", "items": {"type": "string"}},
         "likely_trigger": {"type": "string"}, "confidence": {"type": "number"}},
        ["anomalies", "confidence"]),
    "report_metrics": tool_def("report_metrics", "Submit final metrics analysis",
        {"anomalies": {"type": "array", "items": {"type": "string"}},
         "inflection_point": {"type": "string"}, "confidence": {"type": "number"}},
        ["anomalies", "confidence"]),
    "report_diagnosis": tool_def("report_diagnosis", "Submit final diagnosis",
        {"root_cause": {"type": "string"}, "confidence": {"type": "number"},
         "evidence": {"type": "array", "items": {"type": "string"}},
         "recommended_action": {"type": "string"},
         "action_details": {"type": "object"}}, ["root_cause", "confidence"]),
    "report_remediation": tool_def("report_remediation", "Submit remediation outcome",
        {"status": {"type": "string"}, "action": {"type": "string"},
         "result": {"type": "string"}}, ["status"]),
}

REPORT_TOOL = {"LogAnalyzer": "report_log_findings", "MetricsAgent": "report_metrics",
               "Diagnostician": "report_diagnosis", "Remediator": "report_remediation"}


def _step_to_dict(s) -> dict:
    if hasattr(s, "model_dump"):
        return s.model_dump()
    return dict(s)


def _create_sync(client, **kwargs):
    return client.interactions.create(**kwargs)


# Model tiering for latency (docs: agent_config.model accepts gemini-3.8/3.7/
# 3.6/3.5/3.5-lite). Mechanical fetch->analyze->report agents run on the fast
# tier; analysis-heavy agents (Planner, Diagnostician) keep the default.
# AEGIS_MODEL_TIER=fast forces fast everywhere; =default keeps stock behavior.
FAST_MODEL = "gemini-3.5-flash"
DEFAULT_MODEL = "gemini-3.8-flash"
FAST_TIER_AGENTS = {"LogAnalyzer", "MetricsAgent", "Remediator"}


def _model_for(agent: str) -> str | None:
    tier = os.environ.get("AEGIS_MODEL_TIER", "tired")
    if tier == "default":
        return None  # omit agent_config entirely -> stock default model
    if tier == "fast":
        return FAST_MODEL
    return FAST_MODEL if agent in FAST_TIER_AGENTS else None  # "tired" (default)


async def call_agent(messages, tools=None, previous_interaction_id=None,
                     environment_id=None, timeout=AGENT_TIMEOUT,
                     agent_name: str = "") -> dict:
    """Single Interactions API call. messages: str or list of step/content dicts.
    tools: list of tool_def() dicts. Returns response-shape dict (see module doc)."""
    client = _client()
    kwargs = {"agent": AGENT_ID, "input": messages,
              "environment": environment_id or "remote"}
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id
    if tools:
        kwargs["tools"] = tools
    model = _model_for(agent_name)
    if model:
        # IMPORTANT: set on EVERY chained call — model config is locked at the
        # first interaction of a session (same behavior as the tool-set lock).
        kwargs["agent_config"] = {"type": "antigravity", "model": model}
    interaction = await asyncio.wait_for(
        asyncio.to_thread(_create_sync, client, **kwargs), timeout=timeout)
    steps = [_step_to_dict(s) for s in (interaction.steps or [])]
    calls = [{"call_id": s.get("id"), "name": s.get("name"),
              "arguments": s.get("arguments", {}) or {}}
             for s in steps if s.get("type") == "function_call"]
    return {"interaction_id": interaction.id,
            "environment_id": interaction.environment_id,
            "output_text": interaction.output_text or "",
            "steps": steps, "function_calls": calls}


def _default_executor(name: str, args: dict) -> str:
    """Person B: replace by backend/tools/simulated.py dispatch(). Temporary
    canned data matching ARCHITECTURE.md §3 so integration runs NOW."""
    try:
        from ..tools.simulated import dispatch  # Person B implements this
        return dispatch(name, args)
    except Exception:
        return json.dumps({"status": "success", "note": f"stub result for {name}",
                           "args": args})


async def run_tool_loop(first_input: str, tool_names: list,
                        exec_fn=None, previous_interaction_id=None,
                        environment_id=None, agent_name: str = "") -> dict:
    """Full agent turn: prompt -> (function_call -> local exec -> result)* ->
    final text. Returns last call_agent dict + 'tool_trace' list."""
    exec_fn = exec_fn or _default_executor
    tools = [TOOL_DEFS[n] for n in tool_names]
    resp = await call_agent(first_input, tools, previous_interaction_id,
                            environment_id, agent_name=agent_name)
    trace = []
    for _ in range(MAX_TOOL_TURNS):
        if not resp["function_calls"]:
            break
        results = []
        for c in resp["function_calls"]:
            try:
                out = exec_fn(c["name"], c["arguments"])
            except Exception as e:  # tool errors are DATA, not crashes
                out = json.dumps({"status": "error", "error_code": "EXEC_FAILED",
                                  "message": str(e)})
            trace.append({"tool": c["name"], "args": c["arguments"], "result": out})
            results.append({"type": "function_result", "call_id": c["call_id"],
                            "name": c["name"], "result": out})
        resp = await call_agent(results, tools, resp["interaction_id"],
                                resp["environment_id"], agent_name=agent_name)
    resp["tool_trace"] = trace
    return resp


def safe_parse_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    try:  # salvage largest {...} block (Risk 2)
        start, end = text.index("{"), text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


def _infer_agent(text: str, idx: int) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("log", "error", "trace", "heap", "oom")):
        return "LogAnalyzer"
    if any(k in t for k in ("metric", "cpu", "memory", "latency", "p99")):
        return "MetricsAgent"
    if any(k in t for k in ("correlat", "diagnos", "root cause", "hypothesis")):
        return "Diagnostician"
    if any(k in t for k in ("remediat", "rollback", "restart", "fix", "scale")):
        return "Remediator"
    return ("LogAnalyzer", "MetricsAgent", "Diagnostician", "Remediator")[
        min(idx, 3) % 4]


def _to_plan_step(raw: dict, idx: int, prev_ids: list) -> PlanStep:
    raw = raw if isinstance(raw, dict) else {}
    sid = str(raw.get("id") or f"S{idx+1}")
    agent = str(raw.get("agent") or "")
    if agent not in _VALID_AGENTS:
        agent = _infer_agent(
            f"{raw.get('action', '')} {raw.get('description', '')} {raw.get('details', '')}", idx)
    desc = str(raw.get("description") or raw.get("action") or f"Step {sid}")
    details = raw.get("details")
    if details and details not in desc:
        desc = f"{desc} — {details}"
    deps = raw.get("depends_on") or []
    deps = [str(d) for d in deps] if isinstance(deps, list) else []
    deps = [d for d in deps if d in prev_ids]
    if not deps and prev_ids and agent in ("Diagnostician", "Remediator"):
        deps = list(prev_ids[-2:]) if agent == "Diagnostician" else [prev_ids[-1]]
    return PlanStep(sid, agent, desc, deps)


class RealBackend:
    """AgentBackend over the Interactions API. Keeps interaction/env ids per
    agent for native chaining; failures are read LIVE from the incident state
    (OC's mid-run injection property) with a snapshot fallback."""

    def __init__(self, failures=None, exec_fn=None):
        self._static_failures = failures or []
        self._incident_id: str | None = None
        self.exec_fn = exec_fn
        self.chain: dict = {}  # agent -> {"interaction_id","environment_id"}
        self.timeout = 150.0  # real agent turns need headroom (spike: ~11-17s/call)

    @property
    def failures(self) -> list:
        """Live read: mid-run /api/inject-failure takes effect on the NEXT
        agent call (OC's feature, ported to RealBackend)."""
        if self._incident_id:
            st = store.get_state(self._incident_id)
            if st:
                return st.get("active_failures", [])
        return self._static_failures

    @failures.setter
    def failures(self, value: list):
        self._static_failures = value

    def _exec(self, name: str, args: dict) -> str:
        if name == "fetch_logs" and "LOG_SOURCE_UNAVAILABLE" in self.failures:
            return json.dumps({"status": "error", "error_code": "SOURCE_TIMEOUT",
                "message": "PermissionError: Missing IAM Role for CloudWatch — "
                           "Failed to connect to log aggregation service after 30s"})
        if name == "execute_fix" and "REMEDIATION_FAILED" in self.failures:
            return json.dumps({"status": "error", "error_code": "ROLLBACK_FAILED",
                "message": "DeploymentLockError: Cannot rollback — deployment lock held "
                           "by CI/CD pipeline process pid-4521. Manual intervention required."})
        if self.exec_fn:
            return self.exec_fn(name, args, self.failures)
        return _default_executor(name, args)

    async def _ask(self, agent: str, prompt: str, tools: list,
                   fresh_session: bool = False) -> dict:
        # fresh_session=True skips previous_interaction_id chaining. Needed
        # because chained sessions appear to lock their tool set from the
        # FIRST interaction — a tool registered later is "not available".
        prev = {} if fresh_session else self.chain.get(agent, {})
        resp = await run_tool_loop(prompt, tools, self._exec,
                                   prev.get("interaction_id"),
                                   prev.get("environment_id"),
                                   agent_name=agent)
        self.chain[agent] = {"interaction_id": resp["interaction_id"],
                             "environment_id": resp["environment_id"]}
        return resp

    def _report_args(self, resp: dict, report_tool: str) -> dict | None:
        for t in resp.get("tool_trace", []):
            if t["tool"] == report_tool and isinstance(t["args"], dict):
                return t["args"]
        return None

    async def create_plan(self, alert: dict, context: str = "") -> PlanResult:
        prompt = (
            f"ALERT: {alert.get('type')} on {alert.get('service')} "
            f"({alert.get('severity')}). You MUST call the create_plan tool. "
            f"Each step needs exactly: id (S1, S2...), agent (one of LogAnalyzer, "
            f"MetricsAgent, Diagnostician, Remediator), description, depends_on "
            f"(list of step ids). Plan: S1 LogAnalyzer + S2 MetricsAgent in "
            f"parallel, S3 Diagnostician depends on S1+S2, S4 Remediator depends "
            f"on S3. Do not respond with plain text — call the tool. {context}")
        if "failed" in context.lower():
            # Degraded replan: the failed investigator must be dropped, not
            # retried (retrying just burns the plan-version budget).
            prompt += (" IMPORTANT: a previous step FAILED (source unavailable). "
                       "Do NOT include a step for the failed agent — plan around "
                       "it using the remaining agents only.")
        resp = await self._ask("Planner", prompt, ["create_plan"])
        data = self._report_args(resp, "create_plan") or {}
        if not data.get("steps"):
            data = safe_parse_json(resp["output_text"]) or {}
        raw_steps = data.get("steps", []) if isinstance(data, dict) else []
        steps, ids = [], []
        for i, r in enumerate(raw_steps):
            ps = _to_plan_step(r, i, ids)
            ids.append(ps.id)
            steps.append(ps)
        if not steps:  # deterministic fallback so the pipeline never stalls
            steps = [PlanStep("S1", "LogAnalyzer", "Fetch and analyze logs", []),
                     PlanStep("S2", "MetricsAgent", "Fetch metrics", []),
                     PlanStep("S3", "Diagnostician", "Correlate findings", ["S1", "S2"]),
                     PlanStep("S4", "Remediator", "Execute fix", ["S3"])]
        return PlanResult(steps, str(data.get("reasoning", "")),
                          interaction_id=resp["interaction_id"])

    async def _json_agent(self, agent: str, task: str, tools: list,
                          report_schema_hint: str,
                          fresh_session: bool = False) -> AgentResult:
        report_tool = REPORT_TOOL[agent]
        prompt = (f"{task} Finish by calling {report_tool} with the results. "
                  f"Do not respond with plain text as your final answer — call "
                  f"the {report_tool} tool.")
        resp = await self._ask(agent, prompt, tools + [report_tool],
                               fresh_session=fresh_session)
        data = self._report_args(resp, report_tool)
        if data is None:
            data = safe_parse_json(resp["output_text"])
        if data is None:  # one retry, then deterministic fallback (Risk 2)
            resp2 = await self._ask(
                agent, f"Call {report_tool} now with {report_schema_hint}. No prose.",
                [report_tool])
            data = self._report_args(resp2, report_tool)
            resp = resp2
        if not isinstance(data, dict):
            data = {"status": "completed", "anomalies": [], "confidence": 0.0,
                    "note": "fallback: unparseable agent output"}
        if isinstance(data.get("result"), str):  # unwrap nested tool JSON
            try:
                inner = json.loads(data["result"])
                if isinstance(inner, dict) and inner.get("result"):
                    data["result"] = inner["result"]
            except Exception:
                pass
        ok = str(data.get("status", "completed")) != "error"
        summary = json.dumps(data)[:300]
        return AgentResult(ok, agent, summary, data,
                           error_code=data.get("error_code"), error=data.get("message"),
                           interaction_id=resp["interaction_id"])

    async def analyze_logs(self, service: str, time_window_minutes: int = 30) -> AgentResult:
        result = await self._json_agent(
            "LogAnalyzer",
            f"TASK: Call fetch_logs for service '{service}' (last "
            f"{time_window_minutes} min), then analyze_pattern on the entries. "
            f"If fetch_logs returns status error, IMMEDIATELY call "
            f"report_log_findings with status='error' and the tool's error "
            f"message — do not attempt further analysis.",
            ["fetch_logs", "analyze_pattern"],
            "anomalies[], likely_trigger, confidence")
        if "LOG_SOURCE_UNAVAILABLE" in self.failures:
            # DETERMINISTIC demo semantics: the log source is DOWN. The agent
            # sometimes skips calling fetch_logs and invents findings — the
            # replan pipeline must not depend on its tool obedience. Whatever
            # it reported, the investigation FAILED (SOURCE_TIMEOUT).
            result.ok = False
            result.error_code = "SOURCE_TIMEOUT"
            result.error = ("PermissionError: Missing IAM Role for CloudWatch — "
                            "Failed to connect to log aggregation service after 30s")
            result.data = {"status": "error", "error_code": "SOURCE_TIMEOUT"}
            result.summary = "Log source unreachable"
        return result

    async def analyze_metrics(self, service: str, metrics=None) -> AgentResult:
        want = metrics or ["cpu_percent", "memory_percent", "latency_p99_ms"]
        return await self._json_agent(
            "MetricsAgent",
            f"TASK: Call fetch_metrics for service '{service}' metrics {want}, "
            f"then detect_anomaly on the series. If fetch_metrics returns status "
            f"error, report it via report_metrics with status='error'.",
            ["fetch_metrics", "detect_anomaly"],
            "anomalies[], inflection_point, confidence")

    async def diagnose(self, log_findings: dict, metrics_findings: dict) -> AgentResult:
        return await self._json_agent(
            "Diagnostician",
            f"TASK: Call correlate_findings with LOG={json.dumps(log_findings)[:1200]} "
            f"and METRICS={json.dumps(metrics_findings)[:1200]}, then "
            f"propose_diagnosis with hypothesis + evidence.",
            ["correlate_findings", "propose_diagnosis"],
            "root_cause, confidence, evidence[], recommended_action, action_details")

    async def remediate(self, action_type: str, service: str, details=None) -> AgentResult:
        # NOTE: verify_fix stays registered here (tool-set lock: chained
        # sessions freeze tools from first contact). Verification itself is
        # run DETERMINISTICALLY by the orchestrator against the simulated
        # health check — asking an LLM to verify was both slow (+20-25s per
        # round trip) and unreliable (report args omitted the field).
        return await self._json_agent(
            "Remediator",
            f"TASK: Call execute_fix with action_type '{action_type}' on '{service}' "
            f"(details {json.dumps(details or {})}). If the tool returns an error, "
            f"report status error with the error message. Do not call verify_fix.",
            ["execute_fix", "verify_fix"],
            "status, action, result")
        if "REMEDIATION_FAILED" in self.failures and result.ok:
            # DETERMINISTIC demo semantics (same rationale as analyze_logs):
            # the fix must FAIL while the flag is active, regardless of what
            # the agent reported.
            result.ok = False
            result.error_code = "ROLLBACK_FAILED"
            result.error = ("DeploymentLockError: Cannot rollback — deployment "
                            "lock held by CI/CD pipeline process pid-4521. "
                            "Manual intervention required.")
        return result

    async def verify(self, service: str, check_type: str = "HEALTH_CHECK") -> AgentResult:
        result = await self._json_agent(
            "Remediator",
            f"TASK: Call verify_fix for '{service}' check {check_type}.",
            ["verify_fix"],
            "status, result")
        if not result.ok:  # chained session may not expose verify_fix — retry fresh
            result = await self._json_agent(
                "Remediator",
                f"TASK: Call verify_fix for '{service}' check {check_type}.",
                ["verify_fix"],
                "status, result",
                fresh_session=True)
        return result
