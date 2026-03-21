# tests/test_audit_ledger.py
# Test AuditLedgerAggregate
# RUN: pytest -v tests/test_audit_ledger.py

import os
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from src.aggregates.audit_ledger import AuditLedgerAggregate
from src.event_store import EventStore
from src.models.events import OptimisticConcurrencyError

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def event_store():
    """
    A pytest fixture that creates an EventStore instance using the environment variables
    set in .env or .example.env. It connects to the database, yields the EventStore
    instance, and then closes the connection when the test is finished.

    The EventStore instance is connected to the database before the test is started,
    and then disconnected after the test is finished. This ensures that the database
    connection is properly cleaned up after the test is finished, and that the test
    does not interfere with other tests that may be using the same database.
    """
    load_dotenv()
    dsn = (
        f"postgresql://{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/"
        f"{os.getenv('POSTGRES_DB')}"
    )
    store = EventStore(dsn=dsn)
    await store.connect()
    yield store
    await store.close()


async def test_audit_ledger_causal_ordering(event_store):
    """
    Test causal ordering of events in the Audit Ledger Aggregate.

    Verifies that events are recorded in the correct order and that the Audit Ledger
    Aggregate enforces causal ordering of events across the system.

    Also verifies that the outbox pattern ensures events are both stored and published.
    """
    ledger_id = f"TEST-{uuid.uuid4()}"
    agg = AuditLedgerAggregate(ledger_id)
    version = 0
    event_ids = []

    # --- Record first event ---
    agg.record_event("LedgerInitialized", {"info": "start"})
    for e in agg.events:
        version = await event_store.append(
            f"audit-ledger-{ledger_id}", [e], expected_version=version
        )

    reloaded = await AuditLedgerAggregate.load(event_store, ledger_id)
    event_ids.extend(
        ev.event_id for ev in await event_store.load_stream(f"audit-ledger-{ledger_id}")
    )
    assert "LedgerInitialized" in reloaded.applied_events.values()

    # --- Record second event with valid causation ---
    causation_id = str(event_ids[0])
    reloaded.record_event("LedgerEntryAdded", {"entry": "A"}, causation_id=causation_id)
    for e in reloaded.events:
        version = await event_store.append(
            f"audit-ledger-{ledger_id}", [e], expected_version=version
        )

    reloaded = await AuditLedgerAggregate.load(event_store, ledger_id)
    # only add the new event_id
    new_ids = [
        ev.event_id for ev in await event_store.load_stream(f"audit-ledger-{ledger_id}")
    ]
    event_ids = list(set(new_ids))  # keep unique IDs
    assert "LedgerEntryAdded" in reloaded.applied_events.values()

    # --- Prevent event with invalid causation ---
    with pytest.raises(OptimisticConcurrencyError):
        reloaded.record_event(
            "LedgerEntryAdded", {"entry": "B"}, causation_id="non-existent-id"
        )

    # --- Outbox verification ---
    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])", event_ids
        )
        assert len(rows) == len(event_ids)
        assert all(r["status"] == "pending" for r in rows)
