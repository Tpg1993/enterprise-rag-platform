"""Integration tests for Prometheus /metrics endpoint and chat telemetry integration."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_prometheus_metrics_endpoint_scraping():
    """Verifies that /metrics and /api/v1/metrics return valid scrapable Prometheus text."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Scrape root /metrics
        res_root = await client.get("/metrics")
        assert res_root.status_code == 200
        assert "text/plain" in res_root.headers.get("content-type", "")
        text_root = res_root.text
        assert "rag_requests_total" in text_root

        # 2. Scrape aliased /api/v1/metrics
        res_v1 = await client.get("/api/v1/metrics")
        assert res_v1.status_code == 200
        assert "text/plain" in res_v1.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_chat_execution_updates_prometheus_telemetry():
    """Verifies that sending a query through /api/v1/chat updates Prometheus counters and histograms."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tenant = "tenant_prom_integ"
        query_payload = {
            "query": "How are metrics exported to Prometheus in enterprise RAG?",
            "rag_strategy": "Basic",
            "tenant_id": tenant,
            "user_id": "usr_metrics_tester",
        }

        # 1. Execute chat request
        chat_res = await client.post("/api/v1/chat", json=query_payload)
        assert chat_res.status_code == 200

        # 2. Scrape metrics endpoint
        metrics_res = await client.get("/metrics")
        assert metrics_res.status_code == 200
        metrics_text = metrics_res.text

        # 3. Assert metrics reflect the executed request
        assert f'tenant_id="{tenant}"' in metrics_text
        assert "rag_request_duration_seconds" in metrics_text
        assert "rag_cache_events_total" in metrics_text
