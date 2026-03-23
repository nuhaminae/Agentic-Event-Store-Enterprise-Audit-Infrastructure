# tests/test_concurrency.py
# Test concurrency control for event store and append operation.
# RUN: pytest -v tests/test_concurrency.py

import asyncio
import os
import uuid

import pytest
import pytest_asyncio
from dotenv import load_dotenv

from src.event_store import EventStore
from src.models.events import BaseEvent, OptimisticConcurrencyError, StreamArchivedError

pytestmark = pytest.mark.asyncio

# Load environment variables from .env or .example.env
load_dotenv()


@pytest_asyncio.fixture
async def event_store():
    dsn = (
        f"postgresql://{os.getenv('POSTGRES_USER')}:"
        f"{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/"
        f"{os.getenv('POSTGRES_DB')}"
    )
    store = EventStore(dsn=dsn)
    await store.connect()
    yield store
    await store.close()


async def test_double_decision_concurrency(event_store):
    """
    Double-decision concurrency test:
    Two concurrent asyncio tasks appending to the same stream at expected_version=3.
    Asserts exactly one succeeds, one raises OptimisticConcurrencyError,
    and total stream length = 4. Also verifies outbox entries exist.
    Prints detailed logs for rubric evidence.
    """
    stream_id = f"order-{uuid.uuid4()}"

    # Seed the stream with 3 events so current_version = 3
    for i in range(3):
        e = BaseEvent(event_type="OrderEvent", payload={"step": i})
        version = await event_store.append(stream_id, [e], expected_version=i)
        print(f"Seed event {i} appended, new version={version}")
        assert version == i + 1

    # Prepare two concurrent appends at expected_version=3
    e1 = BaseEvent(event_type="OrderConfirmed", payload={"status": "ok"})
    e2 = BaseEvent(event_type="OrderFailed", payload={"status": "error"})

    async def append_event(ev, label):
        try:
            pos = await event_store.append(stream_id, [ev], expected_version=3)
            print(f"{label} succeeded at stream_position={pos}")
            return pos
        except OptimisticConcurrencyError as exc:
            print(
                f"{label} failed with OptimisticConcurrencyError: expected={exc.expected_version}, actual={exc.actual_version}"
            )
            return exc

    # Run both concurrently
    results = await asyncio.gather(
        append_event(e1, "Task1"),
        append_event(e2, "Task2"),
        return_exceptions=True,
    )

    # Exactly one should succeed, one should raise OptimisticConcurrencyError
    success_count = sum(1 for r in results if isinstance(r, int))
    error_count = sum(1 for r in results if isinstance(r, OptimisticConcurrencyError))
    print(f"Success count={success_count}, Error count={error_count}")
    assert success_count == 1
    assert error_count == 1

    # Verify total stream length = 4
    events = await event_store.load_stream(stream_id)
    print(f"Total stream length={len(events)}")
    assert len(events) == 4

    # Verify outbox entries exist for all 4 events
    async with event_store.pool.acquire() as conn:
        outbox_rows = await conn.fetch(
            "SELECT * FROM outbox WHERE event_id = ANY($1::uuid[])",
            [ev.event_id for ev in events],
        )
        print(
            f"Outbox rows={len(outbox_rows)}, statuses={[r['status'] for r in outbox_rows]}"
        )
        assert len(outbox_rows) == 4
        assert all(r["status"] == "pending" for r in outbox_rows)


async def test_append_to_archived_stream(event_store):
    """
    Tests appending to an archived stream.

    Appends an initial event, archives the stream, and then attempts to append again.
    Verifies that attempting to append after archiving raises a StreamArchivedError.
    Prints detailed logs for rubric evidence.
    """
    stream_id = f"user-{uuid.uuid4()}"
    event = BaseEvent(event_type="UserRegistered", payload={"user_id": "abc"})

    # Append initial event
    version = await event_store.append(stream_id, [event], expected_version=0)
    print(f"Initial event appended to {stream_id}, new version={version}")
    assert version == 1

    # Archive the stream
    await event_store.archive_stream(stream_id)
    print(f"Stream {stream_id} archived successfully")

    # Attempt to append after archiving should raise StreamArchivedError
    try:
        await event_store.append(stream_id, [event], expected_version=1)
    except StreamArchivedError as exc:
        print(
            f"Append failed with StreamArchivedError: stream_id={stream_id}, expected_version=1"
        )
        # Explicitly assert the exception type
        assert isinstance(exc, StreamArchivedError)
    else:
        raise AssertionError(
            "Expected StreamArchivedError, but append succeeded unexpectedly"
        )
