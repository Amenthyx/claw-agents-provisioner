#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER -- Database Migration Runner
=============================================================================
Versioned migration system for all SQLite databases used by the platform
(memory, billing, audit, orchestrator).  Supports forward migrations, rollback,
status reporting, and idempotent execution.

Commands:
  up      -- Run all pending forward migrations
  down    -- Roll back the most recent migration
  status  -- Show current migration state for all databases
  reset   -- Roll back ALL migrations (use with caution)

Each migration file in the migrations/ directory defines:
  - up(conn)   -- Forward migration (CREATE TABLE, ALTER, etc.)
  - down(conn) -- Rollback migration (DROP TABLE, undo ALTER, etc.)
  - DATABASES  -- List of database names this migration applies to

Usage:
  python scripts/migrate.py up
  python scripts/migrate.py down
  python scripts/migrate.py status
  python scripts/migrate.py up --db memory
  python scripts/migrate.py down --db orchestrator

Designed for CLI integration via `claw.sh migrate`.

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by AI Team -- Wave 2 Backend Engineer
Apache 2.0 (c) 2026 Amenthyx
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

# Database paths (match the locations used by each service)
DATABASE_PATHS: Dict[str, Path] = {
    "memory": PROJECT_ROOT / "data" / "memory" / "conversations.db",
    "billing": PROJECT_ROOT / "data" / "billing" / "billing.db",
    "orchestrator": PROJECT_ROOT / "data" / "orchestrator" / "orchestrator.db",
    "audit": PROJECT_ROOT / "data" / "audit" / "audit.db",
}

# -------------------------------------------------------------------------
# Colors
# -------------------------------------------------------------------------
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[migrate]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[migrate]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[migrate]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[migrate]{NC} {msg}")


# -------------------------------------------------------------------------
# Migration table management
# -------------------------------------------------------------------------

def _ensure_migration_table(conn: sqlite3.Connection) -> None:
    """Create the _migrations tracking table if it does not exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            checksum TEXT
        )
    """)
    conn.commit()


def _get_applied_versions(conn: sqlite3.Connection) -> List[str]:
    """Return list of applied migration versions, sorted ascending."""
    _ensure_migration_table(conn)
    rows = conn.execute(
        "SELECT version FROM _migrations ORDER BY version ASC"
    ).fetchall()
    return [row[0] for row in rows]


