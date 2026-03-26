# tests/test_mcp_lifecycle.py
# Test MCP server lifecycle
# RUN: pytest -v tests/test_mcp_lifecycle.py

import uuid

import asyncpg
import pytest
import pytest_asyncio

from src.mcp.core import MCPServer
from src.mcp.resources import register_resources
from src.mcp.tools import register_tools

pytestmark = pytest.mark.asyncio

import os

from dotenv import load_dotenv

load_dotenv()

DSN = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/ledger_app"
)


class MCPTestClient:
    def __init__(self, server):
        self.server = server

    async def call_tool(self, name, payload):
        fn = self.server.tools[name]
        return await fn(payload)

    async def query_resource(self, name, query):
        fn = self.server.resources[name]
        return await fn(query)


# Reset DB before each test run
@pytest_asyncio.fixture(autouse=True)
async def reset_db():
    conn = await asyncpg.connect(DSN)
    await conn.execute("TRUNCATE events, event_streams RESTART IDENTITY CASCADE")
    await conn.close()


@pytest_asyncio.fixture
async def mcp_client():
    server = MCPServer(name="TestMCP")
    register_tools(server)
    register_resources(server)
    return MCPTestClient(server)


async def test_full_lifecycle(mcp_client):
    # Use a unique application_id each run to avoid collisions
    application_id = f"loan-{uuid.uuid4()}"
    compliance_id = f"comp-{uuid.uuid4()}"

    # Submit application
    resp = await mcp_client.call_tool(
        "submit_application", {"application_id": application_id, "amount": 10000}
    )
    assert resp["status"] == "submitted"

    # Record credit analysis
    resp = await mcp_client.call_tool(
        "record_credit_analysis", {"application_id": application_id, "score": 680}
    )
    assert resp["status"] == "credit_analysis_recorded"

    # Record fraud screening
    resp = await mcp_client.call_tool(
        "record_fraud_screening", {"application_id": application_id, "result": "pass"}
    )
    assert resp["status"] == "fraud_screening_recorded"

    # Record compliance check
    resp = await mcp_client.call_tool(
        "record_compliance_check",
        {"compliance_id": compliance_id, "rule": "AML", "result": "pass"},
    )
    assert resp["status"] == "compliance_check_recorded"

    # Generate decision
    resp = await mcp_client.call_tool(
        "generate_decision", {"application_id": application_id, "decision": "approved"}
    )
    assert resp["status"] == "decision_generated"

    # Record human review
    resp = await mcp_client.call_tool(
        "record_human_review",
        {
            "application_id": application_id,
            "reviewer": "agent-456",
            "outcome": "completed",
        },
    )
    assert resp["status"] == "human_review_recorded"

    # Start agent session
    resp = await mcp_client.call_tool(
        "start_agent_session", {"agent_id": "agent-456", "model_version": "v1.0"}
    )
    assert resp["status"] == "agent_session_started"

    # Query application summary
    apps = await mcp_client.query_resource("applications", {"dsn": DSN})
    assert any(app["application_id"] == application_id for app in apps)

    # Run integrity check
    # Run integrity check
    integrity = await mcp_client.call_tool("run_integrity_check", {"dsn": DSN})

    # Verify the structure and the value
    assert isinstance(integrity, dict)
    assert "integrity_passed" in integrity
    assert isinstance(integrity["integrity_passed"], dict)
    assert "integrity_passed" in integrity["integrity_passed"]
    assert integrity["integrity_passed"]["integrity_passed"] is True
