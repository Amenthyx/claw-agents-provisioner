#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Data Access Layer (DAL)
=============================================================================
Unified data access for all XClaw services.  Consolidates 7+ separate
databases/files into the enterprise instance + shared databases with
connection pooling and TTL-based read caching.

Usage:
    from claw_dal import DAL
    dal = DAL.get_instance()
    dal.agents.register("zeroclaw", ...)
    dal.costs.record_cost(...)
    dal.conversations.add_message(...)
    dal.close()

Python 3.8+ stdlib only.
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import hashlib
import json
import queue
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths (same as claw_storage.py)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
STORAGE_CONFIG_FILE = PROJECT_ROOT / "data" / "wizard" / "storage_config.json"
DEFAULT_INSTANCE_DB = PROJECT_ROOT / "data" / "instance.db"
DEFAULT_SHARED_DB = PROJECT_ROOT / "data" / "shared" / "shared.db"

GREEN = "\033[0;32m"
NC = "\033[0m"


def _log(msg: str) -> None:
    print(f"{GREEN}[dal]{NC} {msg}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uuid() -> str:
    return str(uuid.uuid4())


# =========================================================================
#  ConnectionPool
# =========================================================================
class ConnectionPool:
    """Thread-safe connection pool wrapping StorageBackend instances.

    Uses a stdlib ``queue.Queue`` as the pool backing store.  Each call to
    ``connection()`` acquires a backend; the context manager releases it
    automatically.
    """

    def __init__(self, backend_factory, pool_size: int = 5):
        """
        Args:
            backend_factory: callable that returns a new StorageBackend.
            pool_size: max simultaneous connections.
        """
        self._factory = backend_factory
        self._pool: queue.Queue = queue.Queue(maxsize=pool_size)
        self._size = pool_size
        self._created = 0
        self._lock = threading.Lock()

    class _Ctx:
        """Context manager that auto-releases the connection."""
        def __init__(self, pool: "ConnectionPool"):
            self._pool = pool
            self.conn = None

        def __enter__(self):
            self.conn = self._pool._acquire()
            return self.conn

        def __exit__(self, *exc):
            if self.conn is not None:
                self._pool._release(self.conn)
            return False

    def connection(self) -> "_Ctx":
        return self._Ctx(self)

    def _acquire(self):
        # Try to get an existing connection from the pool (non-blocking)
        try:
            conn = self._pool.get_nowait()
            # Validate
            try:
                conn.fetchone("SELECT 1")
                return conn
            except Exception:
                # Dead connection — create new one
                with self._lock:
                    self._created -= 1
        except queue.Empty:
            pass

        # Create a new connection if room
        with self._lock:
            if self._created < self._size:
                self._created += 1
                conn = self._factory()
                return conn

        # Pool exhausted — block until one is returned (timeout 30s)
        try:
            conn = self._pool.get(timeout=30)
            try:
                conn.fetchone("SELECT 1")
                return conn
            except Exception:
                with self._lock:
                    self._created -= 1
                    self._created += 1
                return self._factory()
        except queue.Empty:
            raise RuntimeError("Connection pool exhausted (30s timeout)")

    def _release(self, conn) -> None:
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            # Pool full — close excess connection
            try:
                conn.close()
            except Exception:
                pass
            with self._lock:
                self._created -= 1

    def drain(self) -> None:
        """Close all pooled connections."""
        while True:
            try:
                conn = self._pool.get_nowait()
                try:
                    conn.close()
                except Exception:
                    pass
            except queue.Empty:
                break
        with self._lock:
            self._created = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "pool_size": self._size,
                "created": self._created,
                "available": self._pool.qsize(),
            }


# =========================================================================
#  QueryCache — Thread-safe TTL cache with LRU eviction
# =========================================================================
class QueryCache:
    """In-memory TTL cache for read queries.

    - Key: SHA-256(prefix + sql + params)
    - Max 2000 entries, LRU eviction when full
    - Background cleanup thread every 60s
    """

    def __init__(self, max_entries: int = 2000, cleanup_interval: int = 60):
        self._max = max_entries
        self._lock = threading.Lock()
        # key -> (value, expires_at, last_access)
        self._store: Dict[str, Tuple[Any, float, float]] = {}
        self._cleanup_interval = cleanup_interval
        self._cleaner: Optional[threading.Thread] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._cleaner = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleaner.start()

    def stop(self) -> None:
        self._running = False

    def _cleanup_loop(self) -> None:
        while self._running:
            time.sleep(self._cleanup_interval)
            self._evict_expired()

    def _cache_key(self, prefix: str, sql: str, params: tuple) -> str:
        raw = f"{prefix}|{sql}|{json.dumps(params, default=str)}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, prefix: str, sql: str, params: tuple) -> Optional[Any]:
        key = self._cache_key(prefix, sql, params)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at, _ = entry
            if expires_at > 0 and time.monotonic() > expires_at:
                del self._store[key]
                return None
            # Update last access
            self._store[key] = (value, expires_at, time.monotonic())
            return value

    def put(self, prefix: str, sql: str, params: tuple, value: Any, ttl: int) -> None:
        if ttl <= 0:
            return  # TTL=0 means don't cache
        key = self._cache_key(prefix, sql, params)
        expires_at = time.monotonic() + ttl
        with self._lock:
            if len(self._store) >= self._max:
                self._evict_lru()
            self._store[key] = (value, expires_at, time.monotonic())

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all entries whose key was generated with this prefix."""
        # We can't recover the prefix from the hash, so we store a
        # secondary index.  For simplicity, we just clear everything
        # matching the prefix.  Since writes are infrequent vs reads,
        # a full scan is acceptable.
        # Alternative: maintain a prefix -> [keys] dict.
        # For now, we use a brute-force approach that still beats
        # re-querying the DB.
        removed = 0
        with self._lock:
            # We rebuild the store without matching prefixes
            to_del = []
            for k in self._store:
                # We cannot reverse the hash, so we store prefix in a
                # separate structure.  Let's switch to storing prefix
                # alongside the entry.
                pass
            # Simpler: clear all.  This is the safest approach.
            # Cost writes are rare compared to reads, so clearing is fine.
            removed = len(self._store)
            self._store.clear()
        return removed

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def _evict_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (_, exp, _) in self._store.items()
                       if exp > 0 and now > exp]
            for k in expired:
                del self._store[k]

    def _evict_lru(self) -> None:
        """Remove the least-recently-accessed entry (caller holds lock)."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][2])
        del self._store[oldest_key]

    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {"entries": len(self._store), "max": self._max}


