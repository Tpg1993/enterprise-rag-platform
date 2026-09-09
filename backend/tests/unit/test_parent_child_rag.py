"""Unit tests for Phase 10 Parent-Child Hierarchical RAG chunker and strategy execution."""

from unittest.mock import AsyncMock, MagicMock
import pytest
from src.chunking.parent_child import ParentChildChunker
from src.llm.base import LLMResponse
from src.rag.base import RAGRequest
from src.rag.parent_child.strategy import ParentChildRAGStrategy


def test_parent_child_chunker_generation():
    """Verifies that ParentChildChunker creates linked parent and child chunks with parent_content."""
    chunker = ParentChildChunker(parent_size=500, child_size=100, child_overlap=20)
    sample_text = (
        "Enterprise Multi-Architecture RAG Platform is designed for deep document retrieval. "
        "It supports dense vector search using Qdrant, lexical search using BM25, and reranking. "
        "Parent-child chunking preserves surrounding context while allowing precise child vector matching."
    )
    chunks = chunker.chunk(sample_text, document_id="doc_test_123", tenant_id="tenant_a")

    assert len(chunks) > 0
    parents = [c for c in chunks if c.metadata.get("is_parent") is True]
    children = [c for c in chunks if c.metadata.get("is_parent") is False]

    assert len(parents) >= 1
    assert len(children) >= 1
    assert children[0].parent_id == parents[0].chunk_id
    assert children[0].metadata.get("parent_content") == parents[0].content


@pytest.mark.asyncio
async def test_parent_child_strategy_execution():
    """Verifies ParentChildRAGStrategy resolves child vector search hits to parent context."""
    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [
        {
            "chunk_id": "doc_1_parent_0_child_0",
            "document_id": "doc_1",
            "content": "Precise child matching snippet.",
            "score": 0.88,
            "payload": {
                "document_id": "doc_1",
                "chunk_id": "doc_1_parent_0_child_0",
                "parent_id": "doc_1_parent_0",
                "parent_content": "This is the full rich parent paragraph containing complete enterprise context.",
                "content": "Precise child matching snippet.",
                "metadata": {"filename": "architecture.pdf", "security_classification": "Internal"},
            },
        }
    ]

    mock_embedder = MagicMock()
    mock_embedder.embed_query.return_value = [0.1] * 1024

    mock_llm = MagicMock()
    mock_llm.agenerate = AsyncMock(
        return_value=LLMResponse(
            content="Parent-Child RAG synthesized answer using parent context.",
            model="sarvam-105b-mock",
            prompt_tokens=120,
            completion_tokens=40,
            total_tokens=160,
        )
    )

    strategy = ParentChildRAGStrategy(
        embedding_provider=mock_embedder,
        vector_store=mock_vector_store,
        llm_provider=mock_llm,
    )

    request = RAGRequest(
        query="What is the architecture overview?",
        tenant_id="tenant_a",
        rag_strategy="Parent-Child",
        top_k=5,
    )

    response = await strategy.execute(request)

    assert response.rag_strategy == "Parent-Child"
    assert "synthesized answer" in response.answer
    assert len(response.citations) == 1
    assert response.citations[0].relevance_score == 0.88
    assert response.prompt_tokens == 120
