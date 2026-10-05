"""Integration tests for Autonomous Knowledge Graph Ingestion and Exploration APIs."""

import io

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_knowledge_graph_endpoints_lifecycle():
    """Validates document auto-extraction, graph stats, entities, subgraph, and clear."""
    tenant = "test_graph_tenant"

    # 1. Clear any pre-existing graph for tenant
    clear_res = client.delete(f"/api/v1/graph?tenant_id={tenant}")
    assert clear_res.status_code == 200
    assert clear_res.json()["status"] == "cleared"

    # Initial stats should be 0
    stats_res = client.get(f"/api/v1/graph/stats?tenant_id={tenant}")
    assert stats_res.status_code == 200
    assert stats_res.json()["total_nodes"] == 0
    assert stats_res.json()["total_relationships"] == 0

    # 2. Upload document with enable_graph_extraction=True
    doc_content = (
        "Enterprise Architecture Specification:\n"
        "Sarvam-105B is a neural network model that connects to Qdrant Vector DB. "
        "The architecture achieves 99.9% uptime SLA and enforces RBAC Security Policies. "
        "FastAPI coordinates the retrieval pipeline."
    )
    file_obj = io.BytesIO(doc_content.encode("utf-8"))

    upload_res = client.post(
        "/api/v1/documents",
        data={
            "tenant_id": tenant,
            "chunk_strategy": "recursive",
            "chunk_size": 256,
            "chunk_overlap": 20,
            "embedding_provider": "mock-fast",
            "enable_graph_extraction": "true",
        },
        files={"file": ("architecture_spec.txt", file_obj, "text/plain")},
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["status"] == "ingested"
    assert upload_data["graph_nodes_count"] >= 2
    assert upload_data["graph_relationships_count"] >= 1

    # 3. GET /api/v1/graph/stats
    stats_res2 = client.get(f"/api/v1/graph/stats?tenant_id={tenant}")
    assert stats_res2.status_code == 200
    stats2 = stats_res2.json()
    assert stats2["tenant_id"] == tenant
    assert stats2["total_nodes"] >= 2
    assert stats2["total_relationships"] >= 1

    # 4. GET /api/v1/graph/entities
    ent_res = client.get(f"/api/v1/graph/entities?tenant_id={tenant}&limit=50")
    assert ent_res.status_code == 200
    ent_data = ent_res.json()
    assert ent_data["total_entities"] >= 2
    assert any("degree" in e for e in ent_data["entities"])

    # 5. GET /api/v1/graph/subgraph
    subgraph_res = client.get(f"/api/v1/graph/subgraph?tenant_id={tenant}&depth=2&limit=30")
    assert subgraph_res.status_code == 200
    sg_data = subgraph_res.json()
    assert sg_data["total_nodes"] >= 2
    assert sg_data["total_links"] >= 1
    assert "nodes" in sg_data
    assert "links" in sg_data

    # 6. DELETE /api/v1/graph
    cleanup_res = client.delete(f"/api/v1/graph?tenant_id={tenant}")
    assert cleanup_res.status_code == 200
    stats_final = client.get(f"/api/v1/graph/stats?tenant_id={tenant}").json()
    assert stats_final["total_nodes"] == 0
    assert stats_final["total_relationships"] == 0
