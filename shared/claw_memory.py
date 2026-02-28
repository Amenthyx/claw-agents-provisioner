#!/usr/bin/env python3
"""
=============================================================================
CLAW AGENTS PROVISIONER — Conversation Memory Engine
=============================================================================
SQLite-backed conversation memory with cross-agent context sharing.
Provides per-agent conversation history, full-text search, context sharing
between agents in orchestrated pipelines, and automatic retention policies.

Features:
  - Per-agent conversation storage with role-based messages
  - Cross-agent context sharing for orchestrated pipelines
  - Full-text search across all conversation history
  - Auto-summarization of long conversations
  - Configurable retention policy with auto-pruning
  - Export conversations as JSON or Markdown

HTTP API (port 9096):
  POST /api/memory/conversations              Create conversation
  POST /api/memory/conversations/:id/messages  Add message
  GET  /api/memory/conversations/:id           Get conversation with messages
  POST /api/memory/search                      Full-text search
  POST /api/memory/share                       Share context between agents
  GET  /api/memory/stats                       Usage statistics
  DELETE /api/memory/conversations/:id         Delete conversation

Usage:
  python3 shared/claw_memory.py --start --port 9096
  python3 shared/claw_memory.py --stop
  python3 shared/claw_memory.py --search "query"
  python3 shared/claw_memory.py --export <conversation_id>
  python3 shared/claw_memory.py --prune --days 30
  python3 shared/claw_memory.py --stats

Python 3.8+ stdlib only (no external dependencies).
=============================================================================
Created by Mauro Tommasi — linkedin.com/in/maurotommasi
Apache 2.0 © 2026 Amenthyx
"""

import json
import os
import signal
import sqlite3
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = PROJECT_ROOT / "data" / "memory"
DB_FILE = DATA_DIR / "conversations.db"
PID_FILE = DATA_DIR / "memory.pid"
DEFAULT_PORT = 9096
SUMMARY_THRESHOLD = 20  # auto-summarize after this many messages
SUMMARY_MAX_CHARS = 500  # max chars for generated summaries
DEFAULT_RETENTION_DAYS = 90

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
    print(f"{GREEN}[memory]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[memory]{NC} {msg}")


def err(msg: str) -> None:
    print(f"{RED}[memory]{NC} {msg}", file=sys.stderr)


def info(msg: str) -> None:
    print(f"{BLUE}[memory]{NC} {msg}")


