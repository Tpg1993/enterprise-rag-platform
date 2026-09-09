"""Unit test suite for Phase 23 Persistent Chat and Evaluation History."""

import pytest
from src.storage.history import PersistentHistoryStore


@pytest.fixture
def memory_store():
    """Returns a temporary in-memory history store for clean isolated testing."""
    return PersistentHistoryStore(db_path=":memory:")


def test_session_lifecycle(memory_store):
    """Verifies creating and listing persistent chat sessions."""
    sess = memory_store.create_session(
        user_id="usr_1", tenant_id="tenant_a", title="Q3 Performance Review"
    )
    assert sess["session_id"].startswith("sess_")
    assert sess["title"] == "Q3 Performance Review"

    # List sessions for tenant_a
    sessions = memory_store.list_sessions(tenant_id="tenant_a")
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == sess["session_id"]

    # Different tenant should see 0 sessions (ABAC isolation)
    sessions_b = memory_store.list_sessions(tenant_id="tenant_b")
    assert len(sessions_b) == 0


def test_save_and_get_chat_history(memory_store):
    """Verifies saving chat messages and retrieving chronological history."""
    session_id = "sess_test_123"
    memory_store.save_chat_message(
        session_id=session_id,
        user_id="usr_1",
        tenant_id="tenant_a",
        role="user",
        content="What is Sarvam-105B?",
        rag_strategy="Basic",
    )
    memory_store.save_chat_message(
        session_id=session_id,
        user_id="assistant",
        tenant_id="tenant_a",
        role="assistant",
        content="Sarvam-105B is a foundational Indian language LLM.",
        rag_strategy="Basic",
        latency_ms=120.5,
        cost_usd=0.0002,
        citations=[{"source": "doc.txt", "relevance_score": 0.95}],
    )

    history = memory_store.get_chat_history(session_id=session_id, tenant_id="tenant_a")
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "What is Sarvam-105B?"
    assert history[1]["role"] == "assistant"
    assert len(history[1]["citations"]) == 1
    assert history[1]["citations"][0]["relevance_score"] == 0.95

    # Cross-tenant query should return empty (ABAC boundary)
    cross_tenant_history = memory_store.get_chat_history(session_id=session_id, tenant_id="tenant_b")
    assert len(cross_tenant_history) == 0


def test_evaluation_history_tracking(memory_store):
    """Verifies saving evaluation quality metrics and querying historical trends."""
    eval_res = memory_store.save_evaluation(
        user_id="usr_1",
        tenant_id="tenant_a",
        strategy="Hybrid",
        query="Explain Sarvam-105B architecture",
        answer="Sarvam-105B combines dense and sparse representations.",
        context_precision=0.92,
        context_recall=0.88,
        faithfulness=0.95,
        answer_relevancy=0.90,
        overall_score=0.91,
        latency_ms=250.0,
        total_cost_usd=0.0015,
        contexts_count=3,
    )
    assert eval_res["eval_id"].startswith("eval_")
    assert eval_res["overall_score"] == 0.91

    # Query evaluation history
    runs = memory_store.list_evaluation_history(tenant_id="tenant_a")
    assert len(runs) == 1
    assert runs[0]["strategy"] == "Hybrid"
    assert runs[0]["faithfulness"] == 0.95

    # Filter by non-existent strategy
    empty_runs = memory_store.list_evaluation_history(tenant_id="tenant_a", strategy="GraphRAG")
    assert len(empty_runs) == 0
