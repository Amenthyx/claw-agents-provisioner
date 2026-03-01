"""
Tests for claw_storage.py — Storage Abstraction Layer.
Covers SQLiteBackend, StorageManager, and RBACManager.
"""

import json
import sys
from pathlib import Path

import pytest

# Ensure shared/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from claw_storage import (
    SQLiteBackend,
    StorageManager,
    RBACManager,
    BUILTIN_ROLES,
)


# =========================================================================
#  TestSQLiteBackend
# =========================================================================
class TestSQLiteBackend:
    """Test SQLite storage backend operations."""

    def test_create_and_execute(self, tmp_path):
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
        backend.execute("INSERT INTO items (name) VALUES (?)", ("alpha",))
        backend.execute("INSERT INTO items (name) VALUES (?)", ("beta",))
        backend.close()
        assert db_path.exists()

    def test_fetchone(self, tmp_path):
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT)")
        backend.execute("INSERT INTO kv VALUES (?, ?)", ("foo", "bar"))
        row = backend.fetchone("SELECT * FROM kv WHERE key = ?", ("foo",))
        assert row is not None
        assert row["key"] == "foo"
        assert row["value"] == "bar"
        backend.close()

    def test_fetchall(self, tmp_path):
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.execute("CREATE TABLE nums (n INTEGER)")
        for i in range(5):
            backend.execute("INSERT INTO nums VALUES (?)", (i,))
        rows = backend.fetchall("SELECT * FROM nums ORDER BY n")
        assert len(rows) == 5
        assert rows[0]["n"] == 0
        assert rows[4]["n"] == 4
        backend.close()

    def test_get_health(self, tmp_path):
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.execute("CREATE TABLE t (id INTEGER)")
        health = backend.get_health()
        assert health["status"] == "healthy"
        assert health["engine"] == "sqlite"
        assert health["latency_ms"] >= 0
        assert health["size_bytes"] > 0
        backend.close()

    def test_get_tables(self, tmp_path):
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.execute("CREATE TABLE alpha (id INTEGER)")
        backend.execute("CREATE TABLE beta (id INTEGER)")
        tables = backend.get_tables()
        assert "alpha" in tables
        assert "beta" in tables
        assert len(tables) == 2
        backend.close()

    def test_table_info(self, tmp_path):
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT)")
        info = backend.table_info("users")
        assert len(info) == 3
        names = [c["name"] for c in info]
        assert "id" in names
        assert "name" in names
        assert "email" in names
        # Check primary key detection
        id_col = next(c for c in info if c["name"] == "id")
        assert id_col["pk"] is True
        # Check not-null
        name_col = next(c for c in info if c["name"] == "name")
        assert name_col["notnull"] is True
        backend.close()

    def test_fetchone_returns_none_when_empty(self, tmp_path):
        db_path = tmp_path / "test.db"
        backend = SQLiteBackend(str(db_path))
        backend.execute("CREATE TABLE empty_tbl (id INTEGER)")
        row = backend.fetchone("SELECT * FROM empty_tbl")
        assert row is None
        backend.close()


