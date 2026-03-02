"""
Migration 001: Initial Schema
==============================
Creates the foundational tables for all Claw platform databases:
  - memory: conversations, messages, context_shares
  - billing: usage_records, budget_config, billing_reports
  - orchestrator: agents, tasks, pipelines, events
  - audit: audit_log, security_events

Each table uses IF NOT EXISTS for idempotent forward execution.
Rollback drops all tables created by this migration.
"""

from __future__ import annotations

import sqlite3
from typing import List

# Which databases this migration applies to
DATABASES: List[str] = ["memory", "billing", "orchestrator", "audit"]


def up(conn: sqlite3.Connection) -> None:
    """Apply forward migration -- create initial schema."""

    # Detect which database we're operating on by checking existing tables
    # and applying only the relevant schema.
    existing = _get_existing_tables(conn)

    # =====================================================================
    # Memory tables
    # =====================================================================
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            summary TEXT,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            tokens INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS context_shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            context_summary TEXT NOT NULL,
            shared_at TEXT NOT NULL,
            expires_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conv
            ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_messages_timestamp
            ON messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_conversations_agent
            ON conversations(agent_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_updated
            ON conversations(updated_at);
        CREATE INDEX IF NOT EXISTS idx_context_to_agent
            ON context_shares(to_agent);
        CREATE INDEX IF NOT EXISTS idx_context_from_agent
            ON context_shares(from_agent);
    """)

    # =====================================================================
    # Billing tables
    # =====================================================================
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usage_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            model TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'unknown',
            type TEXT NOT NULL DEFAULT 'cloud' CHECK (type IN ('cloud', 'local')),
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost REAL NOT NULL DEFAULT 0.0,
            response_time_ms INTEGER DEFAULT 0,
            agent_id TEXT DEFAULT '',
            task_type TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS budget_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            monthly_limit REAL NOT NULL DEFAULT 100.0,
            daily_limit REAL,
            weekly_limit REAL,
            warn_threshold REAL NOT NULL DEFAULT 0.80,
            webhook_url TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS billing_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL CHECK (report_type IN ('daily', 'weekly', 'monthly')),
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            total_cost REAL NOT NULL DEFAULT 0.0,
            total_requests INTEGER NOT NULL DEFAULT 0,
            report_data TEXT DEFAULT '{}',
            generated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_usage_timestamp
            ON usage_records(timestamp);
        CREATE INDEX IF NOT EXISTS idx_usage_model
            ON usage_records(model);
        CREATE INDEX IF NOT EXISTS idx_usage_agent
            ON usage_records(agent_id);
        CREATE INDEX IF NOT EXISTS idx_reports_type
            ON billing_reports(report_type);
        CREATE INDEX IF NOT EXISTS idx_reports_period
            ON billing_reports(period_start, period_end);
    """)

    # =====================================================================
    # Orchestrator tables
    # =====================================================================
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            port INTEGER NOT NULL,
            status TEXT DEFAULT 'unknown'
                CHECK (status IN ('unknown', 'healthy', 'unhealthy', 'degraded')),
            capabilities TEXT DEFAULT '[]',
            current_load INTEGER DEFAULT 0,
            max_load INTEGER DEFAULT 10,
            last_health_check TEXT,
            registered_at TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority INTEGER DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
            status TEXT DEFAULT 'pending'
                CHECK (status IN ('pending', 'assigned', 'running', 'completed', 'failed', 'cancelled')),
            assigned_agent TEXT,
            result TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            pipeline_id TEXT,
            pipeline_step INTEGER,
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY (assigned_agent) REFERENCES agents(id)
        );

        CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            steps TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending'
                CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
            current_step INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            metadata TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            source_agent TEXT,
            target_agent TEXT,
            payload TEXT DEFAULT '{}',
            timestamp TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status
            ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_priority
            ON tasks(priority DESC, created_at ASC);
        CREATE INDEX IF NOT EXISTS idx_tasks_pipeline
            ON tasks(pipeline_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_agent
            ON tasks(assigned_agent);
        CREATE INDEX IF NOT EXISTS idx_events_type
            ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp
            ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_agents_status
            ON agents(status);
    """)

    # =====================================================================
    # Audit tables
    # =====================================================================
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL DEFAULT 'system',
            resource TEXT DEFAULT '',
            action TEXT NOT NULL,
            details TEXT DEFAULT '{}',
            ip_address TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            outcome TEXT DEFAULT 'success'
                CHECK (outcome IN ('success', 'failure', 'error'))
        );

        CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info'
                CHECK (severity IN ('info', 'warning', 'critical')),
            event_type TEXT NOT NULL,
            source TEXT DEFAULT '',
            description TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            acknowledged INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_event_type
            ON audit_log(event_type);
        CREATE INDEX IF NOT EXISTS idx_audit_actor
            ON audit_log(actor);
        CREATE INDEX IF NOT EXISTS idx_security_timestamp
            ON security_events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_security_severity
            ON security_events(severity);
        CREATE INDEX IF NOT EXISTS idx_security_acknowledged
            ON security_events(acknowledged);
    """)

    conn.commit()


def down(conn: sqlite3.Connection) -> None:
    """Roll back migration -- drop all tables created in up()."""

    # Drop in reverse dependency order (children before parents)
    tables_to_drop = [
        # Audit
        "security_events",
        "audit_log",
        # Orchestrator
        "events",
        "pipelines",
        "tasks",
        "agents",
        # Billing
        "billing_reports",
        "budget_config",
        "usage_records",
        # Memory
        "context_shares",
        "messages",
        "conversations",
    ]

    for table in tables_to_drop:
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    conn.commit()


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _get_existing_tables(conn: sqlite3.Connection) -> set:
    """Return set of existing table names."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}
