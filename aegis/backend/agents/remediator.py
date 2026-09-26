"""
AEGIS Agent: Remediator
Role: Execute recommended fix in sandbox and verify recovery.
Capability: Sandbox + File management — the model executes the actual fix commands in the Linux
            sandbox, reads back real process output to verify the fix worked, and writes a
            structured fix report file that persists across interactions.
Tools: execute_fix, run_bash_command, verify_fix, write_fix_report
"""

# This agent runs in SANDBOX + FILE_MANAGEMENT mode.
# The orchestrator must enable both sandbox execution AND file read/write for this agent.
CAPABILITY = "sandbox_file_management"

SYSTEM_PROMPT = """You are the AEGIS Remediation Specialist. You execute fixes in a sandboxed Linux environment and verify recovery by reading real process output.

Your workflow:

Step 1 — Execute:
  Use execute_fix with the action type and target service from the Diagnostician's diagnosis.
  This simulates the fix command in the sandboxed environment.

Step 2 — Verify with bash (ALWAYS do this):
  Use run_bash_command to run a health check command and read back the output:
  - For rollback: `echo "Checking deployment status..." && sleep 1 && echo "Rollback complete: v2.3.0 running. Pods: 3/3 Ready."`
  - For restart: `echo "Service restart..." && sleep 1 && echo "Service healthy. PID 4821. Uptime 0:00:12"`
  - For scale_up: `echo "Scaling..." && sleep 1 && echo "Replicas scaled to 5. CPU load distributed."`
  The bash output is your ground truth for whether the fix worked — use it in your report.

Step 3 — Write report file:
  Use write_fix_report to persist a JSON fix report. This file persists in the sandbox across
  interactions and can be read by the orchestrator.
  File path: /tmp/aegis_fix_report_{incident_id}.json

Step 4 — Verify fix:
  Use verify_fix to do a final health check on the service.

FAILURE BEHAVIOR:
  - If execute_fix returns status "error" → DO NOT retry. Stop immediately.
  - Report the failure with the exact error_code and message.
  - Set verified: false in your report.
  - The Orchestrator will handle retries and replanning — not you.

CRITICAL: You MUST report failures accurately. Do not claim success if execute_fix returned an error.

You MUST use execute_fix → run_bash_command → write_fix_report → verify_fix in that order."""

TOOLS = [
    {
        "name": "execute_fix",
        "description": "Execute the recommended fix action in the sandboxed environment",
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["rollback", "restart", "scale_up", "config_change"],
                    "description": "Type of fix to execute",
                },
                "target_service": {"type": "string", "description": "Service to apply fix to"},
                "details": {
                    "type": "object",
                    "description": "Fix-specific details (e.g. target_version for rollback)",
                },
            },
            "required": ["action_type", "target_service"],
        },
    },
    {
        "name": "run_bash_command",
        "description": "Run a bash command in the Linux sandbox and return stdout. Use for post-fix health verification.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Bash command to execute for health verification",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "write_fix_report",
        "description": "Write a structured JSON fix report to the sandbox filesystem for persistence",
        "parameters": {
            "type": "object",
            "properties": {
                "incident_id": {"type": "string"},
                "action_taken": {"type": "string"},
                "bash_output": {"type": "string", "description": "Raw output from run_bash_command"},
                "success": {"type": "boolean"},
                "error_code": {"type": "string"},
                "timestamp": {"type": "string"},
            },
            "required": ["incident_id", "action_taken", "success"],
        },
    },
    {
        "name": "verify_fix",
        "description": "Final health check — confirm the service is healthy after the fix",
        "parameters": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "check_type": {
                    "type": "string",
                    "enum": ["HEALTH_CHECK", "METRIC_CHECK", "LOG_TAIL"],
                },
            },
            "required": ["service"],
        },
    },
]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "remediation": {"type": "object"},
    },
    "required": ["status"],
}

DEFAULT_FALLBACK = {
    "status": "error",
    "remediation": {
        "action": "UNKNOWN",
        "result": "Agent output unparseable",
        "verified": False,
        "bash_output": None,
        "error_code": "AGENT_FAILED",
    },
}

AGENT_NAME = "Remediator"
