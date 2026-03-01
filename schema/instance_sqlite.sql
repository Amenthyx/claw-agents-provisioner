-- =============================================================================
-- XClaw Instance Database Schema (SQLite)
-- =============================================================================
-- Per-instance database for a single XClaw deployment.
-- Covers: conversations, LLM I/O tracking, local config, logs, cache,
--         knowledge base, embeddings, and performance metrics.
--
-- Created by Mauro Tommasi — linkedin.com/in/maurotommasi
-- Apache 2.0 (c) 2026 Amenthyx
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─── Local Configuration ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS local_config (
    key           TEXT PRIMARY KEY,
    value         TEXT,
    category      TEXT DEFAULT 'general',
    description   TEXT,
    updated_at    TEXT DEFAULT (datetime('now')),
    updated_by    TEXT DEFAULT 'system'
);

-- ─── System Logs ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS local_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    level         TEXT DEFAULT 'info'  CHECK (level IN ('debug','info','warn','error','critical')),
    message       TEXT NOT NULL,
    source        TEXT DEFAULT 'system',
    component     TEXT,                 -- agent, router, optimizer, watchdog, security
    trace_id      TEXT,                 -- correlation ID for request tracing
    metadata      TEXT DEFAULT '{}',    -- JSON extra data
    timestamp     TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_logs_level     ON local_logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_component ON local_logs(component);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON local_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_trace_id  ON local_logs(trace_id);

-- ─── Conversations ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    channel       TEXT,                 -- telegram, discord, slack, api, web
    user_id       TEXT,
    status        TEXT DEFAULT 'active' CHECK (status IN ('active','archived','deleted')),
    model         TEXT,                 -- model used for this conversation
    system_prompt TEXT,
    total_tokens  INTEGER DEFAULT 0,
    total_cost    REAL DEFAULT 0.0,
    message_count INTEGER DEFAULT 0,
    metadata      TEXT DEFAULT '{}',
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel);
CREATE INDEX IF NOT EXISTS idx_conv_user    ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_status  ON conversations(status);

-- ─── Messages ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('system','user','assistant','tool','function')),
    content         TEXT,
    model           TEXT,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    latency_ms      REAL DEFAULT 0.0,
    finish_reason   TEXT,               -- stop, length, tool_calls, content_filter
    tool_calls      TEXT,               -- JSON: [{name, arguments, result}]
    metadata        TEXT DEFAULT '{}',
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_msg_conv      ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msg_role      ON messages(role);
CREATE INDEX IF NOT EXISTS idx_msg_created   ON messages(created_at);

