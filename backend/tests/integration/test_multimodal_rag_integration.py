"""Integration tests for Phase 21 Multimodal RAG."""

import pymupdf
import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_multimodal_rag_chat_endpoint():
    """Verifies that POST /api/v1/chat executes Multimodal RAG strategy successfully."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "What is the breakdown in the performance metrics table?",
            "rag_strategy": "Multimodal",
            "top_k": 3,
            "tenant_id": "default_tenant",
        }
        res = await client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["rag_strategy"] == "Multimodal"
        assert "answer" in data
        assert data["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_multimodal_pdf_upload_and_query():
    """Uploads a multimodal PDF with a structured table and queries it via Multimodal RAG."""
    # 1. Create a synthetic PDF with a table
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 40), "Enterprise Operating Metrics 2026")

    rect = pymupdf.Rect(50, 60, 250, 160)
    page.draw_rect(rect)
    page.draw_line(pymupdf.Point(50, 110), pymupdf.Point(250, 110))
    page.draw_line(pymupdf.Point(150, 60), pymupdf.Point(150, 160))
    page.insert_text((60, 90), "KPI")
    page.insert_text((160, 90), "Growth")
    page.insert_text((60, 140), "Active Users")
    page.insert_text((160, 140), "+45%")

    pdf_bytes = doc.tobytes()
    doc.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload
        files = {"file": ("operating_metrics.pdf", pdf_bytes, "application/pdf")}
        data = {
            "embedding_provider": "mock-fast",
            "chunking_strategy": "recursive",
            "tenant_id": "default_tenant",
        }
        upload_res = await client.post("/api/v1/documents", files=files, data=data)
        assert upload_res.status_code == 200
        upload_data = upload_res.json()
        assert upload_data["status"] in ("ingested", "SUCCESS")

        # Query via Multimodal RAG
        query_payload = {
            "query": "What is the growth for Active Users in the KPI table?",
            "rag_strategy": "Multimodal",
            "top_k": 3,
            "tenant_id": "default_tenant",
        }
        chat_res = await client.post("/api/v1/chat", json=query_payload)
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert chat_data["rag_strategy"] == "Multimodal"
        assert len(chat_data["answer"]) > 0
