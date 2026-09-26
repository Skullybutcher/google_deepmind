"""
AEGIS Remediator Guardrails
============================
Hard, code-enforced gate in front of every remediation action.

Rules (in evaluation order):
  1. action must be in ALLOWED_ACTIONS  → else: require human approval
  2. confidence must be >= AUTO_EXECUTE_THRESHOLD  → else: require human approval

These are deterministic Python checks, not prompt instructions.
The orchestrator calls check() before every backend.remediate() call.
"""
from __future__ import annotations

from typing import Any

# Only these actions may be auto-executed by the Remediator.
ALLOWED_ACTIONS: frozenset[str] = frozenset({"rollback", "restart", "ROLLBACK", "RESTART"})

# Minimum diagnosis confidence required for autonomous execution.
AUTO_EXECUTE_THRESHOLD: float = 0.70

# Reason codes (also used by eval harness assertions)
REASON_DISALLOWED_ACTION = "action_not_in_allowlist"
REASON_LOW_CONFIDENCE    = "confidence_below_threshold"


class RemediatorGuardrail:
    """
    Stateless check. Call before every remediate() call in the orchestrator.

    Example:
        guard = RemediatorGuardrail()
        result = guard.check(action=diag.data["recommended_action"],
                             confidence=diag.data["confidence"])
        if not result["allowed"]:
            # surface "Approve Fix?" button in UI, halt execution
            ...
    """

    def check(self, action: str, confidence: float,
              threshold_override: float | None = None) -> dict[str, Any]:
        """threshold_override: severity profiles set their own bar
        (P1 acts fast at 0.60, P3 wants 0.85 certainty). Falls back to the
        global AUTO_EXECUTE_THRESHOLD."""
        threshold = (AUTO_EXECUTE_THRESHOLD if threshold_override is None
                     else threshold_override)
        """
        Returns:
            { "allowed": bool, "reason": str|None, "message": str,
              "action": str, "confidence": float,
              "threshold": float, "allowlist": list[str] }
        """
        if action not in ALLOWED_ACTIONS:
            return {
                "allowed":    False,
                "reason":     REASON_DISALLOWED_ACTION,
                "action":     action,
                "confidence": confidence,
                "threshold":  threshold,
                "allowlist":  sorted(ALLOWED_ACTIONS),
                "message": (
                    f"Action '{action}' is not in the auto-execute allow-list "
                    f"({sorted(ALLOWED_ACTIONS)}). Human approval required."
                ),
            }

        if confidence < threshold:
            return {
                "allowed":    False,
                "reason":     REASON_LOW_CONFIDENCE,
                "action":     action,
                "confidence": confidence,
                "threshold":  threshold,
                "allowlist":  sorted(ALLOWED_ACTIONS),
                "message": (
                    f"Confidence {confidence:.2f} is below the auto-execute "
                    f"threshold {threshold:.2f}. Human approval required."
                ),
            }

        return {
            "allowed":    True,
            "reason":     None,
            "action":     action,
            "confidence": confidence,
            "threshold":  threshold,
            "allowlist":  sorted(ALLOWED_ACTIONS),
            "message":    f"Action '{action}' approved for auto-execution (confidence={confidence:.2f}).",
        }
