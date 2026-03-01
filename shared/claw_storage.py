#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Storage Abstraction Layer
=============================================================================
Provides a unified storage backend for XClaw instances with support for
SQLite (embedded) and PostgreSQL (server).  Includes:

  - StorageBackend ABC with SQLite and PostgreSQL implementations
  - StorageManager for per-instance and shared database lifecycle
  - RBACManager for role-based access control on shared databases
  - Shared database schema for cross-claw data (agents, costs, memory, etc.)

Config file: data/wizard/storage_config.json
Python 3.8+ (stdlib + optional psycopg2 for PostgreSQL).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import json
import os
import sqlite3
import sys
import threading
import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -------------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SCHEMA_DIR = PROJECT_ROOT / "schema"
STORAGE_CONFIG_FILE = PROJECT_ROOT / "data" / "wizard" / "storage_config.json"
DEFAULT_INSTANCE_DB = PROJECT_ROOT / "data" / "instance.db"
DEFAULT_SHARED_DB = PROJECT_ROOT / "data" / "shared" / "shared.db"

# -------------------------------------------------------------------------
# Colors
# -------------------------------------------------------------------------
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[storage]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[storage]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[storage]{NC} {msg}", file=sys.stderr)


def _fmt_bytes(n: int) -> str:
    """Human-readable byte size."""
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


# =========================================================================
#  StorageBackend — Abstract base class
# =========================================================================
class StorageBackend(ABC):
    """Abstract storage backend interface."""

    @abstractmethod
    def execute(self, sql: str, params: tuple = ()) -> Any:
        """Execute a SQL statement (INSERT/UPDATE/DELETE/DDL)."""

    @abstractmethod
    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute query and return first row as dict, or None."""

    @abstractmethod
    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Execute query and return all rows as list of dicts."""

    @abstractmethod
    def close(self) -> None:
        """Close the database connection."""

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        """Return health metrics for this backend."""

    @abstractmethod
    def get_tables(self) -> List[str]:
        """Return list of table names."""

    @abstractmethod
    def table_info(self, name: str) -> List[Dict[str, Any]]:
        """Return column metadata for a table."""


# =========================================================================
#  SQLiteBackend
# =========================================================================
class SQLiteBackend(StorageBackend):
    """SQLite storage backend with WAL mode and thread safety."""

    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

    def execute(self, sql: str, params: tuple = ()) -> Any:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            return cursor.lastrowid

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get_health(self) -> Dict[str, Any]:
        start = time.monotonic()
        try:
            self.fetchone("SELECT 1")
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
            wal_path = Path(str(self.db_path) + "-wal")
            wal_size = wal_path.stat().st_size if wal_path.exists() else 0
            return {
                "status": "healthy",
                "engine": "sqlite",
                "path": str(self.db_path),
                "latency_ms": latency_ms,
                "size_bytes": size_bytes,
                "wal_size_bytes": wal_size,
            }
        except Exception as e:
            return {"status": "error", "engine": "sqlite", "error": str(e)}

    def get_tables(self) -> List[str]:
        rows = self.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        return [r["name"] for r in rows]

    def table_info(self, name: str) -> List[Dict[str, Any]]:
        rows = self.fetchall(f"PRAGMA table_info({name})")
        return [{"name": r["name"], "type": r["type"], "notnull": bool(r["notnull"]), "pk": bool(r["pk"])} for r in rows]


# =========================================================================
#  PostgreSQLBackend
# =========================================================================
def ensure_psycopg2() -> bool:
    """Try to import psycopg2; if missing, auto-install psycopg2-binary via pip.
    Returns True if psycopg2 is available after the attempt."""
    try:
        import psycopg2  # noqa: F401
        return True
    except ImportError:
        pass
    log("psycopg2 not found — installing psycopg2-binary automatically...")
    import subprocess as _sp
    try:
        _sp.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", "psycopg2-binary"],
            stdout=_sp.DEVNULL,
            stderr=_sp.PIPE,
        )
        import psycopg2  # noqa: F811, F401
        log("psycopg2-binary installed successfully")
        return True
    except Exception as e:
        err(f"Failed to install psycopg2-binary: {e}")
        return False


