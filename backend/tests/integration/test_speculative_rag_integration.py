"""Integration tests for Speculative Draft-and-Verify RAG Pipeline."""

import json

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_speculative_rag_chat_endpoint():
    """Verify non-streaming execution of Strategy 18 Speculative-Draft-Verify."""
    payload = {
        "query": "What are the latency guarantees and SLA targets in this platform?",
        "rag_strategy": "Speculative-Draft-Verify",
        "tenant_id": "test_speculative_integration",
        "top_k": 3,
    }

    response = client.post("/api/v1/chat", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["rag_strategy"] == "Speculative-Draft-Verify"
    assert data["answer"] != ""
    assert data["speculative_speedup_ratio"] is not None
    assert data["speculative_speedup_ratio"] >= 1.0
    assert data["drift_score"] is not None
    assert 0.0 <= data["drift_score"] <= 1.0


def test_speculative_rag_chat_stream_endpoint():
    """Verify streaming SSE execution of Strategy 18."""
    payload = {
        "query": "Detail the architecture of the speculative dual-path pipeline.",
        "rag_strategy": "Speculative-Draft-Verify",
        "tenant_id": "test_speculative_stream",
        "top_k": 2,
    }

    response = client.post("/api/v1/chat/stream", json=payload)
    assert response.status_code == 200

    events = []
    for line in response.text.split("\n\n"):
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass

    assert len(events) >= 2
    token_events = [e for e in events if e.get("type") == "token"]
    assert len(token_events) >= 1

    done_events = [e for e in events if e.get("done") is True]
    assert len(done_events) == 1
    done_payload = done_events[0]
    assert done_payload["rag_strategy"] == "Speculative-Draft-Verify"
    assert done_payload["speculative_speedup_ratio"] is not None
