"""
Tests for shared/claw_rag.py — RAG Pipeline (Retrieval-Augmented Generation).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "shared"))

from claw_rag import DocumentLoader, TrigramIndex, KnowledgeBase


class TestDocumentLoaderChunking:
    """Tests for DocumentLoader text chunking."""

    def test_chunk_text_basic(self):
        """chunk_text should split text into chunks of the configured size."""
        loader = DocumentLoader(chunk_size=5, chunk_overlap=1)
        text = "one two three four five six seven eight nine ten"
        chunks = loader.chunk_text(text, source_file="test.txt")
        assert len(chunks) > 0
        for chunk in chunks:
            assert "chunk_id" in chunk
            assert "text" in chunk
            assert "source_file" in chunk
            assert chunk["source_file"] == "test.txt"

    def test_chunk_text_empty(self):
        """chunk_text with empty text should return empty list."""
        loader = DocumentLoader()
        chunks = loader.chunk_text("", source_file="test.txt")
        assert chunks == []

    def test_chunk_text_whitespace_only(self):
        """chunk_text with whitespace should return empty list."""
        loader = DocumentLoader()
        chunks = loader.chunk_text("   \n\n   ", source_file="test.txt")
        assert chunks == []

    def test_chunk_overlap(self):
        """Consecutive chunks should share overlapping words."""
        loader = DocumentLoader(chunk_size=5, chunk_overlap=2)
        words = ["word" + str(i) for i in range(15)]
        text = " ".join(words)
        chunks = loader.chunk_text(text)
        assert len(chunks) >= 3

        # Check that adjacent chunks have overlapping content
        if len(chunks) >= 2:
            words_0 = set(chunks[0]["text"].split())
            words_1 = set(chunks[1]["text"].split())
            overlap = words_0 & words_1
            assert len(overlap) > 0, "Adjacent chunks should share some words"

    def test_chunk_positions_sequential(self):
        """Chunk positions should be sequential starting from 0."""
        loader = DocumentLoader(chunk_size=3, chunk_overlap=0)
        text = "a b c d e f g h i"
        chunks = loader.chunk_text(text)
        positions = [c["position"] for c in chunks]
        assert positions == list(range(len(chunks)))

    def test_read_file_txt(self, tmp_path):
        """read_file should load plain text files."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world, this is a test document.")
        loader = DocumentLoader()
        content = loader.read_file(str(txt_file))
        assert "Hello world" in content

    def test_read_file_json(self, tmp_path):
        """read_file should pretty-print JSON files."""
        json_file = tmp_path / "test.json"
        json_file.write_text(json.dumps({"key": "value", "num": 42}))
        loader = DocumentLoader()
        content = loader.read_file(str(json_file))
        assert "key" in content
        assert "value" in content

    def test_read_file_unsupported(self, tmp_path):
        """read_file should raise ValueError for unsupported extensions."""
        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')")
        loader = DocumentLoader()
        try:
            loader.read_file(str(py_file))
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unsupported" in str(e)


