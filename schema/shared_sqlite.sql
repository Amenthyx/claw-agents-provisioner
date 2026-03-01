-- =============================================================================
-- XClaw Shared Database Schema (SQLite)
-- =============================================================================
-- Cross-instance shared database for multi-claw deployments.
-- Covers: agent registry, cost analytics, shared memory, security events,
--         RBAC, cluster config, audit trail, alerting, and billing.
--
-- Created by Mauro Tommasi — linkedin.com/in/maurotommasi
-- Apache 2.0 (c) 2026 Amenthyx
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─── Agent Registry ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agents (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    platform      TEXT NOT NULL,         -- zeroclaw, nanoclaw, picoclaw, openclaw, parlant
    host          TEXT DEFAULT 'localhost',
    port          INTEGER DEFAULT 0,
    version       TEXT,
    status        TEXT DEFAULT 'unknown' CHECK (status IN ('running','stopped','error','unknown','deploying','healthy','unhealthy','degraded')),
    health        TEXT DEFAULT '{}',     -- JSON: last health check result
    capabilities  TEXT DEFAULT '[]',     -- JSON: list of supported features
    config_hash   TEXT,                  -- SHA-256 of deployment config
    last_seen     TEXT DEFAULT (datetime('now')),
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_agents_status   ON agents(status);
CREATE INDEX IF NOT EXISTS idx_agents_platform ON agents(platform);

-- ─── Shared Memory / Context ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS shared_memory (
    id              TEXT PRIMARY KEY,
    from_agent_id   TEXT NOT NULL REFERENCES agents(id),
    to_agent_id     TEXT,                -- NULL = broadcast to all
    conversation_id TEXT,
    memory_type     TEXT DEFAULT 'context' CHECK (memory_type IN ('context','fact','preference','instruction')),
    key             TEXT,                -- searchable key for retrieval
    content         TEXT NOT NULL,
    priority        INTEGER DEFAULT 0,   -- higher = more important
    ttl_seconds     INTEGER,             -- NULL = never expires
    expires_at      TEXT,
    metadata        TEXT DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_smem_from    ON shared_memory(from_agent_id);
CREATE INDEX IF NOT EXISTS idx_smem_to      ON shared_memory(to_agent_id);
CREATE INDEX IF NOT EXISTS idx_smem_type    ON shared_memory(memory_type);
CREATE INDEX IF NOT EXISTS idx_smem_key     ON shared_memory(key);
CREATE INDEX IF NOT EXISTS idx_smem_expires ON shared_memory(expires_at);

-- ─── Cost Tracking ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cost_tracking (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    model           TEXT NOT NULL,
    provider        TEXT NOT NULL,
    endpoint        TEXT,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    cache_savings   REAL DEFAULT 0.0,    -- cost saved by cache hits
    request_count   INTEGER DEFAULT 1,
    error_count     INTEGER DEFAULT 0,
    avg_latency_ms  REAL DEFAULT 0.0,
    timestamp       TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cost_agent    ON cost_tracking(agent_id);
CREATE INDEX IF NOT EXISTS idx_cost_model    ON cost_tracking(model);
CREATE INDEX IF NOT EXISTS idx_cost_provider ON cost_tracking(provider);
CREATE INDEX IF NOT EXISTS idx_cost_ts       ON cost_tracking(timestamp);

-- ─── Cost Budgets & Alerts ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS cost_budgets (
    id              TEXT PRIMARY KEY,
    scope           TEXT NOT NULL,        -- 'global', agent_id, or model name
    period          TEXT NOT NULL CHECK (period IN ('daily','weekly','monthly')),
    budget_usd      REAL NOT NULL,
    current_spend   REAL DEFAULT 0.0,
    alert_threshold REAL DEFAULT 0.8,     -- alert at 80% by default
    action_on_limit TEXT DEFAULT 'alert'  CHECK (action_on_limit IN ('alert','throttle','block')),
    reset_at        TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ─── Security Events ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS security_events (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT NOT NULL REFERENCES agents(id),
    event_type      TEXT NOT NULL,        -- url_blocked, pii_detected, injection_attempt, auth_failure, rate_limited
    severity        TEXT DEFAULT 'info'   CHECK (severity IN ('debug','info','warn','error','critical')),
    category        TEXT,                 -- filtering, compliance, access, network
    source_ip       TEXT,
    user_id         TEXT,
    rule_id         TEXT,                 -- which security rule triggered
    details         TEXT,                 -- JSON: full event details
    action_taken    TEXT,                 -- blocked, redacted, logged, alerted
    resolved        INTEGER DEFAULT 0,
    resolved_by     TEXT,
    resolved_at     TEXT,
    timestamp       TEXT DEFAULT (datetime('now'))
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
    permissions   TEXT DEFAULT '{}',     -- JSON: {resource: [actions]}
    is_builtin    INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rbac_assignments (
    id            TEXT PRIMARY KEY,
    agent_id      TEXT NOT NULL REFERENCES agents(id),
    role_id       TEXT NOT NULL REFERENCES rbac_roles(id),
    scope         TEXT DEFAULT '*',      -- resource scope limitation
    assigned_at   TEXT DEFAULT (datetime('now')),
    assigned_by   TEXT DEFAULT 'system',
    expires_at    TEXT                   -- NULL = permanent
);
CREATE INDEX IF NOT EXISTS idx_rbac_agent ON rbac_assignments(agent_id);
CREATE INDEX IF NOT EXISTS idx_rbac_role  ON rbac_assignments(role_id);

-- ─── Audit Trail ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    actor         TEXT NOT NULL,          -- agent_id, user_id, or 'system'
    action        TEXT NOT NULL,          -- create, read, update, delete, login, deploy, config_change
    resource_type TEXT NOT NULL,          -- agent, conversation, config, rbac, security_rule
    resource_id   TEXT,
    old_value     TEXT,                   -- JSON: previous state (for updates/deletes)
    new_value     TEXT,                   -- JSON: new state
    ip_address    TEXT,
    user_agent    TEXT,
    success       INTEGER DEFAULT 1,
    error         TEXT,
    timestamp     TEXT DEFAULT (datetime('now'))
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
    encrypted     INTEGER DEFAULT 0,     -- 1 = value is encrypted
    updated_at    TEXT DEFAULT (datetime('now')),
    updated_by    TEXT DEFAULT 'system'
);

-- ─── Alert Channels & Notifications ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_channels (
    id            TEXT PRIMARY KEY,
    channel_type  TEXT NOT NULL,          -- telegram, slack, discord, email, webhook
    name          TEXT NOT NULL,
    config        TEXT DEFAULT '{}',      -- JSON: channel-specific config
    enabled       INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alert_history (
    id            TEXT PRIMARY KEY,
    channel_id    TEXT REFERENCES alert_channels(id),
    trigger_id    TEXT,
    severity      TEXT DEFAULT 'info',
    title         TEXT NOT NULL,
    message       TEXT,
    delivered     INTEGER DEFAULT 0,
    delivery_error TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alert_channel ON alert_history(channel_id);
CREATE INDEX IF NOT EXISTS idx_alert_ts      ON alert_history(created_at);

-- ─── Triggers / Automation Rules ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS triggers (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT,
    condition     TEXT NOT NULL,          -- JSON: {type, metric, operator, threshold}
    action        TEXT NOT NULL,          -- JSON: {type, channel, template}
    cooldown_sec  INTEGER DEFAULT 300,
    enabled       INTEGER DEFAULT 1,
    last_fired    TEXT,
    fire_count    INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

-- ─── Deployment History ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deployments (
    id              TEXT PRIMARY KEY,
    agent_id        TEXT REFERENCES agents(id),
    agent_name      TEXT NOT NULL,
    platform        TEXT NOT NULL,
    deployment_method TEXT NOT NULL,      -- docker, vagrant, ssh, local
    config_snapshot TEXT,                 -- JSON: full assessment config at deploy time
    image_tag       TEXT,
    container_id    TEXT,
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','building','deploying','running','failed','stopped')),
    error           TEXT,
    started_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT,
    stopped_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_deploy_agent  ON deployments(agent_id);
CREATE INDEX IF NOT EXISTS idx_deploy_status ON deployments(status);

-- ─── Compliance Records ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compliance_records (
    id              TEXT PRIMARY KEY,
    framework       TEXT NOT NULL,        -- gdpr, hipaa, pci-dss, soc2
    rule_id         TEXT NOT NULL,        -- gdpr-1, hipaa-3, etc.
    status          TEXT DEFAULT 'acknowledged' CHECK (status IN ('acknowledged','implemented','verified','failed')),
    evidence        TEXT,                 -- JSON: proof of compliance
    verified_by     TEXT,
    verified_at     TEXT,
    next_review     TEXT,
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_comp_framework ON compliance_records(framework);
CREATE INDEX IF NOT EXISTS idx_comp_status    ON compliance_records(status);

-- ─── Data Retention Policies ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS retention_policies (
    id              TEXT PRIMARY KEY,
    resource_type   TEXT NOT NULL,        -- conversations, messages, logs, security_events
    retention_days  INTEGER NOT NULL,
    action          TEXT DEFAULT 'delete' CHECK (action IN ('delete','archive','anonymize')),
    enabled         INTEGER DEFAULT 1,
    last_executed   TEXT,
    records_affected INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ─── Schema Migrations ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version       INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    applied_at    TEXT DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (1, 'initial_enterprise_schema');
