"""AEGIS tool exports (Person B)."""
from .simulated import (
    ACTIVE_FAILURES,
    analyze_pattern,
    correlate_findings,
    detect_anomaly,
    execute_fix,
    fetch_logs,
    fetch_metrics,
    set_failures,
    verify_fix,
)

__all__ = [
    "ACTIVE_FAILURES",
    "analyze_pattern",
    "correlate_findings",
    "detect_anomaly",
    "execute_fix",
    "fetch_logs",
    "fetch_metrics",
    "set_failures",
    "verify_fix",
]
