"""Integration test for Phase 19 GraphRAG end-to-end multi-hop graph retrieval and API chat."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app
from src.graph.extractor import EntityTriple
from src.graph.neo4j_store import get_graph_store


@pytest.mark.asyncio
async def test_graph_rag_api_integration():
    """Validates /api/v1/chat endpoint with rag_strategy='GraphRAG'."""
    graph_store = get_graph_store()
    tenant = "integration_graph_tenant"
    graph_store.clear_tenant(tenant)

    # Seed knowledge graph with entity-relation triples
    triples = [
        EntityTriple(subject="SarvamAI", predicate="DEVELOPS", object="Sarvam105B"),
        EntityTriple(subject="Sarvam105B", predicate="SUPPORTS", object="IndicLanguages"),
        EntityTriple(subject="IndicLanguages", predicate="INCLUDES", object="Hindi"),
        EntityTriple(subject="IndicLanguages", predicate="INCLUDES", object="Tamil"),
        EntityTriple(subject="Sarvam105B", predicate="INTEGRATES_WITH", object="Neo4jGraphRAG"),
    ]
    graph_store.upsert_triples(triples, tenant_id=tenant, doc_id="doc_graph_001")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Query relationship-dense prompt via Chat API
        response = await ac.post(
            "/api/v1/chat",
            json={
                "query": "Which Indic languages does Sarvam-105B support through its architecture?",
                "rag_strategy": "GraphRAG",
                "tenant_id": tenant,
                "max_context_tokens": 2048,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert len(data["answer"]) > 0
        assert data["rag_strategy"] == "GraphRAG"
        assert data["latency_ms"] >= 0
        assert "token_usage" in data

        # Validate that graph knowledge facts were retrieved and cited
        citations = data.get("citations", [])
        assert any(
            c.get("source") == "neo4j_knowledge_graph" or c.get("filename") == "neo4j_knowledge_graph"
            for c in citations
        )
