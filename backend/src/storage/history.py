"""Persistent relational storage for chat sessions, conversation messages, and evaluation history."""

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("HISTORY_DB_PATH", "backend/data/history.db")


class PersistentHistoryStore:
    """Thread-safe persistent store for chat history and evaluation runs."""

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._memory_conn: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            self._memory_conn.row_factory = sqlite3.Row
        self._ensure_db_dir()
        self._init_schema()

    def _ensure_db_dir(self) -> None:
        if self.db_path != ":memory:":
            dirname = os.path.dirname(self.db_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Chat Sessions
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            # 2. Chat Messages
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    rag_strategy TEXT,
                    latency_ms REAL DEFAULT 0.0,
                    cost_usd REAL DEFAULT 0.0,
                    prompt_tokens INTEGER DEFAULT 0,
                    completion_tokens INTEGER DEFAULT 0,
                    citations_json TEXT DEFAULT '[]',
                    created_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                )
                """
            )
            # 3. Evaluation History Tracking
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS evaluation_history (
                    eval_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    query TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    context_precision REAL NOT NULL,
                    context_recall REAL NOT NULL,
                    faithfulness REAL NOT NULL,
                    answer_relevancy REAL NOT NULL,
                    overall_score REAL NOT NULL,
                    latency_ms REAL NOT NULL,
                    total_cost_usd REAL NOT NULL,
                    contexts_count INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
                """
            )
            # 4. Security & Access Audit Events
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details_json TEXT DEFAULT '{}',
                    timestamp REAL NOT NULL
                )
                """
            )
            # Indices for rapid querying with tenant bounds
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON chat_sessions(tenant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_eval_tenant ON evaluation_history(tenant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events(tenant_id)")
            conn.commit()

    def create_session(
        self, user_id: str, tenant_id: str, title: str = "New Conversation"
    ) -> dict[str, Any]:
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_sessions (session_id, user_id, tenant_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, tenant_id, title, now, now),
            )
            conn.commit()
        return {
            "session_id": session_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
        }

    def list_sessions(
        self, tenant_id: str, user_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute(
                    """
                    SELECT session_id, user_id, tenant_id, title, created_at, updated_at
                    FROM chat_sessions
                    WHERE tenant_id = ? AND user_id = ?
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (tenant_id, user_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT session_id, user_id, tenant_id, title, created_at, updated_at
                    FROM chat_sessions
                    WHERE tenant_id = ?
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (tenant_id, limit),
                )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def save_chat_message(
        self,
        session_id: str,
        user_id: str,
        tenant_id: str,
        role: str,
        content: str,
        rag_strategy: str | None = None,
        latency_ms: float = 0.0,
        cost_usd: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        citations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        message_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = time.time()
        citations_str = json.dumps(citations or [])

        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # Ensure session exists or auto-create
            cursor.execute("SELECT session_id FROM chat_sessions WHERE session_id = ?", (session_id,))
            if not cursor.fetchone():
                first_title = content[:35] + ("..." if len(content) > 35 else "")
                cursor.execute(
                    """
                    INSERT INTO chat_sessions (session_id, user_id, tenant_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, user_id, tenant_id, first_title, now, now),
                )
            else:
                cursor.execute(
                    "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?", (now, session_id)
                )

            cursor.execute(
                """
                INSERT INTO chat_messages (
                    message_id, session_id, user_id, tenant_id, role, content,
                    rag_strategy, latency_ms, cost_usd, prompt_tokens,
                    completion_tokens, citations_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    user_id,
                    tenant_id,
                    role,
                    content,
                    rag_strategy,
                    latency_ms,
                    cost_usd,
                    prompt_tokens,
                    completion_tokens,
                    citations_str,
                    now,
                ),
            )
            conn.commit()

        return {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "rag_strategy": rag_strategy,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "created_at": now,
        }

    def get_chat_history(self, session_id: str, tenant_id: str) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT message_id, session_id, user_id, tenant_id, role, content,
                       rag_strategy, latency_ms, cost_usd, prompt_tokens,
                       completion_tokens, citations_json, created_at
                FROM chat_messages
                WHERE session_id = ? AND tenant_id = ?
                ORDER BY created_at ASC
                """,
                (session_id, tenant_id),
            )
            rows = cursor.fetchall()
            messages = []
            for r in rows:
                item = dict(r)
                try:
                    item["citations"] = json.loads(item.get("citations_json", "[]"))
                except Exception:
                    item["citations"] = []
                messages.append(item)
            return messages

    def save_evaluation(
        self,
        user_id: str,
        tenant_id: str,
        strategy: str,
        query: str,
        answer: str,
        context_precision: float,
        context_recall: float,
        faithfulness: float,
        answer_relevancy: float,
        overall_score: float,
        latency_ms: float,
        total_cost_usd: float,
        contexts_count: int = 0,
    ) -> dict[str, Any]:
        eval_id = f"eval_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO evaluation_history (
                    eval_id, user_id, tenant_id, strategy, query, answer,
                    context_precision, context_recall, faithfulness, answer_relevancy,
                    overall_score, latency_ms, total_cost_usd, contexts_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    eval_id,
                    user_id,
                    tenant_id,
                    strategy,
                    query,
                    answer,
                    context_precision,
                    context_recall,
                    faithfulness,
                    answer_relevancy,
                    overall_score,
                    latency_ms,
                    total_cost_usd,
                    contexts_count,
                    now,
                ),
            )
            conn.commit()

        return {
            "eval_id": eval_id,
            "strategy": strategy,
            "overall_score": overall_score,
            "latency_ms": latency_ms,
            "total_cost_usd": total_cost_usd,
            "created_at": now,
        }

    def list_evaluation_history(
        self, tenant_id: str, strategy: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if strategy:
                cursor.execute(
                    """
                    SELECT eval_id, user_id, tenant_id, strategy, query, answer,
                           context_precision, context_recall, faithfulness,
                           answer_relevancy, overall_score, latency_ms,
                           total_cost_usd, contexts_count, created_at
                    FROM evaluation_history
                    WHERE tenant_id = ? AND strategy = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (tenant_id, strategy, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT eval_id, user_id, tenant_id, strategy, query, answer,
                           context_precision, context_recall, faithfulness,
                           answer_relevancy, overall_score, latency_ms,
                           total_cost_usd, contexts_count, created_at
                    FROM evaluation_history
                    WHERE tenant_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (tenant_id, limit),
                )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def record_audit_event(
        self,
        event_type: str,
        user_id: str,
        tenant_id: str,
        action: str,
        resource: str,
        status: str = "SUCCESS",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Records a security or access audit event."""
        event_id = f"aud_{uuid.uuid4().hex[:12]}"
        now = time.time()
        details_json = json.dumps(details or {})
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_events (
                    event_id, event_type, user_id, tenant_id,
                    action, resource, status, details_json, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id, event_type, user_id, tenant_id,
                    action, resource, status, details_json, now
                ),
            )
            conn.commit()
        return {
            "event_id": event_id,
            "event_type": event_type,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "action": action,
            "resource": resource,
            "status": status,
            "details": details or {},
            "timestamp": now,
        }

    def get_audit_events(
        self, tenant_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Retrieves audit events filtered by tenant_id."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if tenant_id:
                cursor.execute(
                    """
                    SELECT event_id, event_type, user_id, tenant_id,
                           action, resource, status, details_json, timestamp
                    FROM audit_events
                    WHERE tenant_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                    """,
                    (tenant_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT event_id, event_type, user_id, tenant_id,
                           action, resource, status, details_json, timestamp
                    FROM audit_events
                    ORDER BY timestamp DESC LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                {
                    "event_id": r["event_id"],
                    "event_type": r["event_type"],
                    "user_id": r["user_id"],
                    "tenant_id": r["tenant_id"],
                    "action": r["action"],
                    "resource": r["resource"],
                    "status": r["status"],
                    "details": json.loads(r["details_json"]),
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]


_history_store: PersistentHistoryStore | None = None


def get_history_store() -> PersistentHistoryStore:
    """Returns global PersistentHistoryStore singleton."""
    global _history_store
    if _history_store is None:
        _history_store = PersistentHistoryStore()
    return _history_store
