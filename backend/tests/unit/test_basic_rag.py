"""Unit tests for Phase 3 Basic RAG Strategy, ContextBuilder, PromptBuilder, and RAGRouter."""

import pytest

from src.context.builder import ContextBuilder
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, Citation, RAGRequest, RAGResponse
from src.rag.basic.strategy import BasicRAGStrategy
from src.rag.router import get_rag_strategy


def test_context_builder_formatting():
    builder = ContextBuilder(max_context_tokens=500)
    hits = [
        {
            "chunk_id": "c1",
            "document_id": "doc1",
            "content": "Sarvam-105B is a 105 billion parameter multilingual LLM.",
            "score": 0.92,
            "payload": {"filename": "sarvam_spec.pdf", "page_number": 1},
        },
        {
            "chunk_id": "c2",
            "document_id": "doc2",
            "content": "Qdrant is an open-source vector database built in Rust.",
            "score": 0.88,
            "payload": {"filename": "qdrant_docs.pdf", "page_number": 3},
        },
    ]

    context_str, citations = builder.build_context(hits)

    assert "Sarvam-105B is a 105 billion parameter" in context_str
    assert "Qdrant is an open-source vector database" in context_str
    assert len(citations) == 2
    assert citations[0].filename == "sarvam_spec.pdf"
    assert citations[0].page_number == 1
    assert citations[1].relevance_score == 0.88


def test_prompt_builder_grounding():
    builder = PromptBuilder()
    prompts = builder.build_prompt(
        query="What is Sarvam-105B?",
        context="Sarvam-105B is an enterprise multilingual LLM for Indic languages.",
    )

    assert "system" in prompts
    assert "user" in prompts
    assert "Sarvam-105B is an enterprise multilingual LLM" in prompts["user"]
    assert "What is Sarvam-105B?" in prompts["user"]
    assert "strictly based on the provided context" in prompts["system"]


def test_rag_router_factory():
    strategy = get_rag_strategy("Basic")
    assert isinstance(strategy, BasicRAGStrategy)

    strategy_auto = get_rag_strategy("AUTO")
    assert isinstance(strategy_auto, BaseRAGStrategy)


@pytest.mark.asyncio
async def test_basic_rag_strategy_execution():
    strategy = BasicRAGStrategy()
    request = RAGRequest(
        query="What is Sarvam-105B architecture?",
        tenant_id="test_tenant",
        rag_strategy="Basic",
    )

    response = await strategy.execute(request)

    assert isinstance(response, RAGResponse)
    assert response.query == "What is Sarvam-105B architecture?"
    assert response.rag_strategy == "Basic"
    assert response.tenant_id == "test_tenant"
    assert response.latency_ms > 0
    assert response.trace_id.startswith("trace_")
