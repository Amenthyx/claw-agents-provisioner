"""
Integration tests for the Memory service — verifies ConversationStore
read/write/search operations with SQLite, cross-agent context sharing,
retention policies, and interaction with auth/rate-limit middleware.
"""

import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_memory import ConversationStore
from claw_auth import check_auth
from claw_ratelimit import RateLimiter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    """Create a ConversationStore with a temp database."""
    db_path = tmp_path / "test_memory.db"
    s = ConversationStore(db_path=db_path)
    yield s
    s.close()


# ---------------------------------------------------------------------------
# CRUD integration
# ---------------------------------------------------------------------------

class TestMemoryCRUDIntegration:
    """Tests full conversation CRUD lifecycle in a single store."""

    def test_create_add_get_cycle(self, store):
        """Create conversation -> add messages -> retrieve all."""
        conv = store.create_conversation("agent-alpha")
        assert conv["agent_id"] == "agent-alpha"

        msg1 = store.add_message(conv["id"], "user", "Hello, agent!")
        msg2 = store.add_message(conv["id"], "assistant", "Hi! How can I help?")
        msg3 = store.add_message(conv["id"], "user", "Help me with Python")

        assert msg1 is not None
        assert msg2 is not None
        assert msg3 is not None

        retrieved = store.get_conversation(conv["id"])
        assert retrieved is not None
        assert len(retrieved["messages"]) == 3
        assert retrieved["messages"][0]["content"] == "Hello, agent!"
        assert retrieved["messages"][1]["role"] == "assistant"
        assert retrieved["messages"][2]["content"] == "Help me with Python"

    def test_multiple_conversations_isolation(self, store):
        """Messages in one conversation should not appear in another."""
        conv1 = store.create_conversation("agent-1")
        conv2 = store.create_conversation("agent-2")

        store.add_message(conv1["id"], "user", "Message for conv1")
        store.add_message(conv2["id"], "user", "Message for conv2")

        c1 = store.get_conversation(conv1["id"])
        c2 = store.get_conversation(conv2["id"])

        assert len(c1["messages"]) == 1
        assert len(c2["messages"]) == 1
        assert c1["messages"][0]["content"] == "Message for conv1"
        assert c2["messages"][0]["content"] == "Message for conv2"

    def test_delete_conversation_cascade(self, store):
        """Deleting a conversation should also delete its messages."""
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Will be deleted")
        store.add_message(conv["id"], "assistant", "Also deleted")

        deleted = store.delete_conversation(conv["id"])
        assert deleted is True

        result = store.get_conversation(conv["id"])
        assert result is None

    def test_delete_nonexistent_returns_false(self, store):
        """Deleting a nonexistent conversation should return False."""
        deleted = store.delete_conversation("nonexistent-id")
        assert deleted is False


# ---------------------------------------------------------------------------
# Search integration
# ---------------------------------------------------------------------------

class TestMemorySearchIntegration:
    """Tests full-text search across conversations and agents."""

    def test_search_across_conversations(self, store):
        """Search should find messages across different conversations."""
        conv1 = store.create_conversation("agent-1")
        conv2 = store.create_conversation("agent-2")

        store.add_message(conv1["id"], "user", "Python programming is fun")
        store.add_message(conv2["id"], "user", "Python data analysis")
        store.add_message(conv2["id"], "user", "JavaScript frameworks")

        results = store.search("Python")
        assert len(results) == 2

    def test_search_with_agent_filter(self, store):
        """Search filtered by agent_id should only return that agent's messages."""
        conv1 = store.create_conversation("agent-alpha")
        conv2 = store.create_conversation("agent-beta")

        store.add_message(conv1["id"], "user", "Machine learning in Python")
        store.add_message(conv2["id"], "user", "Machine learning in R")

        results = store.search("Machine learning", agent_id="agent-alpha")
        assert len(results) == 1
        assert "Python" in results[0]["content"]

    def test_search_empty_results(self, store):
        """Search for nonexistent content should return empty list."""
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Hello world")

        results = store.search("quantum-entanglement-nonexistent")
        assert len(results) == 0

    def test_search_case_insensitive(self, store):
        """Search should be case-insensitive via LIKE."""
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Python Programming Language")

        results = store.search("python")
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# Context sharing integration
# ---------------------------------------------------------------------------

class TestContextSharingIntegration:
    """Tests cross-agent context sharing workflow."""

    def test_share_and_retrieve_context(self, store):
        """Agent A shares context -> Agent B retrieves it."""
        conv = store.create_conversation("agent-alpha")
        store.add_message(conv["id"], "user", "Discussed project architecture")
        store.add_message(conv["id"], "assistant", "Recommended microservices approach")

        # Agent alpha shares context with agent beta
        share_result = store.share_context(
            from_agent="agent-alpha",
            to_agent="agent-beta",
            conversation_id=conv["id"],
            context_summary="User discussed project architecture. "
                            "Recommended microservices approach.",
        )
        assert share_result["from_agent"] == "agent-alpha"
        assert share_result["to_agent"] == "agent-beta"
        assert "shared_at" in share_result

        # Agent beta retrieves shared context
        shared = store.get_shared_context("agent-beta")
        assert len(shared) == 1
        assert "microservices" in shared[0]["context_summary"]

    def test_multiple_shares_to_same_agent(self, store):
        """Multiple agents can share context to the same target agent."""
        conv1 = store.create_conversation("agent-1")
        conv2 = store.create_conversation("agent-2")

        store.share_context("agent-1", "agent-target", conv1["id"],
                            "Context from agent 1")
        store.share_context("agent-2", "agent-target", conv2["id"],
                            "Context from agent 2")

        shared = store.get_shared_context("agent-target")
        assert len(shared) == 2

    def test_shared_context_isolation(self, store):
        """Context shared to agent A should not appear for agent B."""
        conv = store.create_conversation("agent-source")

        store.share_context("agent-source", "agent-a", conv["id"],
                            "For agent A only")

        a_context = store.get_shared_context("agent-a")
        b_context = store.get_shared_context("agent-b")

        assert len(a_context) == 1
        assert len(b_context) == 0


