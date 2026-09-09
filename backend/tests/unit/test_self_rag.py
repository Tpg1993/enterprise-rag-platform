"""Unit tests for Phase 17 Self-RAG Strategy and Self-Reflection Hallucination Grading."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.llm.base import LLMResponse
from src.rag.base import RAGRequest
from src.rag.self_rag.strategy import SelfRAGStrategy


@pytest.mark.asyncio
async def test_self_rag_grounded_execution():
    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [
        {
            "chunk_id": "c_self_1",
            "content": "Sarvam-105B is an enterprise multilingual AI model for Indic languages.",
            "score": 0.95,
            "payload": {"filename": "sarvam_spec.pdf"},
        }
    ]

    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 1024

    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        return_value=LLMResponse(
            content="Sarvam-105B is an enterprise multilingual AI model for Indic languages.",
            model_name="sarvam-105b-mock",
            prompt_tokens=40,
            completion_tokens=20,
            total_tokens=60,
        )
    )

    strategy = SelfRAGStrategy(
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
        min_faithfulness_score=0.5,
    )

    request = RAGRequest(query="What is Sarvam-105B?", tenant_id="tenant_self", rag_strategy="Self-RAG")
    response = await strategy.execute(request)

    assert "Self-RAG (Grounded)" in response.rag_strategy
    assert response.latency_ms > 0
    assert len(response.citations) == 1
