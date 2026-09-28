"""End-to-End (E2E) Browser & Web UI Test Suite verifying static mounting, tab navigation, and UI DOM structure."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_root_endpoint_metadata():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["ui"] == "/ui"
    assert data["docs"] == "/docs"


@pytest.mark.asyncio
async def test_web_ui_bundle_mounting():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/ui/")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    html_text = res.text

    # Validate essential UI DOM elements
    assert "Enterprise RAG & Agentic AI Platform" in html_text
    assert 'data-tab="chat"' in html_text
    assert 'data-tab="documents"' in html_text
    assert 'data-tab="strategies"' in html_text
    assert 'data-tab="comparison"' in html_text
    assert 'data-tab="traces"' in html_text
    assert 'data-tab="evaluations"' in html_text
    assert 'data-tab="admin"' in html_text

    # Validate Strategy selection options (All 15 strategies)
    assert 'value="Basic"' in html_text
    assert 'value="Hybrid"' in html_text
    assert 'value="MMR"' in html_text
    assert 'value="Reranked"' in html_text
    assert 'value="Parent-Child"' in html_text
    assert 'value="Multi-Query"' in html_text
    assert 'value="HyDE"' in html_text
    assert 'value="Adaptive"' in html_text
    assert 'value="Corrective"' in html_text
    assert 'value="Self-RAG"' in html_text
    assert 'value="ReAct"' in html_text
    assert 'value="GraphRAG"' in html_text
    assert 'value="SQL-RAG"' in html_text
    assert 'value="Multimodal"' in html_text
    assert 'value="Hybrid-Graph-Agentic"' in html_text

    # Validate Phase 26 Security & PII Inspector DOM elements
    assert 'id="sec-inspect-input"' in html_text
    assert 'id="btn-sec-inspect"' in html_text
    assert "Open Policy Agent (OPA) Guardrails" in html_text


@pytest.mark.asyncio
async def test_openapi_documentation_mounting():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/docs")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
