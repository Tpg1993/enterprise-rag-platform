"""Unit tests for fixed, recursive, and parent-child chunkers."""

from src.chunking import get_chunker
from src.chunking.parent_child import ParentChildChunker


def test_recursive_chunker():
    chunker = get_chunker("recursive", chunk_size=50, chunk_overlap=10)
    text = "Sentence 1 is long enough. Sentence 2 is also here. Sentence 3 completes it."
    chunks = chunker.chunk(text, "doc_10")
    assert len(chunks) > 0
    assert chunks[0].document_id == "doc_10"


def test_parent_child_chunker():
    chunker = ParentChildChunker(parent_size=100, child_size=30)
    text = "A very long document text meant to test parent child hierarchical splitting logic."
    chunks = chunker.chunk(text, "doc_20")
    parents = [c for c in chunks if c.metadata.get("is_parent")]
    children = [c for c in chunks if not c.metadata.get("is_parent")]

    assert len(parents) > 0
    assert len(children) > 0
    assert children[0].parent_id is not None
