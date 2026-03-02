"""
Integration tests for the RAG pipeline — verifies the full ingest -> index ->
search workflow with DocumentLoader, TrigramIndex, and KnowledgeBase.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_rag import DocumentLoader, TrigramIndex, KnowledgeBase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_docs(tmp_path):
    """Create a temp directory with sample documents for ingestion."""
    doc_dir = tmp_path / "docs"
    doc_dir.mkdir()

    # Plain text document
    (doc_dir / "python.txt").write_text(
        "Python is a high-level programming language known for readability. "
        "It supports multiple paradigms including object-oriented, procedural, "
        "and functional programming. Python has a large standard library and "
        "is widely used in web development, data science, and AI applications."
    )

    # Markdown document
    (doc_dir / "rust.md").write_text(
        "# Rust Programming Language\n\n"
        "Rust is a systems programming language focused on safety, speed, "
        "and concurrency. It prevents null pointer dereferences and data "
        "races at compile time through its ownership model. Rust is used "
        "for operating systems, game engines, and WebAssembly applications."
    )

    # JSON document
    (doc_dir / "config.json").write_text(json.dumps({
        "database": {"host": "localhost", "port": 5432, "name": "mydb"},
        "cache": {"enabled": True, "ttl": 300},
        "features": ["search", "autocomplete", "recommendations"],
    }, indent=2))

    # JSONL document
    (doc_dir / "logs.jsonl").write_text(
        '{"level": "info", "msg": "Server started on port 8080"}\n'
        '{"level": "warn", "msg": "High memory usage detected"}\n'
        '{"level": "error", "msg": "Database connection timeout"}\n'
    )

    return doc_dir


@pytest.fixture
def knowledge_base():
    """Create an empty KnowledgeBase for testing."""
    index = TrigramIndex()
    chunks = {}
    files = {}
    return KnowledgeBase("test-agent", index, chunks, files)


@pytest.fixture
def shared_state():
    """Return shared mutable state for multi-agent tests."""
    return {
        "index": TrigramIndex(),
        "chunks": {},
        "files": {},
    }


# ---------------------------------------------------------------------------
# Ingest -> Search pipeline
# ---------------------------------------------------------------------------

class TestIngestSearchPipeline:
    """Tests the full ingest -> index -> search workflow."""

    def test_ingest_single_file_and_search(self, tmp_path, knowledge_base):
        """Ingest a text file, then search for its content."""
        doc = tmp_path / "test.txt"
        doc.write_text(
            "Machine learning is a subset of artificial intelligence. "
            "It enables computers to learn from data without explicit programming. "
            "Common algorithms include decision trees, neural networks, and SVMs."
        )

        added = knowledge_base.ingest_file(str(doc))
        assert added > 0

        results = knowledge_base.search("machine learning algorithms", top_k=5)
        assert len(results) > 0
        assert results[0]["score"] > 0
        # Top result should contain relevant content
        assert any("machine" in r["text"].lower() or "learning" in r["text"].lower()
                    for r in results)

    def test_ingest_directory_all_files(self, sample_docs, knowledge_base):
        """Ingest an entire directory and verify all files are indexed."""
        added = knowledge_base.ingest_directory(str(sample_docs))
        assert added > 0

        stats = knowledge_base.stats()
        assert stats["files"] == 4  # python.txt, rust.md, config.json, logs.jsonl
        assert stats["chunks"] > 0

    def test_search_relevance_ordering(self, sample_docs, knowledge_base):
        """Search results should be ordered by relevance (Jaccard score)."""
        knowledge_base.ingest_directory(str(sample_docs))

        results = knowledge_base.search("Python programming language", top_k=5)
        assert len(results) > 0

        # Scores should be in descending order
        scores = [r["score"] for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], "Results should be sorted by score desc"

    def test_search_different_queries(self, sample_docs, knowledge_base):
        """Different queries should return different top results."""
        knowledge_base.ingest_directory(str(sample_docs))

        python_results = knowledge_base.search("Python data science")
        rust_results = knowledge_base.search("Rust ownership safety")

        # Both should have results
        assert len(python_results) > 0
        assert len(rust_results) > 0

        # Top results should differ (from different source files)
        if len(python_results) > 0 and len(rust_results) > 0:
            # At least one result's text should differ
            assert python_results[0]["text"] != rust_results[0]["text"]


# ---------------------------------------------------------------------------
# Document loading integration
# ---------------------------------------------------------------------------

class TestDocumentLoadingIntegration:
    """Tests document loading and chunking across file types."""

    def test_load_txt_file(self, sample_docs):
        """Loading a .txt file should produce chunks with source metadata."""
        loader = DocumentLoader(chunk_size=20, chunk_overlap=5)
        chunks = loader.load_file(str(sample_docs / "python.txt"))
        assert len(chunks) > 0
        for chunk in chunks:
            assert "chunk_id" in chunk
            assert "text" in chunk
            assert "source_file" in chunk
            assert "position" in chunk

    def test_load_json_file(self, sample_docs):
        """Loading a .json file should pretty-print and chunk."""
        loader = DocumentLoader(chunk_size=20, chunk_overlap=5)
        chunks = loader.load_file(str(sample_docs / "config.json"))
        assert len(chunks) > 0

    def test_load_jsonl_file(self, sample_docs):
        """Loading a .jsonl file should parse each line."""
        loader = DocumentLoader(chunk_size=20, chunk_overlap=5)
        chunks = loader.load_file(str(sample_docs / "logs.jsonl"))
        assert len(chunks) > 0

    def test_load_markdown_file(self, sample_docs):
        """Loading a .md file should read as plain text."""
        loader = DocumentLoader(chunk_size=20, chunk_overlap=5)
        chunks = loader.load_file(str(sample_docs / "rust.md"))
        assert len(chunks) > 0

    def test_load_unsupported_extension(self, tmp_path):
        """Attempting to load .py should raise ValueError."""
        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')")
        loader = DocumentLoader()

        with pytest.raises(ValueError, match="Unsupported"):
            loader.read_file(str(py_file))

    def test_load_directory(self, sample_docs):
        """Loading a directory should return chunks from all supported files."""
        loader = DocumentLoader(chunk_size=20, chunk_overlap=5)
        chunks = loader.load_directory(str(sample_docs))
        assert len(chunks) > 0

        # Should have chunks from multiple files
        source_files = {c["source_file"] for c in chunks}
        assert len(source_files) >= 2


# ---------------------------------------------------------------------------
# Trigram index integration
# ---------------------------------------------------------------------------

class TestTrigramIndexIntegration:
    """Tests index build, search, and serialization lifecycle."""

    def test_build_search_serialize_restore(self):
        """Build index -> search -> serialize -> deserialize -> search again."""
        index = TrigramIndex()

        texts = {
            "c1": "artificial intelligence and machine learning",
            "c2": "deep learning neural networks transformers",
            "c3": "database optimization and SQL queries",
            "c4": "web development with React and Node.js",
        }

        for cid, text in texts.items():
            index.add_chunk(cid, text)

        assert index.chunk_count() == 4

        # Search
        results = index.search("machine learning neural networks", top_k=4)
        assert len(results) > 0
        top_ids = [r[0] for r in results]
        # c1 or c2 should be in top results (both related to ML)
        assert "c1" in top_ids or "c2" in top_ids

        # Serialize
        data = index.to_dict()
        assert len(data) == 4

        # Deserialize
        restored = TrigramIndex.from_dict(data)
        assert restored.chunk_count() == 4

        # Search on restored index
        restored_results = restored.search("machine learning neural networks", top_k=4)
        assert len(restored_results) > 0
        # Results should be identical
        assert [r[0] for r in results] == [r[0] for r in restored_results]

    def test_remove_chunk_affects_search(self):
        """Removing a chunk should exclude it from search results."""
        index = TrigramIndex()
        index.add_chunk("c1", "Python programming language")
        index.add_chunk("c2", "Rust programming language")
        index.add_chunk("c3", "cooking recipes pasta")

        results_before = index.search("programming language")
        ids_before = {r[0] for r in results_before}
        assert "c1" in ids_before or "c2" in ids_before

        index.remove_chunk("c1")
        results_after = index.search("programming language")
        ids_after = {r[0] for r in results_after}
        assert "c1" not in ids_after

    def test_clear_empties_index(self):
        """Clearing the index should remove all chunks."""
        index = TrigramIndex()
        index.add_chunk("c1", "some text")
        index.add_chunk("c2", "other text")
        assert index.chunk_count() == 2

        index.clear()
        assert index.chunk_count() == 0
        assert index.search("text") == []


# ---------------------------------------------------------------------------
# Multi-agent isolation
# ---------------------------------------------------------------------------

class TestMultiAgentRAGIsolation:
    """Tests that different agents have isolated knowledge bases."""

    def test_agents_share_index_but_isolated_search(self, tmp_path, shared_state):
        """Two agents with separate KBs should only search their own chunks."""
        # Create docs for each agent
        doc_a = tmp_path / "agent_a.txt"
        doc_a.write_text("Agent A specializes in Python web development and Django.")

        doc_b = tmp_path / "agent_b.txt"
        doc_b.write_text("Agent B specializes in Rust systems programming and tokio.")

        kb_a = KnowledgeBase("agent-a", shared_state["index"],
                             shared_state["chunks"], shared_state["files"])
        kb_b = KnowledgeBase("agent-b", shared_state["index"],
                             shared_state["chunks"], shared_state["files"])

        kb_a.ingest_file(str(doc_a))
        kb_b.ingest_file(str(doc_b))

        # Agent A's search should find its own content
        a_results = kb_a.search("Python Django")
        assert len(a_results) > 0
        for r in a_results:
            # Results should come from agent A's chunks
            chunk_meta = shared_state["chunks"].get(r.get("chunk_id", ""), {})
            # If chunk_id available, verify agent
            if chunk_meta:
                assert chunk_meta["agent_id"] == "agent-a"

        # Agent B's search should find its own content
        b_results = kb_b.search("Rust tokio")
        assert len(b_results) > 0

    def test_agent_clear_does_not_affect_other(self, tmp_path, shared_state):
        """Clearing one agent's KB should not affect another's."""
        doc_a = tmp_path / "a.txt"
        doc_a.write_text("Agent A content about machine learning.")

        doc_b = tmp_path / "b.txt"
        doc_b.write_text("Agent B content about database optimization.")

        kb_a = KnowledgeBase("agent-a", shared_state["index"],
                             shared_state["chunks"], shared_state["files"])
        kb_b = KnowledgeBase("agent-b", shared_state["index"],
                             shared_state["chunks"], shared_state["files"])

        kb_a.ingest_file(str(doc_a))
        kb_b.ingest_file(str(doc_b))

        assert kb_a.stats()["chunks"] > 0
        assert kb_b.stats()["chunks"] > 0

        # Clear agent A
        kb_a.clear()
        assert kb_a.stats()["chunks"] == 0
        assert kb_b.stats()["chunks"] > 0  # Agent B unaffected


# ---------------------------------------------------------------------------
# Duplicate ingestion guard
# ---------------------------------------------------------------------------

class TestDuplicateIngestionGuard:
    """Tests that re-ingesting the same file is a no-op."""

    def test_duplicate_ingest_returns_zero(self, tmp_path, knowledge_base):
        """Re-ingesting the same file should add zero new chunks."""
        doc = tmp_path / "doc.txt"
        doc.write_text("Content that should only be ingested once.")

        first = knowledge_base.ingest_file(str(doc))
        assert first > 0

        second = knowledge_base.ingest_file(str(doc))
        assert second == 0

        stats = knowledge_base.stats()
        assert stats["chunks"] == first  # Same count as first ingestion


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestRAGEdgeCases:
    """Tests edge cases in the RAG pipeline."""

    def test_empty_file_ingestion(self, tmp_path, knowledge_base):
        """Ingesting an empty file should produce zero chunks."""
        empty_file = tmp_path / "empty.txt"
        empty_file.write_text("")

        added = knowledge_base.ingest_file(str(empty_file))
        assert added == 0

    def test_whitespace_only_file(self, tmp_path, knowledge_base):
        """Ingesting a whitespace-only file should produce zero chunks."""
        ws_file = tmp_path / "whitespace.txt"
        ws_file.write_text("   \n\n   \t   ")

        added = knowledge_base.ingest_file(str(ws_file))
        assert added == 0

    def test_search_empty_knowledge_base(self, knowledge_base):
        """Searching an empty KB should return empty results."""
        results = knowledge_base.search("anything at all")
        assert results == []

    def test_search_empty_query(self, tmp_path, knowledge_base):
        """Searching with an empty query should return empty results."""
        doc = tmp_path / "doc.txt"
        doc.write_text("Some content in the knowledge base")
        knowledge_base.ingest_file(str(doc))

        results = knowledge_base.search("")
        assert results == []

    def test_very_short_document(self, tmp_path, knowledge_base):
        """Very short documents should still be indexed correctly."""
        doc = tmp_path / "short.txt"
        doc.write_text("Hi")

        added = knowledge_base.ingest_file(str(doc))
        assert added >= 1

    def test_file_not_found(self, knowledge_base):
        """Ingesting a nonexistent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            knowledge_base.ingest_file("/nonexistent/file.txt")
