#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — RAG Pipeline (Retrieval-Augmented Generation)
=============================================================================
Stdlib-only retrieval-augmented generation using trigram-based Jaccard
similarity.  No numpy, no faiss, no external vector DB required.

Documents are chunked into overlapping text segments, indexed by character
trigrams, and retrieved via Jaccard similarity scoring.  Each agent gets
its own isolated knowledge base with independent ingestion and search.

Supported file types:
  - .txt, .md     — plain text (read as-is)
  - .json         — pretty-printed JSON text
  - .jsonl        — each line parsed and pretty-printed

Chunking:
  - Configurable chunk size (default 512 tokens, approximated as words)
  - Configurable overlap (default 64 tokens)
  - Each chunk receives a UUID and source metadata

HTTP API (port 9097):
  POST /api/rag/ingest    — ingest a file or directory
  POST /api/rag/search    — search indexed chunks
  GET  /api/rag/status    — index statistics
  DELETE /api/rag/clear   — clear agent or all knowledge bases
  POST /v1/search         — OpenAI-compatible search endpoint

CLI:
  python3 shared/claw_rag.py --start [--port 9097]
  python3 shared/claw_rag.py --stop
  python3 shared/claw_rag.py --ingest <path> [--agent zeroclaw]
  python3 shared/claw_rag.py --search "query" [--agent zeroclaw] [--top-k 5]
  python3 shared/claw_rag.py --status
  python3 shared/claw_rag.py --clear [--agent zeroclaw]

Storage:
  data/rag/rag_index.json   — serialized trigram index
  data/rag/rag_chunks.json  — chunk_id -> {text, source, agent_id, position}
  data/rag/rag_files.json   — ingested files per agent
  data/rag/rag.pid          — PID file for --stop

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 (c) 2026 Amenthyx
"""

import argparse
import json
import os
import signal
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "rag"
INDEX_FILE = DATA_DIR / "rag_index.json"
CHUNKS_FILE = DATA_DIR / "rag_chunks.json"
FILES_FILE = DATA_DIR / "rag_files.json"
PID_FILE = DATA_DIR / "rag.pid"

DEFAULT_PORT = 9097
DEFAULT_CHUNK_SIZE = 512      # approximate tokens (words)
DEFAULT_CHUNK_OVERLAP = 64    # overlap in approximate tokens
SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".jsonl"}

# -------------------------------------------------------------------------
# Colors (for terminal output)
# -------------------------------------------------------------------------
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
BOLD = "\033[1m"
DIM = "\033[2m"
NC = "\033[0m"


def log(msg: str) -> None:
    print(f"{GREEN}[rag]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[rag]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[rag]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[rag]{NC} {msg}")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =========================================================================
#  DocumentLoader — Read and chunk documents into text segments
# =========================================================================

class DocumentLoader:
    """
    Reads files and splits their content into overlapping text chunks.

    Each chunk is approximately `chunk_size` words long with `overlap`
    words shared between consecutive chunks.  Every chunk gets a unique
    UUID identifier and source metadata.
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    # ── File Reading ─────────────────────────────────────────────────────

    def read_file(self, path: str) -> str:
        """
        Read a file and return its text content.

        Supports .txt, .md (plain text), .json (pretty-printed),
        and .jsonl (each line parsed and pretty-printed).
        """
        file_path = Path(path)
        ext = file_path.suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        raw = file_path.read_text(encoding="utf-8", errors="replace")

        if ext in (".txt", ".md"):
            return raw

        if ext == ".json":
            try:
                data = json.loads(raw)
                return json.dumps(data, indent=2, ensure_ascii=False)
            except json.JSONDecodeError:
                return raw

        if ext == ".jsonl":
            lines = []
            for line_num, line in enumerate(raw.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    lines.append(json.dumps(obj, indent=2, ensure_ascii=False))
                except json.JSONDecodeError:
                    lines.append(line)
            return "\n---\n".join(lines)

        return raw

    # ── Chunking ─────────────────────────────────────────────────────────

    def chunk_text(self, text: str, source_file: str = "") -> List[Dict[str, Any]]:
        """
        Split text into overlapping chunks.

        Returns a list of dicts:
          {"chunk_id": str, "text": str, "source_file": str, "position": int}
        """
        words = text.split()
        if not words:
            return []

        chunks = []
        step = max(1, self.chunk_size - self.chunk_overlap)
        position = 0

        i = 0
        while i < len(words):
            end = min(i + self.chunk_size, len(words))
            chunk_words = words[i:end]
            chunk_text = " ".join(chunk_words)

            if chunk_text.strip():
                chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "text": chunk_text,
                    "source_file": source_file,
                    "position": position,
                })
                position += 1

            if end >= len(words):
                break
            i += step

        return chunks

    def load_file(self, path: str) -> List[Dict[str, Any]]:
        """Read a file and return its chunks."""
        text = self.read_file(path)
        return self.chunk_text(text, source_file=str(Path(path).resolve()))

    def load_directory(self, dir_path: str) -> List[Dict[str, Any]]:
        """Recursively load all supported files from a directory."""
        all_chunks = []
        directory = Path(dir_path)

        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    chunks = self.load_file(str(file_path))
                    all_chunks.extend(chunks)
                except Exception as e:
                    warn(f"Skipping {file_path}: {e}")

        return all_chunks


