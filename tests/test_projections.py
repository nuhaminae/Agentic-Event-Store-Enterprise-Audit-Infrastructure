# tests/test_projections.py
# Test projections with UI contract validation
# RUN: pytest -v tests/test_projections.py

import logging
import os

import asyncpg
import pytest
import pytest_asyncio
from dotenv import load_dotenv

from src.event_store import EventStore
from src.init_db import (
    seed_agent_session,
    seed_compliance_record,
    seed_loan_application,
)
from src.projections.agent_performance import AgentPerformanceProjection
from src.projections.application_summary import ApplicationSummaryProjection
from src.projections.compliance_audit import ComplianceAuditProjection
from src.projections.daemon import ProjectionDaemon

pytestmark = pytest.mark.asyncio
load_dotenv()


@pytest.fixture
def event_store_dsn():
    return (
        f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/ledger_app"
    )


@pytest_asyncio.fixture(autouse=True)
async def reset_and_seed(event_store_dsn):
    conn = await asyncpg.connect(event_store_dsn)
    try:
        # Truncate all tables including event_streams
        await conn.execute("TRUNCATE events CASCADE")
        await conn.execute("TRUNCATE event_streams CASCADE")
        await conn.execute("TRUNCATE outbox CASCADE")
        await conn.execute("TRUNCATE application_summary CASCADE")
        await conn.execute("TRUNCATE agent_performance CASCADE")
        await conn.execute("TRUNCATE compliance_audit CASCADE")
        await conn.execute("TRUNCATE projection_checkpoints CASCADE")

        # Seed fresh events
        store = EventStore(dsn=event_store_dsn)
        await store.connect()
        await seed_loan_application(store)
        await seed_agent_session(store)
        await seed_compliance_record(store)
        await store.close()

        yield
    finally:
        await conn.close()


# -------------------------
# Tests
# -------------------------


async def test_projection_lag_slo(event_store_dsn, caplog):
    projections = [
        ApplicationSummaryProjection(),
        AgentPerformanceProjection(),
        ComplianceAuditProjection(),
    ]
    thresholds = {"ApplicationSummary": 1000, "ComplianceAuditView": 2000}
    daemon = ProjectionDaemon(event_store_dsn, projections, lag_thresholds=thresholds)

    await daemon.connect()
    caplog.set_level(logging.INFO)

    # Run daemon once to process seeded events
    await daemon._process_projection(projections[0])

    lag = await daemon._compute_lag(0)
    assert (
        lag < thresholds["ApplicationSummary"]
    ), f"ApplicationSummary lag too high: {lag}"

    ui_logs = [rec.message for rec in caplog.records if "[UI CONTRACT]" in rec.message]
    assert any(
        "ApplicationSummary" in msg for msg in ui_logs
    ), "UI contract log missing for ApplicationSummary"

    # Verify checkpoint written
    conn = await asyncpg.connect(event_store_dsn)
    cp = await conn.fetchrow(
        "SELECT * FROM projection_checkpoints WHERE projection_name=$1",
        "ApplicationSummary",
    )
    assert cp, "Checkpoint not written for ApplicationSummary"
    await conn.close()


async def test_rebuild_from_scratch(event_store_dsn):
    conn = await asyncpg.connect(event_store_dsn)
    proj = ComplianceAuditProjection()
    await proj.snapshot(conn)  # pass conn explicitly
    rows = await conn.fetch("SELECT * FROM compliance_audit")
    assert len(rows) > 0
    await conn.close()


async def test_projection_lag_warning(event_store_dsn, caplog):
    conn = await asyncpg.connect(event_store_dsn)
    proj = ApplicationSummaryProjection()
    thresholds = {"ApplicationSummary": 1}
    daemon = ProjectionDaemon(event_store_dsn, [proj], lag_thresholds=thresholds)

    await daemon.connect()
    caplog.set_level(logging.WARNING)

    # Force checkpoint to zero
    await conn.execute(
        """INSERT INTO projection_checkpoints (projection_name,last_position,updated_at)
           VALUES ($1,$2,NOW())
           ON CONFLICT (projection_name) DO UPDATE SET last_position=$2""",
        proj.name,
        0,
    )

    # Process projection
    await daemon._process_projection(proj)

    # Compute lag explicitly
    lag = await daemon._compute_lag(0)
    assert lag > thresholds["ApplicationSummary"], "Lag did not exceed threshold"

    await conn.close()
