# Test upcasting of events
# RUN: pytest -v tests/test_upcasting.py

from datetime import datetime, timezone

from src.models.events import BaseEvent
from src.upcasting.registry import UpcasterRegistry
from src.upcasting.upcasters import (
    upcast_credit_analysis_v1_to_v2,
    upcast_decision_generated_v1_to_v2,
)


def test_upcast_credit_analysis():
    """
    Test upcasting of CreditAnalysisCompleted from version 1 to 2.

    Given an original CreditAnalysisCompleted event from version 1, when upcasting it to version 2,
    the resulting event should have the model version and confidence score set, and the version should be 2.
    """
    original = BaseEvent(
        event_type="CreditAnalysisCompleted",
        payload={"score": 720},
        version=1,
        recorded_at=datetime(2026, 3, 25, tzinfo=timezone.utc),
    )
    registry = UpcasterRegistry()
    registry.register("CreditAnalysisCompleted", 1, upcast_credit_analysis_v1_to_v2)

    upcasted = registry.upcast(original)

    assert "model_version" not in original.payload
    assert "confidence_score" not in original.payload
    assert upcasted.payload.get("model_version") is not None
    assert "confidence_score" in upcasted.payload
    assert upcasted.version == 2


def test_upcast_decision_generated():
    """
    Test upcasting of DecisionGenerated from version 1 to 2.

    Given an original DecisionGenerated event from version 1, when upcasting it to version 2,
    the resulting event should have the regulatory_basis set, and the version should be 2.
    """
    original = BaseEvent(
        event_type="DecisionGenerated",
        payload={"decision": "APPROVED"},
        version=1,
        recorded_at=datetime(2026, 3, 25, tzinfo=timezone.utc),
    )
    registry = UpcasterRegistry()
    registry.register("DecisionGenerated", 1, upcast_decision_generated_v1_to_v2)

    upcasted = registry.upcast(original)

    assert "regulatory_basis" not in original.payload
    assert "regulatory_basis" in upcasted.payload
    assert upcasted.version == 2