class TestTrigramIndex:
    """Tests for TrigramIndex trigram extraction and search."""

    def test_extract_trigrams_basic(self):
        """Trigrams should be 3-character substrings of normalized text."""
        trigrams = TrigramIndex._extract_trigrams("hello")
        assert "hel" in trigrams
        assert "ell" in trigrams
        assert "llo" in trigrams
        assert len(trigrams) == 3

    def test_extract_trigrams_short_text(self):
        """Text shorter than 3 chars should return the text itself as a set."""
        trigrams = TrigramIndex._extract_trigrams("ab")
        assert "ab" in trigrams
        assert len(trigrams) == 1

    def test_extract_trigrams_empty(self):
        """Empty text should return an empty set."""
        trigrams = TrigramIndex._extract_trigrams("")
        assert len(trigrams) == 0

    def test_search_with_jaccard_similarity(self):
        """Search should return chunks ranked by Jaccard similarity."""
        index = TrigramIndex()
        index.add_chunk("c1", "machine learning algorithms")
        index.add_chunk("c2", "deep learning neural networks")
        index.add_chunk("c3", "cooking recipe for pasta")

        results = index.search("machine learning", top_k=3)
        assert len(results) > 0
        # c1 should score highest (most overlap with "machine learning")
        assert results[0][0] == "c1"
        assert results[0][1] > 0

    def test_search_empty_index(self):
        """Search on empty index should return empty results."""
        index = TrigramIndex()
        results = index.search("anything")
        assert results == []

    def test_search_empty_query(self):
        """Empty query should return empty results."""
        index = TrigramIndex()
        index.add_chunk("c1", "some text here")
        results = index.search("")
        assert results == []

    def test_chunk_count(self):
        """chunk_count should reflect number of indexed chunks."""
        index = TrigramIndex()
        assert index.chunk_count() == 0
        index.add_chunk("c1", "text one")
        index.add_chunk("c2", "text two")
        assert index.chunk_count() == 2

    def test_remove_chunk(self):
        """Removing a chunk should decrease the count."""
        index = TrigramIndex()
        index.add_chunk("c1", "text one")
        index.add_chunk("c2", "text two")
        index.remove_chunk("c1")
        assert index.chunk_count() == 1

    def test_serialization_roundtrip(self):
        """Index should survive serialization and deserialization."""
        index = TrigramIndex()
        index.add_chunk("c1", "hello world")
        index.add_chunk("c2", "goodbye world")

        data = index.to_dict()
        restored = TrigramIndex.from_dict(data)
        assert restored.chunk_count() == 2
        results = restored.search("hello world", top_k=2)
        assert len(results) > 0
        assert results[0][0] == "c1"


class TestKnowledgeBase:
    """Tests for KnowledgeBase ingest and search."""

    def test_ingest_and_search(self, tmp_path):
        """Ingest a file and search for its content."""
        # Create a test file
        doc = tmp_path / "doc.txt"
        doc.write_text("Python is a high-level programming language. "
                       "It is widely used for web development and data science. "
                       "Python has a large standard library.")

        index = TrigramIndex()
        chunks = {}
        files = {}
        kb = KnowledgeBase("test-agent", index, chunks, files)

        added = kb.ingest_file(str(doc))
        assert added > 0

        results = kb.search("Python programming", top_k=3)
        assert len(results) > 0
        assert results[0]["score"] > 0
        assert "Python" in results[0]["text"]

    def test_empty_index_search(self, tmp_path):
        """Search on empty knowledge base should return empty list."""
        index = TrigramIndex()
        chunks = {}
        files = {}
        kb = KnowledgeBase("test-agent", index, chunks, files)
        results = kb.search("anything")
        assert results == []

    def test_stats(self, tmp_path):
        """stats should reflect the agent's chunk and file counts."""
        doc = tmp_path / "doc.txt"
        doc.write_text("A short test document for stats testing purposes.")

        index = TrigramIndex()
        chunks = {}
        files = {}
        kb = KnowledgeBase("test-agent", index, chunks, files)
        kb.ingest_file(str(doc))

        stats = kb.stats()
        assert stats["agent_id"] == "test-agent"
        assert stats["chunks"] > 0
        assert stats["files"] == 1

    def test_clear(self, tmp_path):
        """clear should remove all chunks for the agent."""
        doc = tmp_path / "doc.txt"
        doc.write_text("Content to be cleared from the knowledge base.")

        index = TrigramIndex()
        chunks = {}
        files = {}
        kb = KnowledgeBase("test-agent", index, chunks, files)
        kb.ingest_file(str(doc))
        assert kb.stats()["chunks"] > 0

        removed = kb.clear()
        assert removed > 0
        assert kb.stats()["chunks"] == 0
        assert kb.stats()["files"] == 0