def _record_migration(conn: sqlite3.Connection, version: str, name: str) -> None:
    """Record a migration as applied."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        "INSERT INTO _migrations (version, name, applied_at) VALUES (?, ?, ?)",
        (version, name, now),
    )
    conn.commit()


def _remove_migration(conn: sqlite3.Connection, version: str) -> None:
    """Remove a migration record (for rollback)."""
    conn.execute("DELETE FROM _migrations WHERE version = ?", (version,))
    conn.commit()


# -------------------------------------------------------------------------
# Migration discovery
# -------------------------------------------------------------------------

def _discover_migrations() -> List[Dict[str, Any]]:
    """
    Discover all migration files in the migrations/ directory.

    Migration files must follow the naming convention: NNN_name.py
    (e.g., 001_initial_schema.py, 002_add_audit_columns.py).

    Returns a sorted list of migration descriptors.
    """
    if not MIGRATIONS_DIR.exists():
        warn(f"Migrations directory not found: {MIGRATIONS_DIR}")
        return []

    migrations = []
    for f in sorted(MIGRATIONS_DIR.iterdir()):
        if not f.is_file():
            continue
        if not f.suffix == ".py":
            continue
        if f.name.startswith("_") or f.name.startswith("."):
            continue

        # Parse version from filename (e.g., "001" from "001_initial_schema.py")
        parts = f.stem.split("_", 1)
        if len(parts) < 2:
            warn(f"Skipping migration with invalid name format: {f.name}")
            continue

        version = parts[0]
        name = parts[1]

        # Load the module
        spec = importlib.util.spec_from_file_location(f"migration_{version}", str(f))
        if spec is None or spec.loader is None:
            warn(f"Could not load migration: {f.name}")
            continue

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            err(f"Error loading migration {f.name}: {exc}")
            continue

        # Validate migration has required attributes
        if not hasattr(module, "up"):
            warn(f"Migration {f.name} missing 'up' function, skipping")
            continue
        if not hasattr(module, "down"):
            warn(f"Migration {f.name} missing 'down' function, skipping")
            continue

        # DATABASES defaults to all databases if not specified
        databases = getattr(module, "DATABASES", list(DATABASE_PATHS.keys()))

        migrations.append({
            "version": version,
            "name": name,
            "file": f,
            "module": module,
            "databases": databases,
        })

    return migrations


# -------------------------------------------------------------------------
# Database connection helper
# -------------------------------------------------------------------------

def _get_connection(db_name: str) -> sqlite3.Connection:
    """Open a connection to the named database, creating directories as needed."""
    db_path = DATABASE_PATHS.get(db_name)
    if db_path is None:
        raise ValueError(f"Unknown database: {db_name}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# -------------------------------------------------------------------------
# Commands
# -------------------------------------------------------------------------

def cmd_up(db_filter: Optional[str] = None) -> int:
    """
    Run all pending forward migrations.

    Returns 0 on success, 1 on error.
    """
    migrations = _discover_migrations()
    if not migrations:
        info("No migrations found.")
        return 0

    target_dbs = [db_filter] if db_filter else list(DATABASE_PATHS.keys())
    total_applied = 0

    for db_name in target_dbs:
        if db_name not in DATABASE_PATHS:
            err(f"Unknown database: {db_name}")
            return 1

        conn = _get_connection(db_name)
        try:
            applied = _get_applied_versions(conn)

            for mig in migrations:
                if db_name not in mig["databases"]:
                    continue
                if mig["version"] in applied:
                    continue

                log(f"[{db_name}] Applying {mig['version']}_{mig['name']}...")
                try:
                    mig["module"].up(conn)
                    _record_migration(conn, mig["version"], mig["name"])
                    total_applied += 1
                    log(f"[{db_name}] Applied {mig['version']}_{mig['name']}")
                except Exception as exc:
                    err(f"[{db_name}] Failed to apply {mig['version']}_{mig['name']}: {exc}")
                    return 1
        finally:
            conn.close()

    if total_applied == 0:
        info("All migrations are up to date.")
    else:
        log(f"Applied {total_applied} migration(s).")

    return 0


def cmd_down(db_filter: Optional[str] = None) -> int:
    """
    Roll back the most recent migration.

    Returns 0 on success, 1 on error.
    """
    migrations = _discover_migrations()
    if not migrations:
        info("No migrations found.")
        return 0

    target_dbs = [db_filter] if db_filter else list(DATABASE_PATHS.keys())
    total_rolled = 0

    for db_name in target_dbs:
        if db_name not in DATABASE_PATHS:
            err(f"Unknown database: {db_name}")
            return 1

        conn = _get_connection(db_name)
        try:
            applied = _get_applied_versions(conn)
            if not applied:
                info(f"[{db_name}] No migrations to roll back.")
                continue

            latest_version = applied[-1]

            # Find the migration module for this version
            mig = None
            for m in migrations:
                if m["version"] == latest_version and db_name in m["databases"]:
                    mig = m
                    break

            if mig is None:
                err(f"[{db_name}] Migration file for version {latest_version} not found")
                return 1

            log(f"[{db_name}] Rolling back {mig['version']}_{mig['name']}...")
            try:
                mig["module"].down(conn)
                _remove_migration(conn, mig["version"])
                total_rolled += 1
                log(f"[{db_name}] Rolled back {mig['version']}_{mig['name']}")
            except Exception as exc:
                err(f"[{db_name}] Rollback failed for {mig['version']}_{mig['name']}: {exc}")
                return 1
        finally:
            conn.close()

    if total_rolled == 0:
        info("Nothing to roll back.")
    else:
        log(f"Rolled back {total_rolled} migration(s).")

    return 0


def cmd_status(db_filter: Optional[str] = None) -> int:
    """
    Show current migration status for all databases.

    Returns 0 always.
    """
    migrations = _discover_migrations()
    target_dbs = [db_filter] if db_filter else list(DATABASE_PATHS.keys())

    for db_name in target_dbs:
        if db_name not in DATABASE_PATHS:
            err(f"Unknown database: {db_name}")
            continue

        db_path = DATABASE_PATHS[db_name]
        if not db_path.exists():
            info(f"[{db_name}] Database not yet created: {db_path}")
            continue

        conn = _get_connection(db_name)
        try:
            applied = _get_applied_versions(conn)

            print(f"\n{BOLD}{CYAN}=== {db_name.upper()} ==={NC}")
            print(f"  Database: {db_path}")
            print(f"  Applied:  {len(applied)} migration(s)")

            if not migrations:
                print(f"  No migration files found in {MIGRATIONS_DIR}")
                continue

            relevant = [m for m in migrations if db_name in m["databases"]]

            for mig in relevant:
                status = "applied" if mig["version"] in applied else "PENDING"
                marker = f"{GREEN}OK{NC}" if status == "applied" else f"{YELLOW}PENDING{NC}"
                print(f"  [{marker}] {mig['version']}_{mig['name']}")

        finally:
            conn.close()

    return 0


def cmd_reset(db_filter: Optional[str] = None) -> int:
    """
    Roll back ALL migrations.

    Returns 0 on success, 1 on error.
    """
    migrations = _discover_migrations()
    if not migrations:
        info("No migrations found.")
        return 0

    target_dbs = [db_filter] if db_filter else list(DATABASE_PATHS.keys())

    for db_name in target_dbs:
        if db_name not in DATABASE_PATHS:
            err(f"Unknown database: {db_name}")
            return 1

        conn = _get_connection(db_name)
        try:
            applied = _get_applied_versions(conn)
            # Roll back in reverse order
            for version in reversed(applied):
                mig = None
                for m in migrations:
                    if m["version"] == version and db_name in m["databases"]:
                        mig = m
                        break

                if mig is None:
                    warn(f"[{db_name}] Migration file for {version} not found, skipping")
                    _remove_migration(conn, version)
                    continue

                log(f"[{db_name}] Rolling back {mig['version']}_{mig['name']}...")
                try:
                    mig["module"].down(conn)
                    _remove_migration(conn, mig["version"])
                except Exception as exc:
                    err(f"[{db_name}] Rollback failed: {exc}")
                    return 1
        finally:
            conn.close()

    log("All migrations rolled back.")
    return 0


# -------------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------------

def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Claw Agents Provisioner -- Database Migration Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["up", "down", "status", "reset"],
        help="Migration command to execute",
    )
    parser.add_argument(
        "--db",
        choices=list(DATABASE_PATHS.keys()),
        default=None,
        help="Target a specific database (default: all)",
    )

    args = parser.parse_args()

    commands = {
        "up": cmd_up,
        "down": cmd_down,
        "status": cmd_status,
        "reset": cmd_reset,
    }

    return commands[args.command](args.db)


if __name__ == "__main__":
    sys.exit(main())
