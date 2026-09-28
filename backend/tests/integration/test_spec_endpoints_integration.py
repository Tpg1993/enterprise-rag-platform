"""Integration tests for Phase 27.2:

End-to-end verification of Reindex, Streaming, Traces, and Audit.
"""

import json

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_end_to_end_reindex_stream_trace_audit_pipeline(client):
    """End-to-end integration:

    1. Ingest a new document.
    2. Re-index document with new chunker.
    3. Stream chat query against the reindexed document.
    4. Verify trace span is retrievable via GET /api/v1/traces/{trace_id}.
    5. Verify audit events are properly recorded in GET /api/v1/audit.
    """
    tenant_id = "tenant_e2e_spec_integration"

    # Step 1: Ingest document
    file_bytes = b"Enterprise Graph RAG leverages Neo4j and vector search for multi-hop synthesis."
    upload_res = client.post(
        f"/api/v1/documents?tenant_id={tenant_id}&chunk_strategy=fixed&chunk_size=120&embedding_provider=bge-m3",
        files={"file": ("graph_rag_spec.txt", file_bytes, "text/plain")},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["document_id"]

    # Step 2: Reindex document
    reindex_res = client.post(
        f"/api/v1/documents/{doc_id}/reindex?tenant_id={tenant_id}&chunk_strategy=semantic&chunk_size=250&chunk_overlap=30&embedding_provider=bge-m3"
    )
    assert reindex_res.status_code == 200
    assert reindex_res.json()["status"] == "reindexed"
    assert reindex_res.json()["chunk_strategy"] == "semantic"

    # Step 3: Stream chat completion
    chat_payload = {
        "query": "How does Enterprise Graph RAG work?",
        "rag_strategy": "Hybrid",
        "tenant_id": tenant_id,
        "user_id": "usr_integration_spec",
    }
    stream_res = client.post("/api/v1/chat/stream", json=chat_payload)
    assert stream_res.status_code == 200
    lines = stream_res.text.strip().split("\n\n")

    done_event = None
    for line in lines:
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            if payload.get("type") == "done":
                done_event = payload

    assert done_event is not None
    assert done_event["done"] is True
    assert "answer" in done_event
    trace_id = done_event["trace_id"]
    assert trace_id != ""

    # Step 4: Verify single trace lookup
    trace_res = client.get(f"/api/v1/traces/{trace_id}")
    assert trace_res.status_code == 200
    trace_data = trace_res.json()
    assert trace_data["trace_id"] == trace_id
    assert trace_data["tenant_id"] == tenant_id

    # Step 5: Verify audit trail
    audit_res = client.get(f"/api/v1/audit?tenant_id={tenant_id}")
    assert audit_res.status_code == 200
    audit_events = audit_res.json()["events"]
    assert len(audit_events) >= 2
    actions = [e["action"] for e in audit_events]
    assert "INGEST" in actions
    assert "REINDEX" in actions
