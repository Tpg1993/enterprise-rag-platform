"""Integration test verifying full multi-component lifecycle: upload -> parse -> index -> RAG query (Basic/Hybrid/MMR) -> delete."""

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.main import app


@pytest.mark.asyncio
async def test_full_ingestion_retrieval_deletion_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Step 1: Health Check
        health_res = await ac.get("/api/v1/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "healthy"

        # Step 2: Upload Document
        sample_text = (
            "Sarvam-105B is a 105 billion parameter Indic multilingual LLM. "
            "It uses hybrid retrieval combining Qdrant dense vector search with BM25 keyword search. "
            "Maximal Marginal Relevance (MMR) eliminates redundant context chunks."
        ).encode("utf-8")

        upload_res = await ac.post(
            "/api/v1/documents",
            files={"file": ("sarvam_architecture_spec.txt", sample_text, "text/plain")},
            data={
                "chunk_strategy": "recursive",
                "chunk_size": 256,
                "chunk_overlap": 30,
                "embedding_provider": "mock-fast",
                "tenant_id": "integration_tenant",
            },
        )
        assert upload_res.status_code == 200
        up_data = upload_res.json()
        doc_id = up_data["document_id"]
        assert up_data["status"] == "ingested"
        assert up_data["total_chunks"] >= 1
        assert up_data["version"] == 1
        assert up_data["security_classification"] == "Internal"

        # Step 3: Verify Document in Listing
        list_res = await ac.get("/api/v1/documents?tenant_id=integration_tenant")
        assert list_res.status_code == 200
        docs_list = list_res.json()
        assert len(docs_list) >= 1
        assert any(d["document_id"] == doc_id for d in docs_list)

        # Step 4: Query using Basic RAG Strategy
        basic_res = await ac.post(
            "/api/v1/chat",
            json={
                "query": "What is Sarvam-105B?",
                "rag_strategy": "Basic",
                "tenant_id": "integration_tenant",
            },
        )
        assert basic_res.status_code == 200
        b_data = basic_res.json()
        assert b_data["rag_strategy"] == "Basic"
        assert b_data["latency_ms"] > 0

        # Step 5: Query using Hybrid RAG Strategy
        hybrid_res = await ac.post(
            "/api/v1/chat",
            json={
                "query": "What combines Qdrant and BM25 search?",
                "rag_strategy": "Hybrid",
                "tenant_id": "integration_tenant",
            },
        )
        assert hybrid_res.status_code == 200
        h_data = hybrid_res.json()
        assert h_data["rag_strategy"] == "Hybrid"
        assert h_data["trace_id"].startswith("trace_hybrid_")

        # Step 6: Query using MMR Strategy
        mmr_res = await ac.post(
            "/api/v1/chat",
            json={
                "query": "How does MMR eliminate redundancy?",
                "rag_strategy": "MMR",
                "tenant_id": "integration_tenant",
            },
        )
        assert mmr_res.status_code == 200
        m_data = mmr_res.json()
        assert m_data["rag_strategy"] == "MMR"
        assert m_data["trace_id"].startswith("trace_mmr_")

        # Step 7: Delete Document
        del_res = await ac.delete(f"/api/v1/documents/{doc_id}?tenant_id=integration_tenant")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Step 8: Verify Listing is Clean
        list_after = await ac.get("/api/v1/documents?tenant_id=integration_tenant")
        assert list_after.status_code == 200
        assert not any(d["document_id"] == doc_id for d in list_after.json())