# =========================================================================
#  BaseRepository
# =========================================================================
class BaseRepository:
    """Base class for all repository classes.

    Provides cached reads, auto-invalidating writes, and SQL
    normalization for SQLite/PostgreSQL portability.
    """

    # Subclasses set this to scope cache keys
    _table_prefix: str = ""

    def __init__(self, pool: ConnectionPool, cache: QueryCache,
                 is_postgres: bool = False):
        self._pool = pool
        self._cache = cache
        self._pg = is_postgres

    def _normalize_sql(self, sql: str) -> str:
        """Convert ``?`` placeholders to ``%s`` for PostgreSQL."""
        if self._pg:
            return sql.replace("?", "%s")
        return sql

    def _execute(self, sql: str, params: tuple = ()) -> Any:
        """Write operation — auto-invalidates cache for this table prefix."""
        sql = self._normalize_sql(sql)
        with self._pool.connection() as conn:
            result = conn.execute(sql, params)
        # Invalidate read cache after writes
        self._cache.invalidate_prefix(self._table_prefix)
        return result

    def _fetchone(self, sql: str, params: tuple = (),
                  ttl: int = 0) -> Optional[Dict[str, Any]]:
        """Single-row read with optional caching."""
        sql = self._normalize_sql(sql)
        if ttl > 0:
            cached = self._cache.get(self._table_prefix, sql, params)
            if cached is not None:
                return cached
        with self._pool.connection() as conn:
            result = conn.fetchone(sql, params)
        if ttl > 0 and result is not None:
            self._cache.put(self._table_prefix, sql, params, result, ttl)
        return result

    def _fetchall(self, sql: str, params: tuple = (),
                  ttl: int = 0) -> List[Dict[str, Any]]:
        """Multi-row read with optional caching."""
        sql = self._normalize_sql(sql)
        if ttl > 0:
            cached = self._cache.get(self._table_prefix, sql, params)
            if cached is not None:
                return cached
        with self._pool.connection() as conn:
            result = conn.fetchall(sql, params)
        if ttl > 0:
            self._cache.put(self._table_prefix, sql, params, result, ttl)
        return result


# =========================================================================
#  Shared DB Repositories
# =========================================================================

class AgentRepository(BaseRepository):
    """CRUD for the ``agents`` table (shared DB)."""
    _table_prefix = "agents"

    def register(self, agent_id: str, name: str, platform: str,
                 host: str = "localhost", port: int = 0,
                 capabilities: Optional[List[str]] = None,
                 version: str = "") -> str:
        existing = self._fetchone(
            "SELECT id FROM agents WHERE id = ?", (agent_id,))
        now = _now_iso()
        caps = json.dumps(capabilities or [])
        if existing:
            self._execute(
                "UPDATE agents SET name=?, platform=?, host=?, port=?, "
                "capabilities=?, version=?, updated_at=? WHERE id=?",
                (name, platform, host, port, caps, version, now, agent_id))
        else:
            self._execute(
                "INSERT INTO agents (id, name, platform, host, port, status, "
                "capabilities, version, health, last_seen, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (agent_id, name, platform, host, port, "unknown",
                 caps, version, "{}", now, now, now))
        return agent_id

    def update_status(self, agent_id: str, status: str,
                      health: Optional[Dict] = None) -> bool:
        now = _now_iso()
        health_json = json.dumps(health) if health else None
        if health_json:
            self._execute(
                "UPDATE agents SET status=?, health=?, last_seen=?, updated_at=? "
                "WHERE id=?",
                (status, health_json, now, now, agent_id))
        else:
            self._execute(
                "UPDATE agents SET status=?, last_seen=?, updated_at=? WHERE id=?",
                (status, now, now, agent_id))
        return True

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        row = self._fetchone("SELECT * FROM agents WHERE id = ?",
                             (agent_id,), ttl=10)
        if row and isinstance(row.get("capabilities"), str):
            try:
                row["capabilities"] = json.loads(row["capabilities"])
            except (json.JSONDecodeError, TypeError):
                row["capabilities"] = []
        if row and isinstance(row.get("health"), str):
            try:
                row["health"] = json.loads(row["health"])
            except (json.JSONDecodeError, TypeError):
                row["health"] = {}
        return row

    def list_all(self) -> List[Dict[str, Any]]:
        rows = self._fetchall("SELECT * FROM agents ORDER BY name", ttl=10)
        for r in rows:
            if isinstance(r.get("capabilities"), str):
                try:
                    r["capabilities"] = json.loads(r["capabilities"])
                except (json.JSONDecodeError, TypeError):
                    r["capabilities"] = []
            if isinstance(r.get("health"), str):
                try:
                    r["health"] = json.loads(r["health"])
                except (json.JSONDecodeError, TypeError):
                    r["health"] = {}
        return rows

    def list_available(self, capability: Optional[str] = None) -> List[Dict[str, Any]]:
        agents = self.list_all()
        available = []
        for a in agents:
            if a.get("status") == "unhealthy":
                continue
            if capability and capability not in a.get("capabilities", []):
                continue
            available.append(a)
        return available

    def delete(self, agent_id: str) -> bool:
        self._execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        return True


