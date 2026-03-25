# src/projections/compliance_audit.py
# Maintains a temporal audit log of compliance checks.
# Each ComplianceCheckRecorded event is inserted as a new row.

import json

from src.models.events import BaseEvent
from src.upcasting.setup import build_registry


class ComplianceAuditProjection:
    name = "ComplianceAudit"

    async def apply(self, conn, event: BaseEvent):
        """
        Applies a ComplianceCheckRecorded event to the projection.

        Inserts a new row into the compliance_audit table with the compliance_id, event_type, payload, and recorded_at.
        If the compliance_id is missing from the event payload, the event is skipped.

        :param conn: The database connection to use
        :param event: The ComplianceCheckRecorded event to apply
        :type conn: asyncpg.Connection
        :type event: dict
        """
        if event.event_type == "ComplianceCheckRecorded":
            payload = event.payload
            compliance_id = payload.get("compliance_id")
            if compliance_id:
                await conn.execute(
                    """INSERT INTO compliance_audit (compliance_id, event_type, payload, recorded_at)
                       VALUES ($1, $2, $3, $4)""",
                    compliance_id,
                    event.event_type,
                    json.dumps(payload),
                    event.recorded_at,
                )

    async def snapshot(self, conn):
        """Rebuild compliance audit from all events."""
        rows = await conn.fetch("SELECT * FROM events ORDER BY global_position ASC")
        registry = build_registry()
        for row in rows:
            event = registry.from_row(row)
            await self.apply(conn, event)
