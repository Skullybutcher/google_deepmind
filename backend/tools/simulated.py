"""Simulated tool implementations — deterministic local sandbox.

Person B owns prompt tuning; this module's DATA shapes follow
ARCHITECTURE.md §3 exactly. Failure injection is handled by RealBackend._exec
BEFORE dispatch (LOG_SOURCE_UNAVAILABLE / REMEDIATION_FAILED), so this file
only implements happy-path + heuristic analysis tools.

dispatch(name, args) -> JSON string. report_*/create_plan are agent-output
tools: echoed back (orchestrator parses their call args, not the return).
"""
import json

LOG_ENTRIES = [
    {"timestamp": "10:02:15", "level": "ERROR",
     "message": "OutOfMemoryError: Java heap space in /api/v2/orders"},
    {"timestamp": "10:02:16", "level": "WARN",
     "message": "GC pause 2.3s, heap usage 98%"},
    {"timestamp": "10:02:18", "level": "ERROR",
     "message": "Request timeout: /api/v2/orders after 30000ms"},
    {"timestamp": "10:01:00", "level": "INFO",
     "message": "Deployment v2.3.1 completed successfully"},
    {"timestamp": "10:02:20", "level": "ERROR",
     "message": "Circuit breaker OPEN for downstream-payment-service"},
]

METRICS = {
    "cpu_percent": [45, 48, 52, 78, 95, 99, 99, 99],
    "memory_percent": [60, 62, 65, 80, 92, 97, 98, 99],
    "latency_p99_ms": [120, 125, 130, 450, 2300, 5000, 8000, 12000],
    # merged from teammate's aegis/backend version — error rate compounds the story
    "error_rate_percent": [0.1, 0.1, 0.2, 2.5, 15.0, 35.0, 42.0, 48.0],
    "timestamps": ["09:55", "09:56", "09:57", "09:58", "09:59", "10:00", "10:01", "10:02"],
}


def _fetch_logs(args: dict) -> dict:
    return {"status": "success", "log_entries": LOG_ENTRIES}


def _analyze_pattern(args: dict) -> dict:
    entries = args.get("log_entries") or LOG_ENTRIES
    errors = [e for e in entries if e.get("level") == "ERROR"]
    anomalies = []
    if any("OutOfMemory" in e.get("message", "") for e in entries):
        anomalies.append("OutOfMemoryError detected — heap exhaustion in request path")
    if any("GC pause" in e.get("message", "") for e in entries):
        anomalies.append("GC pause 2.3s at 98% heap — severe memory pressure")
    if any("Deployment" in e.get("message", "") for e in entries):
        anomalies.append("Anomalies begin immediately after deployment v2.3.1 (10:01)")
    if any("Circuit breaker" in e.get("message", "") for e in entries):
        anomalies.append("Circuit breaker OPEN — cascading failure to downstream")
    if not anomalies and not errors:
        anomalies.append("No error pattern found in window")
    return {"status": "success", "anomalies": anomalies,
            "error_count": len(errors), "confidence": 0.85 if anomalies else 0.2}


def _fetch_metrics(args: dict) -> dict:
    return {"status": "success", "metrics": METRICS}


def _detect_anomaly(args: dict) -> dict:
    m = args.get("metrics") or METRICS
    anomalies = []
    cpu, mem, lat = m["cpu_percent"], m["memory_percent"], m["latency_p99_ms"]
    if max(cpu) - min(cpu) > 30:
        anomalies.append(f"CPU spike {min(cpu)}%->{max(cpu)}% (deploy window)")
    if mem[-1] > 95 and mem[-1] >= mem[0]:
        anomalies.append(f"Memory climbing {mem[0]}%->{mem[-1]}% with no plateau — leak signature")
    if max(lat) > 10 * min(lat):
        anomalies.append(f"P99 latency {min(lat)}ms->{max(lat)}ms (~{max(lat)//min(lat)}x)")
    return {"status": "success", "anomalies": anomalies,
            "inflection_point": "09:58 — matches deploy v2.3.1 window",
            "confidence": 0.92 if anomalies else 0.2}


