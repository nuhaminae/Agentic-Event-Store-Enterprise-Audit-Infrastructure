# src/event_store.py
# Enterprise Event Store & Audit Infrastructure

import json
import uuid
from typing import AsyncIterator, List, Optional

import asyncpg
from asyncpg import UniqueViolationError

from src.models.events import (
    BaseEvent,
    EventStoreError,
    OptimisticConcurrencyError,
    ProjectionCheckpoint,
    StoredEvent,
    StreamArchivedError,
    StreamMetadata,
)


class EventStore:
    """
    Enterprise Event Store & Audit Infrastructure.

    Responsibilities:
    - Append events immutably with audit fields and concurrency control.
    - Maintain stream lifecycle (creation, archiving, versioning).
    - Stage events in outbox for reliable publishing.
    - Support replay via stream-local and global queries.
    - Manage projection checkpoints with versioning and metadata.
    """

    def __init__(self, dsn: str):
        """
        Initialise the EventStore with a PostgreSQL connection string.

        Args:
            dsn (str): Connection string for the PostgreSQL database.

        Attributes:
            dsn (str): Connection string for the PostgreSQL database.
            pool (Optional[asyncpg.Pool]): Underlying connection pool.
        """
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """
        Establish a connection pool to the PostgreSQL database.

        This method sets up an underlying connection pool to the
        PostgreSQL database. It is a prerequisite for any
        other operations on the EventStore.

        Note that this method is idempotent, and calling it multiple
        times will have no additional effect.
        """
        self.pool = await asyncpg.create_pool(dsn=self.dsn)

    async def close(self):
        """
        Close the connection pool to the PostgreSQL database.

        This method closes the underlying connection pool to the
        PostgreSQL database. It is an idempotent operation, and
        calling it multiple times will have no additional effect.

        Note that this method is usually called when the application is
        shutting down, to release any resources held by the pool.
        """
        if self.pool:
            await self.pool.close()

    async def append(
        self,
        stream_id: str,
        events: List[BaseEvent],
        expected_version: int,
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> int:
        """
        Append a list of events to a stream with concurrency control.

        Args:
            stream_id (str): The identifier for the event stream.
            events (List[BaseEvent]): The events to be appended to the stream.
            expected_version (int): The expected current version of the stream.
            correlation_id (str | None, optional): The correlation ID for the events.
            causation_id (str | None, optional): The causation ID for the events.

        Returns:
            int: The new version of the stream after appending the events.

        Raises:
            StreamArchivedError: If the stream has been archived.
            OptimisticConcurrencyError: If the expected version does not match the current version.
        """
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Check stream metadata
                row = await conn.fetchrow(
                    "SELECT current_version, archived_at FROM event_streams WHERE stream_id=$1",
                    stream_id,
                )
                if row and row["archived_at"] is not None:
                    raise StreamArchivedError(f"Stream {stream_id} is archived")

                current_version = row["current_version"] if row else 0

                # Concurrency check
                if expected_version != -1 and current_version != expected_version:
                    raise OptimisticConcurrencyError(
                        stream_id=stream_id,
                        expected_version=expected_version,
                        actual_version=current_version,
                    )

                # Create stream if new
                if row is None:
                    await conn.execute(
                        """
                        INSERT INTO event_streams (stream_id, aggregate_type, current_version, created_at)
                        VALUES ($1, $2, 0, NOW())
                        """,
                        stream_id,
                        stream_id.split("-")[0],
                    )

                new_version = current_version
                for e in events:
                    new_version += 1
                    event_id = str(uuid.uuid4())
                    try:
                        await conn.execute(
                            """
                            INSERT INTO events (
                                event_id, stream_id, stream_position, event_type,
                                event_version, payload, metadata, recorded_at,
                                correlation_id, causation_id
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), $8, $9)
                            """,
                            event_id,
                            stream_id,
                            new_version,
                            e.event_type,
                            e.version,
                            json.dumps(e.payload),
                            json.dumps({"system": "event_store"}),
                            # NOTE: This metadata column is reserved strictly for system-level information
                            # (e.g., audit tags, infrastructure markers). Do not use for domain/business fields.
                            correlation_id,
                            causation_id,
                        )

                    # UniqueViolationError handling
                    except UniqueViolationError:
                        raise OptimisticConcurrencyError(
                            stream_id=stream_id,
                            expected_version=new_version,
                            actual_version=new_version,  # or current_version depending on context
                        )

                    # Outbox insert with status
                    outbox_id = str(uuid.uuid4())
                    await conn.execute(
                        """
                        INSERT INTO outbox (id, event_id, destination, payload, created_at, attempts, status)
                        VALUES ($1, $2, $3, $4, NOW(), 0, 'pending')
                        """,
                        outbox_id,
                        event_id,
                        "event_bus",
                        json.dumps(e.payload),
                    )

                # Update stream version
                await conn.execute(
                    """
                    UPDATE event_streams
                    SET current_version=$2
                    WHERE stream_id=$1
                    """,
                    stream_id,
                    new_version,
                )

                return new_version

    async def load_stream(
        self,
        stream_id: str,
        from_position: int = 0,
        to_position: int | None = None,
    ) -> List[StoredEvent]:
        """
        Load events from a stream in the event store.

        Args:
            stream_id (str): The identifier for the event stream.
            from_position (int, optional): The starting position for the event range. Defaults to 0.
            to_position (int | None, optional): The ending position for the event range. Defaults to None.

        Returns:
            List[StoredEvent]: The list of events loaded from the stream.
        """
        async with self.pool.acquire() as conn:
            query = """
                SELECT * FROM events
                WHERE stream_id=$1 AND stream_position >= $2
            """
            params = [stream_id, from_position]
            if to_position is not None:
                query += " AND stream_position <= $3"
                params.append(to_position)
            query += " ORDER BY stream_position ASC"
            rows = await conn.fetch(query, *params)
            # return [StoredEvent(**dict(r)) for r in rows]
            events = []
            for r in rows:
                data = dict(r)
                # Decode JSON fields into dicts
                data["payload"] = (
                    json.loads(data["payload"])
                    if isinstance(data["payload"], str)
                    else data["payload"]
                )
                data["metadata"] = (
                    json.loads(data["metadata"])
                    if isinstance(data["metadata"], str)
                    else data["metadata"]
                )
                events.append(StoredEvent(**data))
            return events

    async def load_all(
        self,
        from_global_position: int = 0,
        until_position: int | None = None,
        event_types: List[str] | None = None,
        batch_size: int = 500,
    ) -> AsyncIterator[StoredEvent]:
        """Stream all events from the global log, optionally bounded by until_position."""
        async with self.pool.acquire() as conn:
            pos = from_global_position
            while True:
                if event_types:
                    query = """
                        SELECT * FROM events
                        WHERE global_position > $1
                          AND ($2::bigint IS NULL OR global_position <= $2)
                          AND event_type = ANY($3::text[])
                        ORDER BY global_position ASC
                        LIMIT $4
                    """
                    rows = await conn.fetch(
                        query, pos, until_position, event_types, batch_size
                    )
                else:
                    query = """
                        SELECT * FROM events
                        WHERE global_position > $1
                          AND ($2::bigint IS NULL OR global_position <= $2)
                        ORDER BY global_position ASC
                        LIMIT $3
                    """
                    rows = await conn.fetch(query, pos, until_position, batch_size)

                if not rows:
                    break

                for r in rows:
                    yield StoredEvent(**dict(r))
                pos = rows[-1]["global_position"]

                # Stop if we've reached or passed until_position
                if until_position is not None and pos >= until_position:
                    break

    async def stream_version(self, stream_id: str) -> int:
        """
        Return the current version of a stream in the event store.

        Args:
            stream_id (str): The identifier for the event stream.

        Returns:
            int: The current version of the stream, or 0 if the stream does not exist.
        """
        async with self.pool.acquire() as conn:
            version = await conn.fetchval(
                "SELECT current_version FROM event_streams WHERE stream_id=$1",
                stream_id,
            )
            return version or 0

    async def archive_stream(self, stream_id: str) -> None:
        """
        Archive an event stream by setting the archived_at field to the current timestamp.

        Args:
            stream_id (str): The identifier for the event stream to archive.

        Returns:
            None
        """
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE event_streams
                SET archived_at=NOW()
                WHERE stream_id=$1
            """,
                stream_id,
            )

    async def get_stream_metadata(self, stream_id: str) -> StreamMetadata:
        """
        Load the metadata for a stream from the event store.

        Args:
            stream_id (str): The identifier for the event stream.

        Returns:
            StreamMetadata: The metadata for the stream.

        Raises:
            EventStoreError: If the stream is not found.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM event_streams WHERE stream_id=$1", stream_id
            )
            if not row:
                raise EventStoreError(f"Stream {stream_id} not found")
            return StreamMetadata(**dict(row))

    async def get_checkpoint(
        self, projection_name: str, stream_id: str | None = None
    ) -> ProjectionCheckpoint:
        """
        Load the checkpoint for a projection from the event store.

        Args:
            projection_name (str): The identifier for the projection.
            stream_id (str | None, optional): The identifier for the event stream. Defaults to None.

        Returns:
            ProjectionCheckpoint: The checkpoint for the projection.

        Raises:
            EventStoreError: If the checkpoint is not found or if multiple checkpoints exist without a stream_id.
        """
        async with self.pool.acquire() as conn:
            if stream_id:
                row = await conn.fetchrow(
                    "SELECT * FROM projection_checkpoints WHERE projection_name=$1 AND stream_id=$2",
                    projection_name,
                    stream_id,
                )
            else:
                rows = await conn.fetch(
                    "SELECT * FROM projection_checkpoints WHERE projection_name=$1 ORDER BY updated_at DESC",
                    projection_name,
                )
                if len(rows) > 1:
                    raise EventStoreError(
                        f"Multiple checkpoints found for projection '{projection_name}'. "
                        "Please specify a stream_id to disambiguate."
                    )
                row = rows[0] if rows else None

            if not row:
                raise EventStoreError(
                    f"Checkpoint for projection '{projection_name}' (stream={stream_id}) not found"
                )
            return ProjectionCheckpoint(**dict(row))

    async def list_checkpoints(
        self, projection_name: str
    ) -> List[ProjectionCheckpoint]:
        """Return all checkpoints for a given projection."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM projection_checkpoints WHERE projection_name=$1 ORDER BY updated_at DESC",
                projection_name,
            )
            return [ProjectionCheckpoint(**dict(r)) for r in rows]

    async def update_checkpoint(
        self,
        projection_name: str,
        last_position: int,
        stream_id: str | None = None,
        projection_version: int = 1,
        checkpoint_metadata: dict | None = None,
    ) -> None:
        """
        Update the checkpoint for a projection in the event store.

        Args:
            projection_name (str): The identifier for the projection.
            last_position (int): The last global position processed by the projection.
            stream_id (str | None, optional): The identifier for the event stream associated with the projection. Defaults to None.
            projection_version (int, optional): The version number of the projection, used for tracking schema changes. Defaults to 1.
            checkpoint_metadata (dict | None, optional): Additional metadata associated with the checkpoint, such as tags or notes. Defaults to None.

        Raises:
            EventStoreError: If the checkpoint metadata is invalid, or if a duplicate checkpoint is detected.
        """
        async with self.pool.acquire() as conn:
            try:
                await conn.execute(
                    """
                    INSERT INTO projection_checkpoints (
                        projection_name, stream_id, last_position, updated_at,
                        projection_version, checkpoint_metadata
                    )
                    VALUES ($1, $2, $3, NOW(), $4, $5)
                    ON CONFLICT (projection_name, stream_id)
                    DO UPDATE SET last_position=$3, updated_at=NOW(),
                                  projection_version=$4, checkpoint_metadata=$5
                    """,
                    projection_name,
                    stream_id,
                    last_position,
                    projection_version,
                    json.dumps(checkpoint_metadata or {}),
                )
            except (TypeError, ValueError) as e:
                raise EventStoreError(f"Invalid checkpoint metadata: {e}")
            except UniqueViolationError:
                raise EventStoreError(
                    f"Duplicate checkpoint detected for projection '{projection_name}' "
                    f"and stream '{stream_id or 'NULL'}'. Ensure uniqueness on (projection_name, stream_id)."
                )
            except Exception as e:
                raise EventStoreError(f"Unexpected error updating checkpoint: {e}")
