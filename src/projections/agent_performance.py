# src/projections/agent_performance.py
# Tracks agent performance metrics keyed by (agent_id, model_version).
# Increments decisions count when an AgentDecisionMade event occurs.

from src.models.events import BaseEvent
from src.upcasting.setup import build_registry


class AgentPerformanceProjection:
    name = "AgentPerformance"

    async def apply(self, conn, event: BaseEvent):
        """
        Applies an AgentDecisionMade event to the projection.

        Increments the decisions count for the given agent_id and model_version.

        :param conn: The database connection to use
        :param event: The event to apply to the projection
        :type conn: asyncpg.Connection
        :type event: dict
        """

        if event.event_type == "AgentDecisionMade":
            payload = event.payload
            agent_id = payload.get("agent_id")
            model_version = payload.get("model_version", "v1")
            if agent_id:
                await conn.execute(
                    """INSERT INTO agent_performance (agent_id, model_version, decisions)
                       VALUES ($1, $2, 1)
                       ON CONFLICT (agent_id, model_version) DO UPDATE
                       SET decisions = agent_performance.decisions + 1""",
                    agent_id,
                    model_version,
                )

    async def snapshot(self, conn):
        """Rebuild agent performance from all events."""
        rows = await conn.fetch("SELECT * FROM events ORDER BY global_position ASC")
        registry = build_registry()
        for row in rows:
            event = registry.from_row(row)
            await self.apply(conn, event)