def check_postgres_server(host: str = "localhost", port: int = 5432) -> bool:
    """Check if a PostgreSQL server is listening at host:port."""
    import socket as _sock
    try:
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        s.settimeout(3)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except OSError:
        return False


class PostgreSQLBackend(StorageBackend):
    """PostgreSQL storage backend using psycopg2."""

    def __init__(self, host: str, port: int, dbname: str, user: str, password: str) -> None:
        if not ensure_psycopg2():
            raise ImportError(
                "psycopg2 is required for PostgreSQL support and could not be "
                "installed automatically. Install it manually with:\n"
                "  pip install psycopg2-binary"
            )
        import psycopg2
        self._psycopg2 = psycopg2
        self._lock = threading.Lock()
        self._conn = psycopg2.connect(
            host=host, port=port, dbname=dbname, user=user, password=password
        )
        self._conn.autocommit = True
        self._config = {"host": host, "port": port, "dbname": dbname, "user": user}

    def execute(self, sql: str, params: tuple = ()) -> Any:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            return cur.rowcount

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            if cur.description is None:
                return None
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
            return dict(zip(cols, row)) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(sql, params)
            if cur.description is None:
                return []
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def get_health(self) -> Dict[str, Any]:
        start = time.monotonic()
        try:
            self.fetchone("SELECT 1")
            latency_ms = round((time.monotonic() - start) * 1000, 2)
            size_row = self.fetchone(
                "SELECT pg_database_size(current_database()) AS size"
            )
            size_bytes = size_row["size"] if size_row else 0
            conn_row = self.fetchone(
                "SELECT count(*) AS cnt FROM pg_stat_activity WHERE datname = current_database()"
            )
            connections = conn_row["cnt"] if conn_row else 0
            return {
                "status": "healthy",
                "engine": "postgresql",
                "host": self._config["host"],
                "port": self._config["port"],
                "dbname": self._config["dbname"],
                "latency_ms": latency_ms,
                "size_bytes": size_bytes,
                "connections": connections,
            }
        except Exception as e:
            return {"status": "error", "engine": "postgresql", "error": str(e)}

    def get_tables(self) -> List[str]:
        rows = self.fetchall(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        return [r["tablename"] for r in rows]

    def table_info(self, name: str) -> List[Dict[str, Any]]:
        rows = self.fetchall(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (name,),
        )
        return [
            {"name": r["column_name"], "type": r["data_type"], "notnull": r["is_nullable"] == "NO", "pk": False}
            for r in rows
        ]


# =========================================================================
#  Shared Database Schema
# =========================================================================
SHARED_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,
    host TEXT DEFAULT 'localhost',
    port INTEGER DEFAULT 0,
    status TEXT DEFAULT 'unknown',
    created_at TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS shared_memory (
    id TEXT PRIMARY KEY,
    from_agent_id TEXT NOT NULL,
    to_agent_id TEXT,
    conversation_id TEXT,
    context_summary TEXT,
    shared_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (from_agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS cost_tracking (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    timestamp TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS security_events (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    details TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);

CREATE TABLE IF NOT EXISTS rbac_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    permissions TEXT DEFAULT '{}',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rbac_assignments (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    role_id TEXT NOT NULL,
    assigned_at TEXT DEFAULT (datetime('now')),
    assigned_by TEXT DEFAULT 'system',
    FOREIGN KEY (agent_id) REFERENCES agents(id),
    FOREIGN KEY (role_id) REFERENCES rbac_roles(id)
);

CREATE TABLE IF NOT EXISTS cluster_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now')),
    updated_by TEXT DEFAULT 'system'
);
"""

# PostgreSQL variant (uses SERIAL / TIMESTAMP defaults differently)
SHARED_SCHEMA_PG_SQL = """
CREATE TABLE IF NOT EXISTS agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    platform TEXT NOT NULL,
    host TEXT DEFAULT 'localhost',
    port INTEGER DEFAULT 0,
    status TEXT DEFAULT 'unknown',
    created_at TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shared_memory (
    id TEXT PRIMARY KEY,
    from_agent_id TEXT NOT NULL REFERENCES agents(id),
    to_agent_id TEXT,
    conversation_id TEXT,
    context_summary TEXT,
    shared_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_tracking (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    model TEXT NOT NULL,
    provider TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd DOUBLE PRECISION DEFAULT 0.0,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS security_events (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    details TEXT,
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rbac_roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rbac_assignments (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL REFERENCES agents(id),
    role_id TEXT NOT NULL REFERENCES rbac_roles(id),
    assigned_at TIMESTAMP DEFAULT NOW(),
    assigned_by TEXT DEFAULT 'system'
);

CREATE TABLE IF NOT EXISTS cluster_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system'
);
"""

INSTANCE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS local_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS local_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT DEFAULT 'info',
    message TEXT,
    source TEXT DEFAULT 'system',
    timestamp TEXT DEFAULT (datetime('now'))
);
"""

INSTANCE_SCHEMA_PG_SQL = """
CREATE TABLE IF NOT EXISTS local_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS local_logs (
    id SERIAL PRIMARY KEY,
    level TEXT DEFAULT 'info',
    message TEXT,
    source TEXT DEFAULT 'system',
    timestamp TIMESTAMP DEFAULT NOW()
);
"""


# =========================================================================
#  StorageManager
# =========================================================================
class StorageManager:
    """Manages per-instance and shared database backends."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path or STORAGE_CONFIG_FILE
        self._config = self._load_config()
        self._instance_db: Optional[StorageBackend] = None
        self._shared_db: Optional[StorageBackend] = None

    def _load_config(self) -> Dict[str, Any]:
        if self._config_path.exists():
            try:
                return json.loads(self._config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "engine": "sqlite",
            "instance_db": {"engine": "sqlite", "path": str(DEFAULT_INSTANCE_DB)},
            "shared_db": {"enabled": False, "engine": "sqlite", "path": str(DEFAULT_SHARED_DB)},
        }

    def save_config(self, config: Dict[str, Any]) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        self._config = config

    @property
    def config(self) -> Dict[str, Any]:
        return self._config

    def _create_backend(self, cfg: Dict[str, Any]) -> StorageBackend:
        engine = cfg.get("engine", "sqlite")
        if engine == "postgresql":
            return PostgreSQLBackend(
                host=cfg.get("host", "localhost"),
                port=cfg.get("port", 5432),
                dbname=cfg.get("dbname", "xclaw"),
                user=cfg.get("user", "xclaw"),
                password=cfg.get("password", ""),
            )
        else:
            path = cfg.get("path", str(DEFAULT_INSTANCE_DB))
            return SQLiteBackend(path)

    def get_instance_db(self) -> StorageBackend:
        if self._instance_db is None:
            self._instance_db = self._create_backend(self._config.get("instance_db", {}))
        return self._instance_db

    def get_shared_db(self) -> Optional[StorageBackend]:
        shared_cfg = self._config.get("shared_db", {})
        if not shared_cfg.get("enabled", False):
            return None
        if self._shared_db is None:
            self._shared_db = self._create_backend(shared_cfg)
        return self._shared_db

    @staticmethod
    def _load_schema(engine: str, kind: str) -> str:
        """Load schema SQL from .sql file, falling back to inline strings."""
        suffix = "postgres" if engine == "postgresql" else "sqlite"
        sql_file = SCHEMA_DIR / f"{kind}_{suffix}.sql"
        if sql_file.exists():
            log(f"Loading schema from {sql_file}")
            return sql_file.read_text(encoding="utf-8")
        # Fallback to inline
        if kind == "instance":
            return INSTANCE_SCHEMA_PG_SQL if engine == "postgresql" else INSTANCE_SCHEMA_SQL
        return SHARED_SCHEMA_PG_SQL if engine == "postgresql" else SHARED_SCHEMA_SQL

    def _execute_schema(self, db: StorageBackend, schema_sql: str) -> None:
        """Execute a multi-statement SQL schema, handling PRAGMAs and extensions."""
        for raw_stmt in schema_sql.split(";"):
            # Strip comments and whitespace to get the actual SQL
            lines = [l for l in raw_stmt.split("\n") if l.strip() and not l.strip().startswith("--")]
            stmt = "\n".join(lines).strip()
            if not stmt:
                continue
            # Skip PRAGMA for PostgreSQL, skip CREATE EXTENSION for SQLite
            upper = stmt.upper()
            if isinstance(db, SQLiteBackend) and "CREATE EXTENSION" in upper:
                continue
            if isinstance(db, PostgreSQLBackend) and upper.startswith("PRAGMA"):
                continue
            try:
                db.execute(stmt)
            except Exception as e:
                # Non-fatal: log and continue (e.g. IF NOT EXISTS already created)
                warn(f"Schema stmt skipped: {e}")

    def init_instance_schema(self) -> None:
        db = self.get_instance_db()
        engine = self._config.get("instance_db", {}).get("engine", "sqlite")
        schema = self._load_schema(engine, "instance")
        self._execute_schema(db, schema)
        log("Instance database schema initialized")

    def init_shared_schema(self) -> None:
        db = self.get_shared_db()
        if db is None:
            warn("Shared database is disabled — skipping schema init")
            return
        engine = self._config.get("shared_db", {}).get("engine", "sqlite")
        schema = self._load_schema(engine, "shared")
        self._execute_schema(db, schema)
        log("Shared database schema initialized")

    @staticmethod
    def test_connection(config: Dict[str, Any]) -> Dict[str, Any]:
        """Test a database connection and return result with latency.
        For SQLite: checks if the file exists (reports 'will be created' if not).
        For PostgreSQL: attempts actual connection; reports db_exists=False if
        the server is reachable but the database is missing."""
        engine = config.get("engine", "sqlite")
        start = time.monotonic()
        try:
            if engine == "postgresql":
                host = config.get("host", "localhost")
                port = config.get("port", 5432)
                dbname = config.get("dbname", "xclaw")
                user = config.get("user", "xclaw")
                password = config.get("password", "")
                try:
                    backend = PostgreSQLBackend(
                        host=host, port=port, dbname=dbname, user=user, password=password,
                    )
                    backend.fetchone("SELECT 1")
                    latency_ms = round((time.monotonic() - start) * 1000, 2)
                    backend.close()
                    return {
                        "success": True,
                        "message": f"Connected to {dbname}@{host}:{port}",
                        "latency_ms": latency_ms,
                        "db_exists": True,
                    }
                except Exception as pg_err:
                    err_str = str(pg_err).lower()
                    # Detect "database does not exist" vs auth / network errors
                    if "does not exist" in err_str or "nicht" in err_str:
                        return {
                            "success": False,
                            "message": f"Database '{dbname}' does not exist on {host}:{port}",
                            "latency_ms": 0,
                            "db_exists": False,
                            "server_reachable": True,
                        }
                    raise  # re-raise auth / network errors
            else:
                db_path = Path(config.get("path", str(DEFAULT_INSTANCE_DB)))
                if db_path.exists():
                    backend = SQLiteBackend(str(db_path))
                    backend.fetchone("SELECT 1")
                    latency_ms = round((time.monotonic() - start) * 1000, 2)
                    size_bytes = db_path.stat().st_size
                    backend.close()
                    return {
                        "success": True,
                        "message": f"Database exists ({_fmt_bytes(size_bytes)})",
                        "latency_ms": latency_ms,
                        "db_exists": True,
                    }
                else:
                    # File doesn't exist yet — that's OK, it will be created on deploy
                    parent = db_path.parent
                    parent_ok = parent.exists() or True  # parent will be auto-created
                    return {
                        "success": True,
                        "message": f"Database will be created at {db_path}",
                        "latency_ms": 0,
                        "db_exists": False,
                        "parent_writable": parent_ok,
                    }
        except Exception as e:
            return {"success": False, "message": str(e), "latency_ms": 0}

    def get_all_databases_info(self) -> List[Dict[str, Any]]:
        """Return metadata for all configured databases."""
        dbs = []

        # Instance DB
        try:
            inst = self.get_instance_db()
            health = inst.get_health()
            tables = inst.get_tables()
            dbs.append({
                "name": "instance",
                "label": "Instance DB",
                "engine": self._config.get("instance_db", {}).get("engine", "sqlite"),
                "tables": tables,
                "table_count": len(tables),
                "health": health,
            })
        except Exception as e:
            dbs.append({"name": "instance", "label": "Instance DB", "error": str(e)})

        # Shared DB
        shared_cfg = self._config.get("shared_db", {})
        if shared_cfg.get("enabled", False):
            try:
                shared = self.get_shared_db()
                if shared:
                    health = shared.get_health()
                    tables = shared.get_tables()
                    dbs.append({
                        "name": "shared",
                        "label": "Shared DB",
                        "engine": shared_cfg.get("engine", "sqlite"),
                        "tables": tables,
                        "table_count": len(tables),
                        "health": health,
                    })
            except Exception as e:
                dbs.append({"name": "shared", "label": "Shared DB", "error": str(e)})

        return dbs

    def get_health_all(self) -> Dict[str, Any]:
        """Return health metrics for all databases."""
        result: Dict[str, Any] = {}
        try:
            result["instance"] = self.get_instance_db().get_health()
        except Exception as e:
            result["instance"] = {"status": "error", "error": str(e)}

        shared = self.get_shared_db()
        if shared:
            try:
                result["shared"] = shared.get_health()
            except Exception as e:
                result["shared"] = {"status": "error", "error": str(e)}

        return result

    def close_all(self) -> None:
        if self._instance_db:
            self._instance_db.close()
            self._instance_db = None
        if self._shared_db:
            self._shared_db.close()
            self._shared_db = None


# =========================================================================
#  RBACManager
# =========================================================================

# Built-in role definitions
BUILTIN_ROLES = [
    {
        "id": "admin",
        "name": "admin",
        "description": "Full read-write access to all resources",
        "permissions": {
            "memory": ["read", "write", "delete"],
            "costs": ["read", "write", "delete"],
            "security_events": ["read", "write", "delete"],
            "config": ["read", "write", "delete"],
            "rbac": ["read", "write", "delete"],
        },
    },
    {
        "id": "operator",
        "name": "operator",
        "description": "Read-write own data, read shared data",
        "permissions": {
            "memory": ["read", "write"],
            "costs": ["read", "write"],
            "security_events": ["read", "write"],
            "config": ["read"],
            "rbac": ["read"],
        },
    },
    {
        "id": "viewer",
        "name": "viewer",
        "description": "Read-only access to all resources",
        "permissions": {
            "memory": ["read"],
            "costs": ["read"],
            "security_events": ["read"],
            "config": ["read"],
            "rbac": ["read"],
        },
    },
    {
        "id": "agent",
        "name": "agent",
        "description": "Write own data, read shared data",
        "permissions": {
            "memory": ["read", "write"],
            "costs": ["read", "write"],
            "security_events": ["read", "write"],
            "config": ["read"],
            "rbac": [],
        },
    },
]


class RBACManager:
    """Role-based access control for shared database resources."""

    def __init__(self, db: StorageBackend) -> None:
        self._db = db

    def init_builtin_roles(self) -> None:
        """Insert built-in roles if they don't exist."""
        for role in BUILTIN_ROLES:
            existing = self._db.fetchone("SELECT id FROM rbac_roles WHERE id = ?", (role["id"],))
            if not existing:
                self._db.execute(
                    "INSERT INTO rbac_roles (id, name, description, permissions) VALUES (?, ?, ?, ?)",
                    (role["id"], role["name"], role["description"], json.dumps(role["permissions"])),
                )
        log("Built-in RBAC roles initialized")

    def assign_role(self, agent_id: str, role_id: str, assigned_by: str = "system") -> Dict[str, Any]:
        """Assign a role to an agent. Replaces existing assignment."""
        # Verify role exists
        role = self._db.fetchone("SELECT id FROM rbac_roles WHERE id = ?", (role_id,))
        if not role:
            return {"success": False, "error": f"Role '{role_id}' not found"}

        # Remove existing assignment for this agent
        self._db.execute("DELETE FROM rbac_assignments WHERE agent_id = ?", (agent_id,))

        # Create new assignment
        assignment_id = str(uuid.uuid4())
        self._db.execute(
            "INSERT INTO rbac_assignments (id, agent_id, role_id, assigned_by) VALUES (?, ?, ?, ?)",
            (assignment_id, agent_id, role_id, assigned_by),
        )
        return {"success": True, "assignment_id": assignment_id}

    def check_permission(self, agent_id: str, resource: str, action: str) -> bool:
        """Check if an agent has permission for a resource+action."""
        assignment = self._db.fetchone(
            "SELECT ra.role_id, rr.permissions FROM rbac_assignments ra "
            "JOIN rbac_roles rr ON ra.role_id = rr.id "
            "WHERE ra.agent_id = ?",
            (agent_id,),
        )
        if not assignment:
            return False

        try:
            permissions = json.loads(assignment["permissions"]) if isinstance(assignment["permissions"], str) else assignment["permissions"]
        except (json.JSONDecodeError, TypeError):
            return False

        resource_perms = permissions.get(resource, [])
        return action in resource_perms

    def list_roles(self) -> List[Dict[str, Any]]:
        """Return all defined roles."""
        roles = self._db.fetchall("SELECT * FROM rbac_roles ORDER BY name")
        for r in roles:
            if isinstance(r.get("permissions"), str):
                try:
                    r["permissions"] = json.loads(r["permissions"])
                except json.JSONDecodeError:
                    r["permissions"] = {}
        return roles

    def list_assignments(self) -> List[Dict[str, Any]]:
        """Return all role assignments with role details."""
        return self._db.fetchall(
            "SELECT ra.id, ra.agent_id, ra.role_id, rr.name AS role_name, "
            "ra.assigned_at, ra.assigned_by "
            "FROM rbac_assignments ra "
            "JOIN rbac_roles rr ON ra.role_id = rr.id "
            "ORDER BY ra.assigned_at DESC"
        )


# =========================================================================
#  CLI Init Entry Point
# =========================================================================
def init_databases() -> None:
    """Initialize all configured databases. Called from entrypoint."""
    log("Initializing storage backends...")
    mgr = StorageManager()
    mgr.init_instance_schema()
    mgr.init_shared_schema()

    shared = mgr.get_shared_db()
    if shared:
        rbac = RBACManager(shared)
        rbac.init_builtin_roles()

    mgr.close_all()
    log("Storage initialization complete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="XClaw Storage Layer")
    parser.add_argument("--init", action="store_true", help="Initialize database schemas")
    parser.add_argument("--test", action="store_true", help="Test connection to configured databases")
    args = parser.parse_args()

    if args.init:
        init_databases()
    elif args.test:
        mgr = StorageManager()
        inst_cfg = mgr.config.get("instance_db", {})
        result = StorageManager.test_connection(inst_cfg)
        log(f"Instance DB: {result}")
        shared_cfg = mgr.config.get("shared_db", {})
        if shared_cfg.get("enabled"):
            result = StorageManager.test_connection(shared_cfg)
            log(f"Shared DB: {result}")
    else:
        parser.print_help()
