# src/load_seed_events.py
# Load test seed events into the database
# python src/load_seed_events.py

import asyncio
import json
import os
import uuid
from datetime import datetime

import asyncpg
from dotenv import load_dotenv

load_dotenv()
SEED_FILE = "data/seed_events.jsonl"


async def load_seed_events():
    conn = await asyncpg.connect(
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        database=os.getenv("POSTGRES_DB"),
        host=os.getenv("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT")),
    )

    async with conn.transaction():
        with open(SEED_FILE, "r") as f:
            for line in f:
                event = json.loads(line)

                stream_id = event["stream_id"]
                event_type = event["event_type"]
                event_version = event["event_version"]
                payload = event["payload"]
                recorded_at = datetime.fromisoformat(event["recorded_at"])

                # Ensure stream exists
                await conn.execute(
                    """
                    INSERT INTO event_streams (stream_id, aggregate_type, current_version, created_at)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (stream_id) DO UPDATE
                    SET current_version = GREATEST(event_streams.current_version, $3)
                """,
                    stream_id,
                    stream_id.split("-")[0],
                    event_version,
                    recorded_at,
                )

                # Insert event
                event_id = str(uuid.uuid4())
                result = await conn.execute(
                    """
                    INSERT INTO events (
                        event_id, stream_id, stream_position, event_version,
                        event_type, payload, metadata, recorded_at
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT DO NOTHING
                """,
                    event_id,
                    stream_id,
                    event_version,
                    event_version,
                    event_type,
                    json.dumps(payload),
                    json.dumps({"recorded_at": recorded_at.isoformat()}),
                    recorded_at,
                )

                # Only insert into outbox if event was actually inserted
                if result == "INSERT 0 1":
                    outbox_id = str(uuid.uuid4())
                    await conn.execute(
                        """
                        INSERT INTO outbox (id, event_id, destination, payload, published_at, attempts)
                        VALUES ($1, $2, $3, $4, NULL, 0)
                    """,
                        outbox_id,
                        event_id,
                        "event_bus",
                        json.dumps(payload),
                    )

    await conn.close()


if __name__ == "__main__":
    asyncio.run(load_seed_events())
    print("Seed events loaded into the database.")
