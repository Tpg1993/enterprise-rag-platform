"""Unit tests for AgenticWebRAGStrategy (Strategy 17)."""

import pytest
from src.rag.base import RAGRequest
from src.rag.web_agentic.strategy import AgenticWebRAGStrategy
from src.retrieval.web_search import MockSearchProvider


@pytest.mark.asyncio
async def test_agentic_web_rag_trigger_temporal():
    """Verifies that temporal keywords trigger external web search."""
    mock_search = MockSearchProvider()
    strategy = AgenticWebRAGStrategy(search_provider=mock_search)

    req = RAGRequest(
        query="What is the latest stock market trend today?",
        tenant_id="test_tenant",
        rag_strategy="Agentic-Web-RAG",
    )
    res = await strategy.execute(req)

    assert res.rag_strategy == "Agentic-Web-RAG"
    assert res.metadata["web_search_triggered"] is True
    assert "temporal_keywords_detected" in res.metadata["trigger_reason"]
    assert res.metadata["web_results_count"] > 0
    assert any(c.is_web for c in res.citations)
    web_cit = next(c for c in res.citations if c.is_web)
    assert web_cit.url
    assert web_cit.domain


@pytest.mark.asyncio
async def test_agentic_web_rag_force_flag():
    """Verifies that force_web_search flag unconditionally invokes web search."""
    mock_search = MockSearchProvider()
    strategy = AgenticWebRAGStrategy(search_provider=mock_search)

    req = RAGRequest(
        query="Describe internal enterprise architecture",
        tenant_id="test_tenant",
        rag_strategy="Agentic-Web-RAG",
        metadata={"force_web_search": True},
    )
    res = await strategy.execute(req)

    assert res.metadata["web_search_triggered"] is True
    assert res.metadata["trigger_reason"] == "force_web_search_flag"
    assert len(res.citations) > 0


@pytest.mark.asyncio
async def test_agentic_web_rag_citations_structure():
    """Verifies that both internal and web citations are properly structured."""
    mock_search = MockSearchProvider()
    strategy = AgenticWebRAGStrategy(search_provider=mock_search)

    req = RAGRequest(
        query="latest NIST compliance regulations 2026",
        tenant_id="test_tenant",
        rag_strategy="Agentic-Web-RAG",
    )
    res = await strategy.execute(req)

    web_citations = [c for c in res.citations if c.is_web]
    assert len(web_citations) > 0
    for cit in web_citations:
        assert cit.is_web is True
        assert cit.url.startswith("http")
        assert cit.domain != ""
        assert cit.content_snippet != ""
        assert cit.relevance_score > 0.0
