"""BM25 Lexical Retriever supporting rank-bm25 indexing and multi-tenant isolation."""

import logging
import re
from typing import Any

from rank_bm25 import BM25Okapi
from src.chunking.base import Chunk

logger = logging.getLogger(__name__)


def default_tokenizer(text: str) -> list[str]:
    """Tokenizes and normalizes text into lowercase alphanumeric words."""
    if not text:
        return []
    # Tokenize alphanumeric sequences
    tokens = re.findall(r"\w+", text.lower())
    return [t for t in tokens if len(t) > 1]


class BM25Retriever:
    """In-memory BM25 lexical retriever with per-tenant index isolation."""

    def __init__(self) -> None:
        # Keyed by tenant_id -> list of Chunk
        self._tenant_chunks: dict[str, list[Chunk]] = {}
        # Keyed by tenant_id -> BM25Okapi instance
        self._tenant_indexes: dict[str, BM25Okapi | None] = {}

    def index_chunks(self, chunks: list[Chunk], tenant_id: str = "default_tenant") -> None:
        """Indexes or appends chunks into the BM25 index for a tenant."""
        if not chunks:
            return

        if tenant_id not in self._tenant_chunks:
            self._tenant_chunks[tenant_id] = []

        # Filter chunks by tenant_id and deduplicate by chunk_id
        matching_chunks = [c for c in chunks if c.tenant_id == tenant_id]
        existing_ids = {c.chunk_id for c in self._tenant_chunks[tenant_id]}
        new_chunks = [c for c in matching_chunks if c.chunk_id not in existing_ids]

        if new_chunks:
            self._tenant_chunks[tenant_id].extend(new_chunks)
            self._rebuild_index(tenant_id)

    def _rebuild_index(self, tenant_id: str) -> None:
        """Rebuilds the BM25 index for a given tenant."""
        chunks = self._tenant_chunks.get(tenant_id, [])
        if not chunks:
            self._tenant_indexes[tenant_id] = None
            return

        corpus = [default_tokenizer(c.content) for c in chunks]
        self._tenant_indexes[tenant_id] = BM25Okapi(corpus)

    def search(
        self, query: str, tenant_id: str = "default_tenant", top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Executes BM25 lexical keyword search for a given tenant."""
        chunks = self._tenant_chunks.get(tenant_id, [])
        bm25_index = self._tenant_indexes.get(tenant_id)

        if not chunks or bm25_index is None:
            return []

        tokenized_query = default_tokenizer(query)
        if not tokenized_query:
            return []

        scores = bm25_index.get_scores(tokenized_query)

        # Pair scores with chunks
        scored_hits = []
        for idx, score in enumerate(scores):
            c = chunks[idx]
            scored_hits.append(
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "content": c.content,
                    "score": float(score),
                    "payload": {
                        "document_id": c.document_id,
                        "chunk_id": c.chunk_id,
                        "content": c.content,
                        "page_number": c.page_number or 1,
                        "tenant_id": c.tenant_id,
                        "metadata": c.metadata,
                    },
                }
            )

        scored_hits.sort(key=lambda x: x["score"], reverse=True)
        return scored_hits[:top_k]

    def delete_document(self, document_id: str, tenant_id: str = "default_tenant") -> bool:
        """Deletes document chunks from the BM25 index for a tenant."""
        if tenant_id in self._tenant_chunks:
            self._tenant_chunks[tenant_id] = [
                c for c in self._tenant_chunks[tenant_id] if c.document_id != document_id
            ]
            self._rebuild_index(tenant_id)
            return True
        return False


_global_bm25: BM25Retriever | None = None


def get_bm25_retriever() -> BM25Retriever:
    """Returns singleton instance of BM25Retriever."""
    global _global_bm25
    if _global_bm25 is None:
        _global_bm25 = BM25Retriever()
    return _global_bm25

