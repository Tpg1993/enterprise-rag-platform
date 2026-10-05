"""Unit tests for Phase 42: Autonomous Knowledge Graph Auto-Construction on Ingestion."""

import pytest
from src.graph.extractor import EntityTriple, GraphEntityExtractor, classify_entity_type
from src.graph.neo4j_store import Neo4jGraphStore


@pytest.fixture
def clean_graph_store():
    store = Neo4jGraphStore()
    store.clear_tenant("test_tenant_p42")
    yield store
    store.clear_tenant("test_tenant_p42")


def test_classify_entity_type():
    """Validates 6-category entity classification heuristics."""
    assert classify_entity_type("Qdrant Vector DB") == "TECH"
    assert classify_entity_type("FastAPI Microservice") == "TECH"
    assert classify_entity_type("Sarvam AI Corporation") == "ORG"
    assert classify_entity_type("Google DeepMind") == "ORG"
    assert classify_entity_type("P99 Latency SLA") == "METRIC"
    assert classify_entity_type("Context Recall 95%") == "METRIC"
    assert classify_entity_type("RBAC Security Policy") == "POLICY"
    assert classify_entity_type("ISO-27001 Compliance") == "POLICY"
    assert classify_entity_type("Dr. Alice Smith") == "PERSON"
    assert classify_entity_type("Chief Architect Bob") == "PERSON"
    assert classify_entity_type("Semantic Entropy") == "CONCEPT"


def test_heuristic_relation_extraction():
    """Validates heuristic pattern extraction when LLM returns no triples."""
    extractor = GraphEntityExtractor(llm_provider=None)
    text = (
        "FastAPI connects to Qdrant for vector storage. "
        "The architecture achieves 99.9% uptime. "
        "RBAC Engine enforces Zero Trust compliance."
    )
    triples = extractor._heuristic_extract(text)
    assert len(triples) >= 2
    predicates = [t.predicate for t in triples]
    assert any(p in ("CONNECTS_TO", "ACHIEVES", "ENFORCES") for p in predicates)


def test_graph_store_upsert_and_stats(clean_graph_store: Neo4jGraphStore):
    """Validates triple upserting, density calculation, and top connected nodes."""
    triples = [
        EntityTriple(
            subject="FastAPI",
            predicate="CONNECTS_TO",
            object="Qdrant",
            subject_type="TECH",
            object_type="TECH",
        ),
        EntityTriple(
            subject="FastAPI",
            predicate="ENFORCES",
            object="RBAC",
            subject_type="TECH",
            object_type="POLICY",
        ),
        EntityTriple(
            subject="Qdrant",
            predicate="ACHIEVES",
            object="Low Latency",
            subject_type="TECH",
            object_type="METRIC",
        ),
    ]

    clean_graph_store.upsert_triples(
        triples, tenant_id="test_tenant_p42", doc_id="doc_1", chunk_id="chk_1"
    )

    stats = clean_graph_store.get_graph_stats("test_tenant_p42")
    assert stats["tenant_id"] == "test_tenant_p42"
    assert stats["total_nodes"] >= 4
    assert stats["total_relationships"] == 3
    assert stats["density"] > 0.0
    assert "TECH" in stats["type_counts"]

    # Top connected should include FastAPI or Qdrant
    top_names = [n["name"] for n in stats["top_connected"]]
    assert "FastAPI" in top_names or "Qdrant" in top_names


def test_graph_store_entities_filtering(clean_graph_store: Neo4jGraphStore):
    """Validates entity listing and category filtering."""
    triples = [
        EntityTriple(
            subject="Sarvam AI",
            predicate="DEPLOYS",
            object="Sarvam-105B",
            subject_type="ORG",
            object_type="TECH",
        ),
        EntityTriple(
            subject="Sarvam AI",
            predicate="ENFORCES",
            object="GDPR Compliance",
            subject_type="ORG",
            object_type="POLICY",
        ),
    ]
    clean_graph_store.upsert_triples(triples, tenant_id="test_tenant_p42")

    all_entities = clean_graph_store.get_entities("test_tenant_p42")
    assert len(all_entities) >= 3

    policy_entities = clean_graph_store.get_entities("test_tenant_p42", entity_type="POLICY")
    assert len(policy_entities) >= 1
    assert any("Compliance" in e["name"] for e in policy_entities)


def test_graph_store_subgraph_traversal(clean_graph_store: Neo4jGraphStore):
    """Validates multi-hop neighborhood extraction for graph visualization."""
    triples = [
        EntityTriple(subject="A", predicate="LINKS", object="B"),
        EntityTriple(subject="B", predicate="LINKS", object="C"),
        EntityTriple(subject="C", predicate="LINKS", object="D"),
    ]
    clean_graph_store.upsert_triples(triples, tenant_id="test_tenant_p42")

    subgraph = clean_graph_store.get_subgraph(
        entity="A", tenant_id="test_tenant_p42", depth=2, limit=10
    )
    assert subgraph["seed_entity"] == "A"
    node_ids = [n["id"] for n in subgraph["nodes"]]
    assert "A" in node_ids
    assert "B" in node_ids
    assert len(subgraph["links"]) >= 2


def test_graph_store_clear_tenant(clean_graph_store: Neo4jGraphStore):
    """Validates tenant graph data isolation and complete clearing."""
    triples = [EntityTriple(subject="X", predicate="CONNECTED_TO", object="Y")]
    clean_graph_store.upsert_triples(triples, tenant_id="test_tenant_p42")
    assert clean_graph_store.get_graph_stats("test_tenant_p42")["total_nodes"] >= 2

    clean_graph_store.clear_tenant("test_tenant_p42")
    stats = clean_graph_store.get_graph_stats("test_tenant_p42")
    assert stats["total_nodes"] == 0
    assert stats["total_relationships"] == 0
