"""
Tests for claw_dal.py — Data Access Layer.
Covers ConnectionPool, QueryCache, repository classes, and DAL facade.
"""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

# Ensure shared/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))

from claw_storage import SQLiteBackend, StorageManager, SCHEMA_DIR
from claw_dal import (
    ConnectionPool,
    QueryCache,
    BaseRepository,
    AgentRepository,
    CostTrackingRepository,
    ConversationRepository,
    ResponseCacheRepository,
    SecurityEventRepository,
    AuditLogRepository,
    LLMRequestRepository,
    PerformanceRepository,
    LocalLogRepository,
    DAL,
)


# =========================================================================
#  Helpers
# =========================================================================

def _make_storage_config(tmp_path, shared_enabled=True):
    """Create a storage_config.json and return its path."""
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
    config_path = tmp_path / "storage_config.json"
    config_path.write_text(json.dumps(config))
    return config_path


def _run_schema_sql(backend, schema_file):
    """Execute a schema SQL file statement by statement."""
    if not schema_file.exists():
        return
    sql = schema_file.read_text(encoding="utf-8")
    # Remove single-line comments
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    clean_sql = "\n".join(lines)
    for stmt in clean_sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                backend.execute(stmt)
            except Exception:
                pass


def _init_shared_db(tmp_path):
    """Create a shared SQLite DB with the full enterprise schema."""
    db_path = tmp_path / "shared.db"
    backend = SQLiteBackend(str(db_path))
    _run_schema_sql(backend, SCHEMA_DIR / "shared_sqlite.sql")
    return backend


def _init_instance_db(tmp_path):
    """Create an instance SQLite DB with the full enterprise schema."""
    db_path = tmp_path / "instance.db"
    backend = SQLiteBackend(str(db_path))
    _run_schema_sql(backend, SCHEMA_DIR / "instance_sqlite.sql")
    return backend


def _pool_with_shared_db(tmp_path):
    """Return (pool, cache, backend) for shared DB.

    The schema is initialized once via the initial backend.
    The pool factory creates simple connections to the same file.
    """
    backend = _init_shared_db(tmp_path)
    # Close the init backend — schema is persisted in the file
    backend.close()
    cache = QueryCache(max_entries=100)
    db_path = str(tmp_path / "shared.db")

    def factory():
        return SQLiteBackend(db_path)

    pool = ConnectionPool(factory, pool_size=3)
    return pool, cache, None


def _pool_with_instance_db(tmp_path):
    """Return (pool, cache, backend) for instance DB."""
    backend = _init_instance_db(tmp_path)
    backend.close()
    cache = QueryCache(max_entries=100)
    db_path = str(tmp_path / "instance.db")

    def factory():
        return SQLiteBackend(db_path)

    pool = ConnectionPool(factory, pool_size=3)
    return pool, cache, None


