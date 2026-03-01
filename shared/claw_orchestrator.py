#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Multi-Agent Orchestration Engine
=============================================================================
Coordinates multiple running Claw agents for complex workflows.  Provides a
SQLite-backed task queue with priority levels, agent registry with capability
tracking, intelligent task routing, multi-step pipeline execution, periodic
health monitoring, and an in-process event bus for agent-to-agent messaging.

Agent Platforms:
  zeroclaw  -> port 3100  (general, rust, performance, minimal)
  nanoclaw  -> port 3200  (coding, typescript, claude-native, dood)
  picoclaw  -> port 3300  (data, lightweight, go, minimal-ram)
  openclaw  -> port 3400  (integrations, nodejs, plugins, 50-tools)
  parlant   -> port 8800  (guidelines, python, mcp, conversational)

HTTP API (default port 9100):
  POST /api/orchestrator/tasks               Submit a new task
  GET  /api/orchestrator/tasks               List tasks (?status=pending)
  GET  /api/orchestrator/tasks/:id           Get task details
  POST /api/orchestrator/tasks/:id/complete  Mark task complete
  GET  /api/orchestrator/agents              List agents with status
  POST /api/orchestrator/agents/:id/health   Trigger health check
  POST /api/orchestrator/pipeline            Create a pipeline
  POST /api/orchestrator/pipeline/:id/execute  Start pipeline execution
  GET  /api/orchestrator/pipeline/:id        Get pipeline status
  GET  /api/orchestrator/events              Recent events
  GET  /api/orchestrator/status              Overall orchestrator status

Usage:
  python3 shared/claw_orchestrator.py --start [--port 9100]
  python3 shared/claw_orchestrator.py --stop
  python3 shared/claw_orchestrator.py --submit "task description" [--agent zeroclaw] [--priority 3]
  python3 shared/claw_orchestrator.py --status
  python3 shared/claw_orchestrator.py --agents
  python3 shared/claw_orchestrator.py --pipeline "picoclaw->nanoclaw->openclaw" --name "data-pipeline"
  python3 shared/claw_orchestrator.py --health-check

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from claw_auth import check_auth
from claw_metrics import MetricsCollector
from claw_ratelimit import RateLimiter

# =========================================================================
#  Constants
# =========================================================================
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "orchestrator"
DB_FILE = DATA_DIR / "orchestrator.db"
PID_FILE = DATA_DIR / "orchestrator.pid"
DEFAULT_PORT = 9100
HEALTH_CHECK_TIMEOUT = 10  # seconds
HEALTH_CHECK_INTERVAL = 60  # seconds between automatic health sweeps

# =========================================================================
#  Known Agent Platforms
# =========================================================================
KNOWN_AGENTS: Dict[str, Dict[str, Any]] = {
    "zeroclaw": {
        "platform": "zeroclaw",
        "endpoint": "http://localhost:3100",
        "port": 3100,
        "capabilities": ["general", "rust", "performance", "minimal"],
        "max_load": 10,
    },
    "nanoclaw": {
        "platform": "nanoclaw",
        "endpoint": "http://localhost:3200",
        "port": 3200,
        "capabilities": ["coding", "typescript", "claude-native", "dood"],
        "max_load": 10,
    },
    "picoclaw": {
        "platform": "picoclaw",
        "endpoint": "http://localhost:3300",
        "port": 3300,
        "capabilities": ["data", "lightweight", "go", "minimal-ram"],
        "max_load": 10,
    },
    "openclaw": {
        "platform": "openclaw",
        "endpoint": "http://localhost:3400",
        "port": 3400,
        "capabilities": ["integrations", "nodejs", "plugins", "50-tools"],
        "max_load": 10,
    },
    "parlant": {
        "platform": "parlant",
        "endpoint": "http://localhost:8800",
        "port": 8800,
        "capabilities": ["guidelines", "python", "mcp", "conversational"],
        "max_load": 10,
    },
}

# Task keyword -> preferred capabilities for routing
ROUTING_KEYWORDS: Dict[str, List[str]] = {
    "code": ["coding", "typescript", "rust"],
    "coding": ["coding", "typescript", "rust"],
    "typescript": ["typescript", "coding"],
    "rust": ["rust", "performance"],
    "data": ["data", "lightweight"],
    "database": ["data", "lightweight"],
    "csv": ["data", "lightweight"],
    "api": ["integrations", "plugins", "nodejs"],
    "integration": ["integrations", "plugins"],
    "plugin": ["plugins", "integrations"],
    "tool": ["50-tools", "plugins"],
    "chat": ["conversational", "guidelines"],
    "conversation": ["conversational", "guidelines"],
    "guideline": ["guidelines", "conversational"],
    "python": ["python", "guidelines"],
    "performance": ["performance", "rust", "minimal"],
    "minimal": ["minimal", "lightweight"],
    "go": ["go", "lightweight"],
    "general": ["general"],
}

# =========================================================================
#  Colors (for terminal output)
# =========================================================================
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[orchestrator]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[orchestrator]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[orchestrator]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[orchestrator]{NC} {msg}")


def _now() -> str:
    """Return current UTC timestamp as ISO 8601 string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _uuid() -> str:
    """Generate a short unique identifier."""
    return uuid.uuid4().hex[:12]


# =========================================================================
#  Database Initialization
# =========================================================================
def _ensure_data_dir() -> None:
    """Create data/orchestrator/ directory if it does not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize the SQLite database with the orchestrator schema."""
    _ensure_data_dir()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            port INTEGER NOT NULL,
            status TEXT DEFAULT 'unknown',
            capabilities TEXT DEFAULT '[]',
            current_load INTEGER DEFAULT 0,
            max_load INTEGER DEFAULT 10,
            last_health_check TEXT,
            registered_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority INTEGER DEFAULT 3,
            status TEXT DEFAULT 'pending',
            assigned_agent TEXT,
            result TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            pipeline_id TEXT,
            pipeline_step INTEGER,
            FOREIGN KEY (assigned_agent) REFERENCES agents(id)
        );

        CREATE TABLE IF NOT EXISTS pipelines (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            steps TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            current_step INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            source_agent TEXT,
            target_agent TEXT,
            payload TEXT DEFAULT '{}',
            timestamp TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC, created_at ASC);
        CREATE INDEX IF NOT EXISTS idx_tasks_pipeline ON tasks(pipeline_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
    """)
    conn.commit()
    return conn


