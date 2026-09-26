"""AEGIS simulated tools + failure injection hooks (Person B)."""
from __future__ import annotations

from datetime import datetime
from typing import Any

# Global failure flags, set via POST /api/inject-failure.
# Valid values: "LOG_SOURCE_UNAVAILABLE", "REMEDIATION_FAILED"
ACTIVE_FAILURES: set[str] = set()


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


SIMULATED_LOGS_HAPPY: dict[str, Any] = {
    "status": "success",
    "log_entries": [
        {"timestamp": "10:01:00", "level": "INFO", "message": "Deployment v2.3.1 completed successfully"},
        {"timestamp": "10:02:15", "level": "ERROR", "message": "OutOfMemoryError: Java heap space in /api/v2/orders"},
        {"timestamp": "10:02:16", "level": "WARN", "message": "GC pause 2.3s, heap usage 98%"},
        {"timestamp": "10:02:18", "level": "ERROR", "message": "Request timeout: /api/v2/orders after 30000ms"},
        {"timestamp": "10:02:20", "level": "ERROR", "message": "Circuit breaker OPEN for downstream-payment-service"},
    ],
}

SIMULATED_LOGS_FAILURE: dict[str, Any] = {
    "status": "error",
    "error_code": "SOURCE_TIMEOUT",
    "message": "PermissionError: Missing IAM Role for CloudWatch — Failed to connect to log aggregation service after 30s",
}

SIMULATED_METRICS: dict[str, Any] = {
    "status": "success",
    "metrics": {
        "cpu_percent": [45, 48, 52, 78, 95, 99, 99, 99],
        "memory_percent": [60, 62, 65, 80, 92, 97, 98, 99],
        "latency_p99_ms": [120, 125, 130, 450, 2300, 5000, 8000, 12000],
        "error_rate_percent": [0.1, 0.1, 0.2, 2.5, 15.0, 35.0, 42.0, 48.0],
        "timestamps": ["09:55", "09:56", "09:57", "09:58", "09:59", "10:00", "10:01", "10:02"],
    },
}

SIMULATED_FIX_SUCCESS: dict[str, Any] = {
    "status": "success",
    "action": "ROLLBACK to v2.3.0",
    "result": "Deployment rolled back successfully. New pods healthy. Memory usage dropping.",
    "verification_needed": True,
}

SIMULATED_FIX_FAILURE: dict[str, Any] = {
    "status": "error",
    "error_code": "ROLLBACK_FAILED",
    "message": "DeploymentLockError: Cannot rollback — deployment lock held by CI/CD pipeline process pid-4521. Manual intervention required.",
}

SIMULATED_VERIFY_SUCCESS: dict[str, Any] = {
    "status": "success",
    "check_type": "HEALTH_CHECK",
    "result": "All health checks passing. Latency p99: 125ms. Error rate: 0%. Memory: 45%.",
}


def fetch_logs(service: str, time_window_minutes: int = 30, log_level: str = "ALL") -> dict[str, Any]:
    if "LOG_SOURCE_UNAVAILABLE" in ACTIVE_FAILURES:
        return {**SIMULATED_LOGS_FAILURE, "queried_at": _now(), "service": service}
    return {**SIMULATED_LOGS_HAPPY, "queried_at": _now(), "service": service}


def analyze_pattern(log_entries: list[dict[str, Any]], focus_area: str = "errors") -> dict[str, Any]:
    if not log_entries:
        return {"status": "error", "error_code": "NO_LOGS", "message": "No log entries to analyze."}
    errors = [e for e in log_entries if e.get("level") == "ERROR"]
    return {
        "status": "completed",
        "findings": {
            "anomalies": [
                "OutOfMemoryError detected immediately after deployment v2.3.1",
                "GC pause of 2.3s indicates memory pressure",
                "Circuit breaker opened for downstream service",
            ],
            "likely_trigger": "Deployment v2.3.1 introduced a memory leak",
            "confidence": 0.85,
            "recommended_action": "Investigate memory consumption in v2.3.1 changes",
            "error_count": len(errors),
        },
    }


def fetch_metrics(
    service: str, metrics: list[str] | None = None, time_window_minutes: int = 30
) -> dict[str, Any]:
    return {**SIMULATED_METRICS, "queried_at": _now(), "service": service}


