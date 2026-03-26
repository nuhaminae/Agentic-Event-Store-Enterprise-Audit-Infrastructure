# src/models/events.py
# Pydantic models for Event Store domain with typed payloads and structured exceptions

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# --- Typed Payloads for Domain Events ---
class ApplicationSubmittedPayload(BaseModel):
    """Payload for ApplicationSubmitted event"""

    applicant_id: str
    requested_amount_usd: float


class CreditAnalysisCompletedPayload(BaseModel):
    """Payload for CreditAnalysisCompleted event"""

    application_id: str
    agent_id: str
    session_id: str
    model_version: str
    confidence_score: float
    risk_tier: str
    recommended_limit_usd: float
    analysis_duration_ms: int
    input_data_hash: Optional[str] = None


class FraudScreeningCompletedPayload(BaseModel):
    """Payload for FraudScreeningCompleted event"""

    application_id: str
    result: str


class ComplianceCheckCompletedPayload(BaseModel):
    """Payload for ComplianceCheckCompleted event"""

    compliance_id: str
    check_type: str


class DecisionGeneratedPayload(BaseModel):
    """Payload for DecisionGenerated event"""

    decision: str  # "APPROVED" or "REJECTED"
    approved_amount_usd: Optional[float] = None


class HumanReviewRequiredPayload(BaseModel):
    reason: str


class ApplicationArchivedPayload(BaseModel):
    archived_at: str


# --- Base Event (for appending) ---
class BaseEvent(BaseModel):
    """Represents a domain event to be appended to a stream.

    Notes:
        - `metadata` is reserved for event-level extras (headers, tags).
        - Correlation and causation IDs are explicit fields.

    """

    event_type: str
    version: int = Field(default=1, ge=1)
    payload: Dict[str, Any]  # still stored as dict for JSONB
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recorded_at: Optional[datetime] = None


# --- Event Types ---
class EventType(BaseModel):
    """Represents a domain event type definition."""

    name: str
    version: int = Field(default=1, ge=1)
    payload_schema: Optional[Dict[str, Any]] = None


# --- Stored Event Wrapper ---
class StoredEvent(BaseModel):
    """Immutable event as stored in the event store.

    Notes:
        - `metadata` is reserved for event-level extras (headers, tags).
        - Correlation and causation IDs are explicit fields.
    """

    event_id: UUID
    stream_id: str
    stream_position: int
    global_position: int
    event_type: str
    event_version: int
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


# --- Stream Metadata ---
class StreamMetadata(BaseModel):
    """Metadata about an event stream (aggregate).

    Notes:
        - `metadata` is reserved for aggregate-level attributes (labels, owner info).
        - Do not store correlation/causation IDs here.
    """

    stream_id: str
    aggregate_type: str
    current_version: int
    created_at: datetime
    archived_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


# --- Outbox Status ---
class OutboxStatus(str, Enum):
    """Represents the status of an outbox entry."""

    pending = "pending"
    published = "published"
    failed = "failed"


# --- Outbox Entry ---
class OutboxEntry(BaseModel):
    """Represents an outbox entry for reliable publishing."""

    id: UUID
    event_id: UUID
    destination: str
    payload: Dict[str, Any]
    created_at: datetime
    published_at: Optional[datetime] = None
    attempts: int = 0
    status: OutboxStatus = OutboxStatus.pending


# --- Projection Checkpoint ---
class ProjectionCheckpoint(BaseModel):
    """Tracks replay progress for a projection.

    Notes:
        - Use `stream_id` if the projection replays events per stream.
        - `checkpoint_id` ensures uniqueness when multiple checkpoints exist.
    """

    checkpoint_id: UUID
    projection_name: str
    stream_id: Optional[str] = None
    last_position: int
    updated_at: datetime
    projection_version: int
    checkpoint_metadata: Dict[str, Any] = Field(default_factory=dict)


# --- Exceptions ---
class EventStoreError(Exception):
    """Base exception for event store errors."""


class StreamArchivedError(EventStoreError):
    """Raised when attempting to append to an archived stream."""


class OptimisticConcurrencyError(EventStoreError):
    """Raised when optimistic concurrency check fails."""

    def __init__(self, stream_id: str, expected_version: int, actual_version: int):
        self.stream_id = stream_id
        self.expected_version = expected_version
        self.actual_version = actual_version
        super().__init__(
            f"Optimistic concurrency error on stream {stream_id}: "
            f"expected {expected_version}, got {actual_version}"
        )


class DomainError(Exception):
    """Raised when a domain rule or invariant is violated."""
