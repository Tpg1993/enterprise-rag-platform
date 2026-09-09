"""Unit tests for Phase 18 ReAct Agentic RAG Strategy and Tool Execution Loop."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.llm.base import LLMResponse
from src.rag.base import RAGRequest
from src.rag.react.strategy import ReActRAGStrategy


@pytest.mark.asyncio
async def test_react_rag_strategy_execution():
    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [
        {
            "chunk_id": "c_react_1",
            "content": "ReAct agentic tool observation snippet.",
            "score": 0.96,
            "payload": {"filename": "react_agent.pdf"},
        }
    ]

    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 1024

    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        return_value=LLMResponse(
            content="ReAct Agent synthesized response after tool execution.",
            model_name="sarvam-105b-mock",
            prompt_tokens=45,
            completion_tokens=25,
            total_tokens=70,
        )
    )

    strategy = ReActRAGStrategy(
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
    )

    request = RAGRequest(query="How does ReAct agent work?", tenant_id="tenant_react", rag_strategy="ReAct")
    response = await strategy.execute(request)

    assert response.rag_strategy == "ReAct"
    assert response.latency_ms > 0
    assert len(response.citations) == 1