def detect_anomaly(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "completed",
        "findings": {
            "anomalies": [
                "CPU spike from 52% to 95% at 09:58 (correlates with deployment window)",
                "Memory climbing from 65% to 99% — no plateau, suggests leak",
                "P99 latency 100x increase: 130ms → 12000ms",
            ],
            "inflection_point": "09:58 — consistent with deployment v2.3.1 at 10:01",
            "confidence": 0.92,
        },
    }


def correlate_findings(log_findings: dict[str, Any] | None, metrics_findings: dict[str, Any] | None) -> dict[str, Any]:
    """Correlate log + metric findings into joint evidence for diagnosis."""
    partial = log_findings is None or (isinstance(log_findings, dict) and log_findings.get("status") == "error")

    evidence = []
    if not partial and log_findings:
        evidence.append("OutOfMemoryError in logs correlates with memory spike in metrics")
        evidence.append("Both anomalies begin around deployment v2.3.1 time window")
        evidence.append("Circuit breaker activation confirms cascading failure pattern")
    if metrics_findings:
        evidence.append("CPU spike from 52% to 95% at 09:58 matches deployment window")
        evidence.append("Memory climbing to 99% with no plateau — classic leak signature")
        evidence.append("P99 latency 100x increase confirms user-facing impact")

    return {
        "status": "completed",
        "correlated": True,
        "partial_data": partial,
        "missing_source": "logs" if partial else None,
        "evidence": evidence,
        "correlation_strength": "strong" if not partial else "moderate",
        "suggested_root_cause": "Memory leak from deployment v2.3.1" if not partial else "Probable infrastructure issue — insufficient data for certainty",
    }