-- ─── LLM Request/Response Log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_requests (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES conversations(id),
    message_id      TEXT REFERENCES messages(id),
    provider        TEXT NOT NULL,       -- openai, anthropic, deepseek, groq, local
    model           TEXT NOT NULL,
    endpoint        TEXT,                -- full URL or local endpoint
    request_body    TEXT,                -- sanitized request JSON (no API keys)
    response_body   TEXT,                -- raw response JSON
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0.0,
    latency_ms      REAL DEFAULT 0.0,
    status_code     INTEGER,
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    cache_hit       INTEGER DEFAULT 0,   -- 1 = served from cache
    routed_via      TEXT,                -- gateway, direct, failover
    trace_id        TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_llm_provider  ON llm_requests(provider);
CREATE INDEX IF NOT EXISTS idx_llm_model     ON llm_requests(model);
CREATE INDEX IF NOT EXISTS idx_llm_created   ON llm_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_trace     ON llm_requests(trace_id);

-- ─── Response Cache ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS response_cache (
    hash          TEXT PRIMARY KEY,      -- SHA-256 of (model + prompt)
    model         TEXT NOT NULL,
    prompt_hash   TEXT NOT NULL,
    response      TEXT NOT NULL,
    tokens_saved  INTEGER DEFAULT 0,
    cost_saved    REAL DEFAULT 0.0,
    hit_count     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now')),
    last_hit_at   TEXT DEFAULT (datetime('now')),
    expires_at    TEXT                   -- NULL = never expires
);
CREATE INDEX IF NOT EXISTS idx_cache_model   ON response_cache(model);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON response_cache(expires_at);

-- ─── Knowledge Base ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    source        TEXT,                  -- file path, URL, or manual
    content       TEXT NOT NULL,
    content_type  TEXT DEFAULT 'text',   -- text, markdown, code, pdf
    chunk_count   INTEGER DEFAULT 0,
    token_count   INTEGER DEFAULT 0,
    metadata      TEXT DEFAULT '{}',
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id            TEXT PRIMARY KEY,
    document_id   TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    token_count   INTEGER DEFAULT 0,
    embedding     BLOB,                  -- serialized float32 vector
    metadata      TEXT DEFAULT '{}',
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON knowledge_chunks(document_id);

-- ─── Tool / Function Registry ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tools (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT,
    parameters    TEXT DEFAULT '{}',     -- JSON Schema
    handler       TEXT,                  -- module.function path
    enabled       INTEGER DEFAULT 1,
    call_count    INTEGER DEFAULT 0,
    avg_latency   REAL DEFAULT 0.0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id            TEXT PRIMARY KEY,
    tool_id       TEXT NOT NULL REFERENCES tools(id),
    message_id    TEXT REFERENCES messages(id),
    arguments     TEXT,                  -- JSON
    result        TEXT,
    success       INTEGER DEFAULT 1,
    latency_ms    REAL DEFAULT 0.0,
    error         TEXT,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tc_tool    ON tool_calls(tool_id);
CREATE INDEX IF NOT EXISTS idx_tc_created ON tool_calls(created_at);

-- ─── User / Session Management ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    external_id   TEXT,                  -- channel-specific user ID
    channel       TEXT,
    display_name  TEXT,
    role          TEXT DEFAULT 'user',
    preferences   TEXT DEFAULT '{}',     -- JSON user preferences
    consent_given INTEGER DEFAULT 0,     -- GDPR consent flag
    consent_at    TEXT,
    total_messages INTEGER DEFAULT 0,
    last_active   TEXT DEFAULT (datetime('now')),
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_ext     ON users(external_id, channel);
CREATE INDEX IF NOT EXISTS idx_users_channel ON users(channel);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY,
    user_id         TEXT REFERENCES users(id),
    conversation_id TEXT REFERENCES conversations(id),
    channel         TEXT,
    ip_address      TEXT,
    user_agent      TEXT,
    started_at      TEXT DEFAULT (datetime('now')),
    ended_at        TEXT,
    metadata        TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sess_user ON sessions(user_id);

-- ─── Performance Metrics (per-minute aggregates) ─────────────────────────────
CREATE TABLE IF NOT EXISTS performance_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name     TEXT NOT NULL,       -- requests_total, latency_p95, tokens_per_sec, etc.
    metric_value    REAL NOT NULL,
    component       TEXT,                -- agent, router, optimizer, gateway
    tags            TEXT DEFAULT '{}',   -- JSON: {model, provider, ...}
    timestamp       TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_perf_name ON performance_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_perf_ts   ON performance_metrics(timestamp);

-- ─── Scheduled Tasks / Cron ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    cron_expr     TEXT,                  -- cron expression or interval
    handler       TEXT NOT NULL,         -- module.function path
    params        TEXT DEFAULT '{}',
    enabled       INTEGER DEFAULT 1,
    last_run      TEXT,
    next_run      TEXT,
    run_count     INTEGER DEFAULT 0,
    last_status   TEXT DEFAULT 'pending',
    created_at    TEXT DEFAULT (datetime('now'))
);

-- ─── Orchestrator Tasks ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    priority        INTEGER DEFAULT 3,
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed','cancelled')),
    assigned_agent  TEXT,
    result          TEXT,
    pipeline_id     TEXT,
    pipeline_step   INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    started_at      TEXT,
    completed_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_tasks_pipeline ON tasks(pipeline_id);

-- ─── Orchestrator Pipelines ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipelines (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    definition      TEXT NOT NULL DEFAULT '[]',
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed')),
    current_step    INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    completed_at    TEXT
);

-- ─── Migrations Tracking ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version       INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    applied_at    TEXT DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (1, 'initial_enterprise_schema');
INSERT OR IGNORE INTO schema_migrations (version, name) VALUES (2, 'add_orchestrator_tables');