class CostTrackingRepository(BaseRepository):
    """CRUD for ``cost_tracking`` + ``cost_budgets`` tables (shared DB)."""
    _table_prefix = "costs"

    def record_cost(self, agent_id: str, model: str, provider: str,
                    input_tokens: int = 0, output_tokens: int = 0,
                    cost_usd: float = 0.0, endpoint: str = "",
                    cache_savings: float = 0.0,
                    avg_latency_ms: float = 0.0) -> str:
        cost_id = _uuid()
        total = input_tokens + output_tokens
        self._execute(
            "INSERT INTO cost_tracking (id, agent_id, model, provider, endpoint, "
            "input_tokens, output_tokens, total_tokens, cost_usd, cache_savings, "
            "avg_latency_ms, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (cost_id, agent_id, model, provider, endpoint,
             input_tokens, output_tokens, total, cost_usd,
             cache_savings, avg_latency_ms, _now_iso()))
        return cost_id

    def _sum_since(self, since_iso: str,
                   agent_id: Optional[str] = None) -> float:
        if agent_id:
            row = self._fetchone(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total "
                "FROM cost_tracking WHERE timestamp >= ? AND agent_id = ?",
                (since_iso, agent_id))
        else:
            row = self._fetchone(
                "SELECT COALESCE(SUM(cost_usd), 0) AS total "
                "FROM cost_tracking WHERE timestamp >= ?",
                (since_iso,))
        return row["total"] if row else 0.0

    def daily_spend(self, agent_id: Optional[str] = None) -> float:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
        return self._sum_since(today, agent_id)

    def weekly_spend(self, agent_id: Optional[str] = None) -> float:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=now.weekday())).strftime(
            "%Y-%m-%dT00:00:00Z")
        return self._sum_since(start, agent_id)

    def monthly_spend(self, agent_id: Optional[str] = None) -> float:
        start = datetime.now(timezone.utc).strftime("%Y-%m-01T00:00:00Z")
        return self._sum_since(start, agent_id)

    def aggregate(self, since_iso: Optional[str] = None,
                  agent_id: Optional[str] = None) -> Dict[str, Any]:
        """Aggregate cost data for reporting."""
        conditions = []
        params: list = []
        if since_iso:
            conditions.append("timestamp >= ?")
            params.append(since_iso)
        if agent_id:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        row = self._fetchone(
            f"SELECT COALESCE(SUM(cost_usd),0) AS total_cost, "
            f"COALESCE(SUM(input_tokens),0) AS total_input, "
            f"COALESCE(SUM(output_tokens),0) AS total_output, "
            f"COUNT(*) AS total_requests, "
            f"COALESCE(AVG(avg_latency_ms),0) AS avg_response_ms "
            f"FROM cost_tracking {where}",
            tuple(params), ttl=60)

        if not row:
            return {"total_cost": 0, "total_requests": 0,
                    "total_input_tokens": 0, "total_output_tokens": 0,
                    "avg_response_ms": 0}

        # Cost by model
        model_rows = self._fetchall(
            f"SELECT model, SUM(cost_usd) AS cost, "
            f"SUM(input_tokens) AS inp, SUM(output_tokens) AS out, "
            f"COUNT(*) AS reqs "
            f"FROM cost_tracking {where} GROUP BY model ORDER BY cost DESC",
            tuple(params), ttl=60)

        # Cost by provider
        provider_rows = self._fetchall(
            f"SELECT provider, SUM(cost_usd) AS cost "
            f"FROM cost_tracking {where} GROUP BY provider ORDER BY cost DESC",
            tuple(params), ttl=60)

        # Cost by agent
        agent_rows = self._fetchall(
            f"SELECT agent_id, SUM(cost_usd) AS cost "
            f"FROM cost_tracking {where} GROUP BY agent_id ORDER BY cost DESC",
            tuple(params), ttl=60)

        return {
            "total_cost": round(row["total_cost"], 6),
            "total_requests": row["total_requests"],
            "total_input_tokens": row["total_input"],
            "total_output_tokens": row["total_output"],
            "avg_response_ms": round(row["avg_response_ms"], 1),
            "cost_by_model": {r["model"]: round(r["cost"], 6) for r in model_rows},
            "cost_by_provider": {r["provider"]: round(r["cost"], 6) for r in provider_rows},
            "cost_by_agent": {r["agent_id"]: round(r["cost"], 6) for r in agent_rows},
            "tokens_by_model": {
                r["model"]: {"input": r["inp"], "output": r["out"],
                             "requests": r["reqs"]}
                for r in model_rows
            },
        }

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM cost_tracking ORDER BY timestamp DESC LIMIT ?",
            (limit,))

    def set_budget(self, scope: str, period: str, budget_usd: float,
                   alert_threshold: float = 0.8,
                   action_on_limit: str = "alert") -> str:
        budget_id = _uuid()
        self._execute(
            "INSERT INTO cost_budgets (id, scope, period, budget_usd, "
            "alert_threshold, action_on_limit) VALUES (?,?,?,?,?,?)",
            (budget_id, scope, period, budget_usd,
             alert_threshold, action_on_limit))
        return budget_id

    def check_budgets(self) -> List[Dict[str, Any]]:
        budgets = self._fetchall("SELECT * FROM cost_budgets")
        alerts = []
        for b in budgets:
            period = b["period"]
            if period == "daily":
                spend = self.daily_spend()
            elif period == "weekly":
                spend = self.weekly_spend()
            else:
                spend = self.monthly_spend()
            budget = b["budget_usd"]
            pct = (spend / budget * 100) if budget > 0 else 0
            if pct >= 100:
                alerts.append({"level": "critical", "scope": b["scope"],
                               "period": period, "spend": spend,
                               "budget": budget, "percent": round(pct, 1)})
            elif pct >= b.get("alert_threshold", 0.8) * 100:
                alerts.append({"level": "warning", "scope": b["scope"],
                               "period": period, "spend": spend,
                               "budget": budget, "percent": round(pct, 1)})
        return alerts


