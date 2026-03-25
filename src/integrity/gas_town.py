# src/integrity/gas_town.py
# Deterministic replay of agent state with upcaster integration

import asyncpg

from src.upcasting.setup import build_registry


async def reconstruct_agent_context(dsn, agent_id):
    """
    Replay events for crash recovery.
    Deterministically reconstructs agent state from its stream using upcasters.
    """
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch(
        "SELECT * FROM events WHERE stream_id=$1 ORDER BY stream_position ASC", agent_id
    )

    registry = build_registry()
    state = {"agent_id": agent_id, "sessions": 0, "decisions": []}

    for row in rows:
        event = registry.from_row(row)  # normalize with upcasters
        etype = event.event_type
        payload = event.payload

        if etype == "AgentSessionStarted":
            state["sessions"] += 1
        elif etype == "AgentDecisionMade":
            state["decisions"].append(payload.get("decision"))
        elif etype == "AgentSessionEnded":
            state["last_session_closed"] = True

    await conn.close()
    return state
