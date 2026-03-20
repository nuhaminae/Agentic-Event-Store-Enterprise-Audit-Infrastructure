# src/models/events.py
# Pydantic models for Event Store domain

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel, Field


# --- Base Event (for appending) ---
class BaseEvent(BaseModel):
    """Represents a domain event to be appended to a stream.
    
    Notes:
        - `metadata` is reserved for event-level extras (headers, tags).
        - Correlation and causation IDs are explicit fields.
    
    """

    event_type: str   # should match EventType.name
    version: int = Field(default=1, ge=1)  # should match EventType.version
    payload: Dict[str, Any]
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


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
    metadata: Dict[str, str] = Field(default_factory=dict)
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
    metadata: Dict[str, str] = Field(default_factory=dict)

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
    checkpoint_metadata: Dict[str, str] = Field(default_factory=dict)

# --- Exceptions ---
class EventStoreError(Exception):
    """Base exception for event store errors."""


class StreamArchivedError(EventStoreError):
    """Raised when attempting to append to an archived stream."""


class OptimisticConcurrencyError(EventStoreError):
    """Raised when optimistic concurrency check fails."""