# -------------------------------------------------------------------------
# ConversationStore — SQLite-backed conversation storage
# -------------------------------------------------------------------------
class ConversationStore:
    """Thread-safe SQLite store for conversations, messages, and context shares."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        """Create tables if they do not exist."""
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    summary TEXT
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tokens INTEGER DEFAULT 0,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS context_shares (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    context_summary TEXT NOT NULL,
                    shared_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conv
                    ON messages(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_conversations_agent
                    ON conversations(agent_id);
                CREATE INDEX IF NOT EXISTS idx_context_to_agent
                    ON context_shares(to_agent);
            """)

    # --- Conversations ---

    def create_conversation(self, agent_id: str,
                            conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Create a new conversation and return its record."""
        conv_id = conversation_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._conn.execute(
                "INSERT INTO conversations (id, agent_id, created_at, updated_at, summary) "
                "VALUES (?, ?, ?, ?, NULL)",
                (conv_id, agent_id, now, now),
            )

        return {
            "id": conv_id,
            "agent_id": agent_id,
            "created_at": now,
            "updated_at": now,
            "summary": None,
        }

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Return a conversation with all its messages, or None if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()

            if not row:
                return None

            messages = self._conn.execute(
                "SELECT id, role, content, timestamp, tokens "
                "FROM messages WHERE conversation_id = ? ORDER BY id ASC",
                (conv_id,),
            ).fetchall()

        return {
            "id": row["id"],
            "agent_id": row["agent_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "summary": row["summary"],
            "messages": [dict(m) for m in messages],
        }

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and its messages. Returns True if deleted."""
        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM conversations WHERE id = ?", (conv_id,)
            )
        return cursor.rowcount > 0

    def list_conversations(self, agent_id: Optional[str] = None,
                           limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List conversations, optionally filtered by agent_id."""
        with self._lock:
            if agent_id:
                rows = self._conn.execute(
                    "SELECT * FROM conversations WHERE agent_id = ? "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (agent_id, limit, offset),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM conversations "
                    "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()

        return [dict(r) for r in rows]

    # --- Messages ---

    def add_message(self, conv_id: str, role: str, content: str,
                    tokens: int = 0) -> Optional[Dict[str, Any]]:
        """Add a message to a conversation. Returns the message or None if conversation missing."""
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            # Verify conversation exists
            exists = self._conn.execute(
                "SELECT 1 FROM conversations WHERE id = ?", (conv_id,)
            ).fetchone()
            if not exists:
                return None

            cursor = self._conn.execute(
                "INSERT INTO messages (conversation_id, role, content, timestamp, tokens) "
                "VALUES (?, ?, ?, ?, ?)",
                (conv_id, role, content, now, tokens),
            )
            msg_id = cursor.lastrowid

            # Update conversation timestamp
            self._conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conv_id),
            )

            # Auto-summarize if threshold reached
            count = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM messages WHERE conversation_id = ?",
                (conv_id,),
            ).fetchone()["cnt"]

        if count >= SUMMARY_THRESHOLD and count % SUMMARY_THRESHOLD == 0:
            self._auto_summarize(conv_id)

        return {
            "id": msg_id,
            "conversation_id": conv_id,
            "role": role,
            "content": content,
            "timestamp": now,
            "tokens": tokens,
        }

    # --- Context Sharing ---

    def share_context(self, from_agent: str, to_agent: str,
                      conversation_id: str,
                      context_summary: str) -> Dict[str, Any]:
        """Share context from one agent to another."""
        now = datetime.now(timezone.utc).isoformat()

        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO context_shares "
                "(from_agent, to_agent, conversation_id, context_summary, shared_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (from_agent, to_agent, conversation_id, context_summary, now),
            )

        return {
            "id": cursor.lastrowid,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "conversation_id": conversation_id,
            "context_summary": context_summary,
            "shared_at": now,
        }

    def get_shared_context(self, to_agent: str,
                           limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve context shared with a specific agent."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM context_shares WHERE to_agent = ? "
                "ORDER BY shared_at DESC LIMIT ?",
                (to_agent, limit),
            ).fetchall()

        return [dict(r) for r in rows]

    # --- Search ---

    def search(self, query: str, agent_id: Optional[str] = None,
               limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search across message content using LIKE."""
        pattern = f"%{query}%"

        with self._lock:
            if agent_id:
                rows = self._conn.execute(
                    "SELECT m.id, m.conversation_id, m.role, m.content, m.timestamp, "
                    "       c.agent_id "
                    "FROM messages m "
                    "JOIN conversations c ON m.conversation_id = c.id "
                    "WHERE m.content LIKE ? AND c.agent_id = ? "
                    "ORDER BY m.timestamp DESC LIMIT ?",
                    (pattern, agent_id, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT m.id, m.conversation_id, m.role, m.content, m.timestamp, "
                    "       c.agent_id "
                    "FROM messages m "
                    "JOIN conversations c ON m.conversation_id = c.id "
                    "WHERE m.content LIKE ? "
                    "ORDER BY m.timestamp DESC LIMIT ?",
                    (pattern, limit),
                ).fetchall()

        return [dict(r) for r in rows]

    # --- Stats ---

    def get_stats(self) -> Dict[str, Any]:
        """Return usage statistics."""
        with self._lock:
            conv_count = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM conversations"
            ).fetchone()["cnt"]

            msg_count = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM messages"
            ).fetchone()["cnt"]

            share_count = self._conn.execute(
                "SELECT COUNT(*) AS cnt FROM context_shares"
            ).fetchone()["cnt"]

            total_tokens = self._conn.execute(
                "SELECT COALESCE(SUM(tokens), 0) AS total FROM messages"
            ).fetchone()["total"]

            agent_count = self._conn.execute(
                "SELECT COUNT(DISTINCT agent_id) AS cnt FROM conversations"
            ).fetchone()["cnt"]

            oldest = self._conn.execute(
                "SELECT MIN(created_at) AS oldest FROM conversations"
            ).fetchone()["oldest"]

            newest = self._conn.execute(
                "SELECT MAX(updated_at) AS newest FROM conversations"
            ).fetchone()["newest"]

            db_size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "conversations": conv_count,
            "messages": msg_count,
            "context_shares": share_count,
            "total_tokens": total_tokens,
            "unique_agents": agent_count,
            "oldest_conversation": oldest,
            "newest_activity": newest,
            "db_size_bytes": db_size_bytes,
            "db_size_mb": round(db_size_bytes / 1024 / 1024, 2),
            "db_path": str(self.db_path),
        }

    # --- Retention / Pruning ---

    def prune(self, days: int = DEFAULT_RETENTION_DAYS) -> int:
        """Delete conversations older than the specified number of days. Returns count deleted."""
        threshold = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with self._lock:
            cursor = self._conn.execute(
                "DELETE FROM conversations WHERE updated_at < ?",
                (threshold,),
            )
            deleted = cursor.rowcount

            # Clean orphaned context_shares (conversation deleted)
            self._conn.execute(
                "DELETE FROM context_shares WHERE conversation_id NOT IN "
                "(SELECT id FROM conversations)"
            )

        return deleted

    # --- Export ---

    def export_json(self, conv_id: str) -> Optional[str]:
        """Export a conversation as a JSON string."""
        conv = self.get_conversation(conv_id)
        if not conv:
            return None
        return json.dumps(conv, indent=2)

    def export_markdown(self, conv_id: str) -> Optional[str]:
        """Export a conversation as Markdown."""
        conv = self.get_conversation(conv_id)
        if not conv:
            return None

        lines = [
            f"# Conversation {conv['id']}",
            f"",
            f"- **Agent:** {conv['agent_id']}",
            f"- **Created:** {conv['created_at']}",
            f"- **Updated:** {conv['updated_at']}",
        ]

        if conv.get("summary"):
            lines.append(f"- **Summary:** {conv['summary']}")

        lines.append("")
        lines.append("---")
        lines.append("")

        for msg in conv.get("messages", []):
            role = msg["role"].upper()
            lines.append(f"### {role}")
            lines.append(f"*{msg['timestamp']}*")
            if msg.get("tokens"):
                lines.append(f"*tokens: {msg['tokens']}*")
            lines.append("")
            lines.append(msg["content"])
            lines.append("")

        return "\n".join(lines)

    # --- Auto-summarize ---

    def _auto_summarize(self, conv_id: str) -> None:
        """Generate a simple summary by combining the first and last messages."""
        with self._lock:
            messages = self._conn.execute(
                "SELECT role, content FROM messages "
                "WHERE conversation_id = ? ORDER BY id ASC",
                (conv_id,),
            ).fetchall()

        if not messages:
            return

        # Build summary from combined message content (truncation-based)
        combined = " ".join(
            f"[{m['role']}] {m['content']}" for m in messages
        )

        if len(combined) > SUMMARY_MAX_CHARS:
            summary = combined[:SUMMARY_MAX_CHARS] + "..."
        else:
            summary = combined

        with self._lock:
            self._conn.execute(
                "UPDATE conversations SET summary = ? WHERE id = ?",
                (summary, conv_id),
            )

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            self._conn.close()