# =========================================================================
#  TestStorageManager
# =========================================================================
class TestStorageManager:
    """Test StorageManager lifecycle and configuration."""

    def _make_config(self, tmp_path, shared_enabled=False):
        config = {
            "engine": "sqlite",
            "instance_db": {
                "engine": "sqlite",
                "path": str(tmp_path / "instance.db"),
            },
            "shared_db": {
                "enabled": shared_enabled,
                "engine": "sqlite",
                "path": str(tmp_path / "shared.db"),
            },
        }
        config_file = tmp_path / "storage_config.json"
        config_file.write_text(json.dumps(config))
        return config_file

    def test_init_with_sqlite_config(self, tmp_path):
        config_file = self._make_config(tmp_path)
        mgr = StorageManager(config_path=config_file)
        assert mgr.config["engine"] == "sqlite"
        db = mgr.get_instance_db()
        assert db is not None
        mgr.close_all()

    def test_shared_db_disabled(self, tmp_path):
        config_file = self._make_config(tmp_path, shared_enabled=False)
        mgr = StorageManager(config_path=config_file)
        shared = mgr.get_shared_db()
        assert shared is None
        mgr.close_all()

    def test_shared_db_enabled(self, tmp_path):
        config_file = self._make_config(tmp_path, shared_enabled=True)
        mgr = StorageManager(config_path=config_file)
        shared = mgr.get_shared_db()
        assert shared is not None
        mgr.close_all()

    def test_init_shared_schema(self, tmp_path):
        config_file = self._make_config(tmp_path, shared_enabled=True)
        mgr = StorageManager(config_path=config_file)
        mgr.init_shared_schema()
        shared = mgr.get_shared_db()
        tables = shared.get_tables()
        # Core tables that must always exist
        core_tables = ["agents", "cluster_config", "cost_tracking", "rbac_assignments",
                       "rbac_roles", "security_events", "shared_memory"]
        for t in core_tables:
            assert t in tables, f"Expected table '{t}' not found"
        # Enterprise schema adds many more tables
        assert len(tables) >= 7
        mgr.close_all()

    def test_init_instance_schema(self, tmp_path):
        config_file = self._make_config(tmp_path)
        mgr = StorageManager(config_path=config_file)
        mgr.init_instance_schema()
        db = mgr.get_instance_db()
        tables = db.get_tables()
        assert "local_config" in tables
        assert "local_logs" in tables
        # Enterprise schema adds conversations, messages, llm_requests, etc.
        assert len(tables) >= 2
        mgr.close_all()

    def test_test_connection(self, tmp_path):
        # Test with non-existent file (will be created on deploy)
        config = {"engine": "sqlite", "path": str(tmp_path / "test_conn.db")}
        result = StorageManager.test_connection(config)
        assert result["success"] is True
        assert result["db_exists"] is False
        assert "will be created" in result["message"]

        # Test with existing file
        db = SQLiteBackend(str(tmp_path / "existing.db"))
        db.execute("CREATE TABLE test (id INTEGER)")
        db.close()
        config2 = {"engine": "sqlite", "path": str(tmp_path / "existing.db")}
        result2 = StorageManager.test_connection(config2)
        assert result2["success"] is True
        assert result2["db_exists"] is True
        assert "exists" in result2["message"]

    def test_get_all_databases_info(self, tmp_path):
        config_file = self._make_config(tmp_path, shared_enabled=True)
        mgr = StorageManager(config_path=config_file)
        mgr.init_instance_schema()
        mgr.init_shared_schema()
        info = mgr.get_all_databases_info()
        assert len(info) == 2
        names = [d["name"] for d in info]
        assert "instance" in names
        assert "shared" in names
        mgr.close_all()

    def test_save_config(self, tmp_path):
        config_file = self._make_config(tmp_path)
        mgr = StorageManager(config_path=config_file)
        new_config = {
            "engine": "sqlite",
            "instance_db": {"engine": "sqlite", "path": str(tmp_path / "new_inst.db")},
            "shared_db": {"enabled": True, "engine": "sqlite", "path": str(tmp_path / "new_shared.db")},
        }
        mgr.save_config(new_config)
        assert mgr.config["shared_db"]["enabled"] is True
        # Verify file was written
        loaded = json.loads(config_file.read_text())
        assert loaded["shared_db"]["enabled"] is True
        mgr.close_all()

    def test_get_health_all(self, tmp_path):
        config_file = self._make_config(tmp_path, shared_enabled=True)
        mgr = StorageManager(config_path=config_file)
        mgr.init_instance_schema()
        mgr.init_shared_schema()
        health = mgr.get_health_all()
        assert "instance" in health
        assert health["instance"]["status"] == "healthy"
        assert "shared" in health
        assert health["shared"]["status"] == "healthy"
        mgr.close_all()

    def test_default_config_when_no_file(self, tmp_path):
        nonexistent = tmp_path / "does_not_exist.json"
        mgr = StorageManager(config_path=nonexistent)
        assert mgr.config["engine"] == "sqlite"
        assert mgr.config["shared_db"]["enabled"] is False
        mgr.close_all()