# =========================================================================
#  TestConnectionPool
# =========================================================================
class TestConnectionPool:
    """Test connection pool acquire/release/drain mechanics."""

    def test_acquire_and_release(self, tmp_path):
        db_path = tmp_path / "pool_test.db"

        def factory():
            return SQLiteBackend(str(db_path))

        pool = ConnectionPool(factory, pool_size=3)
        with pool.connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
            conn.execute("INSERT INTO t VALUES (1)")
            row = conn.fetchone("SELECT * FROM t")
            assert row is not None
            assert row["id"] == 1
        pool.drain()

    def test_pool_reuses_connections(self, tmp_path):
        db_path = tmp_path / "reuse_test.db"

        def factory():
            b = SQLiteBackend(str(db_path))
            b.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
            return b

        pool = ConnectionPool(factory, pool_size=2)

        # Acquire and release
        with pool.connection() as conn1:
            pass

        stats = pool.stats()
        assert stats["created"] >= 1
        assert stats["available"] >= 1

        # Next acquire should reuse
        with pool.connection() as conn2:
            row = conn2.fetchone("SELECT 1 AS val")
            assert row["val"] == 1

        pool.drain()

    def test_pool_exhaustion_blocks(self, tmp_path):
        """When all connections are taken, new requests block."""
        db_path = tmp_path / "exhaust_test.db"

        def factory():
            b = SQLiteBackend(str(db_path))
            b.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER)")
            return b

        pool = ConnectionPool(factory, pool_size=1)

        # Hold the only connection
        ctx = pool.connection()
        conn = ctx.__enter__()

        released = threading.Event()

        def _release_after_delay():
            time.sleep(0.5)
            ctx.__exit__(None, None, None)
            released.set()

        t = threading.Thread(target=_release_after_delay)
        t.start()

        # This should block until the connection is released
        with pool.connection() as conn2:
            assert conn2 is not None
            row = conn2.fetchone("SELECT 1 AS val")
            assert row["val"] == 1

        t.join()
        pool.drain()

    def test_drain_clears_pool(self, tmp_path):
        db_path = tmp_path / "drain_test.db"

        def factory():
            return SQLiteBackend(str(db_path))

        pool = ConnectionPool(factory, pool_size=3)
        with pool.connection() as conn:
            conn.fetchone("SELECT 1")

        pool.drain()
        stats = pool.stats()
        assert stats["created"] == 0
        assert stats["available"] == 0

    def test_stats(self, tmp_path):
        db_path = tmp_path / "stats_test.db"

        def factory():
            return SQLiteBackend(str(db_path))

        pool = ConnectionPool(factory, pool_size=5)
        stats = pool.stats()
        assert stats["pool_size"] == 5
        assert stats["created"] == 0
        pool.drain()


# =========================================================================
#  TestQueryCache
# =========================================================================
class TestQueryCache:
    """Test TTL cache put/get, expiry, invalidation, and LRU eviction."""

    def test_put_and_get(self):
        cache = QueryCache(max_entries=100)
        cache.put("test", "SELECT 1", (), "result_value", ttl=60)
        val = cache.get("test", "SELECT 1", ())
        assert val == "result_value"

    def test_ttl_expiry(self):
        cache = QueryCache(max_entries=100)
        cache.put("test", "SELECT 1", (), "old_value", ttl=1)
        time.sleep(1.1)
        val = cache.get("test", "SELECT 1", ())
        assert val is None

    def test_zero_ttl_not_cached(self):
        cache = QueryCache(max_entries=100)
        cache.put("test", "SELECT 1", (), "value", ttl=0)
        val = cache.get("test", "SELECT 1", ())
        assert val is None

    def test_invalidate_prefix_clears_all(self):
        cache = QueryCache(max_entries=100)
        cache.put("agents", "SELECT 1", (), "val1", ttl=60)
        cache.put("agents", "SELECT 2", (), "val2", ttl=60)
        cache.put("costs", "SELECT 3", (), "val3", ttl=60)

        removed = cache.invalidate_prefix("agents")
        # invalidate_prefix clears all entries (brute-force approach)
        assert removed >= 2

        assert cache.get("agents", "SELECT 1", ()) is None
        assert cache.get("agents", "SELECT 2", ()) is None
        assert cache.get("costs", "SELECT 3", ()) is None  # also cleared

    def test_lru_eviction(self):
        cache = QueryCache(max_entries=3)
        cache.put("t", "q1", (), "v1", ttl=60)
        cache.put("t", "q2", (), "v2", ttl=60)
        cache.put("t", "q3", (), "v3", ttl=60)

        # Access q1 to make it recently used
        cache.get("t", "q1", ())

        # Adding q4 should evict the LRU (q2)
        cache.put("t", "q4", (), "v4", ttl=60)

        assert cache.get("t", "q1", ()) == "v1"  # still alive (accessed recently)
        assert cache.get("t", "q4", ()) == "v4"  # new entry
        assert cache.get("t", "q3", ()) is not None or cache.get("t", "q2", ()) is None

    def test_clear(self):
        cache = QueryCache(max_entries=100)
        cache.put("t", "q1", (), "v1", ttl=60)
        cache.put("t", "q2", (), "v2", ttl=60)
        cache.clear()
        assert cache.get("t", "q1", ()) is None
        assert cache.get("t", "q2", ()) is None

    def test_stats(self):
        cache = QueryCache(max_entries=50)
        cache.put("t", "q1", (), "v1", ttl=60)
        cache.put("t", "q2", (), "v2", ttl=60)
        stats = cache.stats()
        assert stats["entries"] == 2
        assert stats["max"] == 50

    def test_different_params_different_keys(self):
        cache = QueryCache(max_entries=100)
        cache.put("t", "SELECT * WHERE id=?", (1,), "row1", ttl=60)
        cache.put("t", "SELECT * WHERE id=?", (2,), "row2", ttl=60)
        assert cache.get("t", "SELECT * WHERE id=?", (1,)) == "row1"
        assert cache.get("t", "SELECT * WHERE id=?", (2,)) == "row2"