# =========================================================================
#  AgentRegistry — CRUD for agents table, health check integration
# =========================================================================
class AgentRegistry:
    """Manages agent registration, status tracking, and health checks.

    Uses DAL when available, falls back to direct SQLite connection.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()
        self._dal: Optional[Any] = None
        try:
            from claw_dal import DAL
            self._dal = DAL.get_instance()
            log("AgentRegistry using DAL")
        except Exception:
            pass

    def register(self, platform: str, endpoint: str, port: int,
                 capabilities: List[str], max_load: int = 10) -> str:
        """Register a new agent or update if already registered."""
        agent_id = platform
        now = _now()
        caps_json = json.dumps(capabilities)

        if self._dal:
            self._dal.agents.register(
                agent_id=agent_id, name=platform, platform=platform,
                host="localhost", port=port, capabilities=capabilities)
            return agent_id

        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM agents WHERE id = ?", (agent_id,)
            ).fetchone()

            if existing:
                self._conn.execute("""
                    UPDATE agents SET endpoint = ?, port = ?, capabilities = ?,
                        max_load = ? WHERE id = ?
                """, (endpoint, port, caps_json, max_load, agent_id))
            else:
                self._conn.execute("""
                    INSERT INTO agents (id, platform, endpoint, port, capabilities,
                        max_load, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (agent_id, platform, endpoint, port, caps_json,
                      max_load, now))
            self._conn.commit()

        return agent_id

    def update_status(self, agent_id: str, status: str) -> bool:
        """Update the status of an agent (healthy, unhealthy, unknown)."""
        if self._dal:
            return self._dal.agents.update_status(agent_id, status)

        with self._lock:
            cursor = self._conn.execute(
                "UPDATE agents SET status = ? WHERE id = ?",
                (status, agent_id)
            )
            self._conn.commit()
            return cursor.rowcount > 0

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get a single agent by ID."""
        if self._dal:
            return self._dal.agents.get(agent_id)

        row = self._conn.execute(
            "SELECT * FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        return self._row_to_dict(row) if row else None

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all registered agents."""
        if self._dal:
            return self._dal.agents.list_all()

        rows = self._conn.execute(
            "SELECT * FROM agents ORDER BY platform"
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_available(self, capability: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get agents sorted by load, optionally filtered by capability."""
        if self._dal:
            return self._dal.agents.list_available(capability)

        agents = self.get_all()
        available = []
        for agent in agents:
            if agent["status"] == "unhealthy":
                continue
            if agent["current_load"] >= agent["max_load"]:
                continue
            if capability:
                caps = agent.get("capabilities", [])
                if capability not in caps:
                    continue
            available.append(agent)
        available.sort(key=lambda a: a["current_load"])
        return available

    def increment_load(self, agent_id: str) -> None:
        """Increment the current load counter for an agent."""
        with self._lock:
            self._conn.execute(
                "UPDATE agents SET current_load = current_load + 1 WHERE id = ?",
                (agent_id,)
            )
            self._conn.commit()

    def decrement_load(self, agent_id: str) -> None:
        """Decrement the current load counter for an agent."""
        with self._lock:
            self._conn.execute(
                "UPDATE agents SET current_load = MAX(0, current_load - 1) WHERE id = ?",
                (agent_id,)
            )
            self._conn.commit()

    def health_check(self, agent_id: str) -> Dict[str, Any]:
        """Ping an agent's endpoint and update its status."""
        agent = self.get_agent(agent_id)
        if not agent:
            return {"ok": False, "detail": f"agent '{agent_id}' not found"}

        endpoint = agent["endpoint"]
        port = agent["port"]
        status = "unhealthy"
        detail = ""

        # Try TCP port check first
        try:
            with socket.create_connection(("localhost", port),
                                          timeout=HEALTH_CHECK_TIMEOUT):
                status = "healthy"
                detail = f"port {port} reachable"
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            detail = f"port {port} unreachable: {exc}"

        # If TCP succeeded, try HTTP health endpoint
        if status == "healthy":
            try:
                health_url = f"{endpoint}/health"
                req = Request(health_url, method="GET")
                with urlopen(req, timeout=HEALTH_CHECK_TIMEOUT) as resp:
                    if 200 <= resp.getcode() < 300:
                        detail = f"HTTP health OK ({resp.getcode()})"
                    else:
                        detail = f"HTTP health returned {resp.getcode()}"
            except (URLError, OSError):
                # TCP works but no /health endpoint — still healthy
                detail = f"port {port} reachable (no HTTP /health)"

        now = _now()
        with self._lock:
            self._conn.execute(
                "UPDATE agents SET status = ?, last_health_check = ? WHERE id = ?",
                (status, now, agent_id)
            )
            self._conn.commit()

        return {"ok": status == "healthy", "status": status, "detail": detail,
                "agent_id": agent_id, "checked_at": now}

    def health_check_all(self) -> List[Dict[str, Any]]:
        """Run health checks on all registered agents."""
        results = []
        for agent in self.get_all():
            result = self.health_check(agent["id"])
            results.append(result)
        return results

    def auto_register_known(self) -> int:
        """Register all 5 known agent platforms on startup."""
        count = 0
        for agent_id, config in KNOWN_AGENTS.items():
            self.register(
                platform=config["platform"],
                endpoint=config["endpoint"],
                port=config["port"],
                capabilities=config["capabilities"],
                max_load=config["max_load"],
            )
            count += 1
        return count

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict with parsed JSON fields."""
        d = dict(row)
        if "capabilities" in d and isinstance(d["capabilities"], str):
            try:
                d["capabilities"] = json.loads(d["capabilities"])
            except (json.JSONDecodeError, TypeError):
                d["capabilities"] = []
        return d


# =========================================================================
#  TaskQueue — SQLite-backed priority queue
# =========================================================================
class TaskQueue:
    """SQLite-backed task queue with priority levels (1=low, 5=critical)."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()

    def submit(self, title: str, description: str = "",
               priority: int = 3, agent_hint: Optional[str] = None,
               pipeline_id: Optional[str] = None,
               pipeline_step: Optional[int] = None) -> str:
        """Submit a new task to the queue.  Returns the task ID."""
        task_id = f"task-{_uuid()}"
        now = _now()
        priority = max(1, min(5, priority))

        with self._lock:
            self._conn.execute("""
                INSERT INTO tasks (id, title, description, priority, status,
                    assigned_agent, created_at, pipeline_id, pipeline_step)
                VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """, (task_id, title, description, priority,
                  agent_hint, now, pipeline_id, pipeline_step))
            self._conn.commit()

        return task_id

    def assign(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent and mark it as running."""
        now = _now()
        with self._lock:
            cursor = self._conn.execute("""
                UPDATE tasks SET assigned_agent = ?, status = 'assigned',
                    started_at = ? WHERE id = ? AND status = 'pending'
            """, (agent_id, now, task_id))
            self._conn.commit()
            return cursor.rowcount > 0

    def start(self, task_id: str) -> bool:
        """Mark a task as actively running."""
        now = _now()
        with self._lock:
            cursor = self._conn.execute("""
                UPDATE tasks SET status = 'running', started_at = COALESCE(started_at, ?)
                WHERE id = ? AND status IN ('pending', 'assigned')
            """, (now, task_id))
            self._conn.commit()
            return cursor.rowcount > 0

    def complete(self, task_id: str, result: str = "") -> bool:
        """Mark a task as completed with an optional result."""
        now = _now()
        with self._lock:
            cursor = self._conn.execute("""
                UPDATE tasks SET status = 'completed', result = ?,
                    completed_at = ?
                WHERE id = ? AND status IN ('pending', 'assigned', 'running')
            """, (result, now, task_id))
            self._conn.commit()
            return cursor.rowcount > 0

    def fail(self, task_id: str, error: str = "") -> bool:
        """Mark a task as failed with an error description."""
        now = _now()
        with self._lock:
            cursor = self._conn.execute("""
                UPDATE tasks SET status = 'failed', result = ?,
                    completed_at = ?
                WHERE id = ? AND status IN ('pending', 'assigned', 'running')
            """, (error, now, task_id))
            self._conn.commit()
            return cursor.rowcount > 0

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a single task by ID."""
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_pending(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending tasks ordered by priority (desc) then created_at (asc)."""
        rows = self._conn.execute("""
            SELECT * FROM tasks WHERE status = 'pending'
            ORDER BY priority DESC, created_at ASC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_by_status(self, status: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get tasks filtered by status."""
        rows = self._conn.execute("""
            SELECT * FROM tasks WHERE status = ?
            ORDER BY priority DESC, created_at ASC LIMIT ?
        """, (status, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all tasks, most recent first."""
        rows = self._conn.execute("""
            SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_by_pipeline(self, pipeline_id: str) -> List[Dict[str, Any]]:
        """Get all tasks belonging to a pipeline, ordered by step."""
        rows = self._conn.execute("""
            SELECT * FROM tasks WHERE pipeline_id = ?
            ORDER BY pipeline_step ASC
        """, (pipeline_id,)).fetchall()
        return [dict(r) for r in rows]

    def count_by_status(self) -> Dict[str, int]:
        """Count tasks grouped by status."""
        rows = self._conn.execute("""
            SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status
        """).fetchall()
        return {r["status"]: r["cnt"] for r in rows}


# =========================================================================
#  TaskRouter — matches tasks to agents based on keywords/capabilities
# =========================================================================
class TaskRouter:
    """Routes tasks to the best available agent based on keyword matching."""

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def route(self, task: Dict[str, Any]) -> Optional[str]:
        """Select the best agent for a task.  Returns agent_id or None."""
        # If task already has an agent hint, try that first
        hint = task.get("assigned_agent")
        if hint:
            agent = self._registry.get_agent(hint)
            if agent and agent["status"] != "unhealthy" \
                    and agent["current_load"] < agent["max_load"]:
                return hint

        # Extract keywords from title and description
        text = f"{task.get('title', '')} {task.get('description', '')}".lower()

        # Build a score for each capability based on keyword matches
        capability_scores: Dict[str, int] = {}
        for keyword, preferred_caps in ROUTING_KEYWORDS.items():
            if keyword in text:
                for cap in preferred_caps:
                    capability_scores[cap] = capability_scores.get(cap, 0) + 1

        # Get all available agents
        available = self._registry.get_available()
        if not available:
            return None

        # Score each agent
        best_agent = None
        best_score = -1

        for agent in available:
            agent_caps = agent.get("capabilities", [])
            score = 0
            for cap in agent_caps:
                score += capability_scores.get(cap, 0)

            # Prefer agents with lower load (tie-breaker)
            load_factor = 1.0 - (agent["current_load"] / max(agent["max_load"], 1))
            weighted_score = score + load_factor

            if weighted_score > best_score:
                best_score = weighted_score
                best_agent = agent["id"]

        return best_agent


# =========================================================================
#  PipelineBuilder — define and execute multi-agent chains
# =========================================================================
class PipelineBuilder:
    """Defines and executes multi-step agent pipelines."""

    def __init__(self, conn: sqlite3.Connection, queue: TaskQueue,
                 router: TaskRouter, registry: AgentRegistry,
                 event_bus: EventBus) -> None:
        self._conn = conn
        self._lock = threading.Lock()
        self._queue = queue
        self._router = router
        self._registry = registry
        self._event_bus = event_bus

    def create(self, name: str, steps: List[Dict[str, Any]]) -> str:
        """Create a pipeline definition.

        Each step is a dict with keys:
            agent_id   — target agent platform id
            task_title — title template for the step's task
            task_desc  — description template (optional)
        """
        pipeline_id = f"pipe-{_uuid()}"
        now = _now()
        steps_json = json.dumps(steps)

        with self._lock:
            self._conn.execute("""
                INSERT INTO pipelines (id, name, steps, status, current_step,
                    created_at)
                VALUES (?, ?, ?, 'pending', 0, ?)
            """, (pipeline_id, name, steps_json, now))
            self._conn.commit()

        return pipeline_id

    def execute(self, pipeline_id: str) -> bool:
        """Start executing a pipeline from the current step."""
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            return False

        if pipeline["status"] == "completed":
            return False

        steps = pipeline["steps"]
        if not steps:
            return False

        # Mark as running
        with self._lock:
            self._conn.execute(
                "UPDATE pipelines SET status = 'running' WHERE id = ?",
                (pipeline_id,)
            )
            self._conn.commit()

        # Run pipeline in a background thread
        thread = threading.Thread(
            target=self._run_pipeline, args=(pipeline_id,), daemon=True
        )
        thread.start()
        return True

    def _run_pipeline(self, pipeline_id: str) -> None:
        """Execute pipeline steps sequentially in a background thread."""
        pipeline = self.get_pipeline(pipeline_id)
        if not pipeline:
            return

        steps = pipeline["steps"]
        current = pipeline["current_step"]
        prev_result = ""

        for i in range(current, len(steps)):
            step = steps[i]
            agent_id = step.get("agent_id", "")
            title = step.get("task_title", f"Pipeline step {i}")
            desc = step.get("task_desc", "")

            # Append previous step result as context
            if prev_result:
                desc = f"{desc}\n\n--- Previous step result ---\n{prev_result}"

            # Submit task for this step
            task_id = self._queue.submit(
                title=title,
                description=desc,
                priority=4,  # pipeline tasks get high priority
                agent_hint=agent_id,
                pipeline_id=pipeline_id,
                pipeline_step=i,
            )

            # Auto-assign to the specified agent
            if agent_id:
                self._queue.assign(task_id, agent_id)
                self._registry.increment_load(agent_id)
            else:
                # Use router if no specific agent
                routed = self._router.route(self._queue.get_task(task_id) or {})
                if routed:
                    self._queue.assign(task_id, routed)
                    self._registry.increment_load(routed)

            self._queue.start(task_id)

            # Update pipeline current step
            with self._lock:
                self._conn.execute(
                    "UPDATE pipelines SET current_step = ? WHERE id = ?",
                    (i, pipeline_id)
                )
                self._conn.commit()

            # Publish step-started event
            self._event_bus.publish(
                event_type="pipeline.step.started",
                source=agent_id or "orchestrator",
                target=None,
                payload={"pipeline_id": pipeline_id, "step": i,
                         "task_id": task_id}
            )

            # Wait for task completion (poll with timeout)
            timeout = 300  # 5 minutes per step
            start_time = time.time()
            task_done = False

            while time.time() - start_time < timeout:
                task = self._queue.get_task(task_id)
                if not task:
                    break
                if task["status"] in ("completed", "failed"):
                    task_done = True
                    prev_result = task.get("result", "")
                    if agent_id:
                        self._registry.decrement_load(agent_id)
                    break
                time.sleep(2)

            if not task_done:
                # Timeout — fail the task and pipeline
                self._queue.fail(task_id, "Pipeline step timed out")
                if agent_id:
                    self._registry.decrement_load(agent_id)
                with self._lock:
                    self._conn.execute(
                        "UPDATE pipelines SET status = 'failed' WHERE id = ?",
                        (pipeline_id,)
                    )
                    self._conn.commit()
                self._event_bus.publish(
                    event_type="pipeline.failed",
                    source="orchestrator",
                    target=None,
                    payload={"pipeline_id": pipeline_id, "step": i,
                             "reason": "timeout"}
                )
                return

            # Check if step failed
            task = self._queue.get_task(task_id)
            if task and task["status"] == "failed":
                with self._lock:
                    self._conn.execute(
                        "UPDATE pipelines SET status = 'failed' WHERE id = ?",
                        (pipeline_id,)
                    )
                    self._conn.commit()
                self._event_bus.publish(
                    event_type="pipeline.failed",
                    source="orchestrator",
                    target=None,
                    payload={"pipeline_id": pipeline_id, "step": i,
                             "reason": task.get("result", "step failed")}
                )
                return

        # All steps completed
        now = _now()
        with self._lock:
            self._conn.execute(
                "UPDATE pipelines SET status = 'completed', completed_at = ? WHERE id = ?",
                (now, pipeline_id)
            )
            self._conn.commit()

        self._event_bus.publish(
            event_type="pipeline.completed",
            source="orchestrator",
            target=None,
            payload={"pipeline_id": pipeline_id, "steps": len(steps)}
        )

    def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get pipeline details including parsed steps."""
        row = self._conn.execute(
            "SELECT * FROM pipelines WHERE id = ?", (pipeline_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if isinstance(d.get("steps"), str):
            try:
                d["steps"] = json.loads(d["steps"])
            except (json.JSONDecodeError, TypeError):
                d["steps"] = []
        return d

    def get_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all pipelines."""
        rows = self._conn.execute(
            "SELECT * FROM pipelines ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("steps"), str):
                try:
                    d["steps"] = json.loads(d["steps"])
                except (json.JSONDecodeError, TypeError):
                    d["steps"] = []
            results.append(d)
        return results


# =========================================================================
#  EventBus — in-process pub/sub for agent-to-agent communication
# =========================================================================
class EventBus:
    """Simple in-process pub/sub with SQLite persistence for event history."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._lock = threading.Lock()
        self._subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}

    def publish(self, event_type: str, source: Optional[str] = None,
                target: Optional[str] = None,
                payload: Optional[Dict[str, Any]] = None) -> int:
        """Publish an event.  Persists to DB and notifies subscribers."""
        now = _now()
        payload_json = json.dumps(payload or {})

        with self._lock:
            cursor = self._conn.execute("""
                INSERT INTO events (event_type, source_agent, target_agent,
                    payload, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (event_type, source, target, payload_json, now))
            self._conn.commit()
            event_id: int = cursor.lastrowid or 0

        # Notify in-process subscribers
        callbacks = self._subscribers.get(event_type, [])
        event_data = {
            "id": event_id,
            "event_type": event_type,
            "source_agent": source,
            "target_agent": target,
            "payload": payload or {},
            "timestamp": now,
        }
        for callback in callbacks:
            try:
                callback(event_data)
            except Exception:
                pass  # Do not let subscriber errors break the bus

        return event_id

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback for a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def get_events(self, agent_id: Optional[str] = None,
                   event_type: Optional[str] = None,
                   limit: int = 50) -> List[Dict[str, Any]]:
        """Query event history with optional filters."""
        query = "SELECT * FROM events WHERE 1=1"
        params: List[Any] = []

        if agent_id:
            query += " AND (source_agent = ? OR target_agent = ?)"
            params.extend([agent_id, agent_id])
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if isinstance(d.get("payload"), str):
                try:
                    d["payload"] = json.loads(d["payload"])
                except (json.JSONDecodeError, TypeError):
                    d["payload"] = {}
            results.append(d)
        return results


# =========================================================================
#  HTTP API Handler
# =========================================================================
class OrchestratorHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the orchestrator REST API."""

    # These are set by the server before it starts
    registry: AgentRegistry = None  # type: ignore[assignment]
    queue: TaskQueue = None  # type: ignore[assignment]
    router: TaskRouter = None  # type: ignore[assignment]
    pipeline_builder: PipelineBuilder = None  # type: ignore[assignment]
    event_bus: EventBus = None  # type: ignore[assignment]
    server_start_time: str = ""
    metrics: Optional[MetricsCollector] = None
    rate_limiter: RateLimiter = RateLimiter()

    def _get_client_key(self) -> str:
        """Derive a rate-limit key from Bearer token or client IP."""
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:].strip()
        return self.client_address[0]

    def _check_middleware(self) -> bool:
        """
        Run auth + rate-limit checks before request handling.

        Returns True if the request should proceed, False if a response
        has already been sent (401 or 429).
        """
        ok, error_msg = check_auth(self.headers)
        if not ok:
            self._json_response(401, {"error": error_msg})
            return False

        client_key = self._get_client_key()
        allowed, remaining, reset_at = self.rate_limiter.check(client_key)
        self._rl_remaining = remaining
        self._rl_reset_at = reset_at

        if not allowed:
            body = json.dumps({"error": "Rate limit exceeded. Try again later."}, indent=2, default=str).encode("utf-8")
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-RateLimit-Limit", str(self.rate_limiter.max_requests))
            self.send_header("X-RateLimit-Remaining", str(remaining))
            self.send_header("X-RateLimit-Reset", str(int(reset_at)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return False

        return True

    def _send_metrics(self) -> None:
        """GET /metrics — Prometheus text exposition."""
        if not self.metrics:
            self._json_response(503, {"error": "Metrics not initialized"})
            return
        body = self.metrics.metrics_handler().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.metrics:
            self.metrics.inc_active_connections()
        start = time.time()
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)
        status = 200

        try:
            # Health and metrics bypass auth + rate limiting
            if path == "/metrics":
                self._send_metrics()
                return
            elif path == "/health":
                self._json_response(200, {"status": "healthy", "service": "orchestrator"})
                return

            # Auth + rate-limit middleware
            if not self._check_middleware():
                return

            if path == "/api/orchestrator/status":
                self._handle_status()
            elif path == "/api/orchestrator/agents":
                self._handle_list_agents()
            elif path == "/api/orchestrator/tasks":
                status_filter = query.get("status", [None])[0]
                self._handle_list_tasks(status_filter)
            elif path.startswith("/api/orchestrator/tasks/"):
                task_id = path.split("/")[-1]
                self._handle_get_task(task_id)
            elif path.startswith("/api/orchestrator/pipeline/"):
                pipeline_id = path.split("/")[-1]
                self._handle_get_pipeline(pipeline_id)
            elif path == "/api/orchestrator/events":
                agent_id = query.get("agent_id", [None])[0]
                limit = int(query.get("limit", ["50"])[0])
                self._handle_list_events(agent_id, limit)
            else:
                status = 404
                self._json_response(404, {"error": "not found"})
        except Exception:
            status = 500
            raise
        finally:
            if self.metrics:
                self.metrics.dec_active_connections()
                self.metrics.track_request("GET", path, status, time.time() - start)

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.metrics:
            self.metrics.inc_active_connections()
        start = time.time()
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        status = 200

        try:
            # Auth + rate-limit middleware
            if not self._check_middleware():
                return

            body = self._read_body()

            if path == "/api/orchestrator/tasks":
                self._handle_submit_task(body)
            elif path.endswith("/complete") and "/tasks/" in path:
                parts = path.split("/")
                # /api/orchestrator/tasks/<id>/complete
                task_id = parts[-2]
                self._handle_complete_task(task_id, body)
            elif path.endswith("/health") and "/agents/" in path:
                parts = path.split("/")
                # /api/orchestrator/agents/<id>/health
                agent_id = parts[-2]
                self._handle_agent_health(agent_id)
            elif path == "/api/orchestrator/pipeline":
                self._handle_create_pipeline(body)
            elif path.endswith("/execute") and "/pipeline/" in path:
                parts = path.split("/")
                pipeline_id = parts[-2]
                self._handle_execute_pipeline(pipeline_id)
            else:
                status = 404
                self._json_response(404, {"error": "not found"})
        except Exception:
            status = 500
            raise
        finally:
            if self.metrics:
                self.metrics.dec_active_connections()
                self.metrics.track_request("POST", path, status, time.time() - start)

    # --- Status -----------------------------------------------------------

    def _handle_status(self) -> None:
        agents = self.registry.get_all()
        task_counts = self.queue.count_by_status()
        healthy = sum(1 for a in agents if a["status"] == "healthy")
        total = len(agents)

        self._json_response(200, {
            "status": "running",
            "started_at": self.server_start_time,
            "agents": {
                "total": total,
                "healthy": healthy,
                "unhealthy": total - healthy,
            },
            "tasks": task_counts,
            "uptime_check": _now(),
        })

    # --- Agents -----------------------------------------------------------

    def _handle_list_agents(self) -> None:
        agents = self.registry.get_all()
        self._json_response(200, {"agents": agents, "total": len(agents)})

    def _handle_agent_health(self, agent_id: str) -> None:
        result = self.registry.health_check(agent_id)
        code = 200 if result.get("ok") else 503
        self._json_response(code, result)

    # --- Tasks ------------------------------------------------------------

    def _handle_list_tasks(self, status_filter: Optional[str]) -> None:
        if status_filter:
            tasks = self.queue.get_by_status(status_filter)
        else:
            tasks = self.queue.get_all()
        self._json_response(200, {"tasks": tasks, "total": len(tasks)})

    def _handle_get_task(self, task_id: str) -> None:
        task = self.queue.get_task(task_id)
        if task:
            self._json_response(200, task)
        else:
            self._json_response(404, {"error": f"task '{task_id}' not found"})

    def _handle_submit_task(self, body: Dict[str, Any]) -> None:
        title = body.get("title", "")
        if not title:
            self._json_response(400, {"error": "title is required"})
            return

        description = body.get("description", "")
        priority = int(body.get("priority", 3))
        agent_hint = body.get("agent", None)

        task_id = self.queue.submit(title, description, priority, agent_hint)

        # Auto-route if no agent hint
        task = self.queue.get_task(task_id)
        if task and not agent_hint:
            routed = self.router.route(task)
            if routed:
                self.queue.assign(task_id, routed)
                self.registry.increment_load(routed)
                self.event_bus.publish(
                    event_type="task.assigned",
                    source="orchestrator",
                    target=routed,
                    payload={"task_id": task_id, "title": title}
                )
        elif task and agent_hint:
            self.queue.assign(task_id, agent_hint)
            self.registry.increment_load(agent_hint)

        task = self.queue.get_task(task_id)
        self._json_response(201, {"task_id": task_id, "task": task})

    def _handle_complete_task(self, task_id: str, body: Dict[str, Any]) -> None:
        result = body.get("result", "")
        task = self.queue.get_task(task_id)
        if not task:
            self._json_response(404, {"error": f"task '{task_id}' not found"})
            return

        ok = self.queue.complete(task_id, result)
        if ok:
            agent_id = task.get("assigned_agent")
            if agent_id:
                self.registry.decrement_load(agent_id)
            self.event_bus.publish(
                event_type="task.completed",
                source=agent_id or "unknown",
                target="orchestrator",
                payload={"task_id": task_id, "result": result[:200]}
            )
            self._json_response(200, {"ok": True, "task_id": task_id})
        else:
            self._json_response(409, {"error": "task already completed or not found"})

    # --- Pipelines --------------------------------------------------------

    def _handle_create_pipeline(self, body: Dict[str, Any]) -> None:
        name = body.get("name", "")
        steps = body.get("steps", [])
        if not name or not steps:
            self._json_response(400, {"error": "name and steps are required"})
            return

        pipeline_id = self.pipeline_builder.create(name, steps)
        self._json_response(201, {"pipeline_id": pipeline_id})

    def _handle_execute_pipeline(self, pipeline_id: str) -> None:
        pipeline = self.pipeline_builder.get_pipeline(pipeline_id)
        if not pipeline:
            self._json_response(404, {"error": f"pipeline '{pipeline_id}' not found"})
            return

        ok = self.pipeline_builder.execute(pipeline_id)
        if ok:
            self.event_bus.publish(
                event_type="pipeline.started",
                source="orchestrator",
                target=None,
                payload={"pipeline_id": pipeline_id, "name": pipeline["name"]}
            )
            self._json_response(200, {"ok": True, "pipeline_id": pipeline_id,
                                       "status": "running"})
        else:
            self._json_response(409, {"error": "pipeline already completed or empty"})

    def _handle_get_pipeline(self, pipeline_id: str) -> None:
        pipeline = self.pipeline_builder.get_pipeline(pipeline_id)
        if not pipeline:
            self._json_response(404, {"error": f"pipeline '{pipeline_id}' not found"})
            return

        # Include pipeline tasks
        tasks = self.queue.get_by_pipeline(pipeline_id)
        pipeline["tasks"] = tasks
        self._json_response(200, pipeline)

    # --- Events -----------------------------------------------------------

    def _handle_list_events(self, agent_id: Optional[str],
                            limit: int) -> None:
        events = self.event_bus.get_events(agent_id=agent_id, limit=limit)
        self._json_response(200, {"events": events, "total": len(events)})

    # --- Helpers ----------------------------------------------------------

    def _read_body(self) -> Dict[str, Any]:
        """Read and parse JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        try:
            raw = self.rfile.read(content_length)
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _json_response(self, code: int, data: Any) -> None:
        """Send a JSON response."""
        body = json.dumps(data, indent=2, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        # Rate-limit headers
        self.send_header("X-RateLimit-Limit", str(self.rate_limiter.max_requests))
        if hasattr(self, "_rl_remaining"):
            self.send_header("X-RateLimit-Remaining", str(self._rl_remaining))
        if hasattr(self, "_rl_reset_at"):
            self.send_header("X-RateLimit-Reset", str(int(self._rl_reset_at)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default HTTP logging to keep output clean."""
        pass


# =========================================================================
#  Threaded HTTP Server
# =========================================================================
class OrchestratorServer(ThreadingMixIn, HTTPServer):
    """Multi-threaded HTTP server for the orchestrator API."""
    allow_reuse_address = True
    daemon_threads = True


# =========================================================================
#  Health Monitor — periodic background health sweeps
# =========================================================================
class HealthMonitor:
    """Runs periodic health checks on all agents in a background thread."""

    def __init__(self, registry: AgentRegistry, event_bus: EventBus,
                 interval: int = HEALTH_CHECK_INTERVAL) -> None:
        self._registry = registry
        self._event_bus = event_bus
        self._interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the health monitoring loop."""
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the health monitoring loop."""
        self._running = False

    def _loop(self) -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                results = self._registry.health_check_all()
                for result in results:
                    if not result.get("ok"):
                        self._event_bus.publish(
                            event_type="agent.unhealthy",
                            source="health-monitor",
                            target=result.get("agent_id"),
                            payload={"detail": result.get("detail", "")}
                        )
            except Exception:
                pass  # Health monitor must never crash

            # Sleep in small increments for responsive shutdown
            for _ in range(self._interval):
                if not self._running:
                    break
                time.sleep(1)


# =========================================================================
#  PID File Management
# =========================================================================
def _write_pid() -> None:
    """Write current process PID to file."""
    _ensure_data_dir()
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _read_pid() -> Optional[int]:
    """Read PID from file, or None if missing."""
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def _remove_pid() -> None:
    """Remove the PID file."""
    try:
        PID_FILE.unlink()
    except OSError:
        pass


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


# =========================================================================
#  CLI — start / stop / submit / status / agents / pipeline / health-check
# =========================================================================
def cmd_start(port: int) -> None:
    """Start the orchestrator HTTP server."""
    existing_pid = _read_pid()
    if existing_pid and _is_process_running(existing_pid):
        err(f"Orchestrator already running (PID {existing_pid}).  "
            f"Use --stop first.")
        sys.exit(1)

    log(f"Starting Claw Orchestrator on port {port}...")

    # Initialize database and components
    conn = _init_db(DB_FILE)
    registry = AgentRegistry(conn)
    queue = TaskQueue(conn)
    event_bus = EventBus(conn)
    router = TaskRouter(registry)
    pipeline_builder = PipelineBuilder(conn, queue, router, registry, event_bus)

    # Auto-register known agents
    count = registry.auto_register_known()
    log(f"Registered {count} known agent platforms")

    # Run initial health check
    info("Running initial health check...")
    results = registry.health_check_all()
    healthy = sum(1 for r in results if r.get("ok"))
    log(f"Health check: {healthy}/{len(results)} agents reachable")

    # Configure HTTP handler
    start_time = _now()
    OrchestratorHandler.registry = registry
    OrchestratorHandler.queue = queue
    OrchestratorHandler.router = router
    OrchestratorHandler.pipeline_builder = pipeline_builder
    OrchestratorHandler.event_bus = event_bus
    OrchestratorHandler.server_start_time = start_time
    OrchestratorHandler.metrics = MetricsCollector(service="claw-orchestrator")

    # Start health monitor
    monitor = HealthMonitor(registry, event_bus)
    monitor.start()

    # Start HTTP server
    try:
        server = OrchestratorServer(("0.0.0.0", port), OrchestratorHandler)
    except OSError as exc:
        err(f"Cannot bind to port {port}: {exc}")
        sys.exit(1)

    _write_pid()

    # Graceful shutdown handler
    def _shutdown(sig: int, frame: Any) -> None:
        log("Shutdown signal received")
        monitor.stop()
        server.shutdown()
        conn.close()
        _remove_pid()
        log("Orchestrator stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log(f"Orchestrator listening on http://0.0.0.0:{port}")
    log(f"  API base: http://localhost:{port}/api/orchestrator")
    log(f"  Health:   http://localhost:{port}/health")
    info("Press Ctrl+C to stop")

    # Publish startup event
    event_bus.publish(
        event_type="orchestrator.started",
        source="orchestrator",
        target=None,
        payload={"port": port, "agents_registered": count,
                 "agents_healthy": healthy}
    )

    server.serve_forever()


def cmd_stop() -> None:
    """Stop a running orchestrator by sending SIGTERM to its PID."""
    pid = _read_pid()
    if not pid:
        err("No PID file found.  Orchestrator may not be running.")
        sys.exit(1)

    if not _is_process_running(pid):
        warn(f"Process {pid} is not running.  Cleaning up PID file.")
        _remove_pid()
        return

    log(f"Stopping orchestrator (PID {pid})...")
    try:
        os.kill(pid, signal.SIGTERM)
        log("Stop signal sent")
    except OSError as exc:
        err(f"Failed to stop process {pid}: {exc}")
        sys.exit(1)


def cmd_submit(description: str, agent: Optional[str],
               priority: int) -> None:
    """Submit a task via the HTTP API."""
    port = DEFAULT_PORT
    payload = {
        "title": description,
        "description": description,
        "priority": priority,
    }
    if agent:
        payload["agent"] = agent

    try:
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            f"http://localhost:{port}/api/orchestrator/tasks",
            data=data, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            task_id = result.get("task_id", "unknown")
            task = result.get("task", {})
            assigned = task.get("assigned_agent", "unassigned")
            log(f"Task submitted: {task_id}")
            info(f"  Assigned to: {assigned}")
            info(f"  Priority: {priority}")
    except URLError as exc:
        err(f"Cannot connect to orchestrator on port {port}: {exc}")
        err("Is the orchestrator running?  Start with: --start")
        sys.exit(1)


def cmd_status() -> None:
    """Show overall orchestrator status."""
    port = DEFAULT_PORT
    try:
        req = Request(f"http://localhost:{port}/api/orchestrator/status")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        print(f"\n{BOLD}{CYAN}=== Claw Orchestrator Status ==={NC}\n")
        print(f"  Status:     {GREEN}{data.get('status', 'unknown')}{NC}")
        print(f"  Started:    {data.get('started_at', 'unknown')}")
        print(f"  Checked:    {data.get('uptime_check', 'unknown')}")

        agents = data.get("agents", {})
        total = agents.get("total", 0)
        healthy = agents.get("healthy", 0)
        health_color = GREEN if healthy == total else YELLOW if healthy > 0 else RED
        print(f"  Agents:     {health_color}{healthy}/{total} healthy{NC}")

        tasks = data.get("tasks", {})
        if tasks:
            print(f"\n  {BOLD}Tasks:{NC}")
            for status, count in sorted(tasks.items()):
                color = GREEN if status == "completed" else \
                    YELLOW if status == "running" else \
                    RED if status == "failed" else BLUE
                print(f"    {color}{status:<12}{NC} {count}")

        print()

    except URLError as exc:
        err(f"Cannot connect to orchestrator on port {port}: {exc}")
        err("Is the orchestrator running?  Start with: --start")
        sys.exit(1)


def cmd_agents() -> None:
    """List all registered agents with their status."""
    port = DEFAULT_PORT
    try:
        req = Request(f"http://localhost:{port}/api/orchestrator/agents")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        agents = data.get("agents", [])
        print(f"\n{BOLD}{CYAN}=== Claw Agent Registry ==={NC}\n")
        print(f"  {BOLD}{'Agent':<12} {'Status':<12} {'Port':<8} "
              f"{'Load':<10} {'Capabilities'}{NC}")
        print(f"  {'─' * 12} {'─' * 12} {'─' * 8} {'─' * 10} {'─' * 30}")

        for agent in agents:
            name = agent.get("id", "?")
            status = agent.get("status", "unknown")
            port_num = agent.get("port", 0)
            load = f"{agent.get('current_load', 0)}/{agent.get('max_load', 10)}"
            caps = ", ".join(agent.get("capabilities", [])[:4])

            status_color = GREEN if status == "healthy" else \
                RED if status == "unhealthy" else DIM
            print(f"  {name:<12} {status_color}{status:<12}{NC} "
                  f"{port_num:<8} {load:<10} {caps}")

        last_check = None
        for agent in agents:
            lhc = agent.get("last_health_check")
            if lhc:
                last_check = lhc
                break

        if last_check:
            print(f"\n  {DIM}Last health check: {last_check}{NC}")
        print()

    except URLError as exc:
        err(f"Cannot connect to orchestrator on port {port}: {exc}")
        sys.exit(1)


def cmd_pipeline(spec: str, name: str) -> None:
    """Create and optionally execute a pipeline from a spec string.

    Spec format: "picoclaw->nanoclaw->openclaw"
    """
    port = DEFAULT_PORT
    agent_ids = [a.strip() for a in spec.replace("->", ">").split(">")]
    steps = []
    for i, agent_id in enumerate(agent_ids):
        steps.append({
            "agent_id": agent_id,
            "task_title": f"Step {i + 1}: {agent_id} processing",
            "task_desc": f"Pipeline step {i + 1} handled by {agent_id}",
        })

    payload = json.dumps({"name": name, "steps": steps}).encode("utf-8")

    try:
        # Create pipeline
        req = Request(
            f"http://localhost:{port}/api/orchestrator/pipeline",
            data=payload, method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            pipeline_id = result.get("pipeline_id", "unknown")
            log(f"Pipeline created: {pipeline_id}")
            info(f"  Name:  {name}")
            info(f"  Steps: {' -> '.join(agent_ids)}")

        # Execute pipeline
        exec_req = Request(
            f"http://localhost:{port}/api/orchestrator/pipeline/{pipeline_id}/execute",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urlopen(exec_req, timeout=10) as resp:
            exec_result = json.loads(resp.read().decode("utf-8"))
            if exec_result.get("ok"):
                log(f"Pipeline execution started: {pipeline_id}")
            else:
                warn(f"Pipeline execution issue: {exec_result.get('error', '?')}")

    except URLError as exc:
        err(f"Cannot connect to orchestrator on port {port}: {exc}")
        sys.exit(1)


def cmd_health_check() -> None:
    """Trigger a health check on all agents via the HTTP API."""
    port = DEFAULT_PORT
    try:
        # Get list of agents first
        req = Request(f"http://localhost:{port}/api/orchestrator/agents")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        agents = data.get("agents", [])
        print(f"\n{BOLD}{CYAN}=== Claw Health Check ==={NC}\n")

        for agent in agents:
            agent_id = agent.get("id", "?")
            try:
                hc_req = Request(
                    f"http://localhost:{port}/api/orchestrator/agents/{agent_id}/health",
                    data=b"{}",
                    method="POST",
                    headers={"Content-Type": "application/json"}
                )
                with urlopen(hc_req, timeout=15) as hc_resp:
                    result = json.loads(hc_resp.read().decode("utf-8"))
                    ok = result.get("ok", False)
                    detail = result.get("detail", "")
                    status_str = f"{GREEN}HEALTHY{NC}" if ok else f"{RED}UNHEALTHY{NC}"
                    print(f"  {agent_id:<12} {status_str}  {DIM}{detail}{NC}")
            except URLError:
                print(f"  {agent_id:<12} {RED}UNHEALTHY{NC}  {DIM}health check request failed{NC}")

        print()

    except URLError as exc:
        err(f"Cannot connect to orchestrator on port {port}: {exc}")
        sys.exit(1)


# =========================================================================
#  CLI Entry Point
# =========================================================================
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Claw Agents Orchestrator — Multi-Agent Coordination Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""\
examples:
  python3 shared/claw_orchestrator.py --start
  python3 shared/claw_orchestrator.py --start --port 9100
  python3 shared/claw_orchestrator.py --stop
  python3 shared/claw_orchestrator.py --submit "Analyze data.csv" --agent picoclaw --priority 4
  python3 shared/claw_orchestrator.py --status
  python3 shared/claw_orchestrator.py --agents
  python3 shared/claw_orchestrator.py --pipeline "picoclaw->nanoclaw->openclaw" --name "data-pipeline"
  python3 shared/claw_orchestrator.py --health-check
""",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true",
                       help="Start the orchestrator HTTP server")
    group.add_argument("--stop", action="store_true",
                       help="Stop a running orchestrator")
    group.add_argument("--submit", type=str, metavar="DESCRIPTION",
                       help="Submit a task to the orchestrator")
    group.add_argument("--status", action="store_true",
                       help="Show overall orchestrator status")
    group.add_argument("--agents", action="store_true",
                       help="List all registered agents")
    group.add_argument("--pipeline", type=str, metavar="SPEC",
                       help="Create and execute a pipeline (e.g. 'picoclaw->nanoclaw->openclaw')")
    group.add_argument("--health-check", action="store_true",
                       help="Run health checks on all agents")

    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"HTTP server port (default: {DEFAULT_PORT})")
    parser.add_argument("--agent", type=str, default=None,
                        help="Target agent for --submit (e.g. zeroclaw)")
    parser.add_argument("--priority", type=int, default=3,
                        choices=[1, 2, 3, 4, 5],
                        help="Task priority for --submit (1=low, 5=critical)")
    parser.add_argument("--name", type=str, default="unnamed-pipeline",
                        help="Pipeline name for --pipeline")

    args = parser.parse_args()

    if args.start:
        cmd_start(args.port)
    elif args.stop:
        cmd_stop()
    elif args.submit:
        cmd_submit(args.submit, args.agent, args.priority)
    elif args.status:
        cmd_status()
    elif args.agents:
        cmd_agents()
    elif args.pipeline:
        cmd_pipeline(args.pipeline, args.name)
    elif args.health_check:
        cmd_health_check()


if __name__ == "__main__":
    main()
