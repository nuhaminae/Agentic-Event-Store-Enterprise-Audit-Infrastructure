-- src/projection_schema.sql
-- Projection tables for CQRS read models
-- These tables are populated by the ProjectionDaemon based on domain events.
-- To load into ledger_app: psql -U postgres -d ledger_app -f src/projection_schema.sql

-- ApplicationSummary: one row per loan application
-- Keys: application_id is unique per application
CREATE TABLE application_summary (
    application_id   TEXT PRIMARY KEY,                  -- stable identifier for the application
    applicant_id     TEXT,                              -- from ApplicationSubmittedPayload
    status           TEXT,                              -- e.g. submitted, approved, rejected
    amount           NUMERIC,                           -- requested or approved amount
    submitted_at     TIMESTAMPTZ,                       -- when application was submitted
    decided_at       TIMESTAMPTZ                        -- when decision was generated
);

-- AgentPerformanceLedger: metrics per agent per model version
-- Keys: (agent_id, model_version) uniquely identify performance metrics
CREATE TABLE agent_performance (
    agent_id         TEXT NOT NULL,                     -- stable identifier for the agent
    model_version    TEXT NOT NULL,                     -- version of the credit analysis model
    sessions         BIGINT NOT NULL DEFAULT 0,         -- number of sessions handled
    decisions        BIGINT NOT NULL DEFAULT 0,         -- number of decisions made
    PRIMARY KEY (agent_id, model_version)
);

-- ComplianceAuditView: temporal audit log of compliance checks
-- Keys: (compliance_id, event_type, recorded_at) uniquely identify each compliance event
CREATE TABLE compliance_audit (
    compliance_id    TEXT NOT NULL,                     -- stable identifier for compliance check
    event_type       TEXT NOT NULL,                     -- type of compliance event
    payload          JSONB NOT NULL,                    -- full event payload for audit
    recorded_at      TIMESTAMPTZ NOT NULL,              -- when the event was recorded
    PRIMARY KEY (compliance_id, event_type, recorded_at)
);

-- Indexes for query performance
CREATE INDEX idx_app_summary_status ON application_summary (status);
CREATE INDEX idx_agent_perf_model ON agent_performance (model_version);
CREATE INDEX idx_compliance_audit_time ON compliance_audit (recorded_at);
