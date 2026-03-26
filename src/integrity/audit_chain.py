# src/integrity/audit_chain.py
# Read-only cryptographic hash chain verification
import json
import logging

import asyncpg


async def run_integrity_check(dsn):
    """
    Verify continuity of the cryptographic hash chain per stream.
    Detects tampering by comparing each event's stored prev_hash with the
    stored event_hash of the previous event in the same stream.
    """
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch(
        "SELECT * FROM events ORDER BY stream_id, stream_position ASC"
    )

    tampered = False
    prev_hash_by_stream = {}

    for row in rows:
        # Parse metadata safely
        metadata = row["metadata"]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        elif metadata is None:
            metadata = {}

        event_hash = metadata.get("event_hash")
        prev_in_db = metadata.get("prev_hash")
        stream_id = row["stream_id"]

        # Check continuity within the same stream
        prev_hash = prev_hash_by_stream.get(stream_id)
        if prev_hash and prev_in_db != prev_hash:
            logging.error(
                f"Tampering detected in stream={stream_id} at global_position={row['global_position']}"
            )
            tampered = True

        # Update chain state for this stream
        prev_hash_by_stream[stream_id] = event_hash

    if not tampered:
        logging.info("Integrity check passed: no tampering detected")

    await conn.close()
    return {"integrity_passed": not tampered}
