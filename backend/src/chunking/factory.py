"""Chunker factory routing strategy names to BaseChunker implementations."""

from src.chunking.base import BaseChunker
from src.chunking.fixed import FixedSizeChunker
from src.chunking.parent_child import ParentChildChunker
from src.chunking.recursive import RecursiveCharacterChunker


def get_chunker(
    strategy: str = "recursive", chunk_size: int = 512, chunk_overlap: int = 50
) -> BaseChunker:
    """Returns BaseChunker instance matching strategy name."""
    s_lower = strategy.lower()
    if s_lower == "fixed":
        return FixedSizeChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    elif s_lower == "parent_child":
        return ParentChildChunker(
            parent_size=chunk_size * 2, child_size=chunk_size // 2, child_overlap=chunk_overlap
        )
    else:
        return RecursiveCharacterChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
