# tests/test_agent_session.py
# Test AgentSessionAggregate
# RUN: pytest -v tests/test_agent_session.py

import os
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from src.aggregates.agent_session import AgentSessionAggregate
from src.event_store import EventStore
from src.models.aggregates import AgentSessionState
from src.models.events import DomainError, OptimisticConcurrencyError

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def event_store():
    """
    Connects to the event store, yielding an EventStore instance
    ready for use. Automatically closes the connection after the
    test is finished.
    """

    load_dotenv()
    dsn = (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/"
        f"{os.getenv('POSTGRES_DB')}"
    )
    store = EventStore(dsn=dsn)
    await store.connect()
    yield store
    await store.close()


async def test_agent_session_full_lifecycle(event_store):
    """
    Tests the full lifecycle of an AgentSessionAggregate, from starting a session to archiving it.

    Verifies that the aggregate is correctly persisted and reloaded, and that the outbox
    table contains the correct events with the correct status ("pending").
    """
    session_id = f"TEST-{uuid.uuid4()}"
    agg = AgentSessionAggregate(session_id)
    version = 0
    event_ids = []

    # --- Start session ---
    agg.start_session(
        "AGENT-001", "v1.0", "2026-03-21T05:00:00Z", active_model_versions=[]
    )
    for e in agg.events:
        version = await event_store.append(
            f"agent-session-{session_id}", [e], expected_version=version
        )

    reloaded = await AgentSessionAggregate.load(event_store, session_id)
    event_ids.extend(ev.event_id for ev in reloaded.events)
    assert reloaded.state == AgentSessionState.ACTIVE
    assert reloaded.agent_id == "AGENT-001"
    assert reloaded.model_version == "v1.0"
    reloaded.assert_context_loaded()

    # --- Prevent duplicate start (OptimisticConcurrencyError) ---
    with pytest.raises(OptimisticConcurrencyError):
        reloaded.start_session(
            "AGENT-002", "v2.0", "2026-03-21T05:10:00Z", active_model_versions=[]
        )

    # --- Prevent starting with duplicate model version (DomainError now) ---
    with pytest.raises(DomainError):
        AgentSessionAggregate(session_id).start_session(
            "AGENT-003", "v1.0", "2026-03-21T05:15:00Z", active_model_versions=["v1.0"]
        )

    # --- End session ---
    reloaded.end_session("2026-03-21T05:30:00Z")
    for e in reloaded.events:
        version = await event_store.append(
            f"agent-session-{session_id}", [e], expected_version=version
        )

    reloaded = await AgentSessionAggregate.load(event_store, session_id)
    event_ids.extend(ev.event_id for ev in reloaded.events)
    assert reloaded.state == AgentSessionState.ENDED
    assert reloaded.ended_at == "2026-03-21T05:30:00Z"

    # --- Prevent ending if not active (OptimisticConcurrencyError) ---
    with pytest.raises(OptimisticConcurrencyError):
        AgentSessionAggregate(session_id).end_session("2026-03-21T05:40:00Z")

    # --- Archive session ---
    reloaded.archive("2026-03-21T06:00:00Z")
    for e in reloaded.events:
        version = await event_store.append(
            f"agent-session-{session_id}", [e], expected_version=version
        )

    reloaded = await AgentSessionAggregate.load(event_store, session_id)
    event_ids.extend(ev.event_id for ev in reloaded.events)
    assert reloaded.state == AgentSessionState.ARCHIVED

    # --- Prevent archiving if not ended (OptimisticConcurrencyError) ---
    with pytest.raises(OptimisticConcurrencyError):
        AgentSessionAggregate(session_id).archive("2026-03-21T06:10:00Z")

    # --- Assertions ---
    with pytest.raises(OptimisticConcurrencyError):
        AgentSessionAggregate(session_id).assert_context_loaded()

    reloaded.assert_model_version_current("v1.0")
    with pytest.raises(OptimisticConcurrencyError):
        reloaded.assert_model_version_current("v2.0")

    # --- Outbox verification ---
    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])", event_ids
        )
        assert len(rows) == len(event_ids)
        assert all(r["status"] == "pending" for r in rows)
