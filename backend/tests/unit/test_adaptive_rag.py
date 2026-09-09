"""Unit tests for Phase 15 Adaptive RAG Strategy and Query Intent Classification."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.llm.base import LLMResponse
from src.rag.adaptive.strategy import AdaptiveRAGStrategy
from src.rag.base import RAGRequest


@pytest.mark.asyncio
async def test_adaptive_rag_query_intent_classification_and_routing():
    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        return_value=LLMResponse(
            content="HYBRID",
            model_name="sarvam-105b-mock",
            prompt_tokens=20,
            completion_tokens=5,
            total_tokens=25,
        )
    )

    strategy = AdaptiveRAGStrategy(llm_provider=mock_llm)

    request = RAGRequest(
        query="What is Sarvam-105B model specification?",
        tenant_id="tenant_adaptive",
        rag_strategy="Adaptive",
        top_k=5,
    )

    response = await strategy.execute(request)

    assert "Adaptive (HYBRID)" in response.rag_strategy
    assert response.latency_ms > 0
