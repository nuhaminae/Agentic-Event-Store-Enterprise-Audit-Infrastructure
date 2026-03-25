# src/integrity/audit_chain.py
# Read-only cryptographic hash chain verification

import hashlib
import json
import logging

import asyncpg


async def run_integrity_check(dsn):
    """
    Verify continuity of the cryptographic hash chain across all events.
    Detects tampering by comparing each event's stored prev_hash with the
    recomputed hash of the previous event. Logs tampering but does not mutate DB.
    """
    conn = await asyncpg.connect(dsn)
    rows = await conn.fetch("SELECT * FROM events ORDER BY global_position ASC")

    prev_hash = None
    tampered = False

    for row in rows:
        # Normalize payload for deterministic hashing
        payload_str = json.dumps(row["payload"], sort_keys=True)
        record = f"{row['event_id']}{row['stream_id']}{row['stream_position']}{row['event_type']}{payload_str}{row['recorded_at']}"
        h = hashlib.sha256(record.encode()).hexdigest()

        # Parse metadata safely
        metadata = row["metadata"]
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        elif metadata is None:
            metadata = {}

        prev_in_db = metadata.get("prev_hash")
        if prev_hash and prev_in_db != prev_hash:
            logging.error(
                f"Tampering detected at global_position={row['global_position']}"
            )
            tampered = True

        prev_hash = h

    if not tampered:
        logging.info("Integrity check passed: no tampering detected")

    await conn.close()
    return not tampered
