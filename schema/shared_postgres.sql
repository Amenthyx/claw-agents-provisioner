-- =============================================================================
-- XClaw Shared Database Schema (PostgreSQL)
-- =============================================================================
-- Cross-instance shared database for multi-claw deployments.
-- PostgreSQL variant with JSONB, INET, TIMESTAMP, UUIDs, full-text search,
-- and partitioning support for high-volume tables.
--
-- Created by Mauro Tommasi — linkedin.com/in/maurotommasi
-- Apache 2.0 (c) 2026 Amenthyx
-- =============================================================================

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Agent Registry ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    platform      TEXT NOT NULL,
    host          TEXT DEFAULT 'localhost',
    port          INTEGER DEFAULT 0,
    version       TEXT,
    status        TEXT DEFAULT 'unknown' CHECK (status IN ('running','stopped','error','unknown','deploying','healthy','unhealthy','degraded')),
    health        JSONB DEFAULT '{}',
    capabilities  JSONB DEFAULT '[]',
    config_hash   TEXT,
    last_seen     TIMESTAMP DEFAULT NOW(),
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_agents_status   ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_platform ON agents(platform);

-- ─── Shared Memory / Context ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shared_memory (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    from_agent_id   TEXT NOT NULL REFERENCES agents(id),
    to_agent_id     TEXT,
    conversation_id TEXT,
    memory_type     TEXT DEFAULT 'context' CHECK (memory_type IN ('context','fact','preference','instruction')),
    key             TEXT,
    content         TEXT NOT NULL,
    priority        INTEGER DEFAULT 0,
    ttl_seconds     INTEGER,
    expires_at      TIMESTAMP,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_smem_from    ON shared_memory(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_smem_to      ON shared_memory(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_smem_type    ON shared_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_smem_key     ON shared_memory(key);
CREATE INDEX IF NOT EXISTS idx_smem_expires ON shared_memory(expires_at);

-- Full-text search on shared memory content
CREATE INDEX IF NOT EXISTS idx_smem_fts ON shared_memory USING gin(to_tsvector('english', COALESCE(content, '')));

-- ─── Cost Tracking ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cost_tracking (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    model           TEXT NOT NULL,
    provider        TEXT NOT NULL,
    endpoint        TEXT,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    cost_usd        DOUBLE PRECISION DEFAULT 0.0,
    cache_savings   DOUBLE PRECISION DEFAULT 0.0,
    request_count   INTEGER DEFAULT 1,
    error_count     INTEGER DEFAULT 0,
    avg_latency_ms  DOUBLE PRECISION DEFAULT 0.0,
    timestamp       TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cost_agent    ON cost_tracking(agent_id);
CREATE INDEX IF NOT EXISTS idx_cost_model    ON cost_tracking(model);
CREATE INDEX IF NOT EXISTS idx_cost_provider ON cost_tracking(provider);
CREATE INDEX IF NOT EXISTS idx_cost_ts       ON cost_tracking(timestamp);

-- ─── Cost Budgets & Alerts ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cost_budgets (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    scope           TEXT NOT NULL,
    period          TEXT NOT NULL CHECK (period IN ('daily','weekly','monthly')),
    budget_usd      DOUBLE PRECISION NOT NULL,
    current_spend   DOUBLE PRECISION DEFAULT 0.0,
    alert_threshold DOUBLE PRECISION DEFAULT 0.8,
    action_on_limit TEXT DEFAULT 'alert' CHECK (action_on_limit IN ('alert','throttle','block')),
    reset_at        TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ─── Security Events ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS security_events (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    event_type      TEXT NOT NULL,
    severity        TEXT DEFAULT 'info' CHECK (severity IN ('debug','info','warn','error','critical')),
    category        TEXT,
    source_ip       INET,
    user_id         TEXT,
    rule_id         TEXT,
    details         JSONB,
    action_taken    TEXT,
    resolved        BOOLEAN DEFAULT FALSE,
    resolved_by     TEXT,
    resolved_at     TIMESTAMP,
    timestamp       TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sec_agent    ON security_events(agent_id);
CREATE INDEX IF NOT EXISTS idx_sec_type     ON security_events(event_type);
CREATE INDEX IF NOT EXISTS idx_sec_severity ON security_events(severity);
CREATE INDEX IF NOT EXISTS idx_sec_ts       ON security_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_sec_resolved ON security_events(resolved);

-- ─── RBAC Roles ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS rbac_roles (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT,
    permissions   JSONB DEFAULT '{}',
    is_builtin    BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rbac_assignments (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    agent_id      TEXT NOT NULL REFERENCES agents(id),
    role_id       TEXT NOT NULL REFERENCES rbac_roles(id),
    scope         TEXT DEFAULT '*',
    assigned_at   TIMESTAMP DEFAULT NOW(),
    assigned_by   TEXT DEFAULT 'system',
    expires_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rbac_agent ON rbac_assignments(agent_id);
CREATE INDEX IF NOT EXISTS idx_rbac_role  ON rbac_assignments(role_id);

-- ─── Audit Trail ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id            SERIAL PRIMARY KEY,
    actor         TEXT NOT NULL,
    action        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   TEXT,
    old_value     JSONB,
    new_value     JSONB,
    ip_address    INET,
    user_agent    TEXT,
    success       BOOLEAN DEFAULT TRUE,
    error         TEXT,
    timestamp     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_actor    ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_action   ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts       ON audit_log(timestamp);

-- ─── Cluster Configuration ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cluster_config (
    key           TEXT PRIMARY KEY,
    value         TEXT,
    category      TEXT DEFAULT 'general',
    description   TEXT,
    encrypted     BOOLEAN DEFAULT FALSE,
    updated_at    TIMESTAMP DEFAULT NOW(),
    updated_by    TEXT DEFAULT 'system'
);

-- ─── Alert Channels & Notifications ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_channels (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    channel_type  TEXT NOT NULL,
    name          TEXT NOT NULL,
    config        JSONB DEFAULT '{}',
    enabled       BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alert_history (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    channel_id    TEXT REFERENCES alert_channels(id),
    trigger_id    TEXT,
    severity      TEXT DEFAULT 'info',
    title         TEXT NOT NULL,
    message       TEXT,
    delivered     BOOLEAN DEFAULT FALSE,
    delivery_error TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alert_channel ON alert_history(channel_id);
CREATE INDEX IF NOT EXISTS idx_alert_ts      ON alert_history(created_at);

-- ─── Triggers / Automation Rules ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS triggers (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    name          TEXT NOT NULL,
    description   TEXT,
    condition     JSONB NOT NULL,
    action        JSONB NOT NULL,
    cooldown_sec  INTEGER DEFAULT 300,
    enabled       BOOLEAN DEFAULT TRUE,
    last_fired    TIMESTAMP,
    fire_count    INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ─── Deployment History ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deployments (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    agent_id        TEXT REFERENCES agents(id),
    agent_name      TEXT NOT NULL,
    platform        TEXT NOT NULL,
    deployment_method TEXT NOT NULL,
    config_snapshot JSONB,
    image_tag       TEXT,
    container_id    TEXT,
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','building','deploying','running','failed','stopped')),
    error           TEXT,
    started_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP,
    stopped_at      TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_deploy_agent  ON deployments(agent_id);
CREATE INDEX IF NOT EXISTS idx_deploy_status ON deployments(status);

-- ─── Compliance Records ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compliance_records (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    framework       TEXT NOT NULL,
    rule_id         TEXT NOT NULL,
    status          TEXT DEFAULT 'acknowledged' CHECK (status IN ('acknowledged','implemented','verified','failed')),
    evidence        JSONB,
    verified_by     TEXT,
    verified_at     TIMESTAMP,
    next_review     TIMESTAMP,
    notes           TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comp_framework ON compliance_records(framework);
CREATE INDEX IF NOT EXISTS idx_comp_status    ON compliance_records(status);

-- ─── Data Retention Policies ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS retention_policies (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    resource_type   TEXT NOT NULL,
    retention_days  INTEGER NOT NULL,
    action          TEXT DEFAULT 'delete' CHECK (action IN ('delete','archive','anonymize')),
    enabled         BOOLEAN DEFAULT TRUE,
    last_executed   TIMESTAMP,
    records_affected INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- ─── Schema Migrations ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version       INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    applied_at    TIMESTAMP DEFAULT NOW()
);
INSERT INTO schema_migrations (version, name) VALUES (1, 'initial_enterprise_schema')
ON CONFLICT (version) DO NOTHING;

-- ─── Materialized Views for Analytics ────────────────────────────────────────

-- Daily cost summary per agent/model
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_costs AS
SELECT
    date_trunc('day', timestamp) AS day,
    agent_id,
    model,
    provider,
    SUM(input_tokens)  AS total_input_tokens,
    SUM(output_tokens) AS total_output_tokens,
    SUM(cost_usd)      AS total_cost,
    SUM(request_count)  AS total_requests,
    AVG(avg_latency_ms) AS avg_latency
FROM cost_tracking
GROUP BY day, agent_id, model, provider;

-- Security event summary
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_security_summary AS
SELECT
    date_trunc('day', timestamp) AS day,
    agent_id,
    event_type,
    severity,
    COUNT(*) AS event_count
FROM security_events
GROUP BY day, agent_id, event_type, severity;
