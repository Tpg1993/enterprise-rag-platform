"""Unit tests for Active User Feedback & Continuous Retrieval Fine-Tuning Loop (Phase 36)."""

from src.retrieval.fusion import ReciprocalRankFusion
from src.storage.history import PersistentHistoryStore


def test_feedback_record_and_list():
    """Verify recording and listing user feedback with tenant isolation."""
    store = PersistentHistoryStore(db_path=":memory:")
    fb1 = store.record_feedback(
        user_id="user_alpha",
        tenant_id="tenant_fb_1",
        rating=1,
        query="What is Qdrant?",
        response_snippet="Qdrant is a vector database.",
        category="factual_accuracy",
        chunk_ids=["chunk_qdrant_01"],
    )
    assert fb1["feedback_id"].startswith("fb_")
    assert fb1["rating"] == 1
    assert fb1["category"] == "factual_accuracy"

    fb2 = store.record_feedback(
        user_id="user_beta",
        tenant_id="tenant_fb_1",
        rating=-1,
        query="Explain quantum bypass",
        response_snippet="Quantum bypass enabled.",
        category="hallucination",
        comment="Documentation says no quantum bypass.",
        chunk_ids=["chunk_quantum_bad"],
    )
    assert fb2["rating"] == -1

    # List for tenant_fb_1
    items = store.list_feedback(tenant_id="tenant_fb_1")
    assert len(items) == 2
    assert items[0]["feedback_id"] == fb2["feedback_id"]  # Ordered by created_at DESC

    # List for other tenant
    other_items = store.list_feedback(tenant_id="other_tenant")
    assert len(other_items) == 0


def test_chunk_boost_factor_calculation():
    """Verify chunk boost multiplier increases for positive and decreases for negative ratings."""
    store = PersistentHistoryStore(db_path=":memory:")
    chunk_id = "chk_benchmark_001"
    tenant_id = "tenant_boost_test"

    # Default boost for unrated chunk
    assert store.get_chunk_boost_factor(chunk_id, tenant_id=tenant_id) == 1.0

    # 1 thumbs up -> 1.0 + 0.15 = 1.15
    store.record_feedback(
        user_id="u1",
        tenant_id=tenant_id,
        rating=1,
        chunk_ids=[chunk_id],
    )
    assert store.get_chunk_boost_factor(chunk_id, tenant_id=tenant_id) == 1.15

    # 2 more thumbs up -> 1.0 + min(0.5, 0.45) = 1.45
    store.record_feedback(user_id="u2", tenant_id=tenant_id, rating=1, chunk_ids=[chunk_id])
    store.record_feedback(user_id="u3", tenant_id=tenant_id, rating=1, chunk_ids=[chunk_id])
    assert store.get_chunk_boost_factor(chunk_id, tenant_id=tenant_id) == 1.45

    # 1 thumbs down on bad chunk
    bad_chunk = "chk_hallucinated_999"
    store.record_feedback(
        user_id="u4",
        tenant_id=tenant_id,
        rating=-1,
        chunk_ids=[bad_chunk],
    )
    # 1.0 - 0.20 = 0.8
    assert store.get_chunk_boost_factor(bad_chunk, tenant_id=tenant_id) == 0.8


def test_feedback_analytics_aggregation():
    """Verify aggregated CSAT, category counts, and praised/flagged chunk lists."""
    store = PersistentHistoryStore(db_path=":memory:")
    tenant_id = "tenant_analytics_test"

    store.record_feedback(
        user_id="u1",
        tenant_id=tenant_id,
        rating=1,
        category="factual_accuracy",
        chunk_ids=["chk_top_good"],
    )
    store.record_feedback(
        user_id="u2",
        tenant_id=tenant_id,
        rating=1,
        category="factual_accuracy",
        chunk_ids=["chk_top_good"],
    )
    store.record_feedback(
        user_id="u3",
        tenant_id=tenant_id,
        rating=-1,
        category="hallucination",
        chunk_ids=["chk_hallucinated"],
    )

    analytics = store.get_feedback_analytics(tenant_id=tenant_id)
    assert analytics["total_ratings"] == 3
    assert analytics["positive_ratings"] == 2
    assert analytics["negative_ratings"] == 1
    assert analytics["satisfaction_rate"] == 66.7
    assert analytics["category_distribution"]["factual_accuracy"] == 2
    assert analytics["category_distribution"]["hallucination"] == 1
    assert len(analytics["top_praised_chunks"]) == 1
    assert analytics["top_praised_chunks"][0]["chunk_id"] == "chk_top_good"
    assert analytics["top_praised_chunks"][0]["count"] == 2
    assert len(analytics["top_flagged_chunks"]) == 1
    assert analytics["top_flagged_chunks"][0]["chunk_id"] == "chk_hallucinated"


def test_reciprocal_rank_fusion_with_feedback_boost():
    """Verify RRF fusion algorithm applies feedback boost factors to elevate praised chunks."""
    from src.storage.history import get_history_store

    store = get_history_store()
    tenant_id = "test_rrf_tenant"
    praised_cid = "chk_praised_fusion"
    regular_cid = "chk_regular_fusion"

    # Praise the praised_cid
    store.record_feedback(
        user_id="u_tester",
        tenant_id=tenant_id,
        rating=1,
        chunk_ids=[praised_cid],
    )
    store.record_feedback(
        user_id="u_tester2",
        tenant_id=tenant_id,
        rating=1,
        chunk_ids=[praised_cid],
    )

    # Retrieval run 1 has regular at rank 1, praised at rank 2
    dense_run = [
        {"chunk_id": regular_cid, "score": 0.88},
        {"chunk_id": praised_cid, "score": 0.85},
    ]

    fusion = ReciprocalRankFusion(rrf_k=60)
    # Fuse without boost
    unboosted = fusion.fuse([dense_run], top_k=2, tenant_id=tenant_id, apply_feedback_boost=False)
    assert unboosted[0]["chunk_id"] == regular_cid

    # Fuse with feedback boost enabled
    boosted = fusion.fuse([dense_run], top_k=2, tenant_id=tenant_id, apply_feedback_boost=True)
    # Praised chunk receives 1.3x boost factor and surpasses regular
    assert boosted[0]["chunk_id"] == praised_cid
    assert boosted[0]["feedback_boost"] > 1.0