# -------------------------------------------------------------------------
# MemoryRequestHandler — HTTP API handler
# -------------------------------------------------------------------------
class MemoryRequestHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for the conversation memory API."""

    store: ConversationStore  # set by MemoryServer

    def log_message(self, format: str, *args: Any) -> None:
        """Override to use our log function."""
        info(f"{self.address_string()} {format % args}")

    def _send_json(self, data: Any, status: int = 200) -> None:
        """Send a JSON response."""
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> bytes:
        """Read the request body."""
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return b""
        return self.rfile.read(length)

    def _parse_json_body(self) -> Optional[Dict]:
        """Parse the request body as JSON."""
        raw = self._read_body()
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None

    def _extract_path_id(self, prefix: str) -> Optional[str]:
        """Extract an ID from the URL path after the given prefix."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.startswith(prefix):
            remainder = path[len(prefix):]
            parts = remainder.strip("/").split("/")
            if parts and parts[0]:
                return parts[0]
        return None

    def _path_matches(self, pattern: str) -> bool:
        """Check if the request path matches a pattern (with :id wildcard)."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        return path == pattern.rstrip("/")

    def do_GET(self) -> None:
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # GET /api/memory/stats
        if path == "/api/memory/stats":
            stats = self.store.get_stats()
            self._send_json(stats)
            return

        # GET /api/memory/conversations/:id
        if path.startswith("/api/memory/conversations/"):
            conv_id = path.replace("/api/memory/conversations/", "").split("/")[0]
            if not conv_id:
                self._send_json({"error": "Missing conversation ID"}, 400)
                return

            conv = self.store.get_conversation(conv_id)
            if not conv:
                self._send_json({"error": "Conversation not found"}, 404)
                return

            self._send_json(conv)
            return

        # GET /api/memory/conversations (list)
        if path == "/api/memory/conversations":
            conversations = self.store.list_conversations()
            self._send_json({"conversations": conversations})
            return

        # Health check
        if path == "/health" or path == "/":
            self._send_json({"status": "ok", "service": "claw-memory", "port": DEFAULT_PORT})
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self) -> None:
        """Handle POST requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # POST /api/memory/conversations/:id/messages
        if "/messages" in path and path.startswith("/api/memory/conversations/"):
            parts = path.replace("/api/memory/conversations/", "").split("/")
            conv_id = parts[0] if parts else ""
            if not conv_id:
                self._send_json({"error": "Missing conversation ID"}, 400)
                return

            body = self._parse_json_body()
            if not body:
                self._send_json({"error": "Invalid or missing JSON body"}, 400)
                return

            role = body.get("role", "")
            content = body.get("content", "")
            tokens = body.get("tokens", 0)

            if role not in ("user", "assistant", "system"):
                self._send_json({"error": "Invalid role. Must be user, assistant, or system"}, 400)
                return

            if not content:
                self._send_json({"error": "Missing content"}, 400)
                return

            msg = self.store.add_message(conv_id, role, content, tokens)
            if not msg:
                self._send_json({"error": "Conversation not found"}, 404)
                return

            self._send_json(msg, 201)
            return

        # POST /api/memory/conversations
        if path == "/api/memory/conversations":
            body = self._parse_json_body()
            if not body:
                self._send_json({"error": "Invalid or missing JSON body"}, 400)
                return

            agent_id = body.get("agent_id", "")
            if not agent_id:
                self._send_json({"error": "Missing agent_id"}, 400)
                return

            conv_id = body.get("id")
            conv = self.store.create_conversation(agent_id, conv_id)
            self._send_json(conv, 201)
            return

        # POST /api/memory/search
        if path == "/api/memory/search":
            body = self._parse_json_body()
            if not body:
                self._send_json({"error": "Invalid or missing JSON body"}, 400)
                return

            query = body.get("query", "")
            if not query:
                self._send_json({"error": "Missing query"}, 400)
                return

            agent_id = body.get("agent_id")
            limit = body.get("limit", 50)

            results = self.store.search(query, agent_id=agent_id, limit=limit)
            self._send_json({"query": query, "count": len(results), "results": results})
            return

        # POST /api/memory/share
        if path == "/api/memory/share":
            body = self._parse_json_body()
            if not body:
                self._send_json({"error": "Invalid or missing JSON body"}, 400)
                return

            from_agent = body.get("from_agent", "")
            to_agent = body.get("to_agent", "")
            conversation_id = body.get("conversation_id", "")
            context_summary = body.get("context_summary", "")

            if not all([from_agent, to_agent, conversation_id, context_summary]):
                self._send_json({
                    "error": "Missing required fields: from_agent, to_agent, "
                             "conversation_id, context_summary"
                }, 400)
                return

            share = self.store.share_context(
                from_agent, to_agent, conversation_id, context_summary
            )
            self._send_json(share, 201)
            return

        self._send_json({"error": "Not found"}, 404)

    def do_DELETE(self) -> None:
        """Handle DELETE requests."""
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # DELETE /api/memory/conversations/:id
        if path.startswith("/api/memory/conversations/"):
            conv_id = path.replace("/api/memory/conversations/", "").split("/")[0]
            if not conv_id:
                self._send_json({"error": "Missing conversation ID"}, 400)
                return

            deleted = self.store.delete_conversation(conv_id)
            if deleted:
                self._send_json({"deleted": True, "id": conv_id})
            else:
                self._send_json({"error": "Conversation not found"}, 404)
            return

        self._send_json({"error": "Not found"}, 404)