class SharedMemoryRepository(BaseRepository):
    """CRUD for ``shared_memory`` table (shared DB)."""
    _table_prefix = "shared_memory"

    def share(self, from_agent: str, content: str,
              to_agent: Optional[str] = None,
              conversation_id: Optional[str] = None,
              memory_type: str = "context",
              key: Optional[str] = None,
              ttl_seconds: Optional[int] = None) -> str:
        mem_id = _uuid()
        now = _now_iso()
        expires = None
        if ttl_seconds:
            exp_dt = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            expires = exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._execute(
            "INSERT INTO shared_memory (id, from_agent_id, to_agent_id, "
            "conversation_id, memory_type, key, content, ttl_seconds, "
            "expires_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (mem_id, from_agent, to_agent, conversation_id, memory_type,
             key, content, ttl_seconds, expires, now))
        return mem_id

    def get_for_agent(self, agent_id: str,
                      limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM shared_memory "
            "WHERE (to_agent_id = ? OR to_agent_id IS NULL) "
            "AND (expires_at IS NULL OR expires_at > ?) "
            "ORDER BY created_at DESC LIMIT ?",
            (agent_id, _now_iso(), limit), ttl=5)

    def search_by_key(self, key: str) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM shared_memory WHERE key = ? "
            "AND (expires_at IS NULL OR expires_at > ?) "
            "ORDER BY created_at DESC",
            (key, _now_iso()), ttl=5)

    def expire_stale(self) -> int:
        now = _now_iso()
        self._execute(
            "DELETE FROM shared_memory WHERE expires_at IS NOT NULL "
            "AND expires_at <= ?", (now,))
        return 0  # rowcount not reliably returned across backends


class SecurityEventRepository(BaseRepository):
    """CRUD for ``security_events`` table (shared DB)."""
    _table_prefix = "security"

    def log_event(self, agent_id: str, event_type: str,
                  severity: str = "info", details: Optional[str] = None,
                  category: Optional[str] = None,
                  rule_id: Optional[str] = None,
                  action_taken: Optional[str] = None) -> str:
        event_id = _uuid()
        self._execute(
            "INSERT INTO security_events (id, agent_id, event_type, severity, "
            "category, rule_id, details, action_taken, timestamp) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (event_id, agent_id, event_type, severity, category,
             rule_id, details, action_taken, _now_iso()))
        return event_id

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM security_events ORDER BY timestamp DESC LIMIT ?",
            (limit,), ttl=10)

    def get_summary(self) -> Dict[str, Any]:
        rows = self._fetchall(
            "SELECT severity, COUNT(*) AS cnt FROM security_events "
            "GROUP BY severity", ttl=10)
        return {r["severity"]: r["cnt"] for r in rows}

    def get_unresolved(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM security_events WHERE resolved = 0 "
            "ORDER BY timestamp DESC", ttl=10)

    def resolve(self, event_id: str, resolved_by: str = "system") -> None:
        self._execute(
            "UPDATE security_events SET resolved=1, resolved_by=?, "
            "resolved_at=? WHERE id=?",
            (resolved_by, _now_iso(), event_id))