# =========================================================================
#  TrigramIndex — Character trigram similarity scoring
# =========================================================================

class TrigramIndex:
    """
    Builds character trigram sets per chunk and scores queries via
    Jaccard similarity: |A intersection B| / |A union B|.

    Thread-safe via a threading.Lock on all mutating operations.
    """

    def __init__(self):
        self._trigrams: Dict[str, Set[str]] = {}    # chunk_id -> set of trigrams
        self._lock = threading.Lock()

    @staticmethod
    def _extract_trigrams(text: str) -> Set[str]:
        """
        Extract character trigrams from text.

        Text is lowercased and whitespace-normalized before extraction.
        Returns a set of 3-character substrings.
        """
        normalized = " ".join(text.lower().split())
        if len(normalized) < 3:
            return {normalized} if normalized else set()

        trigrams = set()
        for i in range(len(normalized) - 2):
            trigrams.add(normalized[i:i + 3])
        return trigrams

    def add_chunk(self, chunk_id: str, text: str) -> None:
        """Index a chunk by its trigrams."""
        trigrams = self._extract_trigrams(text)
        with self._lock:
            self._trigrams[chunk_id] = trigrams

    def remove_chunk(self, chunk_id: str) -> None:
        """Remove a chunk from the index."""
        with self._lock:
            self._trigrams.pop(chunk_id, None)

    def remove_chunks(self, chunk_ids: List[str]) -> None:
        """Remove multiple chunks from the index."""
        with self._lock:
            for cid in chunk_ids:
                self._trigrams.pop(cid, None)

    def search(self, query: str, top_k: int = 5,
               candidate_ids: Optional[Set[str]] = None) -> List[Tuple[str, float]]:
        """
        Search for chunks most similar to the query.

        Returns a list of (chunk_id, similarity_score) tuples sorted
        by descending similarity.  If candidate_ids is provided, only
        those chunks are considered.
        """
        query_trigrams = self._extract_trigrams(query)
        if not query_trigrams:
            return []

        scores = []
        with self._lock:
            items = self._trigrams.items()
            for chunk_id, chunk_trigrams in items:
                if candidate_ids is not None and chunk_id not in candidate_ids:
                    continue
                if not chunk_trigrams:
                    continue

                intersection = len(query_trigrams & chunk_trigrams)
                union = len(query_trigrams | chunk_trigrams)
                similarity = intersection / union if union > 0 else 0.0

                if similarity > 0.0:
                    scores.append((chunk_id, similarity))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def chunk_count(self) -> int:
        """Return the number of indexed chunks."""
        with self._lock:
            return len(self._trigrams)

    def clear(self) -> None:
        """Remove all indexed chunks."""
        with self._lock:
            self._trigrams.clear()

    # ── Serialization ────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, List[str]]:
        """
        Serialize the index to a JSON-compatible dict.

        Trigram sets are stored as sorted lists for deterministic output.
        """
        with self._lock:
            return {
                cid: sorted(tgs)
                for cid, tgs in self._trigrams.items()
            }

    @classmethod
    def from_dict(cls, data: Dict[str, List[str]]) -> "TrigramIndex":
        """Deserialize an index from a dict."""
        index = cls()
        for cid, tg_list in data.items():
            index._trigrams[cid] = set(tg_list)
        return index


