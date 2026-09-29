"""Integration tests for Synthetic QA and Tenant Benchmark Endpoints (Phase 35)."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_generate_synthetic_endpoint():
    """Verify POST /api/v1/evaluations/generate-synthetic returns golden QA dataset."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/evaluations/generate-synthetic",
            json={
                "tenant_id": "default_tenant",
                "count": 4,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "SUCCESS"
        assert data["tenant_id"] == "default_tenant"
        assert data["total_generated"] == 4
        assert len(data["samples"]) == 4

        for item in data["samples"]:
            assert "id" in item
            assert "question" in item
            assert "ground_truth_answer" in item
            assert "question_type" in item
            assert "difficulty" in item


@pytest.mark.asyncio
async def test_tenant_benchmark_endpoint():
    """Verify POST /api/v1/evaluations/tenant-benchmark returns comparative leaderboard."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/evaluations/tenant-benchmark",
            json={
                "tenant_id": "default_tenant",
                "strategies": ["Basic", "Hybrid"],
                "num_samples": 2,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "benchmark_id" in data
        assert data["tenant_id"] == "default_tenant"
        assert len(data["leaderboard"]) == 2
        assert "recommended_strategy" in data
        assert data["recommended_strategy"] in ["Basic", "Hybrid"]
        assert "summary" in data

        first_rank = data["leaderboard"][0]
        assert first_rank["rank"] == 1
        assert "overall_score" in first_rank
        assert "context_precision" in first_rank
        assert "faithfulness" in first_rank
        assert "avg_latency_ms" in first_rank


@pytest.mark.asyncio
async def test_evaluation_history_endpoint():
    """Verify GET /api/v1/evaluations/history returns past evaluation runs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/evaluations/history?tenant_id=default_tenant")
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_id"] == "default_tenant"
        assert "total_runs" in data
        assert "history" in data
