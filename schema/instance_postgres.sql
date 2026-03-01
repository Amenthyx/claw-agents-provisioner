-- =============================================================================
-- XClaw Instance Database Schema (PostgreSQL)
-- =============================================================================
-- Per-instance database for a single XClaw deployment.
-- PostgreSQL variant with proper types, JSONB, TIMESTAMP, SERIAL, and
-- full-text search support.
--
-- Created by Mauro Tommasi — linkedin.com/in/maurotommasi
-- Apache 2.0 (c) 2026 Amenthyx
-- =============================================================================

-- ─── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─── Local Configuration ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS local_config (
    key           TEXT PRIMARY KEY,
    value         TEXT,
    category      TEXT DEFAULT 'general',
    description   TEXT,
    updated_at    TIMESTAMP DEFAULT NOW(),
    updated_by    TEXT DEFAULT 'system'
);

-- ─── System Logs ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS local_logs (
    id            SERIAL PRIMARY KEY,
    level         TEXT DEFAULT 'info' CHECK (level IN ('debug','info','warn','error','critical')),
    message       TEXT NOT NULL,
    source        TEXT DEFAULT 'system',
    component     TEXT,
    trace_id      TEXT,
    metadata      JSONB DEFAULT '{}',
    timestamp     TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_logs_level     ON local_logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_component ON local_logs(component);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON local_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_trace_id  ON local_logs(trace_id);

-- ─── Conversations ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    title         TEXT,
    channel       TEXT,
    user_id       TEXT,
    status        TEXT DEFAULT 'active' CHECK (status IN ('active','archived','deleted')),
    model         TEXT,
    system_prompt TEXT,
    total_tokens  INTEGER DEFAULT 0,
    total_cost    DOUBLE PRECISION DEFAULT 0.0,
    message_count INTEGER DEFAULT 0,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conv_channel ON conversations(channel);
CREATE INDEX IF NOT EXISTS idx_conv_user    ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_status  ON conversations(status);

-- ─── Messages ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('system','user','assistant','tool','function')),
    content         TEXT,
    model           TEXT,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    cost_usd        DOUBLE PRECISION DEFAULT 0.0,
    latency_ms      DOUBLE PRECISION DEFAULT 0.0,
    finish_reason   TEXT,
    tool_calls      JSONB,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_msg_conv    ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_msg_role    ON messages(role);
CREATE INDEX IF NOT EXISTS idx_msg_created ON messages(created_at);

-- Full-text search on message content
CREATE INDEX IF NOT EXISTS idx_msg_content_fts ON messages USING gin(to_tsvector('english', COALESCE(content, '')));

