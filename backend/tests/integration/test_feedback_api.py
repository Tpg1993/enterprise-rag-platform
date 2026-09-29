"""Integration tests for User Feedback and Continuous Tuning API (Phase 36)."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_feedback_submit_positive_and_negative():
    """Verify POST /api/v1/chat/feedback records feedback and returns updated chunk boost."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Submit positive feedback
        pos_res = await client.post(
            "/api/v1/chat/feedback",
            json={
                "tenant_id": "test_tenant_api",
                "rating": 1,
                "query": "How is dense search implemented?",
                "response_snippet": "Dense search utilizes Qdrant with cosine distance.",
                "category": "factual_accuracy",
                "chunk_ids": ["chk_api_qdrant_01"],
            },
        )
        assert pos_res.status_code == 200
        pos_data = pos_res.json()
        assert pos_data["status"] == "SUCCESS"
        assert pos_data["rating"] == 1
        assert len(pos_data["boost_applied_to_chunks"]) == 1
        assert pos_data["boost_applied_to_chunks"][0]["new_boost_factor"] > 1.0

        # 2. Submit negative feedback
        neg_res = await client.post(
            "/api/v1/chat/feedback",
            json={
                "tenant_id": "test_tenant_api",
                "rating": -1,
                "query": "Tell me about quantum bypass",
                "response_snippet": "Quantum bypass is verified.",
                "category": "hallucination",
                "comment": "Completely fabricated",
                "chunk_ids": ["chk_bad_chunk_api"],
            },
        )
        assert neg_res.status_code == 200
        neg_data = neg_res.json()
        assert neg_data["status"] == "SUCCESS"
        assert neg_data["rating"] == -1
        assert len(neg_data["boost_applied_to_chunks"]) == 1
        assert neg_data["boost_applied_to_chunks"][0]["new_boost_factor"] < 1.0


@pytest.mark.asyncio
async def test_feedback_validation_error():
    """Verify submitting invalid rating (not 1 or -1) returns 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/chat/feedback",
            json={
                "tenant_id": "test_tenant_api",
                "rating": 0,
                "query": "Invalid rating query",
            },
        )
        assert res.status_code == 400


@pytest.mark.asyncio
async def test_feedback_analytics_and_history_endpoints():
    """Verify GET analytics and history endpoints return structured metrics."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit sample feedback
        await client.post(
            "/api/v1/chat/feedback",
            json={
                "tenant_id": "test_analytics_tenant",
                "rating": 1,
                "category": "completeness",
                "chunk_ids": ["chk_complete_1"],
            },
        )

        # Query analytics
        analytics_res = await client.get(
            "/api/v1/chat/feedback/analytics?tenant_id=test_analytics_tenant"
        )
        assert analytics_res.status_code == 200
        data = analytics_res.json()
        assert data["tenant_id"] == "test_analytics_tenant"
        assert data["total_ratings"] >= 1
        assert data["positive_ratings"] >= 1
        assert "satisfaction_rate" in data

        # Query history
        hist_res = await client.get(
            "/api/v1/chat/feedback/history?tenant_id=test_analytics_tenant&limit=10"
        )
        assert hist_res.status_code == 200
        hist_data = hist_res.json()
        assert hist_data["tenant_id"] == "test_analytics_tenant"
        assert len(hist_data["feedback"]) >= 1

        # Query chunk boost factor
        boost_res = await client.get(
            "/api/v1/chat/feedback/boost/chk_complete_1?tenant_id=test_analytics_tenant"
        )
        assert boost_res.status_code == 200
        boost_data = boost_res.json()
        assert boost_data["chunk_id"] == "chk_complete_1"
        assert boost_data["boost_factor"] > 1.0
        assert boost_data["status"] == "BOOSTED"
