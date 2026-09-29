"""Persistent relational storage for chat sessions, conversation messages,
and evaluation history.
"""

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
            # 5. Active User Feedback & Continuous Retrieval Tuning (Phase 36)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_feedback (
                    feedback_id TEXT PRIMARY KEY,
                    message_id TEXT,
                    session_id TEXT,
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    query TEXT,
                    response_snippet TEXT,
                    rating INTEGER NOT NULL,
                    category TEXT,
                    comment TEXT,
                    chunk_ids_json TEXT DEFAULT '[]',
                    created_at REAL NOT NULL
                )
                """
            )
            # Indices for rapid querying with tenant bounds
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON chat_sessions(tenant_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_eval_tenant ON evaluation_history(tenant_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_tenant ON audit_events(tenant_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_tenant ON chat_feedback(tenant_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_msg ON chat_feedback(message_id)"
            )
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
                INSERT INTO chat_sessions (
                    session_id, user_id, tenant_id, title, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
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
            cursor.execute(
                "SELECT session_id FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            )
            if not cursor.fetchone():
                first_title = content[:35] + ("..." if len(content) > 35 else "")
                cursor.execute(
                    """
                    INSERT INTO chat_sessions (
                        session_id, user_id, tenant_id, title, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (session_id, user_id, tenant_id, first_title, now, now),
                )
            else:
                cursor.execute(
                    "UPDATE chat_sessions SET updated_at = ? WHERE session_id = ?",
                    (now, session_id),
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

    # --- Phase 36: Active User Feedback & Continuous Retrieval Fine-Tuning ---

    def record_feedback(
        self,
        user_id: str,
        tenant_id: str,
        rating: int,
        message_id: str | None = None,
        session_id: str | None = None,
        query: str | None = None,
        response_snippet: str | None = None,
        category: str | None = "general",
        comment: str | None = None,
        chunk_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Records explicit user thumbs up / down feedback."""
        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        now = time.time()
        chunk_ids_json = json.dumps(chunk_ids or [])
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO chat_feedback (
                    feedback_id, message_id, session_id, user_id, tenant_id,
                    query, response_snippet, rating, category, comment,
                    chunk_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback_id,
                    message_id,
                    session_id,
                    user_id,
                    tenant_id,
                    query or "",
                    response_snippet or "",
                    1 if rating > 0 else -1,
                    category or "general",
                    comment or "",
                    chunk_ids_json,
                    now,
                ),
            )
            conn.commit()

        return {
            "feedback_id": feedback_id,
            "message_id": message_id,
            "session_id": session_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "rating": 1 if rating > 0 else -1,
            "category": category,
            "comment": comment,
            "chunk_ids": chunk_ids or [],
            "created_at": now,
        }

    def list_feedback(
        self, tenant_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Lists recent user feedback entries."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if tenant_id:
                cursor.execute(
                    """
                    SELECT feedback_id, message_id, session_id, user_id, tenant_id,
                           query, response_snippet, rating, category, comment,
                           chunk_ids_json, created_at
                    FROM chat_feedback
                    WHERE tenant_id = ?
                    ORDER BY created_at DESC, rowid DESC LIMIT ?
                    """,
                    (tenant_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT feedback_id, message_id, session_id, user_id, tenant_id,
                           query, response_snippet, rating, category, comment,
                           chunk_ids_json, created_at
                    FROM chat_feedback
                    ORDER BY created_at DESC, rowid DESC LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                {
                    "feedback_id": r["feedback_id"],
                    "message_id": r["message_id"],
                    "session_id": r["session_id"],
                    "user_id": r["user_id"],
                    "tenant_id": r["tenant_id"],
                    "query": r["query"],
                    "response_snippet": r["response_snippet"],
                    "rating": r["rating"],
                    "category": r["category"],
                    "comment": r["comment"],
                    "chunk_ids": json.loads(r["chunk_ids_json"]),
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

    def get_feedback_analytics(self, tenant_id: str = "default_tenant") -> dict[str, Any]:
        """Returns aggregated satisfaction analytics and tuning metrics for a tenant."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT rating, category, chunk_ids_json
                FROM chat_feedback
                WHERE tenant_id = ?
                """,
                (tenant_id,),
            )
            rows = cursor.fetchall()

        total = len(rows)
        pos = sum(1 for r in rows if r["rating"] > 0)
        neg = sum(1 for r in rows if r["rating"] < 0)
        csat = round((pos / total * 100.0) if total > 0 else 100.0, 1)

        cat_counts: dict[str, int] = {}
        chunk_praised: dict[str, int] = {}
        chunk_flagged: dict[str, int] = {}

        for r in rows:
            cat = r["category"] or "general"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            chunks = json.loads(r["chunk_ids_json"])
            if r["rating"] > 0:
                for c in chunks:
                    chunk_praised[c] = chunk_praised.get(c, 0) + 1
            else:
                for c in chunks:
                    chunk_flagged[c] = chunk_flagged.get(c, 0) + 1

        top_praised = sorted(chunk_praised.items(), key=lambda x: x[1], reverse=True)[:5]
        top_flagged = sorted(chunk_flagged.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "tenant_id": tenant_id,
            "total_ratings": total,
            "positive_ratings": pos,
            "negative_ratings": neg,
            "satisfaction_rate": csat,
            "category_distribution": cat_counts,
            "top_praised_chunks": [{"chunk_id": c, "count": cnt} for c, cnt in top_praised],
            "top_flagged_chunks": [{"chunk_id": c, "count": cnt} for c, cnt in top_flagged],
        }

    def get_chunk_boost_factor(
        self, chunk_id: str, tenant_id: str = "default_tenant"
    ) -> float:
        """Computes dynamic retrieval boost multiplier based on user feedback.

        Boosts frequently verified chunks (up to 1.5x) and penalizes hallucinated/flagged
        chunks (down to 0.5x). Default multiplier is 1.0.
        """
        if not chunk_id:
            return 1.0
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            pattern = f"%{chunk_id}%"
            cursor.execute(
                """
                SELECT rating
                FROM chat_feedback
                WHERE tenant_id = ? AND chunk_ids_json LIKE ?
                """,
                (tenant_id, pattern),
            )
            rows = cursor.fetchall()

        if not rows:
            return 1.0

        pos = sum(1 for r in rows if r["rating"] > 0)
        neg = sum(1 for r in rows if r["rating"] < 0)

        pos_boost = min(0.5, 0.15 * pos)
        neg_penalty = min(0.5, 0.20 * neg)
        multiplier = 1.0 + pos_boost - neg_penalty
        return round(max(0.5, min(1.5, multiplier)), 3)


_history_store: PersistentHistoryStore | None = None


def get_history_store() -> PersistentHistoryStore:
    """Returns global PersistentHistoryStore singleton."""
    global _history_store
    if _history_store is None:
        _history_store = PersistentHistoryStore()
    return _history_store