-- ─── LLM Request/Response Log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_requests (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    conversation_id TEXT REFERENCES conversations(id),
    message_id      TEXT REFERENCES messages(id),
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    endpoint        TEXT,
    request_body    JSONB,
    response_body   JSONB,
    input_tokens    INTEGER DEFAULT 0,
    output_tokens   INTEGER DEFAULT 0,
    total_tokens    INTEGER DEFAULT 0,
    cost_usd        DOUBLE PRECISION DEFAULT 0.0,
    latency_ms      DOUBLE PRECISION DEFAULT 0.0,
    status_code     INTEGER,
    error           TEXT,
    retry_count     INTEGER DEFAULT 0,
    cache_hit       BOOLEAN DEFAULT FALSE,
    routed_via      TEXT,
    trace_id        TEXT,
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_llm_provider ON llm_requests(provider);
CREATE INDEX IF NOT EXISTS idx_llm_model    ON llm_requests(model);
CREATE INDEX IF NOT EXISTS idx_llm_created  ON llm_requests(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_trace    ON llm_requests(trace_id);

-- ─── Response Cache ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS response_cache (
    hash          TEXT PRIMARY KEY,
    model         TEXT NOT NULL,
    prompt_hash   TEXT NOT NULL,
    response      TEXT NOT NULL,
    tokens_saved  INTEGER DEFAULT 0,
    cost_saved    DOUBLE PRECISION DEFAULT 0.0,
    hit_count     INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT NOW(),
    last_hit_at   TIMESTAMP DEFAULT NOW(),
    expires_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cache_model   ON response_cache(model);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON response_cache(expires_at);

-- ─── Knowledge Base ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    title         TEXT NOT NULL,
    source        TEXT,
    content       TEXT NOT NULL,
    content_type  TEXT DEFAULT 'text',
    chunk_count   INTEGER DEFAULT 0,
    token_count   INTEGER DEFAULT 0,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    document_id   TEXT NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    content       TEXT NOT NULL,
    token_count   INTEGER DEFAULT 0,
    embedding     BYTEA,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON knowledge_chunks(document_id);

-- Full-text search on knowledge
CREATE INDEX IF NOT EXISTS idx_kdoc_fts ON knowledge_documents USING gin(to_tsvector('english', title || ' ' || content));

-- ─── Tool / Function Registry ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tools (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT,
    parameters    JSONB DEFAULT '{}',
    handler       TEXT,
    enabled       BOOLEAN DEFAULT TRUE,
    call_count    INTEGER DEFAULT 0,
    avg_latency   DOUBLE PRECISION DEFAULT 0.0,
    created_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    tool_id       TEXT NOT NULL REFERENCES tools(id),
    message_id    TEXT REFERENCES messages(id),
    arguments     JSONB,
    result        TEXT,
    success       BOOLEAN DEFAULT TRUE,
    latency_ms    DOUBLE PRECISION DEFAULT 0.0,
    error         TEXT,
    created_at    TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tc_tool    ON tool_calls(tool_id);
CREATE INDEX IF NOT EXISTS idx_tc_created ON tool_calls(created_at);

-- ─── User / Session Management ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    external_id   TEXT,
    channel       TEXT,
    display_name  TEXT,
    role          TEXT DEFAULT 'user',
    preferences   JSONB DEFAULT '{}',
    consent_given BOOLEAN DEFAULT FALSE,
    consent_at    TIMESTAMP,
    total_messages INTEGER DEFAULT 0,
    last_active   TIMESTAMP DEFAULT NOW(),
    created_at    TIMESTAMP DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_ext ON users(external_id, channel);
CREATE INDEX IF NOT EXISTS idx_users_channel    ON users(channel);

CREATE TABLE IF NOT EXISTS sessions (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    user_id         TEXT REFERENCES users(id),
    conversation_id TEXT REFERENCES conversations(id),
    channel         TEXT,
    ip_address      INET,
    user_agent      TEXT,
    started_at      TIMESTAMP DEFAULT NOW(),
    ended_at        TIMESTAMP,
    metadata        JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_sess_user ON sessions(user_id);

-- ─── Performance Metrics ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS performance_metrics (
    id              SERIAL PRIMARY KEY,
    metric_name     TEXT NOT NULL,
    metric_value    DOUBLE PRECISION NOT NULL,
    component       TEXT,
    tags            JSONB DEFAULT '{}',
    timestamp       TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_perf_name ON performance_metrics(metric_name);
CREATE INDEX IF NOT EXISTS idx_perf_ts   ON performance_metrics(timestamp);

-- Hypertable-ready partition by time (for TimescaleDB if available)
-- CREATE INDEX IF NOT EXISTS idx_perf_ts_brin ON performance_metrics USING brin(timestamp);

-- ─── Scheduled Tasks ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id            TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    name          TEXT NOT NULL,
    cron_expr     TEXT,
    handler       TEXT NOT NULL,
    params        JSONB DEFAULT '{}',
    enabled       BOOLEAN DEFAULT TRUE,
    last_run      TIMESTAMP,
    next_run      TIMESTAMP,
    run_count     INTEGER DEFAULT 0,
    last_status   TEXT DEFAULT 'pending',
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ─── Orchestrator Tasks ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tasks (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    title           TEXT NOT NULL,
    description     TEXT DEFAULT '',
    priority        INTEGER DEFAULT 3,
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed','cancelled')),
    assigned_agent  TEXT,
    result          TEXT,
    pipeline_id     TEXT,
    pipeline_step   INTEGER,
    created_at      TIMESTAMP DEFAULT NOW(),
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_tasks_pipeline ON tasks(pipeline_id);

-- ─── Orchestrator Pipelines ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipelines (
    id              TEXT PRIMARY KEY DEFAULT uuid_generate_v4()::TEXT,
    name            TEXT NOT NULL,
    definition      TEXT NOT NULL DEFAULT '[]',
    status          TEXT DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed')),
    current_step    INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT NOW(),
    completed_at    TIMESTAMP
);

-- ─── Schema Migrations ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    version       INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    applied_at    TIMESTAMP DEFAULT NOW()
);
INSERT INTO schema_migrations (version, name) VALUES (1, 'initial_enterprise_schema')
ON CONFLICT (version) DO NOTHING;
INSERT INTO schema_migrations (version, name) VALUES (2, 'add_orchestrator_tables')
ON CONFLICT (version) DO NOTHING;
