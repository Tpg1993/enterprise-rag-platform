"""Fixed-size character chunker with overlap."""

import uuid

from src.chunking.base import BaseChunker, Chunk


class FixedSizeChunker(BaseChunker):
    """Fixed-size character chunker with configurable overlap."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = max(100, chunk_size)
        self.chunk_overlap = min(chunk_overlap, self.chunk_size - 10)

    def chunk(self, text: str, document_id: str, tenant_id: str = "default_tenant") -> list[Chunk]:
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)
        idx = 0

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            sub_text = text[start:end].strip()

            if sub_text:
                chunk_id = f"{document_id}_chunk_{idx}_{uuid.uuid4().hex[:6]}"
                chunks.append(
                    Chunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        tenant_id=tenant_id,
                        chunk_index=idx,
                        content=sub_text,
                        token_count=len(sub_text.split()),
                        metadata={"chunk_strategy": "fixed", "size": len(sub_text)},
                    )
                )
                idx += 1

            start += self.chunk_size - self.chunk_overlap

        return chunks
