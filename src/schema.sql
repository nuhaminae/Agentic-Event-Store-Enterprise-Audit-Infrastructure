-- src/schema.sql
-- Enterprise Event Store & Audit Infrastructure
-- To load test: psql -U postgres -d ledger_seed -f src/schema.sql

-- Event Streams: one row per aggregate stream
CREATE TABLE event_streams ( 
    stream_id        TEXT PRIMARY KEY,                      -- unique identifier
    aggregate_type   TEXT NOT NULL,                         -- domain entity
    current_version  BIGINT NOT NULL DEFAULT 0,             -- for optimistic concurrency
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),    -- for audit
    archived_at      TIMESTAMPTZ,                           -- for lifecycle
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb     -- for custom metadata
); 

-- Events: immutable append-only log
CREATE TABLE events ( 
    event_id UUID    PRIMARY KEY DEFAULT gen_random_uuid(),                     -- unique
    stream_id        TEXT NOT NULL,                                             -- links to stream
    stream_position  BIGINT NOT NULL,                                           -- position in stream
    global_position  BIGINT GENERATED ALWAYS AS IDENTITY,                       -- position in all events
    event_type       TEXT NOT NULL,                                             -- domain event
    event_version    SMALLINT NOT NULL DEFAULT 1,                               -- payload version
    payload          JSONB NOT NULL,                                            -- actual eventdata
    metadata         JSONB NOT NULL DEFAULT '{}'::jsonb,                        -- event metadata
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),            -- for audit
    correlation_id   TEXT,                                                      -- for correlation
    causation_id     TEXT,                                                      -- for causation
    CONSTRAINT       uq_stream_position UNIQUE (stream_id, stream_position)     -- for optimistic concurrency
); 

-- Outbox: reliable publishing of events
CREATE TABLE outbox ( 
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),        
    event_id         UUID NOT NULL REFERENCES events(event_id),         -- links to event
    destination      TEXT NOT NULL,                                     -- queue name
    payload          JSONB NOT NULL,                                    -- actual eventdata
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),                -- for audit
    published_at     TIMESTAMPTZ,                                       -- for audit
    attempts         SMALLINT NOT NULL DEFAULT 0,                       -- for retry
    status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','published','failed'))

); 

-- Projection Checkpoints: track replay progress
CREATE TABLE projection_checkpoints ( 
    checkpoint_id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),     -- unique identifier
    projection_name                 TEXT NOT NULL,                                  -- projection name
    stream_id                       TEXT,                                           -- optional, if per-stream
    last_position                   BIGINT NOT NULL DEFAULT 0,                      -- checkpoint
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),             -- checkpoint
    projection_version              INT NOT NULL DEFAULT 1,                         -- versioning for evolving projections
    checkpoint_metadata             JSONB NOT NULL DEFAULT '{}'::jsonb,             -- extra attributes
    CONSTRAINT                      uq_projection UNIQUE (projection_name, stream_id)

); 

-- Indexes for performance
CREATE INDEX idx_events_stream_id ON events (stream_id, stream_position);       -- for optimistic concurrency
CREATE INDEX idx_events_global_pos ON events (global_position);                 -- for replay
CREATE INDEX idx_events_type ON events (event_type);                            -- for replay
CREATE INDEX idx_events_recorded ON events (recorded_at);                       -- for audit 
