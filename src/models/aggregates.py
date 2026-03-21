# src/models/aggregates.py
# Aggregate models

from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel


# ---------- Payloads for Domain Events ----------
class ComplianceCheckRecordedPayload(BaseModel):
    check_type: str


# ---------- Payloads for Domain Events ----------
class AllComplianceChecksCompletedPayload(BaseModel):
    completed: list[str]


# ---------- Payloads for Compliance Record Events ----------
class ComplianceRecordArchivedPayload(BaseModel):
    archived_at: str


# ---------- Payloads for Audit Ledger Events ----------
class AuditLedgerEventPayload(BaseModel):
    data: Dict[str, Any]


# ---------- Payloads for Agent Session Events ----------
class AgentSessionStartedPayload(BaseModel):
    agent_id: str
    model_version: str
    started_at: str


# ---------- Payloads for Agent Session Events ----------
class AgentSessionEndedPayload(BaseModel):
    ended_at: str


# ---------- Payloads for Agent Session Events ----------
class AgentSessionArchivedPayload(BaseModel):
    archived_at: str


# ---------- Application State ----------
class ApplicationState(str, Enum):
    """Loan application state."""

    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    CREDIT_ANALYSED = "CREDIT_ANALYSED"
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
