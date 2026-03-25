# src/projections/daemon.py
# Runs projections in a loop, updating checkpoints and reporting UI contract violations
# Run after initialising the event store with `python -m src.init_db`
# RUN: python src/projections/daemon.py

import asyncio
import logging
import os
from datetime import UTC, datetime

import asyncpg
from dotenv import load_dotenv

from src.projections.agent_performance import AgentPerformanceProjection
from src.projections.application_summary import ApplicationSummaryProjection
from src.projections.compliance_audit import ComplianceAuditProjection
from src.upcasting.setup import build_registry


class ProjectionDaemon:
    def __init__(self, dsn, projections, batch_size=100, lag_thresholds=None):
        """
        Initialises the ProjectionDaemon with the given event store connection string (dsn),
        projections to run, batch size, and lag thresholds for UI contract violations.

        :param dsn: PostgreSQL connection string
        :param projections: List of Projection instances to run
        :param batch_size: Number of events to process in each batch (default: 100)
        :param lag_thresholds: Optional dictionary of projection name to lag threshold
            (in milliseconds) for UI contract violations (default: {})
        """
        self.dsn = dsn
        self.projections = projections
        self.batch_size = batch_size
        self.conn = None
        self.lag_thresholds = lag_thresholds or {}

        # Set up registry with all upcasters
        self.upcaster_registry = build_registry()

    async def connect(self):
        """
        Establishes a connection to the PostgreSQL event store using the given DSN.

        :returns: None
        :rtype: NoneType
        """
        self.conn = await asyncpg.connect(self.dsn)

    async def run(self):
        """
        Runs the projection daemon indefinitely, processing each projection in sequence
        every 100ms (configurable with `lag_thresholds`).

        :returns: None
        :rtype: NoneType
        """
        while True:
            for proj in self.projections:
                await self._process_projection(proj)
            await asyncio.sleep(0.1)

    async def _process_projection(self, projection):
        """
        Processes a single projection, applying it to a batch of events in the event store
        and updating the checkpoint afterwards.

        :param projection: Projection instance to process
        :returns: None
        :rtype: NoneType
        """
        checkpoint = await self._load_checkpoint(projection.name)
        last_pos = checkpoint.get("last_position", 0)

        rows = await self.conn.fetch(
            "SELECT * FROM events WHERE global_position > $1 ORDER BY global_position ASC LIMIT $2",
            last_pos,
            self.batch_size,
        )

        if not rows:
            return

        for row in rows:
            event = self.upcaster_registry.from_row(row)  # normalise event
            await projection.apply(self.conn, event)  # pass normalised event

        new_pos = rows[-1]["global_position"]
        await self._update_checkpoint(projection.name, new_pos)

        # Compute lag relative to projection checkpoint
        lag = await self._compute_lag(projection.name)
        self._report_ui_contract(projection.name, lag, rows[-1]["recorded_at"])

    async def _load_checkpoint(self, name):
        """
        Loads the checkpoint for the given projection name.

        :param name: Name of the projection to load
        :returns: A dictionary containing the checkpoint data if found, otherwise {"last_position": 0}
        :rtype: dict
        """
        row = await self.conn.fetchrow(
            "SELECT * FROM projection_checkpoints WHERE projection_name=$1", name
        )
        return dict(row) if row else {"last_position": 0}

    async def _update_checkpoint(self, name, pos):
        """
        Updates the checkpoint for the given projection name.

        :param name: Name of the projection to update
        :param pos: New last position of the projection
        :returns: None
        :rtype: NoneType
        """
        await self.conn.execute(
            """INSERT INTO projection_checkpoints (projection_name,last_position,updated_at)
               VALUES ($1,$2,$3)
               ON CONFLICT (projection_name) DO UPDATE
               SET last_position=$2, updated_at=$3""",
            name,
            pos,
            datetime.now(UTC),  # timezone‑aware UTC
        )

    async def _compute_lag(self, projection_name: str) -> int:
        """
        Computes the lag of the given projection with respect to the latest event position.

        :param projection_name: The name of the projection whose lag is being computed
        :returns: The lag of the projection in terms of the number of events
        :rtype: int
        """
        checkpoint = await self._load_checkpoint(projection_name)
        pos = checkpoint.get("last_position", 0)
        latest = await self.conn.fetchval("SELECT max(global_position) FROM events")
        return latest - pos if latest else 0

    def _report_ui_contract(self, projection_name, lag, last_event_time):
        """
        Reports the lag of the given projection to the UI contract.

        If the lag of the projection exceeds the configured threshold for that projection,
        a warning message is logged indicating that the data may be stale.

        :param projection_name: Name of the projection to report
        :param lag: The lag of the projection in terms of the number of events
        :param last_event_time: The timestamp of the last event of the projection
        :type projection_name: str
        :type lag: int
        :type last_event_time: datetime
        """
        threshold = self.lag_thresholds.get(projection_name)
        if threshold and lag > threshold:
            logging.warning(
                f"[UI CONTRACT] {projection_name} data may be stale. "
                f"Lag={lag} events. Last updated at {last_event_time}."
            )
        else:
            logging.info(
                f"[UI CONTRACT] {projection_name} data current as of {last_event_time}. "
                f"Lag={lag} events."
            )


# -------------------------
# Main entry point
# -------------------------
load_dotenv()
DSN = (
    f"postgresql://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
    f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/ledger_app"
)


async def main():
    """
    Main entry point for the ProjectionDaemon.

    This function connects to the event store, constructs the projection daemon,
    and starts the projection update loop.

    :return: None
    :rtype: NoneType
    """
    logging.basicConfig(level=logging.INFO)
    logging.info(f"Connecting to DSN: {DSN}")
    projections = [
        ApplicationSummaryProjection(),
        AgentPerformanceProjection(),
        ComplianceAuditProjection(),
    ]

    daemon = ProjectionDaemon(DSN, projections)
    await daemon.connect()
    await daemon.run()


if __name__ == "__main__":
    asyncio.run(main())