class AuditLogRepository(BaseRepository):
    """CRUD for ``audit_log`` table (shared DB)."""
    _table_prefix = "audit"

    def log(self, actor: str, action: str, resource_type: str,
            resource_id: Optional[str] = None,
            old_value: Optional[str] = None,
            new_value: Optional[str] = None) -> None:
        self._execute(
            "INSERT INTO audit_log (actor, action, resource_type, "
            "resource_id, old_value, new_value, timestamp) "
            "VALUES (?,?,?,?,?,?,?)",
            (actor, action, resource_type, resource_id,
             old_value, new_value, _now_iso()))

    def query(self, actor: Optional[str] = None,
              action: Optional[str] = None,
              limit: int = 50) -> List[Dict[str, Any]]:
        conditions = []
        params: list = []
        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if action:
            conditions.append("action = ?")
            params.append(action)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        return self._fetchall(
            f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ?",
            tuple(params))

    def count_actions(self, since_iso: Optional[str] = None) -> Dict[str, int]:
        if since_iso:
            rows = self._fetchall(
                "SELECT action, COUNT(*) AS cnt FROM audit_log "
                "WHERE timestamp >= ? GROUP BY action", (since_iso,))
        else:
            rows = self._fetchall(
                "SELECT action, COUNT(*) AS cnt FROM audit_log GROUP BY action")
        return {r["action"]: r["cnt"] for r in rows}


class AlertRepository(BaseRepository):
    """CRUD for ``alert_channels`` + ``alert_history`` (shared DB)."""
    _table_prefix = "alerts"

    def add_channel(self, channel_type: str, name: str,
                    config: Optional[Dict] = None) -> str:
        ch_id = _uuid()
        self._execute(
            "INSERT INTO alert_channels (id, channel_type, name, config) "
            "VALUES (?,?,?,?)",
            (ch_id, channel_type, name, json.dumps(config or {})))
        return ch_id

    def send_alert(self, channel_id: str, title: str,
                   message: str = "", severity: str = "info",
                   trigger_id: Optional[str] = None) -> str:
        alert_id = _uuid()
        self._execute(
            "INSERT INTO alert_history (id, channel_id, trigger_id, severity, "
            "title, message, created_at) VALUES (?,?,?,?,?,?,?)",
            (alert_id, channel_id, trigger_id, severity, title, message,
             _now_iso()))
        return alert_id

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM alert_history ORDER BY created_at DESC LIMIT ?",
            (limit,))


class DeploymentRepository(BaseRepository):
    """CRUD for ``deployments`` table (shared DB)."""
    _table_prefix = "deployments"

    def create(self, agent_id: str, agent_name: str, platform: str,
               deployment_method: str, config_snapshot: Optional[str] = None,
               image_tag: Optional[str] = None) -> str:
        deploy_id = _uuid()
        self._execute(
            "INSERT INTO deployments (id, agent_id, agent_name, platform, "
            "deployment_method, config_snapshot, image_tag, status, started_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (deploy_id, agent_id, agent_name, platform, deployment_method,
             config_snapshot, image_tag, "pending", _now_iso()))
        return deploy_id

    def update_status(self, deploy_id: str, status: str,
                      error: Optional[str] = None) -> None:
        now = _now_iso()
        if status in ("running", "failed", "stopped"):
            self._execute(
                "UPDATE deployments SET status=?, completed_at=?, error=? "
                "WHERE id=?", (status, now, error, deploy_id))
        else:
            self._execute(
                "UPDATE deployments SET status=?, error=? WHERE id=?",
                (status, error, deploy_id))

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM deployments ORDER BY started_at DESC LIMIT ?",
            (limit,))


class ClusterConfigRepository(BaseRepository):
    """CRUD for ``cluster_config`` table (shared DB)."""
    _table_prefix = "config"

    def get(self, key: str) -> Optional[str]:
        row = self._fetchone(
            "SELECT value FROM cluster_config WHERE key = ?",
            (key,), ttl=300)
        return row["value"] if row else None

    def set(self, key: str, value: str,
            updated_by: str = "system") -> None:
        existing = self._fetchone(
            "SELECT key FROM cluster_config WHERE key = ?", (key,))
        now = _now_iso()
        if existing:
            self._execute(
                "UPDATE cluster_config SET value=?, updated_at=?, "
                "updated_by=? WHERE key=?",
                (value, now, updated_by, key))
        else:
            self._execute(
                "INSERT INTO cluster_config (key, value, updated_at, updated_by) "
                "VALUES (?,?,?,?)",
                (key, value, now, updated_by))

    def get_all(self) -> Dict[str, str]:
        rows = self._fetchall("SELECT key, value FROM cluster_config", ttl=300)
        return {r["key"]: r["value"] for r in rows}

    def delete(self, key: str) -> None:
        self._execute("DELETE FROM cluster_config WHERE key = ?", (key,))


# =========================================================================
#  Instance DB Repositories
# =========================================================================