# =========================================================================
#  KnowledgeBase — Per-agent document collection
# =========================================================================

class KnowledgeBase:
    """
    Per-agent knowledge base with document ingestion, indexing, and search.

    Each agent has an isolated namespace.  Ingested files are tracked to
    avoid redundant re-ingestion.
    """

    def __init__(self, agent_id: str, index: TrigramIndex,
                 chunks: Dict[str, Dict[str, Any]],
                 files: Dict[str, List[str]]):
        self.agent_id = agent_id
        self._index = index
        self._chunks = chunks          # shared chunk store (all agents)
        self._files = files            # shared file tracker (all agents)
        self._loader = DocumentLoader()
        self._lock = threading.Lock()

    def _get_agent_files(self) -> List[str]:
        """Get list of files ingested by this agent."""
        return self._files.get(self.agent_id, [])

    def _get_agent_chunk_ids(self) -> Set[str]:
        """Get all chunk IDs belonging to this agent."""
        ids = set()
        for cid, meta in self._chunks.items():
            if meta.get("agent_id") == self.agent_id:
                ids.add(cid)
        return ids

    def ingest_file(self, path: str) -> int:
        """
        Ingest a single file into the knowledge base.

        Returns the number of new chunks added.  Skips files that
        have already been ingested.
        """
        resolved = str(Path(path).resolve())
        agent_files = self._get_agent_files()

        if resolved in agent_files:
            info(f"Already ingested: {resolved}")
            return 0

        chunks = self._loader.load_file(path)
        added = 0

        with self._lock:
            for chunk in chunks:
                cid = chunk["chunk_id"]
                self._chunks[cid] = {
                    "text": chunk["text"],
                    "source_file": chunk["source_file"],
                    "agent_id": self.agent_id,
                    "position": chunk["position"],
                    "ingested_at": _now(),
                }
                self._index.add_chunk(cid, chunk["text"])
                added += 1

            if self.agent_id not in self._files:
                self._files[self.agent_id] = []
            self._files[self.agent_id].append(resolved)

        return added

    def ingest_directory(self, dir_path: str) -> int:
        """
        Recursively ingest all supported files from a directory.

        Returns the total number of new chunks added.
        """
        directory = Path(dir_path)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        total_added = 0
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file() and file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    added = self.ingest_file(str(file_path))
                    total_added += added
                except Exception as e:
                    warn(f"Skipping {file_path}: {e}")

        return total_added

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search this agent's knowledge base.

        Returns a list of result dicts with chunk text, source, score,
        and position metadata.
        """
        candidate_ids = self._get_agent_chunk_ids()
        if not candidate_ids:
            return []

        results = self._index.search(query, top_k=top_k,
                                     candidate_ids=candidate_ids)
        output = []
        for cid, score in results:
            meta = self._chunks.get(cid, {})
            output.append({
                "chunk_id": cid,
                "text": meta.get("text", ""),
                "source_file": meta.get("source_file", ""),
                "position": meta.get("position", 0),
                "score": round(score, 6),
            })

        return output

    def clear(self) -> int:
        """
        Remove all chunks and file records for this agent.

        Returns the number of chunks removed.
        """
        chunk_ids = list(self._get_agent_chunk_ids())
        with self._lock:
            for cid in chunk_ids:
                self._chunks.pop(cid, None)
            self._index.remove_chunks(chunk_ids)
            self._files.pop(self.agent_id, None)
        return len(chunk_ids)

    def stats(self) -> Dict[str, Any]:
        """Return statistics for this agent's knowledge base."""
        chunk_ids = self._get_agent_chunk_ids()
        agent_files = self._get_agent_files()
        return {
            "agent_id": self.agent_id,
            "chunks": len(chunk_ids),
            "files": len(agent_files),
            "file_list": agent_files,
        }


