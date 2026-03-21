# tests/test_compliance_record.py
# Test ComplianceRecordAggregate
# RUN: pytest -v tests/test_compliance_record.py

import os
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from src.aggregates.compliance_record import MANDATORY_CHECKS, ComplianceRecordAggregate
from src.event_store import EventStore
from src.models.aggregates import ComplianceState
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

    The EventStore instance is yielded from the fixture, so that it can be used in the test.
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


async def test_compliance_record_full_lifecycle(event_store):
    """
    Tests the full lifecycle of a ComplianceRecordAggregate, including recording mandatory checks,
    verifying all checks are completed, preventing duplicate checks, archiving the record, and
    preventing recording after archiving. Also verifies that the outbox pattern ensures events
    are both stored and published.
    """
    record_id = f"TEST-{uuid.uuid4()}"
    agg = ComplianceRecordAggregate(record_id)
    version = 0
    event_ids = []

    # --- Record mandatory checks ---
    for check in MANDATORY_CHECKS:
        agg.record_check(check)
        for e in agg.events:
            version = await event_store.append(
                f"compliance-{record_id}", [e], expected_version=version
            )
        reloaded = await ComplianceRecordAggregate.load(event_store, record_id)
        event_ids.extend(ev.event_id for ev in reloaded.events)
        assert check in reloaded.completed_checks
        assert reloaded.state in {
            ComplianceState.CHECKS_IN_PROGRESS,
            ComplianceState.ALL_CHECKS_COMPLETED,
        }

    # --- Verify all checks completed ---
    reloaded = await ComplianceRecordAggregate.load(event_store, record_id)
    assert reloaded.state == ComplianceState.ALL_CHECKS_COMPLETED
    reloaded.assert_all_checks_completed()

    # --- Prevent duplicate check ---
    with pytest.raises(OptimisticConcurrencyError):
        reloaded.record_check("fraud")

    # --- Archive record ---
    reloaded.archive("2026-03-21T06:00:00Z")
    for e in reloaded.events:
        version = await event_store.append(
            f"compliance-{record_id}", [e], expected_version=version
        )
    reloaded = await ComplianceRecordAggregate.load(event_store, record_id)
    event_ids.extend(ev.event_id for ev in reloaded.events)
    assert reloaded.state == ComplianceState.ARCHIVED
    assert reloaded.archived_at == "2026-03-21T06:00:00Z"

    # --- Prevent recording after archive ---
    with pytest.raises(OptimisticConcurrencyError):
        reloaded.record_check("extra-check")

    # --- Prevent archiving if not completed ---
    incomplete = ComplianceRecordAggregate(f"TEST-{uuid.uuid4()}")
    with pytest.raises(OptimisticConcurrencyError):
        incomplete.archive("2026-03-21T06:10:00Z")

    # --- Outbox verification ---
    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])", event_ids
        )
        assert len(rows) == len(event_ids)
        assert all(r["status"] == "pending" for r in rows)
