"""Recursive character chunker prioritizing paragraph, sentence, and word boundaries."""

import uuid

from src.chunking.base import BaseChunker, Chunk


class RecursiveCharacterChunker(BaseChunker):
    """Recursive chunker that splits on paragraphs, sentences, and words."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def chunk(self, text: str, document_id: str, tenant_id: str = "default_tenant") -> list[Chunk]:
        if not text:
            return []

        raw_splits = self._recursive_split(text, self.separators)
        merged_chunks = self._merge_splits(raw_splits)

        chunks = []
        for idx, content in enumerate(merged_chunks):
            chunk_id = f"{document_id}_rchunk_{idx}_{uuid.uuid4().hex[:6]}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    tenant_id=tenant_id,
                    chunk_index=idx,
                    content=content,
                    token_count=len(content.split()),
                    metadata={
                        "chunk_strategy": "recursive",
                        "size": len(content),
                    },
                )
            )

        return chunks

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size or not separators:
            return [text]

        sep = separators[0]
        next_seps = separators[1:]

        if sep == "":
            return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

        splits = text.split(sep)
        final_splits = []

        for s in splits:
            if len(s) > self.chunk_size:
                final_splits.extend(self._recursive_split(s, next_seps))
            else:
                final_splits.append(s)

        return final_splits

    def _merge_splits(self, splits: list[str]) -> list[str]:
        merged: list[str] = []
        current: list[str] = []
        curr_len = 0

        for s in splits:
            s_len = len(s)
            if curr_len + s_len > self.chunk_size and current:
                merged.append(" ".join(current).strip())
                current = []
                curr_len = 0
            current.append(s)
            curr_len += s_len

        if current:
            merged.append(" ".join(current).strip())

        return merged
