"""Unit tests for Unified Hybrid-Graph-Agentic RAG Strategy."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.rag import RAGRequest, get_rag_strategy
from src.rag.hybrid_graph_agentic.strategy import HybridGraphAgenticRAGStrategy


@pytest.fixture
def mock_dependencies():
    vector_store = MagicMock()
    vector_store.search.return_value = [
        {
            "content": "Sarvam AI builds sovereign LLMs tailored for Indian languages.",
            "payload": {
                "filename": "sarvam_overview.pdf",
                "document_id": "doc_1",
                "chunk_id": "chunk_1",
                "page_number": 1,
            },
            "score": 0.88,
        }
    ]

    bm25_retriever = MagicMock()
    bm25_retriever.search.return_value = [
        {
            "content": "Sarvam AI platform provides state of the art language architectures.",
            "payload": {
                "filename": "sarvam_specs.txt",
                "document_id": "doc_2",
                "chunk_id": "chunk_2",
                "page_number": 1,
            },
            "score": 0.85,
        }
    ]

    graph_store = MagicMock()
    graph_store.search_subgraph.return_value = [
        {
            "source": "Sarvam AI",
            "predicate": "DEVELOPED_MODEL",
            "target": "sarvam-105b",
        },
        {
            "source": "sarvam-105b",
            "predicate": "SUPPORTS_LANGUAGE",
            "target": "Hindi",
        },
    ]

    entity_extractor = MagicMock()
    extraction = MagicMock()
    extraction.entities = ["Sarvam AI", "sarvam-105b"]
    entity_extractor.aextract = AsyncMock(return_value=extraction)

    reranker = MagicMock()
    reranker.rerank.side_effect = lambda query, candidate_chunks, top_k: candidate_chunks[:top_k]

    llm_provider = MagicMock()
    llm_res = MagicMock()
    llm_res.content = (
        "Sarvam AI has developed sarvam-105b with native Hindi [neo4j_knowledge_graph]."
    )
    llm_res.model_name = "sarvam-105b"
    llm_res.prompt_tokens = 120
    llm_res.completion_tokens = 45
    llm_provider.agenerate = AsyncMock(return_value=llm_res)

    return {
        "vector_store": vector_store,
        "bm25_retriever": bm25_retriever,
        "graph_store": graph_store,
        "entity_extractor": entity_extractor,
        "reranker": reranker,
        "llm_provider": llm_provider,
    }


@pytest.mark.asyncio
async def test_hybrid_search_tool(mock_dependencies):
    """Verifies that _tool_hybrid_search combines dense and lexical hits via RRF."""
    strategy = HybridGraphAgenticRAGStrategy(
        vector_store=mock_dependencies["vector_store"],
        bm25_retriever=mock_dependencies["bm25_retriever"],
        graph_store=mock_dependencies["graph_store"],
        entity_extractor=mock_dependencies["entity_extractor"],
        reranker=mock_dependencies["reranker"],
        llm_provider=mock_dependencies["llm_provider"],
    )
    hits = await strategy._tool_hybrid_search(
        query="What is Sarvam AI?",
        tenant_id="default_tenant",
        top_k=2,
    )
    assert len(hits) >= 1
    assert "content" in hits[0]
    assert hits[0]["score"] > 0


@pytest.mark.asyncio
async def test_graph_traversal_tool(mock_dependencies):
    """Verifies that _tool_graph_traversal extracts entities and formats relational facts."""
    strategy = HybridGraphAgenticRAGStrategy(
        vector_store=mock_dependencies["vector_store"],
        bm25_retriever=mock_dependencies["bm25_retriever"],
        graph_store=mock_dependencies["graph_store"],
        entity_extractor=mock_dependencies["entity_extractor"],
        reranker=mock_dependencies["reranker"],
        llm_provider=mock_dependencies["llm_provider"],
    )
    graph_chunks = await strategy._tool_graph_traversal(
        query="Tell me about Sarvam AI models",
        tenant_id="default_tenant",
    )
    assert len(graph_chunks) == 1
    assert "Relational Entity Facts" in graph_chunks[0]["content"]
    assert "DEVELOPED_MODEL" in graph_chunks[0]["content"]


@pytest.mark.asyncio
async def test_hybrid_graph_agentic_execute(mock_dependencies):
    """Verifies full execution pipeline of HybridGraphAgenticRAGStrategy."""
    strategy = HybridGraphAgenticRAGStrategy(
        vector_store=mock_dependencies["vector_store"],
        bm25_retriever=mock_dependencies["bm25_retriever"],
        graph_store=mock_dependencies["graph_store"],
        entity_extractor=mock_dependencies["entity_extractor"],
        reranker=mock_dependencies["reranker"],
        llm_provider=mock_dependencies["llm_provider"],
    )
    req = RAGRequest(
        query="Explain Sarvam AI and sarvam-105b language support",
        tenant_id="default_tenant",
        rag_strategy="Hybrid-Graph-Agentic",
    )
    res = await strategy.execute(req)

    assert res.rag_strategy == "Hybrid-Graph-Agentic"
    assert res.model == "sarvam-105b"
    assert res.tenant_id == "default_tenant"
    assert "sarvam-105b" in res.answer
    assert res.latency_ms > 0
    assert len(res.citations) >= 1


def test_router_hybrid_graph_agentic():
    """Verifies that RAG router correctly instantiates HybridGraphAgenticRAGStrategy."""
    strat = get_rag_strategy("Hybrid-Graph-Agentic")
    assert isinstance(strat, HybridGraphAgenticRAGStrategy)
