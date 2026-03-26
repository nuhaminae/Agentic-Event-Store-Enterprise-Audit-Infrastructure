# src/mcp/tools.py

import os

import asyncpg
from dotenv import load_dotenv

from src.event_store import EventStore
from src.integrity.audit_chain import run_integrity_check
from src.models.events import BaseEvent

load_dotenv()
DSN = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/ledger_app"
)


async def _append_with_version(stream_id, event):
    # Query current version directly with asyncpg
    conn = await asyncpg.connect(DSN)
    row = await conn.fetchrow(
        "SELECT current_version FROM event_streams WHERE stream_id=$1", stream_id
    )
    current_version = row["current_version"] if row else 0
    await conn.close()

    store = EventStore(dsn=DSN)
    await store.connect()
    # ✅ Pass current_version directly, not +1
    await store.append(stream_id, [event], expected_version=current_version)
    await store.close()


def register_tools(server):
    @server.tool("submit_application")
    async def submit_application(payload):
        event = BaseEvent(event_type="ApplicationSubmitted", payload=payload)
        await _append_with_version(payload["application_id"], event)
        return {"status": "submitted"}

    @server.tool("record_credit_analysis")
    async def record_credit_analysis(payload):
        event = BaseEvent(event_type="CreditAnalysisCompleted", payload=payload)
        await _append_with_version(payload["application_id"], event)
        return {"status": "credit_analysis_recorded"}

    @server.tool("record_fraud_screening")
    async def record_fraud_screening(payload):
        event = BaseEvent(event_type="FraudScreeningCompleted", payload=payload)
        await _append_with_version(payload["application_id"], event)
        return {"status": "fraud_screening_recorded"}

    @server.tool("record_compliance_check")
    async def record_compliance_check(payload):
        event = BaseEvent(event_type="ComplianceCheckRecorded", payload=payload)
        await _append_with_version(payload["compliance_id"], event)
        return {"status": "compliance_check_recorded"}

    @server.tool("generate_decision")
    async def generate_decision(payload):
        event = BaseEvent(event_type="DecisionGenerated", payload=payload)
        await _append_with_version(payload["application_id"], event)
        return {"status": "decision_generated"}

    @server.tool("record_human_review")
    async def record_human_review(payload):
        event = BaseEvent(event_type="HumanReviewCompleted", payload=payload)
        await _append_with_version(payload["application_id"], event)
        return {"status": "human_review_recorded"}

    @server.tool("start_agent_session")
    async def start_agent_session(payload):
        event = BaseEvent(event_type="AgentSessionStarted", payload=payload)
        await _append_with_version(payload["agent_id"], event)
        return {"status": "agent_session_started"}

    @server.tool("run_integrity_check")
    async def run_integrity(payload):
        dsn = payload.get("dsn", DSN)
        result = await run_integrity_check(dsn)
        return {"integrity_passed": result}