# -------------------------------------------------------------------------
# MemoryServer — HTTP server wrapper
# -------------------------------------------------------------------------
class MemoryServer:
    """HTTP server for the conversation memory API."""

    def __init__(self, port: int = DEFAULT_PORT, db_path: Optional[Path] = None) -> None:
        self.port = port
        self.store = ConversationStore(db_path)
        self.server: Optional[HTTPServer] = None

    def start(self) -> None:
        """Start the HTTP server."""
        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Write PID file
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))

        # Configure handler with store reference
        MemoryRequestHandler.store = self.store

        self.server = HTTPServer(("0.0.0.0", self.port), MemoryRequestHandler)

        # Handle graceful shutdown
        def _shutdown(signum: int, frame: Any) -> None:
            log("Shutting down memory server...")
            if self.server:
                threading.Thread(target=self.server.shutdown).start()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        log(f"Memory server starting on port {self.port}")
        log(f"Database: {self.store.db_path}")
        log(f"PID file: {PID_FILE}")
        info(f"API base: http://localhost:{self.port}/api/memory")

        try:
            self.server.serve_forever()
        finally:
            self.store.close()
            if PID_FILE.exists():
                PID_FILE.unlink()
            log("Memory server stopped.")

    @staticmethod
    def stop() -> bool:
        """Stop a running memory server by reading the PID file."""
        if not PID_FILE.exists():
            err("No PID file found. Server may not be running.")
            return False

        try:
            pid = int(PID_FILE.read_text().strip())
        except (ValueError, OSError):
            err("Invalid PID file.")
            return False

        try:
            os.kill(pid, signal.SIGTERM)
            log(f"Sent SIGTERM to PID {pid}")
            # Wait briefly for process to exit
            for _ in range(10):
                try:
                    os.kill(pid, 0)  # Check if process exists
                    time.sleep(0.3)
                except OSError:
                    break
            if PID_FILE.exists():
                PID_FILE.unlink()
            log("Memory server stopped.")
            return True
        except OSError as e:
            err(f"Failed to stop server (PID {pid}): {e}")
            if PID_FILE.exists():
                PID_FILE.unlink()
            return False


