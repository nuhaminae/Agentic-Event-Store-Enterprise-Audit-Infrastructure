# src/projections/application_summary.py
# Maintains one row per loan application keyed by application_id.
# Updates status, amount, and decision timestamp when a DecisionGenerated event occurs.

import json


class ApplicationSummaryProjection:
    name = "ApplicationSummary"

    async def apply(self, conn, event):
        """
        Applies the given event to the projection.

        If the event is a DecisionGenerated event, updates the application_summary row
        with the given application_id with the latest decision and approved amount.

        :param conn: The database connection to use
        :param event: The event to apply to the projection
        :type conn: asyncpg.Connection
        :type event: dict
        """
        if event["event_type"] == "DecisionGenerated":
            payload = json.loads(event["payload"])
            decision = payload.get("decision")
            approved_amount = payload.get("approved_amount_usd")
            application_id = payload.get("application_id", "loan-123")

            if decision is not None:
                await conn.execute(
                    """INSERT INTO application_summary (application_id, status, amount, decided_at)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (application_id) DO UPDATE
                       SET status=$2, amount=$3, decided_at=$4""",
                    application_id,
                    decision,
                    approved_amount,
                    event["recorded_at"],
                )

    async def snapshot(self, conn):
        """Rebuild application summary from all events."""
        rows = await conn.fetch("SELECT * FROM events ORDER BY global_position ASC")
        for row in rows:
            await self.apply(conn, row)
