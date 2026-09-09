"""Unit tests for Phase 4 Hybrid RAG, BM25Retriever, and ReciprocalRankFusion."""

import pytest
from src.chunking.base import Chunk
from src.rag.base import RAGRequest, RAGResponse
from src.rag.hybrid.strategy import HybridRAGStrategy
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.fusion import ReciprocalRankFusion


def test_bm25_retriever_indexing_and_search():
    retriever = BM25Retriever()
    chunks = [
        Chunk(
            chunk_id="c1",
            document_id="doc1",
            chunk_index=0,
            content="Sarvam-105B is a 105 billion parameter Indic language model.",
            tenant_id="tenant_a",
        ),
        Chunk(
            chunk_id="c2",
            document_id="doc1",
            chunk_index=1,
            content="Qdrant vector database handles dense embeddings.",
            tenant_id="tenant_a",
        ),
        Chunk(
            chunk_id="c3",
            document_id="doc2",
            chunk_index=0,
            content="Other tenant content isolated completely.",
            tenant_id="tenant_b",
        ),
    ]

    retriever.index_chunks(chunks, tenant_id="tenant_a")

    hits = retriever.search("Sarvam-105B parameter model", tenant_id="tenant_a", top_k=2)
    assert len(hits) >= 1
    assert hits[0]["chunk_id"] == "c1"
    assert hits[0]["score"] >= 0.0

    # Verify tenant isolation
    hits_b = retriever.search("Sarvam-105B", tenant_id="tenant_b", top_k=2)
    assert len(hits_b) == 0


def test_reciprocal_rank_fusion():
    fusion = ReciprocalRankFusion(rrf_k=60)

    dense_hits = [
        {"chunk_id": "c1", "content": "Dense chunk 1", "score": 0.95},
        {"chunk_id": "c2", "content": "Dense chunk 2", "score": 0.85},
    ]
    bm25_hits = [
        {"chunk_id": "c2", "content": "Dense chunk 2", "score": 4.5},
        {"chunk_id": "c3", "content": "Lexical chunk 3", "score": 3.1},
    ]

    fused = fusion.fuse([dense_hits, bm25_hits], top_k=3)

    assert len(fused) == 3
    # c2 is present in both runs, so it should rank first with highest RRF score
    assert fused[0]["chunk_id"] == "c2"
    assert fused[0]["score"] > fused[1]["score"]


@pytest.mark.asyncio
async def test_hybrid_rag_strategy_execution():
    strategy = HybridRAGStrategy()
    request = RAGRequest(
        query="What is Sarvam-105B architecture?",
        tenant_id="test_tenant_hybrid",
        rag_strategy="Hybrid",
    )

    response = await strategy.execute(request)

    assert isinstance(response, RAGResponse)
    assert response.query == "What is Sarvam-105B architecture?"
    assert response.rag_strategy == "Hybrid"
    assert response.tenant_id == "test_tenant_hybrid"
    assert response.latency_ms > 0
    assert response.trace_id.startswith("trace_hybrid_")