class ConversationRepository(BaseRepository):
    """CRUD for ``conversations`` + ``messages`` (instance DB)."""
    _table_prefix = "conversations"

    def create(self, agent_id: str, title: Optional[str] = None,
               channel: Optional[str] = None,
               conversation_id: Optional[str] = None) -> Dict[str, Any]:
        conv_id = conversation_id or _uuid()
        now = _now_iso()
        self._execute(
            "INSERT INTO conversations (id, title, channel, user_id, status, "
            "created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (conv_id, title, channel, agent_id, "active", now, now))
        return {"id": conv_id, "agent_id": agent_id, "title": title,
                "channel": channel, "created_at": now, "updated_at": now}

    def get(self, conv_id: str) -> Optional[Dict[str, Any]]:
        conv = self._fetchone(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,))
        if not conv:
            return None
        messages = self._fetchall(
            "SELECT * FROM messages WHERE conversation_id = ? "
            "ORDER BY created_at ASC", (conv_id,))
        conv["messages"] = messages
        return conv

    def list_conversations(self, agent_id: Optional[str] = None,
                           limit: int = 50,
                           offset: int = 0) -> List[Dict[str, Any]]:
        if agent_id:
            return self._fetchall(
                "SELECT * FROM conversations WHERE user_id = ? "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (agent_id, limit, offset), ttl=5)
        return self._fetchall(
            "SELECT * FROM conversations "
            "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            (limit, offset), ttl=5)

    def add_message(self, conv_id: str, role: str, content: str,
                    model: Optional[str] = None,
                    input_tokens: int = 0, output_tokens: int = 0,
                    cost_usd: float = 0.0) -> Optional[Dict[str, Any]]:
        msg_id = _uuid()
        now = _now_iso()
        # Verify conversation exists
        exists = self._fetchone(
            "SELECT id FROM conversations WHERE id = ?", (conv_id,))
        if not exists:
            return None
        self._execute(
            "INSERT INTO messages (id, conversation_id, role, content, model, "
            "input_tokens, output_tokens, cost_usd, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (msg_id, conv_id, role, content, model,
             input_tokens, output_tokens, cost_usd, now))
        # Update conversation stats
        self._execute(
            "UPDATE conversations SET updated_at=?, "
            "message_count=message_count+1, "
            "total_tokens=total_tokens+?+?, "
            "total_cost=total_cost+? WHERE id=?",
            (now, input_tokens, output_tokens, cost_usd, conv_id))
        return {"id": msg_id, "conversation_id": conv_id, "role": role,
                "content": content, "created_at": now}

    def search(self, query: str, agent_id: Optional[str] = None,
               limit: int = 50) -> List[Dict[str, Any]]:
        pattern = f"%{query}%"
        if agent_id:
            return self._fetchall(
                "SELECT m.id, m.conversation_id, m.role, m.content, "
                "m.created_at, c.user_id AS agent_id "
                "FROM messages m JOIN conversations c ON m.conversation_id=c.id "
                "WHERE m.content LIKE ? AND c.user_id = ? "
                "ORDER BY m.created_at DESC LIMIT ?",
                (pattern, agent_id, limit))
        return self._fetchall(
            "SELECT m.id, m.conversation_id, m.role, m.content, "
            "m.created_at, c.user_id AS agent_id "
            "FROM messages m JOIN conversations c ON m.conversation_id=c.id "
            "WHERE m.content LIKE ? ORDER BY m.created_at DESC LIMIT ?",
            (pattern, limit))

    def delete(self, conv_id: str) -> bool:
        self._execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        return True

    def get_stats(self) -> Dict[str, Any]:
        row = self._fetchone(
            "SELECT COUNT(*) AS convs, "
            "COALESCE(SUM(message_count),0) AS msgs, "
            "COALESCE(SUM(total_tokens),0) AS tokens, "
            "COALESCE(SUM(total_cost),0) AS cost "
            "FROM conversations")
        return {
            "conversations": row["convs"] if row else 0,
            "messages": row["msgs"] if row else 0,
            "total_tokens": row["tokens"] if row else 0,
            "total_cost": round(row["cost"], 6) if row else 0,
        }

    def prune(self, days: int = 90) -> int:
        threshold = (datetime.now(timezone.utc) - timedelta(days=days)
                     ).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._execute(
            "DELETE FROM conversations WHERE updated_at < ?", (threshold,))
        return 0


class LLMRequestRepository(BaseRepository):
    """CRUD for ``llm_requests`` table (instance DB)."""
    _table_prefix = "llm_requests"

    def record(self, provider: str, model: str,
               input_tokens: int = 0, output_tokens: int = 0,
               cost_usd: float = 0.0, latency_ms: float = 0.0,
               status_code: int = 200, cache_hit: bool = False,
               conversation_id: Optional[str] = None,
               trace_id: Optional[str] = None,
               routed_via: Optional[str] = None,
               error: Optional[str] = None) -> str:
        req_id = _uuid()
        total = input_tokens + output_tokens
        self._execute(
            "INSERT INTO llm_requests (id, conversation_id, provider, model, "
            "input_tokens, output_tokens, total_tokens, cost_usd, latency_ms, "
            "status_code, cache_hit, trace_id, routed_via, error, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (req_id, conversation_id, provider, model,
             input_tokens, output_tokens, total, cost_usd, latency_ms,
             status_code, 1 if cache_hit else 0, trace_id, routed_via,
             error, _now_iso()))
        return req_id

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT * FROM llm_requests ORDER BY created_at DESC LIMIT ?",
            (limit,))

    def aggregate_by_model(self) -> List[Dict[str, Any]]:
        return self._fetchall(
            "SELECT model, provider, COUNT(*) AS requests, "
            "SUM(input_tokens) AS total_input, "
            "SUM(output_tokens) AS total_output, "
            "SUM(cost_usd) AS total_cost, "
            "AVG(latency_ms) AS avg_latency "
            "FROM llm_requests GROUP BY model, provider "
            "ORDER BY total_cost DESC")