# ---------------------------------------------------------------------------
# Token tracking integration
# ---------------------------------------------------------------------------

class TestTokenTrackingIntegration:
    """Tests token counting across messages and conversations."""

    def test_token_counts_in_stats(self, store):
        """Stats should correctly aggregate token counts."""
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Hello", tokens=10)
        store.add_message(conv["id"], "assistant", "Hi there", tokens=15)
        store.add_message(conv["id"], "user", "How are you?", tokens=8)

        stats = store.get_stats()
        assert stats["total_tokens"] == 33
        assert stats["messages"] == 3

    def test_token_counts_multi_conversation(self, store):
        """Token counts should aggregate across all conversations."""
        conv1 = store.create_conversation("agent-1")
        conv2 = store.create_conversation("agent-2")

        store.add_message(conv1["id"], "user", "Query 1", tokens=100)
        store.add_message(conv2["id"], "user", "Query 2", tokens=200)

        stats = store.get_stats()
        assert stats["total_tokens"] == 300
        assert stats["conversations"] == 2
        assert stats["unique_agents"] == 2


# ---------------------------------------------------------------------------
# Export integration
# ---------------------------------------------------------------------------

class TestExportIntegration:
    """Tests conversation export in JSON and Markdown formats."""

    def test_export_json_roundtrip(self, store):
        """Exported JSON should be parseable and contain all messages."""
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "What is Python?")
        store.add_message(conv["id"], "assistant", "Python is a language.")

        exported = store.export_json(conv["id"])
        assert exported is not None

        parsed = json.loads(exported)
        assert parsed["id"] == conv["id"]
        assert len(parsed["messages"]) == 2

    def test_export_markdown_format(self, store):
        """Exported markdown should contain conversation header and messages."""
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Hello")
        store.add_message(conv["id"], "assistant", "World")

        md = store.export_markdown(conv["id"])
        assert md is not None
        assert "# Conversation" in md
        assert "USER" in md
        assert "ASSISTANT" in md


# ---------------------------------------------------------------------------
# Prune integration
# ---------------------------------------------------------------------------

class TestPruneIntegration:
    """Tests conversation pruning respects age thresholds."""

    def test_prune_preserves_recent(self, store):
        """Pruning should keep recent conversations and only delete old ones."""
        # Create old conversation
        old_conv = store.create_conversation("agent-old")
        store.add_message(old_conv["id"], "user", "Old message")
        old_time = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        store._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (old_time, old_conv["id"]),
        )

        # Create recent conversation
        recent_conv = store.create_conversation("agent-recent")
        store.add_message(recent_conv["id"], "user", "Recent message")

        deleted = store.prune(days=30)
        assert deleted == 1

        assert store.get_conversation(old_conv["id"]) is None
        assert store.get_conversation(recent_conv["id"]) is not None


# ---------------------------------------------------------------------------
# Auth + Memory integration
# ---------------------------------------------------------------------------

class TestMemoryAuthIntegration:
    """Tests that auth middleware gates memory access correctly."""

    def test_auth_required_for_memory_write(self, monkeypatch, store):
        """Simulates auth-gated memory write: auth pass -> write succeeds."""
        monkeypatch.setenv("CLAW_API_TOKEN", "mem-token")
        ok, _ = check_auth({"Authorization": "Bearer mem-token"})
        assert ok is True

        # If auth passes, memory operations proceed normally
        conv = store.create_conversation("gated-agent")
        msg = store.add_message(conv["id"], "user", "Authenticated write")
        assert msg is not None
        assert msg["content"] == "Authenticated write"

    def test_auth_failure_blocks_memory_access(self, monkeypatch):
        """Simulates auth-gated access: auth fail -> no memory operations."""
        monkeypatch.setenv("CLAW_API_TOKEN", "secret")
        ok, err = check_auth({"Authorization": "Bearer wrong"})
        assert ok is False
        # In real server, the handler would return 401 and not touch memory


# ---------------------------------------------------------------------------
# List conversations integration
# ---------------------------------------------------------------------------

class TestListConversationsIntegration:
    """Tests listing conversations with filters."""

    def test_list_all_conversations(self, store):
        """list_conversations should return all conversations."""
        store.create_conversation("agent-1")
        store.create_conversation("agent-2")
        store.create_conversation("agent-1")

        convs = store.list_conversations()
        assert len(convs) == 3

    def test_list_by_agent(self, store):
        """list_conversations with agent filter should return only that agent."""
        store.create_conversation("agent-1")
        store.create_conversation("agent-2")
        store.create_conversation("agent-1")

        convs = store.list_conversations(agent_id="agent-1")
        assert len(convs) == 2
        for c in convs:
            assert c["agent_id"] == "agent-1"

    def test_list_with_pagination(self, store):
        """list_conversations should respect limit and offset."""
        for i in range(5):
            store.create_conversation(f"agent-{i}")

        page1 = store.list_conversations(limit=2, offset=0)
        page2 = store.list_conversations(limit=2, offset=2)

        assert len(page1) == 2
        assert len(page2) == 2

        # Pages should have different conversations
        ids_1 = {c["id"] for c in page1}
        ids_2 = {c["id"] for c in page2}
        assert ids_1.isdisjoint(ids_2)