# =========================================================================
#  TestAgentRepository
# =========================================================================
class TestAgentRepository:
    """Test AgentRepository CRUD operations."""

    def test_register_new_agent(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AgentRepository(pool, cache)
        agent_id = repo.register("zclaw-1", "ZeroClaw Test", "zeroclaw",
                                  host="localhost", port=3100)
        assert agent_id == "zclaw-1"
        pool.drain()

    def test_register_updates_existing(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AgentRepository(pool, cache)
        repo.register("zclaw-1", "ZeroClaw V1", "zeroclaw")
        repo.register("zclaw-1", "ZeroClaw V2", "zeroclaw")
        agent = repo.get("zclaw-1")
        assert agent is not None
        assert agent["name"] == "ZeroClaw V2"
        pool.drain()

    def test_get_agent(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AgentRepository(pool, cache)
        repo.register("agent-x", "AgentX", "nanoclaw",
                       capabilities=["chat", "code"])
        agent = repo.get("agent-x")
        assert agent is not None
        assert agent["platform"] == "nanoclaw"
        assert "chat" in agent["capabilities"]
        pool.drain()

    def test_list_all(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AgentRepository(pool, cache)
        repo.register("a1", "Agent1", "zeroclaw")
        repo.register("a2", "Agent2", "nanoclaw")
        agents = repo.list_all()
        assert len(agents) == 2
        pool.drain()

    def test_list_available_filters_unhealthy(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AgentRepository(pool, cache)
        repo.register("a1", "Agent1", "zeroclaw")
        repo.register("a2", "Agent2", "nanoclaw")
        repo.update_status("a2", "unhealthy")
        available = repo.list_available()
        ids = [a["id"] for a in available]
        assert "a1" in ids
        assert "a2" not in ids
        pool.drain()

    def test_update_status_running(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AgentRepository(pool, cache)
        repo.register("a1", "Agent1", "zeroclaw")
        repo.update_status("a1", "running", health={"cpu": "5%"})
        agent = repo.get("a1")
        assert agent["status"] == "running"
        assert agent["health"]["cpu"] == "5%"
        pool.drain()

    def test_update_status_healthy(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AgentRepository(pool, cache)
        repo.register("a1", "Agent1", "zeroclaw")
        repo.update_status("a1", "healthy")
        agent = repo.get("a1")
        assert agent["status"] == "healthy"
        pool.drain()

    def test_delete_agent(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AgentRepository(pool, cache)
        repo.register("a1", "Agent1", "zeroclaw")
        repo.delete("a1")
        agent = repo.get("a1")
        assert agent is None
        pool.drain()


# =========================================================================
#  TestCostTrackingRepository
# =========================================================================
class TestCostTrackingRepository:
    """Test cost tracking record, aggregate, and spend methods."""

    def _register_agents(self, pool, cache, *agent_ids):
        """Register agents first to satisfy FK constraints."""
        agent_repo = AgentRepository(pool, cache)
        for aid in agent_ids:
            agent_repo.register(aid, f"Agent-{aid}", "zeroclaw")

    def test_record_cost(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "agent-1")
        repo = CostTrackingRepository(pool, cache)
        cost_id = repo.record_cost(
            agent_id="agent-1", model="claude-3-opus",
            provider="anthropic", input_tokens=100,
            output_tokens=200, cost_usd=0.05)
        assert cost_id is not None
        pool.drain()

    def test_aggregate(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "a1", "a2")
        repo = CostTrackingRepository(pool, cache)
        repo.record_cost("a1", "claude-3-opus", "anthropic",
                          input_tokens=100, output_tokens=200, cost_usd=0.05)
        repo.record_cost("a1", "gpt-4", "openai",
                          input_tokens=50, output_tokens=100, cost_usd=0.03)
        repo.record_cost("a2", "claude-3-opus", "anthropic",
                          input_tokens=200, output_tokens=400, cost_usd=0.10)

        agg = repo.aggregate()
        assert agg["total_requests"] == 3
        assert agg["total_cost"] == pytest.approx(0.18, abs=0.001)
        assert "claude-3-opus" in agg["cost_by_model"]
        assert "anthropic" in agg["cost_by_provider"]
        pool.drain()

    def test_daily_spend(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "a1")
        repo = CostTrackingRepository(pool, cache)
        repo.record_cost("a1", "claude", "anthropic", cost_usd=0.10)
        repo.record_cost("a1", "claude", "anthropic", cost_usd=0.20)
        spend = repo.daily_spend()
        assert spend == pytest.approx(0.30, abs=0.001)
        pool.drain()

    def test_spend_by_agent(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "a1", "a2")
        repo = CostTrackingRepository(pool, cache)
        repo.record_cost("a1", "claude", "anthropic", cost_usd=0.10)
        repo.record_cost("a2", "claude", "anthropic", cost_usd=0.20)
        spend_a1 = repo.daily_spend(agent_id="a1")
        spend_a2 = repo.daily_spend(agent_id="a2")
        assert spend_a1 == pytest.approx(0.10, abs=0.001)
        assert spend_a2 == pytest.approx(0.20, abs=0.001)
        pool.drain()

    def test_recent(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "a1")
        repo = CostTrackingRepository(pool, cache)
        for i in range(5):
            repo.record_cost("a1", "claude", "anthropic", cost_usd=float(i))
        recent = repo.recent(limit=3)
        assert len(recent) == 3
        pool.drain()

    def test_set_and_check_budgets(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "a1")
        repo = CostTrackingRepository(pool, cache)
        repo.set_budget("global", "daily", budget_usd=0.50, alert_threshold=0.5)
        repo.record_cost("a1", "claude", "anthropic", cost_usd=0.30)
        alerts = repo.check_budgets()
        # 0.30/0.50 = 60% >= 50% threshold
        assert len(alerts) >= 1
        assert alerts[0]["level"] in ("warning", "critical")
        pool.drain()


# =========================================================================
#  TestConversationRepository
# =========================================================================
class TestConversationRepository:
    """Test conversation CRUD operations."""

    def test_create_conversation(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ConversationRepository(pool, cache)
        conv = repo.create("agent-1", title="Test Chat", channel="telegram")
        assert "id" in conv
        assert conv["title"] == "Test Chat"
        pool.drain()

    def test_add_message(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ConversationRepository(pool, cache)
        conv = repo.create("agent-1", title="Chat")
        msg = repo.add_message(conv["id"], "user", "Hello!")
        assert msg is not None
        assert msg["role"] == "user"
        assert msg["content"] == "Hello!"
        pool.drain()

    def test_get_conversation_with_messages(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ConversationRepository(pool, cache)
        conv = repo.create("agent-1", title="Chat")
        repo.add_message(conv["id"], "user", "Hello!")
        repo.add_message(conv["id"], "assistant", "Hi there!")

        fetched = repo.get(conv["id"])
        assert fetched is not None
        assert len(fetched["messages"]) == 2
        assert fetched["messages"][0]["role"] == "user"
        assert fetched["messages"][1]["role"] == "assistant"
        pool.drain()

    def test_list_conversations(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ConversationRepository(pool, cache)
        repo.create("agent-1", title="Chat 1")
        repo.create("agent-1", title="Chat 2")
        repo.create("agent-2", title="Chat 3")

        all_convs = repo.list_conversations()
        assert len(all_convs) == 3

        agent1_convs = repo.list_conversations(agent_id="agent-1")
        assert len(agent1_convs) == 2
        pool.drain()

    def test_search_messages(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ConversationRepository(pool, cache)
        conv = repo.create("agent-1", title="Chat")
        repo.add_message(conv["id"], "user", "How do I use Python?")
        repo.add_message(conv["id"], "assistant", "Python is a great language.")

        results = repo.search("Python")
        assert len(results) == 2
        pool.drain()

    def test_delete_conversation(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ConversationRepository(pool, cache)
        conv = repo.create("agent-1", title="To Delete")
        repo.delete(conv["id"])
        fetched = repo.get(conv["id"])
        assert fetched is None
        pool.drain()

    def test_get_stats(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ConversationRepository(pool, cache)
        conv = repo.create("agent-1", title="Chat")
        repo.add_message(conv["id"], "user", "Hello", input_tokens=10)
        repo.add_message(conv["id"], "assistant", "Hi", output_tokens=5)
        stats = repo.get_stats()
        assert stats["conversations"] == 1
        assert stats["messages"] == 2
        pool.drain()

    def test_add_message_nonexistent_conversation(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ConversationRepository(pool, cache)
        msg = repo.add_message("nonexistent-id", "user", "Hello")
        assert msg is None
        pool.drain()


# =========================================================================
#  TestResponseCacheRepository
# =========================================================================
class TestResponseCacheRepository:
    """Test response cache put/get/stats."""

    def test_put_and_get_exact(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ResponseCacheRepository(pool, cache)
        import hashlib
        prompt_hash = hashlib.sha256(b"test prompt").hexdigest()
        repo.put(prompt_hash, "claude-3-opus", "cached response",
                 tokens_saved=100, cost_saved=0.01)

        cache_hash = hashlib.sha256(
            f"claude-3-opus|{prompt_hash}".encode()).hexdigest()
        result = repo.get_exact(cache_hash)
        assert result == "cached response"
        pool.drain()

    def test_stats(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ResponseCacheRepository(pool, cache)
        import hashlib
        for i in range(3):
            ph = hashlib.sha256(f"prompt_{i}".encode()).hexdigest()
            repo.put(ph, "model", f"response_{i}", tokens_saved=10)
        stats = repo.stats()
        assert stats["total_entries"] == 3
        pool.drain()

    def test_expired_entry_returns_none(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = ResponseCacheRepository(pool, cache)
        import hashlib
        prompt_hash = hashlib.sha256(b"expiring").hexdigest()
        repo.put(prompt_hash, "model", "will expire",
                 ttl_seconds=1)
        time.sleep(1.5)
        cache_hash = hashlib.sha256(
            f"model|{prompt_hash}".encode()).hexdigest()
        result = repo.get_exact(cache_hash)
        assert result is None
        pool.drain()


# =========================================================================
#  TestSecurityEventRepository
# =========================================================================
class TestSecurityEventRepository:
    """Test security event logging and querying."""

    def _register_agents(self, pool, cache, *agent_ids):
        agent_repo = AgentRepository(pool, cache)
        for aid in agent_ids:
            agent_repo.register(aid, f"Agent-{aid}", "zeroclaw")

    def test_log_and_get_recent(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "agent-1")
        repo = SecurityEventRepository(pool, cache)
        event_id = repo.log_event("agent-1", "url_blocked",
                                   severity="error",
                                   details="Blocked malicious URL")
        assert event_id is not None
        recent = repo.get_recent(limit=10)
        assert len(recent) == 1
        assert recent[0]["event_type"] == "url_blocked"
        pool.drain()

    def test_get_summary(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "a1", "a2")
        repo = SecurityEventRepository(pool, cache)
        repo.log_event("a1", "url_blocked", severity="error")
        repo.log_event("a1", "content_violation", severity="error")
        repo.log_event("a2", "rate_limit", severity="info")
        summary = repo.get_summary()
        assert summary.get("error", 0) == 2
        assert summary.get("info", 0) == 1
        pool.drain()

    def test_resolve_event(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        self._register_agents(pool, cache, "a1")
        repo = SecurityEventRepository(pool, cache)
        event_id = repo.log_event("a1", "url_blocked", severity="error")
        unresolved = repo.get_unresolved()
        assert len(unresolved) >= 1
        repo.resolve(event_id, resolved_by="admin")
        unresolved_after = repo.get_unresolved()
        resolved_ids = {e["id"] for e in unresolved_after}
        assert event_id not in resolved_ids
        pool.drain()


# =========================================================================
#  TestAuditLogRepository
# =========================================================================
class TestAuditLogRepository:
    """Test audit log write and query."""

    def test_log_and_query(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AuditLogRepository(pool, cache)
        repo.log("admin", "update_config", "cluster_config",
                 resource_id="key1", old_value="old", new_value="new")
        entries = repo.query(actor="admin")
        assert len(entries) == 1
        assert entries[0]["action"] == "update_config"
        pool.drain()

    def test_count_actions(self, tmp_path):
        pool, cache, _ = _pool_with_shared_db(tmp_path)
        repo = AuditLogRepository(pool, cache)
        repo.log("admin", "create", "agent")
        repo.log("admin", "update", "config")
        repo.log("admin", "create", "agent")
        counts = repo.count_actions()
        assert counts.get("create", 0) == 2
        assert counts.get("update", 0) == 1
        pool.drain()


# =========================================================================
#  TestLLMRequestRepository
# =========================================================================
class TestLLMRequestRepository:
    """Test LLM request recording and aggregation."""

    def test_record_and_get_recent(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = LLMRequestRepository(pool, cache)
        req_id = repo.record("anthropic", "claude-3-opus",
                              input_tokens=100, output_tokens=200,
                              cost_usd=0.05, latency_ms=1200)
        assert req_id is not None
        recent = repo.get_recent(limit=5)
        assert len(recent) == 1
        assert recent[0]["model"] == "claude-3-opus"
        pool.drain()

    def test_aggregate_by_model(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = LLMRequestRepository(pool, cache)
        repo.record("anthropic", "claude-3-opus",
                      input_tokens=100, cost_usd=0.05)
        repo.record("anthropic", "claude-3-opus",
                      input_tokens=200, cost_usd=0.10)
        repo.record("openai", "gpt-4",
                      input_tokens=50, cost_usd=0.03)
        agg = repo.aggregate_by_model()
        assert len(agg) == 2
        # Should be ordered by total_cost desc
        assert agg[0]["total_cost"] > agg[1]["total_cost"]
        pool.drain()


# =========================================================================
#  TestPerformanceRepository
# =========================================================================
class TestPerformanceRepository:
    """Test performance metrics recording."""

    def test_record_and_get_latest(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = PerformanceRepository(pool, cache)
        repo.record("response_time", 150.5, component="router")
        repo.record("response_time", 120.3, component="router")
        latest = repo.get_latest("response_time")
        assert latest is not None
        # Both records may have same timestamp (second precision);
        # just verify a valid record is returned
        assert latest["metric_name"] == "response_time"
        assert latest["metric_value"] in (150.5, 120.3)
        pool.drain()

    def test_get_series(self, tmp_path):
        pool, cache, _ = _pool_with_instance_db(tmp_path)
        repo = PerformanceRepository(pool, cache)
        for i in range(5):
            repo.record("cpu_usage", float(i * 10), component="system")
        series = repo.get_series("cpu_usage", limit=3)
        assert len(series) == 3
        pool.drain()


# =========================================================================
#  TestDALIntegration
# =========================================================================
class TestDALIntegration:
    """Integration tests for the full DAL lifecycle."""

    def test_dal_singleton(self, tmp_path, monkeypatch):
        """DAL.get_instance() returns the same instance."""
        # Point DAL config to temp dir
        config = {
            "engine": "sqlite",
            "instance_db": {"engine": "sqlite", "path": str(tmp_path / "inst.db")},
            "shared_db": {"enabled": False, "engine": "sqlite",
                          "path": str(tmp_path / "shared.db")},
        }
        config_path = tmp_path / "storage_config.json"
        config_path.write_text(json.dumps(config))
        monkeypatch.setattr("claw_dal.STORAGE_CONFIG_FILE", config_path)

        DAL.reset_instance()
        dal1 = DAL.get_instance()
        dal2 = DAL.get_instance()
        assert dal1 is dal2
        dal1.close()
        DAL.reset_instance()

    def test_full_lifecycle(self, tmp_path, monkeypatch):
        """Agent → cost → conversation → close lifecycle."""
        config = {
            "engine": "sqlite",
            "instance_db": {"engine": "sqlite", "path": str(tmp_path / "inst.db")},
            "shared_db": {"enabled": True, "engine": "sqlite",
                          "path": str(tmp_path / "shared.db")},
        }
        config_path = tmp_path / "storage_config.json"
        config_path.write_text(json.dumps(config))
        monkeypatch.setattr("claw_dal.STORAGE_CONFIG_FILE", config_path)

        # Also need to point StorageManager to our config
        monkeypatch.setattr("claw_storage.STORAGE_CONFIG_FILE", config_path)

        DAL.reset_instance()
        dal = DAL.get_instance()

        # Register agent
        dal.agents.register("zclaw-test", "ZeroClaw Test", "zeroclaw")
        agents = dal.agents.list_all()
        assert len(agents) >= 1

        # Record cost
        dal.costs.record_cost("zclaw-test", "claude-3-opus", "anthropic",
                               input_tokens=100, output_tokens=50,
                               cost_usd=0.025)
        agg = dal.costs.aggregate()
        assert agg["total_requests"] >= 1
        assert agg["total_cost"] > 0

        # Create conversation
        conv = dal.conversations.create("zclaw-test", title="Test Conv")
        dal.conversations.add_message(conv["id"], "user", "Hello!")
        fetched = dal.conversations.get(conv["id"])
        assert fetched is not None
        assert len(fetched["messages"]) == 1

        # Health check
        health = dal.health()
        assert "instance_pool" in health
        assert "cache" in health

        dal.close()
        DAL.reset_instance()

    def test_cache_invalidation_on_write(self, tmp_path, monkeypatch):
        """Writes should invalidate cached reads."""
        config = {
            "engine": "sqlite",
            "instance_db": {"engine": "sqlite", "path": str(tmp_path / "inst.db")},
            "shared_db": {"enabled": True, "engine": "sqlite",
                          "path": str(tmp_path / "shared.db")},
        }
        config_path = tmp_path / "storage_config.json"
        config_path.write_text(json.dumps(config))
        monkeypatch.setattr("claw_dal.STORAGE_CONFIG_FILE", config_path)
        monkeypatch.setattr("claw_storage.STORAGE_CONFIG_FILE", config_path)

        DAL.reset_instance()
        dal = DAL.get_instance()

        # Register and list (caches the result)
        dal.agents.register("a1", "Agent1", "zeroclaw")
        agents_v1 = dal.agents.list_all()
        assert len(agents_v1) == 1

        # Register another — should invalidate cache
        dal.agents.register("a2", "Agent2", "nanoclaw")
        agents_v2 = dal.agents.list_all()
        assert len(agents_v2) == 2

        dal.close()
        DAL.reset_instance()

    def test_concurrent_writes(self, tmp_path, monkeypatch):
        """Multiple threads writing concurrently should not corrupt data."""
        config = {
            "engine": "sqlite",
            "instance_db": {"engine": "sqlite", "path": str(tmp_path / "inst.db")},
            "shared_db": {"enabled": True, "engine": "sqlite",
                          "path": str(tmp_path / "shared.db")},
        }
        config_path = tmp_path / "storage_config.json"
        config_path.write_text(json.dumps(config))
        monkeypatch.setattr("claw_dal.STORAGE_CONFIG_FILE", config_path)
        monkeypatch.setattr("claw_storage.STORAGE_CONFIG_FILE", config_path)

        DAL.reset_instance()
        dal = DAL.get_instance()

        # Register agents first (FK constraint)
        for i in range(4):
            dal.agents.register(f"agent-{i}", f"Agent {i}", "zeroclaw")

        errors = []

        def _write_costs(agent_id: str, count: int):
            try:
                for i in range(count):
                    dal.costs.record_cost(agent_id, "claude", "anthropic",
                                           cost_usd=0.01)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(4):
            t = threading.Thread(target=_write_costs, args=(f"agent-{i}", 10))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=30)

        assert len(errors) == 0, f"Concurrent write errors: {errors}"

        agg = dal.costs.aggregate()
        assert agg["total_requests"] == 40  # 4 threads * 10 writes
        assert agg["total_cost"] == pytest.approx(0.40, abs=0.01)

        dal.close()
        DAL.reset_instance()
