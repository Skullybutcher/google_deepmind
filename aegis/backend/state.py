from dataclasses import dataclass, field, asdict
from datetime import datetime
import json
import os

@dataclass
class IncidentState:
    incident_id: str
    status: str = "PLANNING"
    alert: dict = field(default_factory=dict)
    plan: dict = field(default_factory=dict)
    plan_version: int = 1
    findings: dict = field(default_factory=dict)
    diagnosis: dict = None
    remediation: dict = None
    history: list = field(default_factory=list)
    plan_version_history: list = field(default_factory=list)
    interaction_ids: dict = field(default_factory=dict)

    def add_event(self, event_type: str, **kwargs):
        self.history.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": event_type,
            **kwargs
        })

    def persist(self):
        with open(f"state_{self.incident_id}.json", "w") as f:
            json.dump(asdict(self), f, indent=2, default=str)
