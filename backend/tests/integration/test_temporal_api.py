"""Integration test suite for Temporal-Aware Time-Travel RAG & Version Diff APIs."""

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


class TestTemporalAPIIntegration:
    """Tests temporal REST endpoints."""

    def test_parse_temporal_query_api_quarter(self) -> None:
        payload = {"query": "What were the liability limits in Q2 2024 for enterprise accounts?"}
        response = client.post("/api/v1/temporal/parse", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["has_temporal_intent"] is True
        t_filter = data["temporal_filter"]
        assert t_filter["start_date"] == "2024-04-01"
        assert t_filter["end_date"] == "2024-06-30"
        assert t_filter["temporal_mode"] == "range"

    def test_parse_temporal_query_api_point_in_time(self) -> None:
        payload = {"query": "Explain data encryption requirements as of 2024-05-15"}
        response = client.post("/api/v1/temporal/parse", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["has_temporal_intent"] is True
        assert data["temporal_filter"]["as_of_date"] == "2024-05-15"
        assert data["temporal_filter"]["temporal_mode"] == "point_in_time"

    def test_get_document_timeline_all(self) -> None:
        response = client.get("/api/v1/temporal/timeline")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        # Check seeded MSA documents exist
        doc_ids = [d["document_id"] for d in data]
        assert "doc_msa_v1" in doc_ids
        assert "doc_msa_v2" in doc_ids

    def test_get_document_timeline_filtered(self) -> None:
        response = client.get("/api/v1/temporal/timeline?document_id=doc_sec_2023")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["version"] == "1.0"
        assert data[0]["status"] == "deprecated"

    def test_compute_version_diff_by_document_id(self) -> None:
        payload = {
            "document_id": "doc_msa_v1",
            "version_a": "1.0",
            "version_b": "2.0",
        }
        response = client.post("/api/v1/temporal/diff", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "similarity_ratio" in data
        assert "summary" in data
        assert data["source_label"] == "doc_msa_v1 (v1.0)"

    def test_compute_version_diff_raw_text(self) -> None:
        payload = {
            "raw_text_a": "Section 1: Data stored in single region.\nSection 2: 99.5% uptime.",
            "raw_text_b": (
                "Section 1: Data replicated across multi-region.\n"
                "Section 2: 99.99% uptime.\nSection 3: AI safety audit."
            ),
            "version_a": "2023",
            "version_b": "2025",
        }
        response = client.post("/api/v1/temporal/diff", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["added_count"] >= 1
        assert data["modified_count"] >= 1
        assert len(data["unified_diff"]) > 0

    def test_compute_version_diff_point_in_time(self) -> None:
        payload = {
            "as_of_a": "2023-06-01",
            "as_of_b": "2025-06-01",
        }
        response = client.post("/api/v1/temporal/diff", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "Knowledge State as of 2023-06-01" in data["source_label"]
        assert "Knowledge State as of 2025-06-01" in data["target_label"]

    def test_chat_with_temporal_as_of_date(self) -> None:
        payload = {
            "query": "What is our uptime SLA guarantee?",
            "rag_strategy": "Basic",
            "as_of_date": "2024-06-01",
            "user_role": "ADMIN",
        }
        response = client.post("/api/v1/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert isinstance(data["citations"], list)
