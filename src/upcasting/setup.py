# src/upcasting/setup.py
# Central place to register upcasters

from src.upcasting.registry import UpcasterRegistry
from src.upcasting.upcasters import (
    upcast_credit_analysis_v1_to_v2,
    upcast_decision_generated_v1_to_v2,
)


def build_registry() -> UpcasterRegistry:
    registry = UpcasterRegistry()
    registry.register("CreditAnalysisCompleted", 1, upcast_credit_analysis_v1_to_v2)
    registry.register("DecisionGenerated", 1, upcast_decision_generated_v1_to_v2)
    return registry
