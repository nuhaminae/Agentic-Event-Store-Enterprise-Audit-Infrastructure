# tests/test_loan_application.py
# Test LoanApplicationAggregate
# RUN: pytest -v tests/test_loan_application.py

import os
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from src.aggregates.loan_application import LoanApplicationAggregate
from src.event_store import EventStore
from src.models.aggregates import ApplicationState
from src.models.events import OptimisticConcurrencyError

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def event_store():
    """
    A pytest fixture that creates an EventStore instance using the environment
    variables set in .env or .example.env. It connects to the database, yields
    the EventStore instance, and then closes the connection when the test is
    finished.

    The EventStore instance is connected to the database before the test is
    started, and then disconnected after the test is finished. This ensures
    that the database connection is properly cleaned up after the test is finished,
    and that the test does not interfere with other tests that may be using the
    same database.

    The EventStore instance is yielded from the fixture, so that it can be used
    in the test.
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


# --- Command + Persistence + Reload Tests ---
async def test_submit_application_persists_and_reloads(event_store):
    """
    Test that submitting an application persists the events and reloads the
    aggregate correctly, with the correct state and event data.

    Verify that the outbox table contains the correct events and that the
    events are in the "pending" status.
    """
    app_id = f"TEST-{uuid.uuid4()}"
    agg = LoanApplicationAggregate(app_id)
    agg.submit_application("COMP-999", 12345.0)

    version = 0
    for e in agg.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    assert reloaded.state == ApplicationState.SUBMITTED
    assert reloaded.applicant_id == "COMP-999"
    assert reloaded.requested_amount == 12345.0

    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])",
            [ev.event_id for ev in reloaded.events],
        )
        assert len(rows) == len(reloaded.events)
        assert all(r["status"] == "pending" for r in rows)


async def test_submit_application_twice_raises_error(event_store):
    """
    Test that submitting an application twice raises an OptimisticConcurrencyError.

    This test verifies that an application can only be submitted once.
    If the application is already submitted, attempting to submit it again will
    result in an OptimisticConcurrencyError being raised.

    The test creates an application, submits it, and then attempts to submit it
    again. It verifies that the OptimisticConcurrencyError is raised in this
    case.
    """
    app_id = f"TEST-{uuid.uuid4()}"
    agg = LoanApplicationAggregate(app_id)
    agg.submit_application("COMP-111", 5000.0)

    version = 0
    for e in agg.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    with pytest.raises(OptimisticConcurrencyError):
        reloaded.submit_application("COMP-222", 6000.0)


async def test_generate_decision_sets_state_and_outbox(event_store):
    """
    Test that generating a decision sets the state and outbox correctly.

    This test verifies that generating a decision sets the state of the
    application to DECIDED and that the outbox table contains the correct events
    with the correct status ("pending").

    The test creates an application, sets its state to COMPLIANCE_CHECKED, and
    then generates a decision. It then verifies that the state of the application
    is DECIDED and that the outbox table contains the correct events with the
    correct status ("pending").
    """
    app_id = f"TEST-{uuid.uuid4()}"
    agg = LoanApplicationAggregate(app_id)
    agg.state = ApplicationState.COMPLIANCE_CHECKED
    agg.generate_decision("APPROVED", approved_amount_usd=2000.0)

    version = 0
    for e in agg.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    assert reloaded.state == ApplicationState.DECIDED
    assert reloaded.decision == "APPROVED"
    assert reloaded.approved_amount == 2000.0

    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])",
            [ev.event_id for ev in reloaded.events],
        )
        assert len(rows) == len(reloaded.events)
        assert all(r["status"] == "pending" for r in rows)


async def test_require_human_review_and_outbox(event_store):
    """
    Test that requiring a human review sets the state and outbox correctly.

    This test verifies that requiring a human review sets the state of the
    application to HUMAN_REVIEW and that the outbox table contains the correct
    events with the correct status ("pending").

    The test creates an application, sets its state to COMPLIANCE_CHECKED, and
    then requires a human review. It then verifies that the state of the
    application is HUMAN_REVIEW and that the outbox table contains the correct
    events with the correct status ("pending").

    """
    app_id = f"TEST-{uuid.uuid4()}"
    agg = LoanApplicationAggregate(app_id)
    agg.state = ApplicationState.COMPLIANCE_CHECKED
    agg.require_human_review("Suspicious activity")

    version = 0
    for e in agg.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    assert reloaded.state == ApplicationState.HUMAN_REVIEW

    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])",
            [ev.event_id for ev in reloaded.events],
        )
        assert len(rows) == len(reloaded.events)
        assert all(r["status"] == "pending" for r in rows)


async def test_archive_and_outbox(event_store):
    """
    Tests archiving an application and verifies that the outbox contains the correct events
    with the correct status ("pending").

    The test creates an application, sets its state to DECIDED, archives the application, and
    then verifies that the state of the application is ARCHIVED and that the outbox table contains
    the correct events with the correct status ("pending").
    """
    app_id = f"TEST-{uuid.uuid4()}"
    agg = LoanApplicationAggregate(app_id)
    agg.state = ApplicationState.DECIDED
    agg.archive("2026-03-21T05:00:00Z")

    version = 0
    for e in agg.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    assert reloaded.state == ApplicationState.ARCHIVED
    assert reloaded.archived_at == "2026-03-21T05:00:00Z"

    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])",
            [ev.event_id for ev in reloaded.events],
        )
        assert len(rows) == len(reloaded.events)
        assert all(r["status"] == "pending" for r in rows)


# --- End-to-End Multi-Event Scenario ---
async def test_full_lifecycle_submit_to_archive(event_store):
    """
    Tests the full lifecycle of a LoanApplicationAggregate, from submission to archival.

    Verifies that the aggregate is correctly persisted and reloaded, and that the outbox
    table contains the correct events with the correct status ("pending").
    """
    app_id = f"TEST-{uuid.uuid4()}"
    agg = LoanApplicationAggregate(app_id)

    # Submit
    agg.submit_application("COMP-777", 9999.0)
    version = 0
    for e in agg.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    # Compliance check
    agg.state = ApplicationState.COMPLIANCE_CHECKED
    agg.generate_decision("APPROVED", approved_amount_usd=5000.0)
    for e in agg.events[1:]:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    # Archive
    agg.state = ApplicationState.DECIDED
    agg.archive("2026-03-21T06:00:00Z")
    for e in agg.events[2:]:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    assert reloaded.state == ApplicationState.ARCHIVED
    assert reloaded.archived_at == "2026-03-21T06:00:00Z"

    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])",
            [ev.event_id for ev in reloaded.events],
        )
        assert len(rows) == len(reloaded.events)
        assert all(r["status"] == "pending" for r in rows)


async def test_credit_analysis_completed_and_outbox(event_store):
    """
    Tests that completing a credit analysis sets the state and outbox correctly.

    Verifies that the aggregate is correctly persisted and reloaded, and that the outbox
    table contains the correct events with the correct status ("pending").

    The test creates an application, submits it, reloads the application, runs a credit
    analysis, persists the credit analysis, reloads the application again, and verifies
    that the state of the application is CREDIT_ANALYZED and that the outbox table
    contains the correct events with the correct status ("pending").
    """
    app_id = f"TEST-{uuid.uuid4()}"
    agg = LoanApplicationAggregate(app_id)
    agg.submit_application("COMP-123", 1000.0)

    # persist submission
    version = 0
    for e in agg.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    # reload and run credit analysis
    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    reloaded.credit_analysis_completed(
        agent_id="AGENT-1",
        session_id="SESSION-1",
        model_version="v1.0",
        confidence_score=0.95,
        risk_tier="LOW",
        recommended_limit_usd=5000.0,
        duration_ms=123,
        input_data_hash="hash-abc",
    )

    for e in reloaded.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    assert reloaded.state == ApplicationState.CREDIT_ANALYZED

    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])",
            [ev.event_id for ev in reloaded.events],
        )
        assert len(rows) == len(reloaded.events)
        assert all(r["status"] == "pending" for r in rows)


async def test_fraud_screening_completed_and_outbox(event_store):
    """
    Tests that completing a fraud screening sets the state and outbox correctly.

    Verifies that the aggregate is correctly persisted and reloaded, and that the outbox
    table contains the correct events with the correct status ("pending").

    The test creates an application, sets its state to CREDIT_ANALYZED, completes a
    fraud screening, persists the fraud screening, reloads the application again, and
    verifies that the state of the application is FRAUD_SCREENED and that the outbox table
    contains the correct events with the correct status ("pending").
    """
    app_id = f"TEST-{uuid.uuid4()}"
    agg = LoanApplicationAggregate(app_id)
    agg.state = ApplicationState.CREDIT_ANALYZED
    agg.fraud_screening_completed("PASS")

    version = 0
    for e in agg.events:
        version = await event_store.append(
            f"loan-{app_id}", [e], expected_version=version
        )

    reloaded = await LoanApplicationAggregate.load(event_store, app_id)
    assert reloaded.state == ApplicationState.FRAUD_SCREENED

    async with event_store.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])",
            [ev.event_id for ev in reloaded.events],
        )
        assert len(rows) == len(reloaded.events)
        assert all(r["status"] == "pending" for r in rows)
