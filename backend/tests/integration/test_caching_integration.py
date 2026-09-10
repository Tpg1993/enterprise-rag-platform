"""Integration tests for Multi-Tier Caching with Chat Pipeline and Telemetry APIs."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_chat_pipeline_cache_hit_and_telemetry():
    """Tests end-to-end chat cache hit flow, cost reduction, and stats API."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tenant_id = "tenant_cache_integ"
        query_text = "What is the role of reciprocal rank fusion in enterprise RAG?"

        # 1. Flush cache first to ensure pristine state
        clear_res = await client.post("/api/v1/cache/clear")
        assert clear_res.status_code == 200

        # 2. Initial chat request (Cache MISS)
        req_payload = {
            "query": query_text,
            "rag_strategy": "Basic",
            "tenant_id": tenant_id,
            "user_id": "usr_cache_test",
        }
        res1 = await client.post("/api/v1/chat", json=req_payload)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["cache_hit"] is False
        assert data1["answer"] is not None
        miss_latency = data1["latency_ms"]

        # 3. Second identical chat request (Cache HIT)
        res2 = await client.post("/api/v1/chat", json=req_payload)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["cache_hit"] is True
        assert data2["answer"] == data1["answer"]
        assert data2["estimated_cost_usd"] == 0.0
        assert data2["token_usage"]["total_tokens"] == 0
        # Instant cached retrieval should be faster or very low latency
        assert data2["latency_ms"] < 100.0

        # 4. Check cache telemetry API
        stats_res = await client.get("/api/v1/cache/stats")
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats["total_hits"] >= 1
        assert stats["hit_rate"] > 0.0
        assert stats["tier_hits"]["llm_response"] >= 1

        # 5. Flush cache and verify next request is a MISS again
        clear_res2 = await client.post("/api/v1/cache/clear")
        assert clear_res2.status_code == 200
        
        res3 = await client.post("/api/v1/chat", json=req_payload)
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["cache_hit"] is False