class ResponseCacheRepository(BaseRepository):
    """CRUD for ``response_cache`` table (instance DB)."""
    _table_prefix = "response_cache"

    def get_exact(self, cache_hash: str) -> Optional[str]:
        row = self._fetchone(
            "SELECT response, expires_at, hit_count FROM response_cache "
            "WHERE hash = ?", (cache_hash,))
        if not row:
            return None
        # Check expiry
        if row.get("expires_at"):
            try:
                exp = datetime.fromisoformat(
                    row["expires_at"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp:
                    return None
            except (ValueError, AttributeError):
                pass
        # Increment hit count
        self._execute(
            "UPDATE response_cache SET hit_count=hit_count+1, last_hit_at=? "
            "WHERE hash=?", (_now_iso(), cache_hash))
        return row["response"]

    def get_similar(self, message: str, threshold: float = 0.85,
                    ttl_seconds: int = 3600) -> Optional[str]:
        """Trigram similarity search (basic LIKE fallback)."""
        # For a proper implementation, this would use trigram similarity.
        # The basic approach just does exact hash lookup.
        cache_hash = hashlib.sha256(message.encode()).hexdigest()
        return self.get_exact(cache_hash)

    def put(self, prompt_hash: str, model: str, response: str,
            tokens_saved: int = 0, cost_saved: float = 0.0,
            ttl_seconds: Optional[int] = None) -> None:
        cache_hash = hashlib.sha256(
            f"{model}|{prompt_hash}".encode()).hexdigest()
        now = _now_iso()
        expires = None
        if ttl_seconds:
            exp_dt = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            expires = exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Upsert
        existing = self._fetchone(
            "SELECT hash FROM response_cache WHERE hash = ?", (cache_hash,))
        if existing:
            self._execute(
                "UPDATE response_cache SET response=?, hit_count=hit_count+1, "
                "last_hit_at=?, expires_at=? WHERE hash=?",
                (response, now, expires, cache_hash))
        else:
            self._execute(
                "INSERT INTO response_cache (hash, model, prompt_hash, response, "
                "tokens_saved, cost_saved, created_at, last_hit_at, expires_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (cache_hash, model, prompt_hash, response,
                 tokens_saved, cost_saved, now, now, expires))

    def stats(self) -> Dict[str, Any]:
        row = self._fetchone(
            "SELECT COUNT(*) AS total, COALESCE(SUM(hit_count),0) AS hits, "
            "COALESCE(SUM(tokens_saved),0) AS tokens_saved, "
            "COALESCE(SUM(cost_saved),0) AS cost_saved "
            "FROM response_cache")
        return {
            "total_entries": row["total"] if row else 0,
            "total_hits": row["hits"] if row else 0,
            "tokens_saved": row["tokens_saved"] if row else 0,
            "cost_saved": round(row["cost_saved"], 6) if row else 0,
        }

    def evict_expired(self) -> int:
        self._execute(
            "DELETE FROM response_cache WHERE expires_at IS NOT NULL "
            "AND expires_at <= ?", (_now_iso(),))
        return 0


class LocalLogRepository(BaseRepository):
    """CRUD for ``local_logs`` table (instance DB)."""
    _table_prefix = "local_logs"

    def log(self, message: str, level: str = "info",
            source: str = "system", component: Optional[str] = None,
            trace_id: Optional[str] = None,
            metadata: Optional[Dict] = None) -> None:
        self._execute(
            "INSERT INTO local_logs (level, message, source, component, "
            "trace_id, metadata, timestamp) VALUES (?,?,?,?,?,?,?)",
            (level, message, source, component, trace_id,
             json.dumps(metadata or {}), _now_iso()))

    def query(self, level: Optional[str] = None,
              component: Optional[str] = None,
              limit: int = 100) -> List[Dict[str, Any]]:
        conditions = []
        params: list = []
        if level:
            conditions.append("level = ?")
            params.append(level)
        if component:
            conditions.append("component = ?")
            params.append(component)
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        params.append(limit)
        return self._fetchall(
            f"SELECT * FROM local_logs {where} "
            f"ORDER BY timestamp DESC LIMIT ?",
            tuple(params))

    def count_by_level(self) -> Dict[str, int]:
        rows = self._fetchall(
            "SELECT level, COUNT(*) AS cnt FROM local_logs GROUP BY level")
        return {r["level"]: r["cnt"] for r in rows}


class PerformanceRepository(BaseRepository):
    """CRUD for ``performance_metrics`` table (instance DB)."""
    _table_prefix = "performance"

    def record(self, metric_name: str, metric_value: float,
               component: Optional[str] = None,
               tags: Optional[Dict] = None) -> None:
        self._execute(
            "INSERT INTO performance_metrics (metric_name, metric_value, "
            "component, tags, timestamp) VALUES (?,?,?,?,?)",
            (metric_name, metric_value, component,
             json.dumps(tags or {}), _now_iso()))

    def get_series(self, metric_name: str,
                   since_iso: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        if since_iso:
            return self._fetchall(
                "SELECT * FROM performance_metrics "
                "WHERE metric_name = ? AND timestamp >= ? "
                "ORDER BY timestamp DESC LIMIT ?",
                (metric_name, since_iso, limit))
        return self._fetchall(
            "SELECT * FROM performance_metrics WHERE metric_name = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (metric_name, limit))

    def get_latest(self, metric_name: str) -> Optional[Dict[str, Any]]:
        return self._fetchone(
            "SELECT * FROM performance_metrics WHERE metric_name = ? "
            "ORDER BY timestamp DESC LIMIT 1",
            (metric_name,))


# =========================================================================
#  DAL Facade — Singleton
# =========================================================================
class DAL:
    """Unified Data Access Layer.  Thread-safe singleton.

    Usage::

        dal = DAL.get_instance()
        dal.agents.list_all()
        dal.costs.record_cost(...)
        dal.conversations.add_message(...)
    """

    _instance: Optional["DAL"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        # Load config
        self._config = self._load_config()

        # Import StorageBackend classes
        from claw_storage import (
            SQLiteBackend, StorageManager, SCHEMA_DIR,
        )

        self._storage_mgr = StorageManager()

        # Determine if PostgreSQL
        inst_engine = self._config.get("instance_db", {}).get("engine", "sqlite")
        shared_engine = self._config.get("shared_db", {}).get("engine", "sqlite")
        self._inst_pg = inst_engine == "postgresql"
        self._shared_pg = shared_engine == "postgresql"

        # Create connection pools
        def _make_instance_backend():
            return self._storage_mgr._create_backend(
                self._config.get("instance_db", {}))

        self._instance_pool = ConnectionPool(_make_instance_backend, pool_size=5)

        # Shared DB pool (falls back to instance if shared disabled)
        shared_cfg = self._config.get("shared_db", {})
        if shared_cfg.get("enabled", False):
            def _make_shared_backend():
                return self._storage_mgr._create_backend(shared_cfg)
            self._shared_pool = ConnectionPool(_make_shared_backend, pool_size=5)
        else:
            self._shared_pool = self._instance_pool
            self._shared_pg = self._inst_pg

        # Initialize schemas
        self._storage_mgr.init_instance_schema()
        self._storage_mgr.init_shared_schema()

        # Query cache
        self._cache = QueryCache()
        self._cache.start()

        # --- Shared DB repositories ---
        self.agents = AgentRepository(
            self._shared_pool, self._cache, self._shared_pg)
        self.costs = CostTrackingRepository(
            self._shared_pool, self._cache, self._shared_pg)
        self.shared_memory = SharedMemoryRepository(
            self._shared_pool, self._cache, self._shared_pg)
        self.security_events = SecurityEventRepository(
            self._shared_pool, self._cache, self._shared_pg)
        self.audit = AuditLogRepository(
            self._shared_pool, self._cache, self._shared_pg)
        self.alerts = AlertRepository(
            self._shared_pool, self._cache, self._shared_pg)
        self.deployments = DeploymentRepository(
            self._shared_pool, self._cache, self._shared_pg)
        self.config = ClusterConfigRepository(
            self._shared_pool, self._cache, self._shared_pg)

        # --- Instance DB repositories ---
        self.conversations = ConversationRepository(
            self._instance_pool, self._cache, self._inst_pg)
        self.llm_requests = LLMRequestRepository(
            self._instance_pool, self._cache, self._inst_pg)
        self.response_cache = ResponseCacheRepository(
            self._instance_pool, self._cache, self._inst_pg)
        self.local_logs = LocalLogRepository(
            self._instance_pool, self._cache, self._inst_pg)
        self.performance = PerformanceRepository(
            self._instance_pool, self._cache, self._inst_pg)

        _log("DAL initialized (instance + shared pools)")

    @classmethod
    def get_instance(cls) -> "DAL":
        """Return the singleton DAL instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
            cls._instance = None

    def _load_config(self) -> Dict[str, Any]:
        if STORAGE_CONFIG_FILE.exists():
            try:
                return json.loads(
                    STORAGE_CONFIG_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "engine": "sqlite",
            "instance_db": {"engine": "sqlite",
                            "path": str(DEFAULT_INSTANCE_DB)},
            "shared_db": {"enabled": False, "engine": "sqlite",
                          "path": str(DEFAULT_SHARED_DB)},
        }

    def health(self) -> Dict[str, Any]:
        """Return pool stats + cache stats."""
        return {
            "instance_pool": self._instance_pool.stats(),
            "shared_pool": self._shared_pool.stats(),
            "cache": self._cache.stats(),
        }

    def close(self) -> None:
        """Drain pools + clear cache."""
        self._cache.stop()
        self._cache.clear()
        self._instance_pool.drain()
        if self._shared_pool is not self._instance_pool:
            self._shared_pool.drain()
        self._storage_mgr.close_all()
        _log("DAL closed")
