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


# === TOOL DISPATCH TABLE ===
# Person A's orchestrator can use this to route tool calls from agents
# to the correct simulated function by name.
TOOL_HANDLERS: dict[str, Any] = {
    "fetch_logs": fetch_logs,
    "analyze_pattern": analyze_pattern,
    "fetch_metrics": fetch_metrics,
    "detect_anomaly": detect_anomaly,
    "correlate_findings": correlate_findings,
    "propose_diagnosis": propose_diagnosis,
    "execute_fix": execute_fix,
    "verify_fix": verify_fix,
}

