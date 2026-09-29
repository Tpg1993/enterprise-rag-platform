"""Integration tests for Multi-Document Comparative Matrix & Delta Synthesis API."""

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_compare_documents_validation_error():
    """Verify that comparing fewer than 2 documents is rejected."""
    payload = {
        "document_ids": ["doc_single_only"],
        "query": "Compare clauses",
    }
    response = client.post("/api/v1/documents/compare", json=payload)
    assert response.status_code in (400, 422)


def test_compare_documents_success_and_history():
    """Verify end-to-end multi-document matrix generation, persistence, and retrieval."""
    tenant = "test_compare_tenant"
    doc_ids = ["doc_test_msa_v1", "doc_test_msa_v2"]
    payload = {
        "document_ids": doc_ids,
        "query": "Compare contractual indemnity, SLA commitments, and cloud compute budgets",
        "tenant_id": tenant,
        "focus_areas": ["Cloud Compute Quota", "Cyber Insurance"],
    }

    # 1. POST /documents/compare
    res = client.post("/api/v1/documents/compare", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["comparison_id"].startswith("cmp_")
    assert data["tenant_id"] == tenant
    assert data["document_ids"] == doc_ids
    assert len(data["dimensions"]) >= 5
    assert "|" in data["matrix_markdown"]
    assert "overall_summary" in data
    assert "risk_assessment" in data

    comp_id = data["comparison_id"]

    # 2. GET /documents/compare/history
    hist_res = client.get(f"/api/v1/documents/compare/history?tenant_id={tenant}")
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["tenant_id"] == tenant
    assert hist_data["total_comparisons"] >= 1
    found = any(c["comparison_id"] == comp_id for c in hist_data["comparisons"])
    assert found is True

    # 3. GET /documents/compare/{comparison_id}
    detail_res = client.get(f"/api/v1/documents/compare/{comp_id}")
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["comparison_id"] == comp_id
    assert detail_data["overall_summary"] == data["overall_summary"]


def test_compare_documents_not_found():
    """Verify 404 for nonexistent comparison ID."""
    res = client.get("/api/v1/documents/compare/cmp_nonexistent_99999")
    assert res.status_code == 404