def _correlate(args: dict) -> dict:
    # Partial-data aware (merged from teammate's version): when log findings
    # are missing/errored (degraded mode), evidence and verdict must say so —
    # the Diagnostician's output then honestly reflects metrics-only analysis.
    log_f = args.get("log_findings")
    partial = (not log_f) or (isinstance(log_f, dict) and log_f.get("status") == "error")
    if partial:
        return {"status": "success",
                "correlated": True,
                "partial_data": True,
                "missing_source": "logs",
                "correlation": ("Log source unavailable — correlating on metrics "
                                "alone: memory climb with no plateau + P99 latency "
                                "explosion + error-rate spike share one onset "
                                "window. Verdict: probable memory leak, moderate "
                                "confidence."),
                "evidence": ["Memory climbing with no plateau — leak signature",
                             "P99 latency 100x increase matches onset window",
                             "Error rate 0.1%->48% confirms user-facing impact"],
                "confidence": 0.7}
    return {"status": "success",
            "correlated": True,
            "partial_data": False,
            "correlation": ("OOM errors + GC pressure in logs coincide with "
                            "memory-climb + latency explosion in metrics; "
                            "shared onset 09:58-10:01 = deploy v2.3.1 window. "
                            "Verdict: single root cause, not coincidence."),
            "evidence": ["OOM errors correlate with memory spike",
                         "Both anomalies begin at deploy v2.3.1 window",
                         "Circuit breaker confirms cascading failure"],
            "confidence": 0.9}


def _propose_diagnosis(args: dict) -> dict:
    return {"status": "completed",
            "root_cause": "Memory leak introduced in deployment v2.3.1 causing "
                          "OOM errors and cascading latency",
            "confidence": 0.9,
            "evidence": ["OOM errors correlate with memory spike",
                         "Onset matches deploy window (09:58-10:01)",
                         "Circuit breaker confirms cascading failure"],
            "recommended_action": "rollback",
            "action_details": {"type": "ROLLBACK", "target_version": "v2.3.0",
                               "service": "api-gateway"}}


def _execute_fix(args: dict) -> dict:
    return {"status": "success",
            "action": f"{args.get('action_type', 'ROLLBACK')} on "
                      f"{args.get('target_service', 'api-gateway')}",
            "result": "Deployment rolled back successfully. New pods healthy.",
            "verification_needed": True}


def _verify_fix(args: dict) -> dict:
    # Defense-in-depth (merged from teammate's version): if remediation-failure
    # is still active mid-run, verification must NOT report a healthy system.
    # Our orchestrator normally never reaches verify under this flag, but this
    # guards against flag changes mid-incident.
    if "REMEDIATION_FAILED" in _active_failures_hook():
        return {"status": "error", "check_type": args.get("check_type", "HEALTH_CHECK"),
                "result": "Verification FAILED: service still unhealthy. Latency "
                          "p99: 9500ms. Error rate: 38%."}
    return {"status": "success", "check_type": args.get("check_type", "HEALTH_CHECK"),
            "result": "All health checks passing. Latency p99 back to 125ms. "
                      "Error rate: 0%."}


def _active_failures_hook() -> list:
    """Read the active incident's failure flags without a circular import.
    Falls back to empty if state isn't reachable (pure tool-unit usage)."""
    try:
        from .. import state as _store
        st = _store.get_state()
        if st:
            return st.get("active_failures", [])
    except Exception:
        pass
    return []


_HANDLERS = {"fetch_logs": _fetch_logs, "analyze_pattern": _analyze_pattern,
             "fetch_metrics": _fetch_metrics, "detect_anomaly": _detect_anomaly,
             "correlate_findings": _correlate, "propose_diagnosis": _propose_diagnosis,
             "execute_fix": _execute_fix, "verify_fix": _verify_fix}


def dispatch(name: str, args: dict) -> str:
    """Main entry: tool name + args -> JSON string result."""
    if not isinstance(args, dict):
        args = {}
    if name in ("create_plan",) or name.startswith("report_"):
        return json.dumps({"status": "ok", "echo": args})  # agent-output tools
    fn = _HANDLERS.get(name)
    if not fn:
        return json.dumps({"status": "error", "error_code": "UNKNOWN_TOOL",
                           "message": f"no simulated tool '{name}'"})
    return json.dumps(fn(args))
