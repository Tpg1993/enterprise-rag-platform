"""Unit tests for Phase 11 Multi-Query Expansion RAG strategy and RRF fusion."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.llm.base import LLMResponse
from src.rag.base import RAGRequest
from src.rag.multi_query.strategy import MultiQueryRAGStrategy, reciprocal_rank_fusion_multi_query


def test_reciprocal_rank_fusion_multi_query_math():
    """Verifies reciprocal rank fusion combines and scores hits across 3 query streams."""
    stream_1 = [
        {"chunk_id": "c1", "content": "Chunk 1 content", "score": 0.90},
        {"chunk_id": "c2", "content": "Chunk 2 content", "score": 0.80},
    ]
    stream_2 = [
        {"chunk_id": "c2", "content": "Chunk 2 content", "score": 0.85},
        {"chunk_id": "c3", "content": "Chunk 3 content", "score": 0.75},
    ]

    fused = reciprocal_rank_fusion_multi_query([stream_1, stream_2], rrf_k=60)
    assert len(fused) == 3
    # Chunk c2 appeared in both streams (rank 2 in stream 1, rank 1 in stream 2) -> highest RRF score
    assert fused[0]["chunk_id"] == "c2"


@pytest.mark.asyncio
async def test_multi_query_strategy_execution():
    """Verifies MultiQueryRAGStrategy generates query variations, executes parallel retrieval, and returns answer."""
    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [
        {
            "chunk_id": "doc_mq_1_c0",
            "document_id": "doc_mq_1",
            "content": "Multi-query expansion retrieval snippet.",
            "score": 0.92,
            "payload": {
                "document_id": "doc_mq_1",
                "chunk_id": "doc_mq_1_c0",
                "content": "Multi-query expansion retrieval snippet.",
                "metadata": {"filename": "multi_query_doc.pdf"},
            },
        }
    ]

    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 1024

    mock_llm = MagicMock()
    # LLM generate call 1: query variations generation, call 2: final RAG completion
    mock_llm.agenerate = AsyncMock(
        side_effect=[
            LLMResponse(
                content="Query variation 1\nQuery variation 2\nQuery variation 3",
                model_name="sarvam-105b-mock",
                prompt_tokens=40,
                completion_tokens=20,
                total_tokens=60,
            ),
            LLMResponse(
                content="Multi-Query RAG synthesized answer across expanded query perspectives.",
                model_name="sarvam-105b-mock",
                prompt_tokens=150,
                completion_tokens=50,
                total_tokens=200,
            ),
        ]
    )

    strategy = MultiQueryRAGStrategy(
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
    )

    request = RAGRequest(
        query="What are the platform deployment steps?",
        tenant_id="tenant_mq",
        rag_strategy="Multi-Query",
        top_k=5,
    )

    response = await strategy.execute(request)

    assert response.rag_strategy == "Multi-Query"
    assert "synthesized answer" in response.answer
    assert response.prompt_tokens == 150
    assert len(response.citations) == 1
