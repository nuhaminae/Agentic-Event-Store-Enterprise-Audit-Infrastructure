# src/commands/models.py
# Command models

from typing import Any, Dict, Optional

from pydantic import BaseModel


# ----------- Application Commands -----------
class SubmitApplicationCommand(BaseModel):
    """Submit an application."""

    application_id: str
    applicant_id: str
    requested_amount_usd: float
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


# ----------- Credit Analysis Commands -----------
class CreditAnalysisCompletedCommand(BaseModel):
    """Record a credit analysis result for an application."""

    application_id: str
    agent_id: str
    session_id: str
    model_version: str
    confidence_score: float
    risk_tier: str
    recommended_limit_usd: float
    duration_ms: int
    input_data: Dict[str, Any]
    input_data_hash: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


# ----------- Fraud Screening Commands -----------
class FraudScreeningCommand(BaseModel):
    """Record a fraud screening result for an application."""

    application_id: str
    result: str
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


# ----------- Compliance Check Commands -----------
class ComplianceCheckCommand(BaseModel):
    """Record a compliance check for a compliance record."""

    record_id: str
    check_type: str
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


# ----------- Decision Commands -----------
class GenerateDecisionCommand(BaseModel):
    """Generate a decision for an application."""

    application_id: str
    decision: str  # "APPROVED" or "REJECTED"
    approved_amount_usd: Optional[float] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


# ----------- Human Review Commands -----------
class HumanReviewCommand(BaseModel):
    """Initiate a human review for an application."""

    application_id: str
    reason: str
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


# ----------- Agent Session Commands -----------
class StartAgentSessionCommand(BaseModel):
    """Start a new agent session."""

    session_id: str
    agent_id: str
    model_version: str
    started_at: str
    active_model_versions: list[str]
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
