"""Unit tests for Phase 6 Cross-Encoder Reranker and RerankedRAGStrategy."""

import pytest
from src.rag.base import RAGRequest, RAGResponse
from src.rag.reranked.strategy import RerankedRAGStrategy
from src.reranking.cross_encoder import CrossEncoderReranker


def test_cross_encoder_reranker_scoring():
    reranker = CrossEncoderReranker(use_model=False)
    query = "What is Sarvam-105B Indic model?"

    hits = [
        {
            "chunk_id": "c1",
            "content": "Unrelated vector database documentation for Qdrant storage.",
            "score": 0.90,
        },
        {
            "chunk_id": "c2",
            "content": "Sarvam-105B Indic multilingual model architecture parameters.",
            "score": 0.75,
        },
    ]

    reranked = reranker.rerank(query, hits, top_n=2)

    assert len(reranked) == 2
    # c2 has high query term cross-overlap and should be re-ranked first over c1
    assert reranked[0]["chunk_id"] == "c2"
    assert "rerank_score" in reranked[0]
    assert reranked[0]["rerank_score"] > reranked[1]["rerank_score"]


@pytest.mark.asyncio
async def test_reranked_rag_strategy_execution():
    strategy = RerankedRAGStrategy()
    request = RAGRequest(
        query="Explain Sarvam-105B cross-encoder reranking.",
        tenant_id="test_tenant_reranked",
        rag_strategy="Reranked",
    )

    response = await strategy.execute(request)

    assert isinstance(response, RAGResponse)
    assert response.query == "Explain Sarvam-105B cross-encoder reranking."
    assert response.rag_strategy == "Reranked"
    assert response.tenant_id == "test_tenant_reranked"
    assert response.latency_ms > 0
    assert response.trace_id.startswith("trace_rerank_")
