"""Unit tests for Phase 19 GraphRAG (Neo4j Entity-Relationship Knowledge Graph RAG)."""

import pytest
from src.graph.extractor import EntityTriple, GraphEntityExtractor
from src.graph.neo4j_store import Neo4jGraphStore
from src.llm.mock import MockLLMProvider
from src.rag.base import RAGRequest
from src.rag.graph_rag.strategy import GraphRAGStrategy
from src.rag.router import get_rag_strategy


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture
def graph_store():
    store = Neo4jGraphStore()
    store.clear_tenant("test_tenant")
    return store


@pytest.mark.asyncio
async def test_entity_extractor_heuristic():
    extractor = GraphEntityExtractor(llm_provider=None)
    text = "FastAPI supports Asynchronous Endpoints. Neo4j connects to GraphRAG. Python uses LangChain."
    result = extractor.extract_sync(text)

    assert len(result.triples) >= 2
    subjects = [t.subject for t in result.triples]
    predicates = [t.predicate for t in result.triples]

    assert any("FastAPI" in s for s in subjects)
    assert any(p in ("SUPPORTS", "CONNECTS_TO", "USES") for p in predicates)
    assert len(result.entities) >= 2


@pytest.mark.asyncio
async def test_entity_extractor_json_llm(mock_llm):
    extractor = GraphEntityExtractor(llm_provider=mock_llm)
    text = "Sarvam AI develops Sarvam-105B LLM for enterprise applications."
    result = await extractor.aextract(text)

    assert isinstance(result.triples, list)
    assert isinstance(result.entities, list)


def test_neo4j_store_upsert_and_traversal(graph_store):
    tenant = "test_tenant"
    triples = [
        EntityTriple(subject="FastAPI", predicate="USES", object="Pydantic"),
        EntityTriple(subject="Pydantic", predicate="PROVIDES", object="DataValidation"),
        EntityTriple(subject="DataValidation", predicate="ENFORCES", object="SecurityBounds"),
    ]

    upsert_count = graph_store.upsert_triples(triples, tenant_id=tenant, doc_id="doc_1")
    assert upsert_count == 3

    # Test 1-hop traversal from FastAPI
    subgraph_1 = graph_store.search_subgraph(["FastAPI"], tenant_id=tenant, max_hops=1)
    assert len(subgraph_1) >= 1
    assert subgraph_1[0]["source"] == "FastAPI"
    assert subgraph_1[0]["target"] == "Pydantic"

    # Test 2-hop traversal reaching DataValidation
    subgraph_2 = graph_store.search_subgraph(["FastAPI"], tenant_id=tenant, max_hops=2)
    targets = [rel["target"] for rel in subgraph_2] + [rel["source"] for rel in subgraph_2]
    assert "DataValidation" in targets


def test_neo4j_store_tenant_isolation(graph_store):
    triples_a = [EntityTriple(subject="SecretProject", predicate="OWNED_BY", object="TenantAlpha")]
    triples_b = [EntityTriple(subject="PublicProject", predicate="OWNED_BY", object="TenantBeta")]

    graph_store.upsert_triples(triples_a, tenant_id="tenant_alpha")
    graph_store.upsert_triples(triples_b, tenant_id="tenant_beta")

    # Query as tenant_alpha
    results_a = graph_store.search_subgraph(["SecretProject"], tenant_id="tenant_alpha")
    assert len(results_a) == 1
    assert results_a[0]["target"] == "TenantAlpha"

    # Query as tenant_beta looking for SecretProject - must be isolated and return empty
    results_b = graph_store.search_subgraph(["SecretProject"], tenant_id="tenant_beta")
    assert len(results_b) == 0


@pytest.mark.asyncio
async def test_graph_rag_strategy_execution(mock_llm, graph_store):
    tenant = "test_tenant"
    triples = [
        EntityTriple(subject="LangGraph", predicate="ORCHESTRATES", object="MultiAgentWorkflow"),
        EntityTriple(subject="MultiAgentWorkflow", predicate="EXECUTES", object="ReActCycles"),
    ]
    graph_store.upsert_triples(triples, tenant_id=tenant)

    strategy = GraphRAGStrategy(
        graph_store=graph_store,
        llm_provider=mock_llm,
        embedding_provider_name="mock-fast",
    )

    request = RAGRequest(
        query="How does LangGraph orchestrate multi-agent workflows?",
        tenant_id=tenant,
        rag_strategy="GraphRAG",
        top_k=3,
    )

    response = await strategy.execute(request)

    assert response.rag_strategy == "GraphRAG"
    assert response.answer is not None
    assert len(response.answer) > 0
    assert response.latency_ms > 0
    assert response.tenant_id == tenant
    assert any(c.filename == "neo4j_knowledge_graph" for c in response.citations)


def test_graph_rag_router_resolution():
    strat = get_rag_strategy("GraphRAG")
    assert isinstance(strat, GraphRAGStrategy)

    strat2 = get_rag_strategy("GRAPH-RAG")
    assert isinstance(strat2, GraphRAGStrategy)
