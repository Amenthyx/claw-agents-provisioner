"""
Tests for shared/claw_memory.py — Conversation Memory Engine.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_memory import ConversationStore


class TestConversationStoreCreation:
    """Tests for ConversationStore initialization."""

    def test_store_creates_db(self, tmp_path):
        """ConversationStore should create the SQLite database file."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        assert db_path.exists()
        store.close()

    def test_store_initializes_schema(self, tmp_path):
        """ConversationStore should create conversations and messages tables."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        # Verify tables exist by attempting operations
        conv = store.create_conversation("test-agent")
        assert conv is not None
        assert conv["agent_id"] == "test-agent"
        store.close()


class TestCreateConversation:
    """Tests for conversation creation."""

    def test_create_conversation(self, tmp_path):
        """create_conversation should return a conversation dict with ID."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("agent-1")
        assert "id" in conv
        assert conv["agent_id"] == "agent-1"
        assert conv["created_at"] is not None
        assert conv["summary"] is None
        store.close()

    def test_create_with_custom_id(self, tmp_path):
        """create_conversation should accept a custom conversation ID."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("agent-1", conversation_id="custom-id-123")
        assert conv["id"] == "custom-id-123"
        store.close()


class TestAddMessage:
    """Tests for message management."""

    def test_add_message(self, tmp_path):
        """add_message should insert a message and return it."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("agent-1")
        msg = store.add_message(conv["id"], "user", "Hello!", tokens=5)
        assert msg is not None
        assert msg["role"] == "user"
        assert msg["content"] == "Hello!"
        assert msg["tokens"] == 5
        store.close()

    def test_add_message_nonexistent_conversation(self, tmp_path):
        """add_message to nonexistent conversation should return None."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        msg = store.add_message("nonexistent-id", "user", "Hello!")
        assert msg is None
        store.close()


class TestGetConversation:
    """Tests for conversation retrieval with messages."""

    def test_get_conversation_with_messages(self, tmp_path):
        """get_conversation should return conversation with all messages."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Hello!")
        store.add_message(conv["id"], "assistant", "Hi there!")
        store.add_message(conv["id"], "user", "How are you?")

        result = store.get_conversation(conv["id"])
        assert result is not None
        assert len(result["messages"]) == 3
        assert result["messages"][0]["role"] == "user"
        assert result["messages"][1]["role"] == "assistant"
        store.close()

    def test_get_nonexistent_conversation(self, tmp_path):
        """get_conversation for missing ID should return None."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        result = store.get_conversation("does-not-exist")
        assert result is None
        store.close()


class TestSearch:
    """Tests for conversation search."""

    def test_search_finds_messages(self, tmp_path):
        """search should find messages matching the query."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Tell me about Python programming")
        store.add_message(conv["id"], "assistant", "Python is a great language")
        store.add_message(conv["id"], "user", "What about JavaScript?")

        results = store.search("Python")
        assert len(results) == 2  # Both messages mention Python
        store.close()

    def test_search_no_results(self, tmp_path):
        """search with no matching content should return empty."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Hello world")

        results = store.search("quantum-entanglement-xyz")
        assert len(results) == 0
        store.close()


class TestPrune:
    """Tests for conversation pruning."""

    def test_prune_old_conversations(self, tmp_path):
        """prune should delete conversations older than the threshold."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)

        # Create a conversation and manually set old timestamp
        conv = store.create_conversation("agent-1")
        old_time = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        store._conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (old_time, conv["id"]),
        )

        # Create a recent conversation
        recent = store.create_conversation("agent-2")

        deleted = store.prune(days=30)
        assert deleted == 1

        # Recent conversation should still exist
        assert store.get_conversation(recent["id"]) is not None
        # Old conversation should be gone
        assert store.get_conversation(conv["id"]) is None
        store.close()


class TestExport:
    """Tests for conversation export."""

    def test_export_json(self, tmp_path):
        """export_json should return valid JSON string."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Hello")

        result = store.export_json(conv["id"])
        assert result is not None
        parsed = json.loads(result)
        assert parsed["id"] == conv["id"]
        assert len(parsed["messages"]) == 1
        store.close()

    def test_export_markdown(self, tmp_path):
        """export_markdown should return formatted markdown."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv = store.create_conversation("agent-1")
        store.add_message(conv["id"], "user", "Hello")
        store.add_message(conv["id"], "assistant", "Hi!")

        result = store.export_markdown(conv["id"])
        assert result is not None
        assert f"# Conversation {conv['id']}" in result
        assert "### USER" in result
        assert "### ASSISTANT" in result
        store.close()

    def test_export_nonexistent(self, tmp_path):
        """Export of nonexistent conversation should return None."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        assert store.export_json("missing") is None
        assert store.export_markdown("missing") is None
        store.close()


class TestStats:
    """Tests for usage statistics."""

    def test_stats(self, tmp_path):
        """get_stats should return correct counts."""
        db_path = tmp_path / "test.db"
        store = ConversationStore(db_path=db_path)
        conv1 = store.create_conversation("agent-1")
        conv2 = store.create_conversation("agent-2")
        store.add_message(conv1["id"], "user", "Hello", tokens=10)
        store.add_message(conv1["id"], "assistant", "Hi", tokens=5)
        store.add_message(conv2["id"], "user", "Test", tokens=3)

        stats = store.get_stats()
        assert stats["conversations"] == 2
        assert stats["messages"] == 3
        assert stats["total_tokens"] == 18
        assert stats["unique_agents"] == 2
        store.close()