# =========================================================================
#  RAGEngine — Central orchestrator for all knowledge bases
# =========================================================================

class RAGEngine:
    """
    Central RAG engine managing multiple per-agent knowledge bases,
    shared trigram index, and persistent storage.
    """

    def __init__(self):
        self._index = TrigramIndex()
        self._chunks: Dict[str, Dict[str, Any]] = {}
        self._files: Dict[str, List[str]] = {}
        self._lock = threading.Lock()
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        """Load persisted index, chunks, and file records from disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load chunks
        if CHUNKS_FILE.exists():
            try:
                raw = CHUNKS_FILE.read_text(encoding="utf-8")
                self._chunks = json.loads(raw)
                log(f"Loaded {len(self._chunks)} chunks from disk")
            except (json.JSONDecodeError, OSError) as e:
                warn(f"Could not load chunks: {e}")
                self._chunks = {}

        # Load index
        if INDEX_FILE.exists():
            try:
                raw = INDEX_FILE.read_text(encoding="utf-8")
                data = json.loads(raw)
                self._index = TrigramIndex.from_dict(data)
                log(f"Loaded trigram index ({self._index.chunk_count()} entries)")
            except (json.JSONDecodeError, OSError) as e:
                warn(f"Could not load index: {e}")
                self._index = TrigramIndex()

        # Load file records
        if FILES_FILE.exists():
            try:
                raw = FILES_FILE.read_text(encoding="utf-8")
                self._files = json.loads(raw)
                log(f"Loaded file records for {len(self._files)} agents")
            except (json.JSONDecodeError, OSError) as e:
                warn(f"Could not load file records: {e}")
                self._files = {}

    def save_to_disk(self) -> None:
        """Persist index, chunks, and file records to disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        with self._lock:
            # Save chunks
            CHUNKS_FILE.write_text(
                json.dumps(self._chunks, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )

            # Save index
            INDEX_FILE.write_text(
                json.dumps(self._index.to_dict(), ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )

            # Save file records
            FILES_FILE.write_text(
                json.dumps(self._files, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def get_kb(self, agent_id: str) -> KnowledgeBase:
        """Get or create a knowledge base for an agent."""
        return KnowledgeBase(agent_id, self._index, self._chunks, self._files)

    def ingest(self, path: str, agent_id: str = "default") -> Dict[str, Any]:
        """
        Ingest a file or directory for an agent.

        Returns a summary dict with counts and timing.
        """
        start = time.time()
        kb = self.get_kb(agent_id)
        target = Path(path)

        if target.is_dir():
            added = kb.ingest_directory(path)
        elif target.is_file():
            added = kb.ingest_file(path)
        else:
            raise FileNotFoundError(f"Path not found: {path}")

        elapsed = round(time.time() - start, 3)

        # Auto-save after ingestion
        self.save_to_disk()

        return {
            "agent_id": agent_id,
            "path": str(target.resolve()),
            "chunks_added": added,
            "total_chunks": self._index.chunk_count(),
            "elapsed_seconds": elapsed,
        }

    def search(self, query: str, agent_id: str = "default",
               top_k: int = 5) -> List[Dict[str, Any]]:
        """Search an agent's knowledge base."""
        kb = self.get_kb(agent_id)
        return kb.search(query, top_k=top_k)

    def clear(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear knowledge base(s).

        If agent_id is provided, clear only that agent.
        Otherwise, clear everything.
        """
        if agent_id:
            kb = self.get_kb(agent_id)
            removed = kb.clear()
            self.save_to_disk()
            return {
                "agent_id": agent_id,
                "chunks_removed": removed,
                "total_chunks": self._index.chunk_count(),
            }
        else:
            with self._lock:
                count = len(self._chunks)
                self._chunks.clear()
                self._files.clear()
                self._index.clear()
            self.save_to_disk()
            return {
                "agent_id": "all",
                "chunks_removed": count,
                "total_chunks": 0,
            }

    def status(self) -> Dict[str, Any]:
        """Return global index statistics."""
        agents = {}
        agent_ids = set()
        for meta in self._chunks.values():
            aid = meta.get("agent_id", "unknown")
            agent_ids.add(aid)

        for aid in sorted(agent_ids):
            kb = self.get_kb(aid)
            agents[aid] = kb.stats()

        return {
            "total_chunks": self._index.chunk_count(),
            "total_files": sum(len(v) for v in self._files.values()),
            "agents": agents,
            "storage": {
                "index_file": str(INDEX_FILE),
                "chunks_file": str(CHUNKS_FILE),
                "files_file": str(FILES_FILE),
                "index_size_bytes": INDEX_FILE.stat().st_size if INDEX_FILE.exists() else 0,
                "chunks_size_bytes": CHUNKS_FILE.stat().st_size if CHUNKS_FILE.exists() else 0,
            },
        }

    def context_for_prompt(self, query: str, agent_id: str = "default",
                           top_k: int = 5, max_chars: int = 4000) -> str:
        """
        Build a context string suitable for prepending to an LLM prompt.

        Retrieves the top_k most relevant chunks and formats them as a
        numbered list with source attribution.  Truncates to max_chars.
        """
        results = self.search(query, agent_id=agent_id, top_k=top_k)
        if not results:
            return ""

        parts = ["--- Retrieved Context ---"]
        total_len = len(parts[0])

        for i, result in enumerate(results, start=1):
            source = Path(result["source_file"]).name if result["source_file"] else "unknown"
            header = f"\n[{i}] (source: {source}, score: {result['score']:.4f})"
            text = result["text"]

            entry = f"{header}\n{text}"
            if total_len + len(entry) > max_chars:
                remaining = max_chars - total_len - len(header) - 10
                if remaining > 50:
                    entry = f"{header}\n{text[:remaining]}..."
                    parts.append(entry)
                break

            parts.append(entry)
            total_len += len(entry)

        parts.append("\n--- End Context ---")
        return "\n".join(parts)


# =========================================================================
#  RAGRequestHandler — HTTP API
# =========================================================================

class RAGRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for the RAG server.

    Endpoints:
      POST   /api/rag/ingest  — {"path": "...", "agent_id": "..."}
      POST   /api/rag/search  — {"query": "...", "agent_id": "...", "top_k": 5}
      GET    /api/rag/status   — index statistics
      DELETE /api/rag/clear    — {"agent_id": "..."} or clear all
      POST   /v1/search        — OpenAI-compatible search
    """

    engine: Optional["RAGEngine"] = None

    def _send_json(self, status: int, data: Any) -> None:
        """Send a JSON response."""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Dict[str, Any]:
        """Read and parse JSON request body."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/api/rag/status":
            self._handle_status()
        elif self.path == "/health":
            self._send_json(200, {"status": "ok", "service": "claw-rag"})
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        """Handle POST requests."""
        if self.path == "/api/rag/ingest":
            self._handle_ingest()
        elif self.path == "/api/rag/search":
            self._handle_search()
        elif self.path == "/v1/search":
            self._handle_v1_search()
        else:
            self._send_json(404, {"error": "Not found"})

    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        if self.path == "/api/rag/clear":
            self._handle_clear()
        else:
            self._send_json(404, {"error": "Not found"})

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ── Endpoint Handlers ────────────────────────────────────────────────

    def _handle_ingest(self) -> None:
        """POST /api/rag/ingest"""
        body = self._read_body()
        path = body.get("path", "")
        agent_id = body.get("agent_id", "default")

        if not path:
            self._send_json(400, {"error": "Missing 'path' field"})
            return

        try:
            result = self.engine.ingest(path, agent_id=agent_id)
            self._send_json(200, {"ok": True, **result})
        except FileNotFoundError as e:
            self._send_json(404, {"error": str(e)})
        except NotADirectoryError as e:
            self._send_json(400, {"error": str(e)})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_search(self) -> None:
        """POST /api/rag/search"""
        body = self._read_body()
        query = body.get("query", "")
        agent_id = body.get("agent_id", "default")
        top_k = int(body.get("top_k", 5))

        if not query:
            self._send_json(400, {"error": "Missing 'query' field"})
            return

        try:
            results = self.engine.search(query, agent_id=agent_id, top_k=top_k)
            self._send_json(200, {
                "ok": True,
                "query": query,
                "agent_id": agent_id,
                "results": results,
                "count": len(results),
            })
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_v1_search(self) -> None:
        """
        POST /v1/search — OpenAI-compatible search endpoint.

        Accepts: {"query": "...", "agent_id": "...", "top_k": 5}
        Returns: {"data": [{"text": "...", "score": 0.85, "metadata": {...}}]}
        """
        body = self._read_body()
        query = body.get("query", body.get("input", ""))
        agent_id = body.get("agent_id", "default")
        top_k = int(body.get("top_k", body.get("n", 5)))

        if not query:
            self._send_json(400, {"error": "Missing 'query' or 'input' field"})
            return

        try:
            results = self.engine.search(query, agent_id=agent_id, top_k=top_k)
            openai_results = []
            for r in results:
                openai_results.append({
                    "text": r["text"],
                    "score": r["score"],
                    "metadata": {
                        "chunk_id": r["chunk_id"],
                        "source_file": r["source_file"],
                        "position": r["position"],
                    },
                })

            self._send_json(200, {
                "object": "list",
                "data": openai_results,
                "model": "claw-rag-trigram",
                "usage": {"total_chunks_searched": self.engine._index.chunk_count()},
            })
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_status(self) -> None:
        """GET /api/rag/status"""
        try:
            status = self.engine.status()
            self._send_json(200, {"ok": True, **status})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def _handle_clear(self) -> None:
        """DELETE /api/rag/clear"""
        body = self._read_body()
        agent_id = body.get("agent_id", None)

        try:
            result = self.engine.clear(agent_id=agent_id)
            self._send_json(200, {"ok": True, **result})
        except Exception as e:
            self._send_json(500, {"error": str(e)})

    def log_message(self, format: str, *args) -> None:
        """Custom log format matching claw style."""
        info(f"HTTP {args[0] if args else ''}")


# =========================================================================
#  RAGServer — HTTP server wrapper with PID management
# =========================================================================

class RAGServer:
    """
    HTTP server for the RAG pipeline.

    Manages server lifecycle including PID file for --stop support,
    graceful shutdown on SIGINT/SIGTERM, and threaded request handling.
    """

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.engine = RAGEngine()
        self._server: Optional[HTTPServer] = None

    def start(self) -> None:
        """Start the HTTP server."""
        RAGRequestHandler.engine = self.engine

        self._server = HTTPServer(("0.0.0.0", self.port), RAGRequestHandler)
        self._server.request_queue_size = 32

        # Write PID file
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()), encoding="utf-8")

        # Install signal handlers
        def _shutdown(sig, frame):
            log("Shutdown signal received")
            self.stop()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        log(f"RAG server starting on port {self.port}")
        log(f"  Endpoints:")
        log(f"    POST   http://0.0.0.0:{self.port}/api/rag/ingest")
        log(f"    POST   http://0.0.0.0:{self.port}/api/rag/search")
        log(f"    GET    http://0.0.0.0:{self.port}/api/rag/status")
        log(f"    DELETE http://0.0.0.0:{self.port}/api/rag/clear")
        log(f"    POST   http://0.0.0.0:{self.port}/v1/search")
        log(f"  PID file: {PID_FILE}")

        status = self.engine.status()
        log(f"  Index: {status['total_chunks']} chunks, "
            f"{status['total_files']} files, "
            f"{len(status['agents'])} agents")

        try:
            self._server.serve_forever()
        except Exception:
            pass
        finally:
            self._cleanup_pid()

    def stop(self) -> None:
        """Stop the HTTP server gracefully."""
        if self._server:
            self._server.shutdown()
        self._cleanup_pid()

    def _cleanup_pid(self) -> None:
        """Remove the PID file."""
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except OSError:
            pass


def stop_server() -> bool:
    """
    Stop a running RAG server by reading its PID file and sending SIGTERM.

    Returns True if the signal was sent, False otherwise.
    """
    if not PID_FILE.exists():
        err("No PID file found — server may not be running")
        return False

    try:
        pid_text = PID_FILE.read_text(encoding="utf-8").strip()
        pid = int(pid_text)
    except (ValueError, OSError) as e:
        err(f"Could not read PID file: {e}")
        return False

    try:
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(1, False, pid)
            if handle:
                kernel32.TerminateProcess(handle, 0)
                kernel32.CloseHandle(handle)
                log(f"Sent terminate signal to PID {pid}")
            else:
                err(f"Could not open process {pid} — server may have exited")
                PID_FILE.unlink(missing_ok=True)
                return False
        else:
            os.kill(pid, signal.SIGTERM)
            log(f"Sent SIGTERM to PID {pid}")
    except ProcessLookupError:
        warn(f"Process {pid} not found — cleaning up PID file")
        PID_FILE.unlink(missing_ok=True)
        return False
    except PermissionError:
        err(f"Permission denied sending signal to PID {pid}")
        return False

    # Wait briefly for shutdown
    for _ in range(10):
        time.sleep(0.5)
        if not PID_FILE.exists():
            log("Server stopped successfully")
            return True

    # Clean up stale PID file
    try:
        PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass

    log("Server stop signal sent")
    return True


# =========================================================================
#  CLI Commands (offline, no server needed)
# =========================================================================

def cli_ingest(path: str, agent_id: str = "default") -> None:
    """Ingest files directly without starting the server."""
    engine = RAGEngine()
    target = Path(path)

    if not target.exists():
        err(f"Path not found: {path}")
        sys.exit(1)

    log(f"Ingesting: {target.resolve()}")
    log(f"Agent: {agent_id}")

    result = engine.ingest(str(target), agent_id=agent_id)

    log(f"Chunks added: {result['chunks_added']}")
    log(f"Total chunks: {result['total_chunks']}")
    log(f"Elapsed: {result['elapsed_seconds']}s")


def cli_search(query: str, agent_id: str = "default", top_k: int = 5) -> None:
    """Search the index directly without starting the server."""
    engine = RAGEngine()

    log(f"Query: {query}")
    log(f"Agent: {agent_id}")
    log(f"Top-K: {top_k}")
    print()

    results = engine.search(query, agent_id=agent_id, top_k=top_k)

    if not results:
        warn("No results found")
        return

    for i, result in enumerate(results, start=1):
        source = Path(result["source_file"]).name if result["source_file"] else "unknown"
        score = result["score"]

        # Color-code by score
        if score >= 0.3:
            color = GREEN
        elif score >= 0.15:
            color = YELLOW
        else:
            color = DIM

        print(f"{BOLD}[{i}]{NC} {color}score={score:.4f}{NC}  "
              f"{CYAN}source={source}{NC}  pos={result['position']}")
        print(f"    {result['text'][:200]}{'...' if len(result['text']) > 200 else ''}")
        print()


def cli_status() -> None:
    """Show index status without starting the server."""
    engine = RAGEngine()
    status = engine.status()

    print(f"\n{BOLD}RAG Index Status{NC}")
    print(f"{'=' * 50}")
    print(f"  Total chunks:  {status['total_chunks']}")
    print(f"  Total files:   {status['total_files']}")
    print(f"  Agents:        {len(status['agents'])}")

    storage = status.get("storage", {})
    index_kb = storage.get("index_size_bytes", 0) / 1024
    chunks_kb = storage.get("chunks_size_bytes", 0) / 1024
    print(f"\n  {DIM}Index size:  {index_kb:.1f} KB{NC}")
    print(f"  {DIM}Chunks size: {chunks_kb:.1f} KB{NC}")

    if status["agents"]:
        print(f"\n{BOLD}Per-Agent Breakdown:{NC}")
        for aid, agent_stats in status["agents"].items():
            print(f"\n  {CYAN}{aid}{NC}")
            print(f"    Chunks: {agent_stats['chunks']}")
            print(f"    Files:  {agent_stats['files']}")
            for f in agent_stats.get("file_list", []):
                fname = Path(f).name
                print(f"      {DIM}- {fname}{NC}")
    else:
        print(f"\n  {DIM}No agents have ingested data yet.{NC}")

    print()


def cli_clear(agent_id: Optional[str] = None) -> None:
    """Clear knowledge base(s) without starting the server."""
    engine = RAGEngine()

    if agent_id:
        log(f"Clearing knowledge base for agent: {agent_id}")
    else:
        log("Clearing ALL knowledge bases")

    result = engine.clear(agent_id=agent_id)

    log(f"Chunks removed: {result['chunks_removed']}")
    log(f"Total chunks remaining: {result['total_chunks']}")


# =========================================================================
#  CLI Argument Parser
# =========================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claw_rag",
        description=(
            "Claw RAG Pipeline -- Stdlib-only Retrieval-Augmented Generation\n"
            "Trigram-based similarity search for agent knowledge bases."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Server commands
    parser.add_argument(
        "--start", action="store_true",
        help="Start the RAG HTTP server",
    )
    parser.add_argument(
        "--stop", action="store_true",
        help="Stop a running RAG server",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Server port (default: {DEFAULT_PORT})",
    )

    # Offline commands
    parser.add_argument(
        "--ingest", type=str, metavar="PATH",
        help="Ingest a file or directory (offline, no server needed)",
    )
    parser.add_argument(
        "--search", type=str, metavar="QUERY",
        help="Search the index (offline, no server needed)",
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Show index statistics",
    )
    parser.add_argument(
        "--clear", action="store_true",
        help="Clear knowledge base(s)",
    )

    # Shared options
    parser.add_argument(
        "--agent", type=str, default="default",
        help="Agent ID for scoped operations (default: 'default')",
    )
    parser.add_argument(
        "--top-k", type=int, default=5,
        help="Number of results to return (default: 5)",
    )

    return parser


# =========================================================================
#  Main Entry Point
# =========================================================================

def main():
    parser = build_parser()
    args = parser.parse_args()

    # Check that at least one command was given
    has_command = any([
        args.start, args.stop, args.ingest, args.search,
        args.status, args.clear,
    ])

    if not has_command:
        parser.print_help()
        sys.exit(1)

    # Dispatch
    if args.stop:
        ok = stop_server()
        sys.exit(0 if ok else 1)

    if args.start:
        server = RAGServer(port=args.port)
        server.start()
        return

    if args.ingest:
        cli_ingest(args.ingest, agent_id=args.agent)
        return

    if args.search:
        cli_search(args.search, agent_id=args.agent, top_k=args.top_k)
        return

    if args.status:
        cli_status()
        return

    if args.clear:
        agent = args.agent if args.agent != "default" else None
        cli_clear(agent_id=agent)
        return


if __name__ == "__main__":
    main()
