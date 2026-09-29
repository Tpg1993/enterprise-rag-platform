"""Integration tests for Visual Citation Preview and Bounding Box API (Phase 34)."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_get_document_page_preview():
    """Verify GET /api/v1/documents/{document_id}/preview returns page layout and bounding boxes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/v1/documents/doc_test_spec/preview?page=1&tenant_id=default_tenant"
        )
        assert response.status_code == 200
        data = response.json()

        assert data["document_id"] == "doc_test_spec"
        assert data["page_number"] == 1
        assert "page_dimensions" in data
        assert "width" in data["page_dimensions"]
        assert "height" in data["page_dimensions"]
        assert "blocks" in data
        assert len(data["blocks"]) > 0

        first_block = data["blocks"][0]
        assert "content" in first_block
        assert "bbox" in first_block
        assert len(first_block["bbox"]) == 4


@pytest.mark.asyncio
async def test_chat_response_includes_citation_bounding_boxes():
    """Verify POST /api/v1/chat citations schema includes bbox coordinates and page dimensions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={
                "query": "What is the platform objective and architecture?",
                "rag_strategy": "Basic",
                "tenant_id": "default_tenant",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "citations" in data

        # Check citation structure
        for c in data["citations"]:
            assert "source" in c
            assert "page" in c
            assert "bbox" in c
            assert "page_dimensions" in c
