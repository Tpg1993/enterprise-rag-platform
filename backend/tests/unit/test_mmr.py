"""Unit tests for Phase 5 Maximal Marginal Relevance (MMR) selector and MMRRAGStrategy."""

import pytest
from src.rag.base import RAGRequest, RAGResponse
from src.rag.mmr.strategy import MMRRAGStrategy
from src.retrieval.mmr import MaximalMarginalRelevance, cosine_similarity


def test_cosine_similarity_math():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert cosine_similarity(v1, v2) == pytest.approx(1.0)
    assert cosine_similarity(v1, v3) == pytest.approx(0.0)


def test_mmr_selector_diversity_reranking():
    query_vector = [1.0, 0.0, 0.0]

    # Candidate 1: Perfect match to query
    c1_vector = [1.0, 0.0, 0.0]
    # Candidate 2: High similarity duplicate of Candidate 1
    c2_vector = [0.99, 0.1, 0.0]
    # Candidate 3: Diverse vector with complementary angle
    c3_vector = [0.707, 0.707, 0.0]

    candidate_hits = [
        {"chunk_id": "c1", "content": "Query exact topic."},
        {"chunk_id": "c2", "content": "Query duplicate topic."},
        {"chunk_id": "c3", "content": "Diverse complementary topic."},
    ]
    candidate_vectors = [c1_vector, c2_vector, c3_vector]

    selector = MaximalMarginalRelevance(lambda_mult=0.3)
    selected = selector.select(
        query_vector=query_vector,
        candidate_hits=candidate_hits,
        candidate_vectors=candidate_vectors,
        final_k=2,
    )

    assert len(selected) == 2
    # c1 is selected first for highest query similarity
    assert selected[0]["chunk_id"] == "c1"
    # c3 is selected second (over near-duplicate c2) due to diversity penalty
    assert selected[1]["chunk_id"] == "c3"


@pytest.mark.asyncio
async def test_mmr_rag_strategy_execution():
    strategy = MMRRAGStrategy()
    request = RAGRequest(
        query="Explain Sarvam-105B Indic model architecture.",
        tenant_id="test_tenant_mmr",
        rag_strategy="MMR",
    )

    response = await strategy.execute(request)

    assert isinstance(response, RAGResponse)
    assert response.query == "Explain Sarvam-105B Indic model architecture."
    assert response.rag_strategy == "MMR"
    assert response.tenant_id == "test_tenant_mmr"
    assert response.latency_ms > 0
    assert response.trace_id.startswith("trace_mmr_")
