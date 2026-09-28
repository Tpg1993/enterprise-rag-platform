"""Unit tests for RAG Strategy Catalog and Version Manifest endpoints."""

import pytest
from src.api.routes.rag import get_rag_strategies, get_rag_versions
from src.api.schemas import RAGStrategiesResponse, RAGVersionResponse


@pytest.mark.asyncio
async def test_get_rag_strategies_catalog():
    """Verifies that strategy catalog returns all 15 production RAG strategies."""
    res = await get_rag_strategies()
    assert isinstance(res, RAGStrategiesResponse)
    assert res.total_strategies == 15
    assert len(res.strategies) == 15

    strategy_ids = [s.id for s in res.strategies]
    expected_ids = [
        "Basic", "Hybrid", "MMR", "Reranked", "Parent-Child",
        "Multi-Query", "HyDE", "Adaptive", "Corrective", "Self-RAG",
        "ReAct", "GraphRAG", "SQL-RAG", "Multimodal", "Hybrid-Graph-Agentic"
    ]
    for exp in expected_ids:
        assert exp in strategy_ids

    # Validate schema fields
    for s in res.strategies:
        assert s.name
        assert s.description
        assert s.framework in ("none", "langchain", "langgraph")
        assert s.category
        assert s.version == "1.0.0"
        assert len(s.features) >= 2


@pytest.mark.asyncio
async def test_get_rag_versions_manifest():
    """Verifies that version manifest returns valid application, model, and strategy versions."""
    res = await get_rag_versions()
    assert isinstance(res, RAGVersionResponse)
    assert res.application["name"] == "enterprise-rag-platform"
    assert res.application["version"] == "3.4.0"

    # Validate models metadata
    assert res.models["llm"]["model"] == "sarvam-105b"
    assert res.models["embedding"]["model"] == "bge-m3"
    assert res.models["reranker"]["model"] == "bge-reranker-large"

    # Validate strategy registry
    assert "basic" in res.rag
    assert "hybrid" in res.rag
    assert "hybrid_graph_agentic" in res.rag
    assert res.rag["hybrid_graph_agentic"]["framework"] == "langgraph"

    # Validate security guardrail versions
    assert "opa_guardrails" in res.security
    assert "presidio_pii" in res.security