# -------------------------------------------------------------------------
# CLI Output Formatting
# -------------------------------------------------------------------------
def print_stats(stats: Dict[str, Any]) -> None:
    """Print a formatted statistics report."""
    print(f"\n{BOLD}{CYAN}=== Conversation Memory — Statistics ==={NC}\n")
    print(f"  {BOLD}Conversations:{NC}   {stats['conversations']}")
    print(f"  {BOLD}Messages:{NC}        {stats['messages']}")
    print(f"  {BOLD}Context Shares:{NC}  {stats['context_shares']}")
    print(f"  {BOLD}Total Tokens:{NC}    {stats['total_tokens']:,}")
    print(f"  {BOLD}Unique Agents:{NC}   {stats['unique_agents']}")
    print(f"  {BOLD}Oldest:{NC}          {stats['oldest_conversation'] or 'N/A'}")
    print(f"  {BOLD}Newest:{NC}          {stats['newest_activity'] or 'N/A'}")
    print(f"  {BOLD}DB Size:{NC}         {stats['db_size_mb']} MB")
    print(f"  {BOLD}DB Path:{NC}         {stats['db_path']}")
    print()


def print_search_results(results: List[Dict[str, Any]], query: str) -> None:
    """Print formatted search results."""
    print(f"\n{BOLD}{CYAN}=== Search Results for '{query}' ==={NC}\n")

    if not results:
        print(f"  {DIM}No results found.{NC}\n")
        return

    print(f"  Found {BOLD}{len(results)}{NC} result(s):\n")

    for i, r in enumerate(results, 1):
        role_color = GREEN if r["role"] == "assistant" else BLUE if r["role"] == "user" else DIM
        content_preview = r["content"][:120].replace("\n", " ")
        if len(r["content"]) > 120:
            content_preview += "..."

        print(f"  {BOLD}{i}.{NC} [{role_color}{r['role']}{NC}] conv={r['conversation_id'][:12]}... agent={r.get('agent_id', '?')}")
        print(f"     {content_preview}")
        print(f"     {DIM}{r['timestamp']}{NC}")
        print()