def propose_diagnosis(
    root_cause: str,
    confidence: float,
    evidence: list[str],
    recommended_action: str,
    action_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Accept the agent's structured diagnosis. This is a pass-through — the
    agent's own reasoning IS the diagnosis, we just stamp and return it."""
    return {
        "status": "completed",
        "diagnosis": {
            "root_cause": root_cause,
            "confidence": confidence,
            "evidence": evidence,
            "recommended_action": recommended_action,
            "action_details": action_details or {"type": recommended_action.upper(), "target_version": "v2.3.0", "service": "api-gateway"},
            "diagnosed_at": _now(),
        },
    }


def execute_fix(action_type: str, target_service: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    if "REMEDIATION_FAILED" in ACTIVE_FAILURES:
        return {**SIMULATED_FIX_FAILURE, "attempted_at": _now(), "service": target_service}
    return {**SIMULATED_FIX_SUCCESS, "attempted_at": _now(), "service": target_service}


def verify_fix(service: str, check_type: str = "HEALTH_CHECK") -> dict[str, Any]:
    # If remediation was injected as failed, verification should also reflect instability
    if "REMEDIATION_FAILED" in ACTIVE_FAILURES:
        return {
            "status": "error",
            "check_type": check_type,
            "result": f"Verification FAILED: {service} still unhealthy. Latency p99: 9500ms. Error rate: 38%.",
            "verified_at": _now(),
            "service": service,
        }
    return {**SIMULATED_VERIFY_SUCCESS, "verified_at": _now(), "service": service}


def set_failures(failures: list[str]) -> list[str]:
    """Set active failure injection flags. Pass ['NONE'] to clear all."""
    ACTIVE_FAILURES.clear()
    for f in failures:
        if f != "NONE":
            ACTIVE_FAILURES.add(f)
    return sorted(ACTIVE_FAILURES)



def run_python_analysis(code: str) -> dict[str, Any]:
    """Simulate Python code execution in sandbox. Returns realistic analysis output
    as if the model had actually run the code on the log/metrics data."""
    # In production this would execute code in a real sandbox.
    # For the demo, return pre-computed output that matches the simulated data.
    return {
        "status": "success",
        "stdout": (
            "ERROR count: 3 | WARN count: 1 | INFO count: 1\n"
            "Most frequent: 'OutOfMemoryError: Java heap space in /api/v2/orders' (2 occurrences)\n"
            "Rapid onset: 3 errors within 5 seconds (10:02:15 – 10:02:20)\n"
            "Error rate: 3 errors/min at peak\n"
            "CPU inflection at: 09:58 (delta +26.0%)\n"
            "Memory monotonically increasing (leak signature): True\n"
            "cpu_percent: max=99, mean=76.6, anomaly_score=0.29\n"
            "memory_percent: max=99, mean=81.6, anomaly_score=0.21\n"
            "latency_p99_ms: max=12000, mean=3266, anomaly_score=2.67\n"
            "error_rate_percent: max=48.0, mean=17.5, anomaly_score=1.74\n"
        ),
        "exit_code": 0,
        "executed_at": _now(),
    }


def web_search(query: str) -> dict[str, Any]:
    """Simulate Google Search for error signature validation.
    Returns realistic search results matching OutOfMemoryError + deployment patterns."""
    return {
        "status": "success",
        "query": query,
        "results": [
            {
                "title": "OutOfMemoryError Java heap space after deployment — Stack Overflow",
                "url": "https://stackoverflow.com/questions/37817064",
                "snippet": (
                    "Common cause: new deployment increases memory footprint beyond heap limit. "
                    "Immediate fix: rollback to previous version. Root cause: memory leak in new code or "
                    "heap size not scaled for new feature. JVM heap usage climbing monotonically to 99% "
                    "with no GC recovery is the classic signature."
                ),
            },
            {
                "title": "Circuit breaker OPEN due to memory pressure — Netflix Tech Blog",
                "url": "https://netflixtechblog.com/circuit-breakers-memory",
                "snippet": (
                    "When JVM heap exhaustion causes request timeouts, circuit breakers open to prevent "
                    "cascade failures to downstream services. Pattern: OutOfMemoryError → timeout → circuit open. "
                    "Resolution: immediate rollback + heap size increase in follow-up deployment."
                ),
            },
            {
                "title": "Kubernetes deployment memory leak detection and rollback",
                "url": "https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#rolling-back",
                "snippet": (
                    "Use kubectl rollout undo deployment/<name> to rollback. Memory leak from bad deployment "
                    "identified by: monotonically increasing memory_percent with no plateau + concurrent "
                    "OOM errors in logs. Rollback typically restores health within 2-3 minutes."
                ),
            },
        ],
        "searched_at": _now(),
    }


def run_bash_command(command: str) -> dict[str, Any]:
    """Simulate bash command execution in sandbox. Returns realistic health check output."""
    # Simulate post-fix health output
    if "REMEDIATION_FAILED" in ACTIVE_FAILURES:
        return {
            "status": "error",
            "stdout": "",
            "stderr": "bash: kubectl: command blocked — deployment lock held by CI/CD pipeline pid-4521",
            "exit_code": 1,
            "executed_at": _now(),
        }
    return {
        "status": "success",
        "stdout": (
            "Rollback complete: api-gateway v2.3.0 running.\n"
            "Pods: 3/3 Ready. Restarts: 0\n"
            "Memory: 44% (dropping from 99%). CPU: 38%.\n"
            "Latency p99: 128ms. Error rate: 0.1%.\n"
            "Health endpoint: HTTP 200 OK"
        ),
        "stderr": "",
        "exit_code": 0,
        "executed_at": _now(),
    }


def write_fix_report(
    incident_id: str,
    action_taken: str,
    success: bool,
    bash_output: str | None = None,
    error_code: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Simulate writing a fix report JSON file to the sandbox filesystem."""
    report = {
        "incident_id": incident_id,
        "action_taken": action_taken,
        "success": success,
        "bash_output": bash_output,
        "error_code": error_code,
        "timestamp": timestamp or _now(),
    }
    # In production, this writes to /tmp/aegis_fix_report_{incident_id}.json in the sandbox.
    # For the demo, we just return a confirmation.
    return {
        "status": "success",
        "file_path": f"/tmp/aegis_fix_report_{incident_id}.json",
        "written_at": _now(),
        "report": report,
    }


# === TOOL DISPATCH TABLE ===
# Person A's orchestrator uses this to route agent tool calls to the correct handler.
TOOL_HANDLERS: dict[str, Any] = {
    "fetch_logs": fetch_logs,
    "analyze_pattern": analyze_pattern,
    "run_python_analysis": run_python_analysis,
    "fetch_metrics": fetch_metrics,
    "detect_anomaly": detect_anomaly,
    "correlate_findings": correlate_findings,
    "web_search": web_search,
    "propose_diagnosis": propose_diagnosis,
    "execute_fix": execute_fix,
    "run_bash_command": run_bash_command,
    "write_fix_report": write_fix_report,
    "verify_fix": verify_fix,
}
