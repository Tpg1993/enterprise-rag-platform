"""Unit tests for Phase 14 Hypothetical Document Embeddings (HyDE) RAG Strategy."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.llm.base import LLMResponse
from src.rag.base import RAGRequest
from src.rag.hyde.strategy import HyDERAGStrategy


@pytest.mark.asyncio
async def test_hyde_strategy_execution():
    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [
        {
            "chunk_id": "doc_hyde_1_c0",
            "document_id": "doc_hyde_1",
            "content": "Hypothetical document embedding vector search snippet.",
            "score": 0.94,
            "payload": {
                "document_id": "doc_hyde_1",
                "chunk_id": "doc_hyde_1_c0",
                "content": "Hypothetical document embedding vector search snippet.",
                "metadata": {"filename": "hyde_spec.pdf"},
            },
        }
    ]

    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 1024

    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        side_effect=[
            LLMResponse(
                content="Hypothetical technical passage describing HyDE vector embeddings.",
                model_name="sarvam-105b-mock",
                prompt_tokens=30,
                completion_tokens=40,
                total_tokens=70,
            ),
            LLMResponse(
                content="HyDE RAG synthesized answer based on hypothetical vector search.",
                model_name="sarvam-105b-mock",
                prompt_tokens=140,
                completion_tokens=45,
                total_tokens=185,
            ),
        ]
    )

    strategy = HyDERAGStrategy(
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
    )

    request = RAGRequest(
        query="What is HyDE vector retrieval?",
        tenant_id="tenant_hyde",
        rag_strategy="HyDE",
        top_k=5,
    )

    response = await strategy.execute(request)

    assert response.rag_strategy == "HyDE"
    assert "synthesized answer" in response.answer
    assert response.latency_ms > 0
    assert len(response.citations) == 1
