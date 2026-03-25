# Upcasters
# Handles upcasting of events / functions that perform schema upgrade

import json
from datetime import datetime, timezone
from pathlib import Path

from src.models.events import BaseEvent


def upcast_credit_analysis_v1_to_v2(event: BaseEvent) -> BaseEvent:
    payload = event.payload.copy()
    payload["model_version"] = infer_model_version(event.recorded_at)
    payload["confidence_score"] = None
    return event.model_copy(update={"version": 2, "payload": payload})


def upcast_decision_generated_v1_to_v2(event: BaseEvent) -> BaseEvent:
    payload = event.payload.copy()
    payload["regulatory_basis"] = infer_reg_basis(event.recorded_at)
    return event.model_copy(update={"version": 2, "payload": payload})


# Load config once
MODEL_CONFIG = json.loads(Path("src/config/model_versions.json").read_text())


def infer_model_version(recorded_at: datetime) -> str:
    latest = "legacy"
    for entry in MODEL_CONFIG["versions"]:
        # Ensure start is UTC‑aware
        start = datetime.fromisoformat(entry["start"]).replace(tzinfo=timezone.utc)
        if recorded_at >= start:
            latest = entry["label"]
    return latest


REGULATORY_REGIMES = [
    {"start": (2025, 1), "basis": "AML-KYC-2025"},
    {"start": (2026, 1), "basis": "AML-KYC-2026"},
]


def infer_reg_basis(recorded_at: datetime) -> str:
    basis = "legacy"
    for regime in REGULATORY_REGIMES:
        y, m = regime["start"]
        if recorded_at.year > y or (recorded_at.year == y and recorded_at.month >= m):
            basis = regime["basis"]
    return basis
