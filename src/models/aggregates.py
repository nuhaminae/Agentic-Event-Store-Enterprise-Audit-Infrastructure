# src/models/aggregates.py
# Aggregate models

from enum import Enum


# ---------- Application State ----------
class ApplicationState(str, Enum):
    """Loan application state."""

    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    CREDIT_ANALYZED = "CREDIT_ANALYZED"
    FRAUD_SCREENED = "FRAUD_SCREENED"
    COMPLIANCE_CHECKED = "COMPLIANCE_CHECKED"
    DECIDED = "DECIDED"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    ARCHIVED = "ARCHIVED"


# ---------- Agent Session State ----------
class AgentSessionState(str, Enum):
    """Agent session state."""

    NEW = "NEW"
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    ARCHIVED = "ARCHIVED"


# ---------- Compliance Record State ----------
class ComplianceState(str, Enum):
    """Compliance record state."""

    NEW = "NEW"
    CHECKS_IN_PROGRESS = "CHECKS_IN_PROGRESS"
    ALL_CHECKS_COMPLETED = "ALL_CHECKS_COMPLETED"
    ARCHIVED = "ARCHIVED"