# =========================================================================
#  TestRBACManager
# =========================================================================
class TestRBACManager:
    """Test RBAC role management and permission checking."""

    def _setup_rbac(self, tmp_path):
        db_path = tmp_path / "rbac_test.db"
        backend = SQLiteBackend(str(db_path))
        # Create schema
        from claw_storage import SHARED_SCHEMA_SQL
        for stmt in SHARED_SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                backend.execute(stmt)
        rbac = RBACManager(backend)
        return backend, rbac

    def test_init_builtin_roles(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        roles = rbac.list_roles()
        assert len(roles) == 4
        role_names = {r["name"] for r in roles}
        assert role_names == {"admin", "operator", "viewer", "agent"}
        backend.close()

    def test_init_builtin_roles_idempotent(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        rbac.init_builtin_roles()  # second call should not error
        roles = rbac.list_roles()
        assert len(roles) == 4
        backend.close()

    def test_assign_role(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        # Create an agent
        backend.execute(
            "INSERT INTO agents (id, name, platform) VALUES (?, ?, ?)",
            ("agent-1", "TestAgent", "zeroclaw"),
        )
        result = rbac.assign_role("agent-1", "viewer")
        assert result["success"] is True
        assert "assignment_id" in result
        backend.close()

    def test_assign_nonexistent_role(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        backend.execute(
            "INSERT INTO agents (id, name, platform) VALUES (?, ?, ?)",
            ("agent-1", "TestAgent", "zeroclaw"),
        )
        result = rbac.assign_role("agent-1", "nonexistent")
        assert result["success"] is False
        backend.close()

    def test_check_permission_viewer_read_only(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        backend.execute(
            "INSERT INTO agents (id, name, platform) VALUES (?, ?, ?)",
            ("agent-1", "TestAgent", "zeroclaw"),
        )
        rbac.assign_role("agent-1", "viewer")
        # Viewer can read
        assert rbac.check_permission("agent-1", "memory", "read") is True
        assert rbac.check_permission("agent-1", "costs", "read") is True
        # Viewer cannot write
        assert rbac.check_permission("agent-1", "memory", "write") is False
        assert rbac.check_permission("agent-1", "costs", "delete") is False
        backend.close()

    def test_check_permission_admin_full_access(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        backend.execute(
            "INSERT INTO agents (id, name, platform) VALUES (?, ?, ?)",
            ("agent-1", "TestAgent", "zeroclaw"),
        )
        rbac.assign_role("agent-1", "admin")
        # Admin has full access to everything
        for resource in ["memory", "costs", "security_events", "config", "rbac"]:
            for action in ["read", "write", "delete"]:
                assert rbac.check_permission("agent-1", resource, action) is True
        backend.close()

    def test_check_permission_agent_role(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        backend.execute(
            "INSERT INTO agents (id, name, platform) VALUES (?, ?, ?)",
            ("agent-1", "TestAgent", "zeroclaw"),
        )
        rbac.assign_role("agent-1", "agent")
        # Agent can read+write memory and costs
        assert rbac.check_permission("agent-1", "memory", "read") is True
        assert rbac.check_permission("agent-1", "memory", "write") is True
        # Agent can read config but not write
        assert rbac.check_permission("agent-1", "config", "read") is True
        assert rbac.check_permission("agent-1", "config", "write") is False
        # Agent has no RBAC permissions
        assert rbac.check_permission("agent-1", "rbac", "read") is False
        backend.close()

    def test_check_permission_unassigned_agent(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        # Agent with no role assignment
        assert rbac.check_permission("unknown-agent", "memory", "read") is False
        backend.close()

    def test_list_assignments(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        backend.execute(
            "INSERT INTO agents (id, name, platform) VALUES (?, ?, ?)",
            ("agent-1", "Agent1", "zeroclaw"),
        )
        backend.execute(
            "INSERT INTO agents (id, name, platform) VALUES (?, ?, ?)",
            ("agent-2", "Agent2", "nanoclaw"),
        )
        rbac.assign_role("agent-1", "admin")
        rbac.assign_role("agent-2", "viewer")
        assignments = rbac.list_assignments()
        assert len(assignments) == 2
        agent_ids = {a["agent_id"] for a in assignments}
        assert agent_ids == {"agent-1", "agent-2"}
        backend.close()

    def test_reassign_role_replaces_existing(self, tmp_path):
        backend, rbac = self._setup_rbac(tmp_path)
        rbac.init_builtin_roles()
        backend.execute(
            "INSERT INTO agents (id, name, platform) VALUES (?, ?, ?)",
            ("agent-1", "TestAgent", "zeroclaw"),
        )
        rbac.assign_role("agent-1", "viewer")
        assert rbac.check_permission("agent-1", "memory", "write") is False
        # Reassign to admin
        rbac.assign_role("agent-1", "admin")
        assert rbac.check_permission("agent-1", "memory", "write") is True
        # Should only have one assignment
        assignments = rbac.list_assignments()
        agent_assignments = [a for a in assignments if a["agent_id"] == "agent-1"]
        assert len(agent_assignments) == 1
        backend.close()
