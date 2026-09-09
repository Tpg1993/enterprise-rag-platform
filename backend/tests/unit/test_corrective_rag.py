"""Unit tests for Phase 16 Corrective RAG (CRAG) Strategy and Web Search Fallback."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.llm.base import LLMResponse
from src.rag.base import RAGRequest
from src.rag.corrective.strategy import CorrectiveRAGStrategy


@pytest.mark.asyncio
async def test_corrective_rag_high_confidence_execution():
    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [
        {
            "chunk_id": "c_kb_1",
            "content": "High relevance knowledge base content snippet.",
            "score": 0.95,
            "payload": {"filename": "kb_doc.pdf"},
        }
    ]

    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 1024

    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        return_value=LLMResponse(
            content="Grounded CRAG response from high confidence KB hit.",
            model_name="sarvam-105b-mock",
            prompt_tokens=40,
            completion_tokens=20,
            total_tokens=60,
        )
    )

    strategy = CorrectiveRAGStrategy(
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
        relevance_threshold=0.5,
    )

    request = RAGRequest(query="What is CRAG?", tenant_id="tenant_crag", rag_strategy="Corrective")
    response = await strategy.execute(request)

    assert "Corrective (KB Grounded)" in response.rag_strategy
    assert response.latency_ms > 0


@pytest.mark.asyncio
async def test_corrective_rag_web_search_fallback():
    mock_vector_store = MagicMock()
    # Return low relevance score hit (< 0.5) to trigger web search fallback
    mock_vector_store.search.return_value = [
        {
            "chunk_id": "c_kb_low",
            "content": "Low relevance snippet.",
            "score": 0.20,
            "payload": {"filename": "low_doc.pdf"},
        }
    ]

    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 1024

    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        return_value=LLMResponse(
            content="Grounded CRAG response using web search fallback context.",
            model_name="sarvam-105b-mock",
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75,
        )
    )

    strategy = CorrectiveRAGStrategy(
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
        relevance_threshold=0.5,
    )

    request = RAGRequest(query="What is real-time stock price?", tenant_id="tenant_crag", rag_strategy="Corrective")
    response = await strategy.execute(request)

    assert "Corrective (CRAG + Web Search)" in response.rag_strategy
    assert len(response.citations) >= 1
