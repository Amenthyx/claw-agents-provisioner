"""
Tests for orchestrator components — AgentRegistry, TaskQueue, TaskRouter,
PipelineBuilder, EventBus.

These test standalone orchestration patterns used across the Claw provisioner.
Since the orchestrator is composed from multiple modules, these tests verify
the orchestration logic directly.
"""

import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable


# ---------------------------------------------------------------------------
# Minimal orchestrator implementations for testing
# (These would normally live in shared/claw_orchestrator.py)
# ---------------------------------------------------------------------------

class AgentRegistry:
    """Registry of available agents with metadata."""

    def __init__(self):
        self._agents: Dict[str, Dict[str, Any]] = {}

    def register(self, agent_id: str, capabilities: List[str],
                 platform: str = "zeroclaw") -> None:
        self._agents[agent_id] = {
            "agent_id": agent_id,
            "capabilities": capabilities,
            "platform": platform,
            "registered_at": time.time(),
        }

    def get(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self._agents.get(agent_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        return list(self._agents.values())

    def find_by_capability(self, capability: str) -> List[Dict[str, Any]]:
        return [a for a in self._agents.values() if capability in a["capabilities"]]


class TaskQueue:
    """Simple in-memory task queue."""

    def __init__(self):
        self._tasks: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def submit(self, task_type: str, payload: Dict[str, Any],
               priority: int = 5) -> str:
        task_id = str(uuid.uuid4())
        with self._lock:
            self._tasks.append({
                "task_id": task_id,
                "task_type": task_type,
                "payload": payload,
                "priority": priority,
                "status": "pending",
                "submitted_at": time.time(),
            })
        return task_id

    def get_pending(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            pending = [t for t in self._tasks if t["status"] == "pending"]
            pending.sort(key=lambda t: t["priority"])
            return pending[:limit]

    def complete(self, task_id: str) -> bool:
        with self._lock:
            for task in self._tasks:
                if task["task_id"] == task_id:
                    task["status"] = "completed"
                    return True
        return False


class TaskRouter:
    """Routes tasks to appropriate agents based on capability matching."""

    def __init__(self, registry: AgentRegistry):
        self._registry = registry

    def route(self, task_type: str) -> Optional[Dict[str, Any]]:
        agents = self._registry.find_by_capability(task_type)
        if agents:
            return agents[0]
        return None


class PipelineBuilder:
    """Builds sequential processing pipelines."""

    def __init__(self):
        self._steps: List[Dict[str, Any]] = []

    def add_step(self, name: str, handler: Callable, **kwargs) -> "PipelineBuilder":
        self._steps.append({"name": name, "handler": handler, "kwargs": kwargs})
        return self

    def create(self) -> Dict[str, Any]:
        return {
            "pipeline_id": str(uuid.uuid4()),
            "steps": [{"name": s["name"]} for s in self._steps],
            "step_count": len(self._steps),
        }

    def execute(self, data: Any) -> Any:
        result = data
        for step in self._steps:
            result = step["handler"](result, **step["kwargs"])
        return result


class EventBus:
    """Simple publish/subscribe event system."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, callback: Callable) -> None:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, data: Any = None) -> int:
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))
        for handler in handlers:
            handler(data)
        return len(handlers)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    """Tests for AgentRegistry."""

    def test_register_and_get(self):
        """Register an agent and retrieve it by ID."""
        registry = AgentRegistry()
        registry.register("agent-1", ["coding", "review"], platform="zeroclaw")
        agent = registry.get("agent-1")
        assert agent is not None
        assert agent["agent_id"] == "agent-1"
        assert "coding" in agent["capabilities"]
        assert agent["platform"] == "zeroclaw"

    def test_list_agents(self):
        """list_agents should return all registered agents."""
        registry = AgentRegistry()
        registry.register("a1", ["coding"])
        registry.register("a2", ["review"])
        agents = registry.list_agents()
        assert len(agents) == 2

    def test_find_by_capability(self):
        """find_by_capability should filter agents by capability."""
        registry = AgentRegistry()
        registry.register("a1", ["coding", "review"])
        registry.register("a2", ["review", "testing"])
        registry.register("a3", ["coding"])

        coders = registry.find_by_capability("coding")
        assert len(coders) == 2

        reviewers = registry.find_by_capability("review")
        assert len(reviewers) == 2

    def test_get_missing_agent(self):
        """get for a nonexistent agent should return None."""
        registry = AgentRegistry()
        assert registry.get("missing") is None


class TestTaskQueue:
    """Tests for TaskQueue."""

    def test_submit_and_get_pending(self):
        """Submit tasks and retrieve pending ones."""
        queue = TaskQueue()
        tid1 = queue.submit("coding", {"file": "main.py"}, priority=3)
        tid2 = queue.submit("review", {"pr": 42}, priority=1)

        pending = queue.get_pending()
        assert len(pending) == 2
        # Priority 1 should come first
        assert pending[0]["priority"] == 1

    def test_complete_task(self):
        """Completing a task should remove it from pending."""
        queue = TaskQueue()
        tid = queue.submit("coding", {"file": "app.py"})
        assert len(queue.get_pending()) == 1

        queue.complete(tid)
        assert len(queue.get_pending()) == 0

    def test_submit_returns_unique_ids(self):
        """Each submitted task should have a unique ID."""
        queue = TaskQueue()
        ids = set()
        for i in range(10):
            tid = queue.submit("task", {"n": i})
            ids.add(tid)
        assert len(ids) == 10


class TestTaskRouter:
    """Tests for TaskRouter."""

    def test_route_matching(self):
        """Router should find an agent matching the task type."""
        registry = AgentRegistry()
        registry.register("coder", ["coding", "debugging"])
        registry.register("writer", ["creative", "marketing"])

        router = TaskRouter(registry)
        agent = router.route("coding")
        assert agent is not None
        assert agent["agent_id"] == "coder"

    def test_route_no_match(self):
        """Router should return None when no agent matches."""
        registry = AgentRegistry()
        registry.register("coder", ["coding"])

        router = TaskRouter(registry)
        agent = router.route("music_composition")
        assert agent is None


class TestPipelineBuilder:
    """Tests for PipelineBuilder."""

    def test_create_pipeline(self):
        """create should return a pipeline descriptor."""
        builder = PipelineBuilder()
        builder.add_step("step1", lambda x: x)
        builder.add_step("step2", lambda x: x)
        pipeline = builder.create()

        assert "pipeline_id" in pipeline
        assert pipeline["step_count"] == 2
        assert len(pipeline["steps"]) == 2
        assert pipeline["steps"][0]["name"] == "step1"

    def test_execute_pipeline(self):
        """execute should chain step handlers sequentially."""
        builder = PipelineBuilder()
        builder.add_step("double", lambda x: x * 2)
        builder.add_step("add_ten", lambda x: x + 10)

        result = builder.execute(5)
        assert result == 20  # (5 * 2) + 10

    def test_empty_pipeline(self):
        """Empty pipeline should pass data through unchanged."""
        builder = PipelineBuilder()
        result = builder.execute("hello")
        assert result == "hello"


class TestEventBus:
    """Tests for EventBus publish/subscribe."""

    def test_publish_subscribe(self):
        """Subscribers should receive published events."""
        bus = EventBus()
        received = []
        bus.subscribe("task.completed", lambda data: received.append(data))

        count = bus.publish("task.completed", {"task_id": "123"})
        assert count == 1
        assert len(received) == 1
        assert received[0]["task_id"] == "123"

    def test_multiple_subscribers(self):
        """Multiple subscribers should all receive the event."""
        bus = EventBus()
        results_a = []
        results_b = []
        bus.subscribe("event", lambda d: results_a.append(d))
        bus.subscribe("event", lambda d: results_b.append(d))

        bus.publish("event", "data")
        assert len(results_a) == 1
        assert len(results_b) == 1

    def test_publish_no_subscribers(self):
        """Publishing with no subscribers should return 0."""
        bus = EventBus()
        count = bus.publish("unsubscribed.event", "data")
        assert count == 0

    def test_separate_event_types(self):
        """Different event types should be isolated."""
        bus = EventBus()
        a_data = []
        b_data = []
        bus.subscribe("type_a", lambda d: a_data.append(d))
        bus.subscribe("type_b", lambda d: b_data.append(d))

        bus.publish("type_a", "A")
        assert len(a_data) == 1
        assert len(b_data) == 0
