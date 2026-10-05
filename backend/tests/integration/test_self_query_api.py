"""Integration tests for Phase 47: Self-Query Retrieval REST API endpoints."""

import json

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


class TestSelfQueryAPIIntegration:
    """End-to-end integration tests for self-query parsing and chat strategy dispatch."""

    def test_parse_self_query_endpoint(self) -> None:
        payload = {"query": "Find confidential contracts signed in 2024 with SLA penalty > 5000"}
        response = client.post("/api/v1/retrieval/self-query/parse", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "semantic_query" in data
        assert len(data["filters"]) >= 3
        fields = [f["field"] for f in data["filters"]]
        assert "classification" in fields
        assert "doc_type" in fields
        assert "sla_penalty_usd" in fields
        assert "qdrant_filter_dict" in data
        assert "must" in data["qdrant_filter_dict"]

    def test_schema_endpoint(self) -> None:
        response = client.get("/api/v1/retrieval/self-query/schema")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        field_names = [f["name"] for f in data]
        assert "doc_type" in field_names
        assert "classification" in field_names
        assert "sla_penalty_usd" in field_names
        assert "uptime_sla_pct" in field_names

    def test_chat_with_self_query_strategy(self) -> None:
        payload = {
            "query": "Termination liabilities in confidential contracts with penalty > 10000?",
            "rag_strategy": "Self-Query-RAG",
            "max_context_tokens": 1024,
            "tenant_id": "test_sq_tenant",
        }
        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["rag_strategy"] == "Self-Query-RAG"
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_streaming_chat_with_self_query_strategy(self) -> None:
        payload = {
            "query": "List policy guidelines for data retention in 2024",
            "rag_strategy": "Self-Query-RAG",
            "max_context_tokens": 1024,
            "tenant_id": "test_sq_tenant",
        }
        response = client.post("/api/v1/chat/stream", json=payload)
        assert response.status_code == 200
        text = response.text
        assert "event: token" in text or "data: {" in text
        done_found = False
        for line in text.split("\n"):
            if line.startswith("data: "):
                try:
                    event = json.loads(line[6:])
                    if event.get("type") == "done":
                        done_found = True
                        assert event.get("rag_strategy") == "Self-Query-RAG"
                except Exception:
                    continue
        assert done_found is True
