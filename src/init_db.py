# src/init_db.py
# Initialises the event store database
# RUN: python -m src.init_db

import asyncio
import os

from dotenv import load_dotenv

from src.event_store import EventStore
from src.models.events import BaseEvent

load_dotenv()
DSN = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/ledger_app"
)


async def seed_loan_application(store):
    """
    Seeds the event store with a loan application aggregate
    containing multiple events.

    :param store: an instance of EventStore
    :return: None
    """
    stream_id = "loan-123"
    events = [
        BaseEvent(
            event_type="ApplicationSubmitted",
            payload={"applicant_id": "applicant-123", "requested_amount_usd": 5000},
        ),
        BaseEvent(
            event_type="CreditAnalysisCompleted",
            payload={
                "application_id": "loan-123",
                "agent_id": "agent-123",
                "session_id": "session-123",
                "model_version": "v1.0",
                "confidence_score": 0.8,
                "risk_tier": "high",
                "recommended_limit_usd": 10000,
                "analysis_duration_ms": 1000,
                "input_data_hash": "hash-123",
            },
        ),
        BaseEvent(
            event_type="FraudScreeningCompleted",
            payload={"application_id": "loan-123", "result": "pass"},
        ),
        BaseEvent(
            event_type="ComplianceCheckCompleted",
            payload={"compliance_id": "comp-aml-123", "check_type": "AML"},
        ),
        BaseEvent(
            event_type="DecisionGenerated",
            payload={"decision": "approved", "approved_amount_usd": 10000},
        ),
        BaseEvent(event_type="HumanReviewRequired", payload={"reason": "high_risk"}),
        BaseEvent(
            event_type="ApplicationArchived",
            payload={"archived_at": "2023-01-01T00:00:00Z"},
        ),
    ]
    for i, e in enumerate(events):
        version = await store.append(stream_id, [e], expected_version=i)
        print(f"LoanApplication event {e.event_type} appended at version={version}")


async def seed_agent_session(store):
    """
    Seeds the event store with an agent session aggregate containing multiple events.

    :param store: an instance of EventStore
    :return: None
    """
    stream_id = "agent-456"
    events = [
        BaseEvent(
            event_type="AgentSessionStarted",
            payload={"agent_id": "agent-456", "model_version": "v1.0"},
        ),
        BaseEvent(
            event_type="AgentDecisionMade",
            payload={"agent_id": "agent-456", "decision": "approve"},
        ),
        BaseEvent(event_type="AgentSessionEnded", payload={"agent_id": "agent-456"}),
    ]
    for i, e in enumerate(events):
        version = await store.append(stream_id, [e], expected_version=i)
        print(f"AgentSession event {e.event_type} appended at version={version}")


async def seed_compliance_record(store):
    """
    Seeds the event store with a compliance record aggregate containing multiple events.

    :param store: an instance of EventStore
    :return: None
    """
    stream_id = "compliance-789"
    events = [
        BaseEvent(
            event_type="ComplianceCheckRecorded",
            payload={
                "compliance_id": "compliance-789",
                "rule": "AML",
                "result": "pass",
            },
        ),
        BaseEvent(
            event_type="ComplianceCheckRecorded",
            payload={
                "compliance_id": "compliance-789",
                "rule": "KYC",
                "result": "pass",
            },
        ),
    ]
    for i, e in enumerate(events):
        version = await store.append(stream_id, [e], expected_version=i)
        print(f"ComplianceRecord event {e.event_type} appended at version={version}")


async def main():
    """
    Initialises the event store with sample data.

    This function is the entry point for the database initialisation script.

    It creates an instance of the EventStore class and connects to the PostgreSQL
    database specified by the DSN environment variable.

    It then calls the seed_loan_application, seed_agent_session, and seed_compliance_record
    functions to populate the event store with sample data.

    Finally, it closes the connection to the database.

    :return: None
    """
    store = EventStore(dsn=DSN)
    await store.connect()

    await seed_loan_application(store)
    await seed_agent_session(store)
    await seed_compliance_record(store)

    await store.close()


if __name__ == "__main__":
    asyncio.run(main())
