"""Integration tests for Agentic Web RAG (Strategy 17)."""

import json

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app
from src.rag.base import RAGRequest, RAGResponse
from src.rag.router import get_rag_strategy
from src.rag.web_agentic.strategy import AgenticWebRAGStrategy


@pytest.mark.asyncio
async def test_agentic_web_rag_router_resolution():
    """Verifies that RAG router resolves 'Agentic-Web-RAG' to AgenticWebRAGStrategy."""
    strat = get_rag_strategy("Agentic-Web-RAG")
    assert isinstance(strat, AgenticWebRAGStrategy)

    strat2 = get_rag_strategy("WEB")
    assert isinstance(strat2, AgenticWebRAGStrategy)

    req = RAGRequest(
        query="What is the latest headline news today?",
        tenant_id="default_tenant",
        rag_strategy="Agentic-Web-RAG",
    )
    res = await strat.execute(req)
    assert isinstance(res, RAGResponse)
    assert res.rag_strategy == "Agentic-Web-RAG"
    assert res.metadata["web_search_triggered"] is True


@pytest.mark.asyncio
async def test_chat_endpoint_agentic_web_rag():
    """Verifies that POST /api/v1/chat executes Strategy 17 with web citations."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "Give me the latest stock market trend and rates today",
            "rag_strategy": "Agentic-Web-RAG",
            "tenant_id": "default_tenant",
            "stream": False,
        }
        res = await client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["rag_strategy"] == "Agentic-Web-RAG"
        assert len(data["citations"]) > 0
        assert any(c.get("is_web") is True for c in data["citations"])
        web_c = next(c for c in data["citations"] if c.get("is_web") is True)
        assert web_c["domain"] != ""
        assert web_c["url"].startswith("http")


@pytest.mark.asyncio
async def test_chat_streaming_agentic_web_rag():
    """Verifies that POST /api/v1/chat/stream executes Strategy 17 with web citations."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "What are the latest NIST compliance security guidelines?",
            "rag_strategy": "Agentic-Web-RAG",
            "tenant_id": "default_tenant",
            "stream": True,
        }
        res = await client.post("/api/v1/chat/stream", json=payload)
        assert res.status_code == 200
        body = res.text
        assert "data: " in body

        # Parse SSE events
        done_found = False
        for line in body.split("\n"):
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data.get("type") == "done":
                    done_found = True
                    assert data["rag_strategy"] == "Agentic-Web-RAG"
                    assert len(data["citations"]) > 0
                    assert any(c.get("is_web") is True for c in data["citations"])
        assert done_found is True
