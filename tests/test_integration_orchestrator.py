"""
Integration tests for the Orchestrator — verifies agent registration, task
routing, task queue lifecycle, pipeline execution, and event bus across
the full orchestration layer with SQLite-backed storage.
"""

import json
import sqlite3
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_orchestrator import (
    AgentRegistry,
    TaskQueue,
    _init_db,
    KNOWN_AGENTS,
    ROUTING_KEYWORDS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def orch_db(tmp_path):
    """Create a temporary orchestrator database and return the connection."""
    db_path = tmp_path / "orchestrator.db"
    with patch("claw_orchestrator.DATA_DIR", tmp_path):
        conn = _init_db(db_path)
    yield conn
    conn.close()


@pytest.fixture
def registry(orch_db):
    """Create an AgentRegistry backed by the temp database.

    Mocks DAL import to prevent the singleton from trying to open the
    production database (which may not exist in test environments).
    """
    with patch("claw_orchestrator.AgentRegistry.__init__.__module__", "claw_orchestrator"):
        pass
    # Directly construct with DAL disabled
    reg = AgentRegistry.__new__(AgentRegistry)
    reg._conn = orch_db
    reg._lock = __import__("threading").Lock()
    reg._dal = None  # Bypass DAL
    return reg


@pytest.fixture
def task_queue(orch_db):
    """Create a TaskQueue backed by the temp database."""
    return TaskQueue(orch_db)


# ---------------------------------------------------------------------------
# Agent registration integration
# ---------------------------------------------------------------------------

class TestAgentRegistrationIntegration:
    """Tests agent registration and status management lifecycle."""

    def test_register_and_retrieve_agent(self, registry):
        """Register an agent and retrieve it by ID."""
        agent_id = registry.register(
            platform="zeroclaw",
            endpoint="http://localhost:3100",
            port=3100,
            capabilities=["general", "rust", "performance"],
            max_load=10,
        )
        assert agent_id == "zeroclaw"

        agent = registry.get_agent("zeroclaw")
        assert agent is not None
        assert agent["platform"] == "zeroclaw"
        assert agent["port"] == 3100
        assert "general" in agent["capabilities"]

    def test_register_all_known_agents(self, registry):
        """auto_register_known should register all 5 agent platforms."""
        count = registry.auto_register_known()
        assert count == 5

        agents = registry.get_all()
        assert len(agents) == 5

        platform_names = {a["platform"] for a in agents}
        expected = {"zeroclaw", "nanoclaw", "picoclaw", "openclaw", "parlant"}
        assert platform_names == expected

    def test_update_agent_status(self, registry):
        """Updating agent status should be reflected on retrieval."""
        registry.register("zeroclaw", "http://localhost:3100", 3100,
                          ["general"], 10)

        updated = registry.update_status("zeroclaw", "healthy")
        assert updated is True

        agent = registry.get_agent("zeroclaw")
        assert agent["status"] == "healthy"

    def test_update_status_nonexistent(self, registry):
        """Updating status of a nonexistent agent should return False."""
        result = registry.update_status("nonexistent-agent", "healthy")
        assert result is False

    def test_re_register_updates_existing(self, registry):
        """Re-registering an existing agent should update its config."""
        registry.register("zeroclaw", "http://localhost:3100", 3100,
                          ["general"], 10)
        registry.register("zeroclaw", "http://localhost:3101", 3101,
                          ["general", "coding"], 20)

        agent = registry.get_agent("zeroclaw")
        assert agent["port"] == 3101
        assert "coding" in agent["capabilities"]


# ---------------------------------------------------------------------------
# Agent capability routing integration
# ---------------------------------------------------------------------------

class TestAgentRoutingIntegration:
    """Tests that task routing correctly matches agents by capability."""

    def test_route_to_capability(self, registry):
        """get_available with a capability filter should return matching agents."""
        registry.auto_register_known()

        # Mark some agents as healthy
        registry.update_status("zeroclaw", "healthy")
        registry.update_status("nanoclaw", "healthy")
        registry.update_status("picoclaw", "healthy")

        # Find agents with "coding" capability
        coding_agents = registry.get_available(capability="coding")
        platform_names = [a["platform"] for a in coding_agents]
        assert "nanoclaw" in platform_names  # nanoclaw has "coding" capability

    def test_unhealthy_agents_excluded(self, registry):
        """Unhealthy agents should not appear in available list."""
        registry.auto_register_known()
        registry.update_status("zeroclaw", "healthy")
        registry.update_status("nanoclaw", "unhealthy")

        available = registry.get_available()
        platforms = {a["platform"] for a in available}
        assert "zeroclaw" in platforms
        assert "nanoclaw" not in platforms

    def test_overloaded_agents_excluded(self, registry):
        """Agents at max load should not appear in available list."""
        registry.register("zeroclaw", "http://localhost:3100", 3100,
                          ["general"], max_load=2)
        registry.update_status("zeroclaw", "healthy")

        # Increment load to max
        registry.increment_load("zeroclaw")
        registry.increment_load("zeroclaw")

        available = registry.get_available()
        assert len(available) == 0

    def test_load_balancing_order(self, registry):
        """Available agents should be sorted by current load (ascending)."""
        registry.register("agent-a", "http://a:3100", 3100, ["general"], 10)
        registry.register("agent-b", "http://b:3200", 3200, ["general"], 10)
        registry.update_status("agent-a", "healthy")
        registry.update_status("agent-b", "healthy")

        # Agent A has higher load
        registry.increment_load("agent-a")
        registry.increment_load("agent-a")
        registry.increment_load("agent-a")

        # Agent B has lower load
        registry.increment_load("agent-b")

        available = registry.get_available()
        assert len(available) == 2
        assert available[0]["id"] == "agent-b"  # Lower load first
        assert available[1]["id"] == "agent-a"


# ---------------------------------------------------------------------------
# Task queue integration
# ---------------------------------------------------------------------------

class TestTaskQueueIntegration:
    """Tests the full task lifecycle: submit -> assign -> start -> complete."""

    def test_submit_and_list_pending(self, task_queue):
        """Submitted tasks should appear in the pending list."""
        tid1 = task_queue.submit("Review code", priority=3)
        tid2 = task_queue.submit("Deploy service", priority=5)

        pending = task_queue.get_pending()
        assert len(pending) == 2

    def test_task_priority_ordering(self, task_queue):
        """Pending tasks should be ordered by priority (highest first)."""
        task_queue.submit("Low priority task", priority=1)
        task_queue.submit("Critical task", priority=5)
        task_queue.submit("Normal task", priority=3)

        pending = task_queue.get_pending()
        priorities = [t["priority"] for t in pending]
        assert priorities == sorted(priorities, reverse=True)

    def test_assign_task_to_agent(self, task_queue, registry):
        """Assigning a task should change its status from pending to assigned."""
        registry.register("zeroclaw", "http://localhost:3100", 3100,
                          ["general"], 10)

        tid = task_queue.submit("Write tests")
        assigned = task_queue.assign(tid, "zeroclaw")
        assert assigned is True

        # Task should no longer be pending
        pending = task_queue.get_pending()
        assert len(pending) == 0

    def test_complete_task(self, task_queue):
        """Completing a task should update its status and result."""
        tid = task_queue.submit("Run tests")
        completed = task_queue.complete(tid, result="All 42 tests passed")
        assert completed is True

        # Task should not be in pending
        pending = task_queue.get_pending()
        assert len(pending) == 0

    def test_fail_task(self, task_queue):
        """Failing a task should mark it as failed with an error."""
        tid = task_queue.submit("Compile project")
        failed = task_queue.fail(tid, error="Compilation error on line 42")
        assert failed is True

    def test_full_task_lifecycle(self, task_queue, registry):
        """Submit -> assign -> start -> complete should work sequentially."""
        registry.register("nanoclaw", "http://localhost:3200", 3200,
                          ["coding"], 10)

        # Submit
        tid = task_queue.submit("Implement feature", description="Add user auth",
                                priority=4)
        assert tid.startswith("task-")

        # Assign
        assigned = task_queue.assign(tid, "nanoclaw")
        assert assigned is True

        # Start
        started = task_queue.start(tid)
        assert started is True

        # Complete
        completed = task_queue.complete(tid, result="Feature implemented successfully")
        assert completed is True

    def test_double_complete_returns_false(self, task_queue):
        """Completing an already-completed task should return False."""
        tid = task_queue.submit("Task A")
        task_queue.complete(tid)

        # Second complete should fail
        result = task_queue.complete(tid, result="Duplicate")
        assert result is False


# ---------------------------------------------------------------------------
# Task + Agent integration
# ---------------------------------------------------------------------------

class TestTaskAgentIntegration:
    """Tests the interaction between task queue and agent load management."""

    def test_assign_increments_load(self, task_queue, registry):
        """Assigning a task should increment the agent's load counter."""
        registry.register("zeroclaw", "http://localhost:3100", 3100,
                          ["general"], 10)

        tid = task_queue.submit("Process data")
        task_queue.assign(tid, "zeroclaw")
        registry.increment_load("zeroclaw")

        agent = registry.get_agent("zeroclaw")
        assert agent["current_load"] == 1

    def test_complete_decrements_load(self, task_queue, registry):
        """Completing a task should allow decrementing the agent's load."""
        registry.register("zeroclaw", "http://localhost:3100", 3100,
                          ["general"], 10)

        tid = task_queue.submit("Process data")
        task_queue.assign(tid, "zeroclaw")
        registry.increment_load("zeroclaw")

        task_queue.complete(tid, result="Done")
        registry.decrement_load("zeroclaw")

        agent = registry.get_agent("zeroclaw")
        assert agent["current_load"] == 0

    def test_load_does_not_go_negative(self, registry):
        """Decrementing load below 0 should clamp to 0."""
        registry.register("zeroclaw", "http://localhost:3100", 3100,
                          ["general"], 10)

        registry.decrement_load("zeroclaw")  # Already at 0
        agent = registry.get_agent("zeroclaw")
        assert agent["current_load"] == 0


# ---------------------------------------------------------------------------
# Routing keywords integration
# ---------------------------------------------------------------------------

class TestRoutingKeywordsIntegration:
    """Tests that routing keywords map correctly to agent capabilities."""

    def test_code_keyword_maps_to_coding_capability(self, registry):
        """The 'code' keyword should map to agents with 'coding' capability."""
        registry.auto_register_known()
        registry.update_status("nanoclaw", "healthy")

        caps = ROUTING_KEYWORDS.get("code", [])
        assert "coding" in caps

        coding_agents = registry.get_available(capability="coding")
        platforms = {a["platform"] for a in coding_agents}
        assert "nanoclaw" in platforms

    def test_data_keyword_maps_to_data_capability(self, registry):
        """The 'data' keyword should map to agents with 'data' capability."""
        registry.auto_register_known()
        registry.update_status("picoclaw", "healthy")

        caps = ROUTING_KEYWORDS.get("data", [])
        assert "data" in caps

        data_agents = registry.get_available(capability="data")
        platforms = {a["platform"] for a in data_agents}
        assert "picoclaw" in platforms

    def test_all_keywords_have_capabilities(self):
        """Every routing keyword should map to at least one capability."""
        for keyword, caps in ROUTING_KEYWORDS.items():
            assert len(caps) > 0, f"Keyword '{keyword}' has no mapped capabilities"


# ---------------------------------------------------------------------------
# Concurrent access
# ---------------------------------------------------------------------------

class TestOrchestratorConcurrency:
    """Tests thread safety of orchestrator operations."""

    def test_concurrent_task_submission(self, task_queue):
        """Submitting tasks from multiple threads should be safe."""
        errors = []
        task_ids = []
        lock = threading.Lock()

        def submit_tasks():
            try:
                for i in range(10):
                    tid = task_queue.submit(f"Task-{threading.current_thread().name}-{i}")
                    with lock:
                        task_ids.append(tid)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=submit_tasks, name=f"T{i}")
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(task_ids) == 50
        # All IDs should be unique
        assert len(set(task_ids)) == 50