def print_export(content: str, fmt: str) -> None:
    """Print exported conversation content."""
    print(f"\n{BOLD}{CYAN}=== Conversation Export ({fmt.upper()}) ==={NC}\n")
    print(content)


# -------------------------------------------------------------------------
# Main CLI
# -------------------------------------------------------------------------
def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 shared/claw_memory.py [OPTIONS]")
        print()
        print("Server:")
        print("  --start [--port PORT]   Start memory server (default port 9096)")
        print("  --stop                  Stop running memory server")
        print()
        print("Queries:")
        print("  --search QUERY          Full-text search across conversations")
        print("  --export ID [--format FORMAT]  Export conversation (json|markdown)")
        print("  --stats                 Show usage statistics")
        print("  --prune [--days N]      Delete conversations older than N days (default 90)")
        sys.exit(1)

    action = sys.argv[1]

    if action == "--start":
        port = DEFAULT_PORT
        # Parse --port argument
        if "--port" in sys.argv:
            port_idx = sys.argv.index("--port")
            if port_idx + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[port_idx + 1])
                except ValueError:
                    err(f"Invalid port: {sys.argv[port_idx + 1]}")
                    sys.exit(1)

        # Check if already running
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, 0)  # Check if process exists
                err(f"Memory server already running (PID {pid}). Use --stop first.")
                sys.exit(1)
            except (OSError, ValueError):
                # Stale PID file — remove it
                PID_FILE.unlink()

        server = MemoryServer(port=port)
        server.start()

    elif action == "--stop":
        success = MemoryServer.stop()
        sys.exit(0 if success else 1)

    elif action == "--search":
        if len(sys.argv) < 3:
            err("Missing search query. Usage: --search QUERY")
            sys.exit(1)

        query = " ".join(sys.argv[2:])
        store = ConversationStore()
        results = store.search(query)
        print_search_results(results, query)
        store.close()

    elif action == "--export":
        if len(sys.argv) < 3:
            err("Missing conversation ID. Usage: --export CONVERSATION_ID [--format json|markdown]")
            sys.exit(1)

        conv_id = sys.argv[2]
        fmt = "json"
        if "--format" in sys.argv:
            fmt_idx = sys.argv.index("--format")
            if fmt_idx + 1 < len(sys.argv):
                fmt = sys.argv[fmt_idx + 1].lower()

        store = ConversationStore()

        if fmt == "markdown" or fmt == "md":
            content = store.export_markdown(conv_id)
        else:
            content = store.export_json(conv_id)

        if content is None:
            err(f"Conversation not found: {conv_id}")
            store.close()
            sys.exit(1)

        print_export(content, fmt)
        store.close()

    elif action == "--prune":
        days = DEFAULT_RETENTION_DAYS
        if "--days" in sys.argv:
            days_idx = sys.argv.index("--days")
            if days_idx + 1 < len(sys.argv):
                try:
                    days = int(sys.argv[days_idx + 1])
                except ValueError:
                    err(f"Invalid days value: {sys.argv[days_idx + 1]}")
                    sys.exit(1)

        store = ConversationStore()
        deleted = store.prune(days)
        log(f"Pruned {deleted} conversation(s) older than {days} days.")
        store.close()

    elif action == "--stats":
        store = ConversationStore()
        stats = store.get_stats()
        print_stats(stats)
        store.close()

    else:
        err(f"Unknown action: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
