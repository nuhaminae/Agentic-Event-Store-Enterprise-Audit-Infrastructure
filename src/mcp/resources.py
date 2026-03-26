# src/mcp/resources.py

import asyncpg


def register_resources(server):
    @server.resource("applications")
    async def applications(query):
        conn = await asyncpg.connect(query["dsn"])
        # Instead of querying application_summary, pull from events
        rows = await conn.fetch("""
            SELECT DISTINCT stream_id AS application_id
            FROM events
            WHERE event_type = 'ApplicationSubmitted'
        """)
        await conn.close()
        return [dict(r) for r in rows]

    @server.resource("compliance")
    async def compliance(query):
        conn = await asyncpg.connect(query["dsn"])
        rows = await conn.fetch("SELECT * FROM compliance_audit")
        await conn.close()
        return [dict(r) for r in rows]

    @server.resource("audit-trail")
    async def audit_trail(query):
        conn = await asyncpg.connect(query["dsn"])
        rows = await conn.fetch("SELECT * FROM events ORDER BY global_position ASC")
        await conn.close()
        return [dict(r) for r in rows]

    @server.resource("agent-performance")
    async def agent_performance(query):
        conn = await asyncpg.connect(query["dsn"])
        rows = await conn.fetch("SELECT * FROM agent_performance")
        await conn.close()
        return [dict(r) for r in rows]

    @server.resource("agent-sessions")
    async def agent_sessions(query):
        conn = await asyncpg.connect(query["dsn"])
        rows = await conn.fetch(
            "SELECT * FROM events WHERE event_type LIKE 'AgentSession%' ORDER BY recorded_at ASC"
        )
        await conn.close()
        return [dict(r) for r in rows]

    @server.resource("ledger-health")
    async def ledger_health(query):
        conn = await asyncpg.connect(query["dsn"])
        latest = await conn.fetchval("SELECT max(global_position) FROM events")
        await conn.close()
        return {"latest_event_position": latest}
