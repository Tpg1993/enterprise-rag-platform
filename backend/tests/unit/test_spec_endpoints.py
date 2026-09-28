"""Unit tests for Phase 27.2 specifications:

Trace Lookup, Audit Trail, Document Re-index, and SSE Chat Stream.
"""

import json

import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.observability.tracing import Tracer
from src.storage.history import get_history_store


@pytest.fixture
def client():
    return TestClient(app)


def test_get_single_trace_by_id(client):
    """Test GET /api/v1/traces/{trace_id} returns the specific span or 404."""
    trace_id = "test-trace-lookup-12345"
    Tracer.record_span(
        trace_id=trace_id,
        name="Test_Trace_Span",
        rag_strategy="Basic",
        latency_ms=45.2,
        tenant_id="tenant_trace_test",
        user_id="usr_trace_test",
        status="SUCCESS",
        metadata={"query": "test query", "model": "sarvam-105b"},
    )

    response = client.get(f"/api/v1/traces/{trace_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["trace_id"] == trace_id
    assert data["name"] == "Test_Trace_Span"
    assert data["rag_strategy"] == "Basic"
    assert data["latency_ms"] == 45.2
    assert data["tenant_id"] == "tenant_trace_test"

    # Non-existent trace
    resp_404 = client.get("/api/v1/traces/non-existent-trace-id-xyz")
    assert resp_404.status_code == 404
    assert "not found" in resp_404.json()["detail"].lower()


def test_audit_trail_endpoint(client):
    """Test GET /api/v1/audit retrieves security and pipeline events."""
    store = get_history_store()
    tenant = "audit_tenant_xyz"
    store.record_audit_event(
        event_type="ACCESS_TEST",
        user_id="analyst_test",
        tenant_id=tenant,
        action="TEST_ACTION",
        resource="test_resource",
        status="SUCCESS",
        details={"info": "sample audit details"},
    )

    response = client.get(f"/api/v1/audit?tenant_id={tenant}")
    assert response.status_code == 200
    data = response.json()
    assert "total_events" in data
    assert data["total_events"] >= 1
    events = data["events"]
    matching = [e for e in events if e["tenant_id"] == tenant and e["action"] == "TEST_ACTION"]
    assert len(matching) >= 1
    assert matching[0]["resource"] == "test_resource"
    assert matching[0]["details"]["info"] == "sample audit details"


def test_document_reindex_flow(client):
    """Test POST /api/v1/documents/{document_id}/reindex re-chunks and re-embeds document."""
    # 1. Ingest a document
    tenant = "tenant_reindex_test"
    file_content = (
        b"Enterprise AI architecture with multi-layer RAG strategies and zero-trust policies."
    )
    files = {"file": ("reindex_doc.txt", file_content, "text/plain")}
    upload_res = client.post(
        f"/api/v1/documents?tenant_id={tenant}&chunk_strategy=fixed&chunk_size=100&embedding_provider=bge-m3",
        files=files,
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["document_id"]
    initial_version = upload_res.json()["version"]

    # 2. Re-index document with recursive chunker and new chunk size
    reindex_res = client.post(
        f"/api/v1/documents/{doc_id}/reindex?tenant_id={tenant}&chunk_strategy=recursive&chunk_size=200&chunk_overlap=20&embedding_provider=bge-m3"
    )
    assert reindex_res.status_code == 200
    reindex_data = reindex_res.json()
    assert reindex_data["document_id"] == doc_id
    assert reindex_data["status"] == "reindexed"
    assert reindex_data["chunk_strategy"] == "recursive"
    assert reindex_data["version"] >= initial_version

    # 3. Test 404 on missing document
    missing_res = client.post("/api/v1/documents/non_existent_doc_id/reindex")
    assert missing_res.status_code == 404


def test_chat_stream_sse_endpoint(client):
    """Test POST /api/v1/chat/stream emits Server-Sent Events with ITL tracking."""
    payload = {
        "query": "What is the architecture of this RAG platform?",
        "rag_strategy": "Basic",
        "tenant_id": "tenant_stream_test",
        "user_id": "usr_stream_test",
    }
    response = client.post("/api/v1/chat/stream", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")

    raw_lines = response.text.strip().split("\n\n")
    assert len(raw_lines) >= 2

    tokens_received = []
    done_event = None

    for line in raw_lines:
        if line.startswith("data: "):
            event_obj = json.loads(line[6:])
            if event_obj.get("type") == "token":
                tokens_received.append(event_obj["token"])
                assert "itl_ms" in event_obj
            elif event_obj.get("type") == "done":
                done_event = event_obj

    assert len(tokens_received) > 0
    assert done_event is not None
    assert done_event["done"] is True
    assert "answer" in done_event
    assert "ttft_ms" in done_event
    assert "avg_itl_ms" in done_event
    assert done_event["security_verdict"] == "ALLOWED"


def test_chat_stream_opa_blocked(client):
    """Test POST /api/v1/chat/stream blocks restricted roles according to OPA policy."""
    payload = {
        "query": "Tell me secrets",
        "rag_strategy": "Basic",
        "tenant_id": "tenant_stream_test",
        "user_id": "usr_stream_blocked",
        "metadata": {"role": "GUEST"},  # GUEST role is blocked by OPA
    }
    response = client.post("/api/v1/chat/stream", json=payload)
    assert response.status_code == 200
    raw_lines = response.text.strip().split("\n\n")
    first_event = json.loads(raw_lines[0].replace("data: ", ""))
    assert first_event.get("security_verdict") == "BLOCKED"
    assert first_event.get("done") is True
