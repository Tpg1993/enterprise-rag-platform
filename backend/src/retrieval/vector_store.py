"""Qdrant Vector Database manager handling HNSW indexing, payload schemas, and tenant filtering."""

import logging
from typing import Any

import qdrant_client
from qdrant_client.http import models as qmodels
from src.chunking.base import Chunk
from src.config.loader import load_settings

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    """Qdrant vector store manager supporting HNSW indexes and multi-tenant isolation."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        api_key: str | None = None,
    ):
        settings = load_settings()
        self.host = host or settings.vector_store.qdrant_url.replace("http://", "").split(":")[0]
        self.port = (
            port or settings.vector_store.qdrant_port
            if hasattr(settings.vector_store, "qdrant_port")
            else 6333
        )
        self.collection_name = f"{settings.vector_store.collection_prefix}_vectors"
        self.dimension = settings.embeddings.dimension

        self.client: qdrant_client.QdrantClient | None = None
        self._memory_store: dict[str, dict[str, Any]] = {}

        try:
            self.client = qdrant_client.QdrantClient(
                host=self.host, port=self.port, api_key=api_key, timeout=0.5
            )
            self._ensure_collection()
        except Exception as e:
            logger.warning(
                f"Could not connect to Qdrant at {self.host}:{self.port} ({e}). Using memory mode."
            )
            self.client = None

    def _ensure_collection(self) -> None:
        if not self.client:
            return
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                settings = load_settings()
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=self.dimension,
                        distance=qmodels.Distance.COSINE,
                    ),
                    hnsw_config=qmodels.HnswConfigDiff(
                        m=settings.hnsw.m,
                        ef_construct=settings.hnsw.ef_construction,
                    ),
                )
                logger.info(
                    f"Created Qdrant collection '{self.collection_name}' (M={settings.hnsw.m})."
                )
        except Exception as e:
            logger.warning(f"Failed to ensure Qdrant collection ({e}). Using memory mode.")
            self.client = None

    def upsert_chunks(self, chunks: list[Chunk], vectors: list[list[float]]) -> bool:
        """Upserts chunks and their vector embeddings into Qdrant."""
        if not chunks or len(chunks) != len(vectors):
            return False

        if self.client:
            try:
                points = []
                for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
                    payload = {
                        "document_id": chunk.document_id,
                        "chunk_id": chunk.chunk_id,
                        "tenant_id": chunk.tenant_id,
                        "parent_id": chunk.parent_id or "",
                        "chunk_index": chunk.chunk_index,
                        "content": chunk.content,
                        "page_number": chunk.page_number or 0,
                        "token_count": chunk.token_count,
                        "metadata": chunk.metadata,
                    }
                    points.append(
                        qmodels.PointStruct(
                            id=abs(hash(chunk.chunk_id)) % (2**31) + idx,
                            vector=vector,
                            payload=payload,
                        )
                    )
                self.client.upsert(collection_name=self.collection_name, points=points)
                return True
            except Exception as e:
                logger.error(
                    f"Failed to upsert points to Qdrant ({e}). Storing in memory fallback."
                )
                self.client = None

        # Fallback in-memory indexing
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
            payload = {
                "document_id": chunk.document_id,
                "chunk_id": chunk.chunk_id,
                "tenant_id": chunk.tenant_id,
                "parent_id": chunk.parent_id or "",
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "page_number": chunk.page_number or 0,
                "token_count": chunk.token_count,
                "metadata": chunk.metadata,
                **(chunk.metadata if isinstance(chunk.metadata, dict) else {}),
            }
            self._memory_store[chunk.chunk_id] = {
                "chunk": chunk,
                "vector": vector,
                "payload": payload,
            }
        return True

    def search(
        self,
        query_vector: list[float],
        tenant_id: str = "default_tenant",
        top_k: int = 5,
        apply_feedback_boost: bool = True,
        metadata_filter: Any | None = None,
        filter_conditions: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Dense vector search with query-level tenant and structured metadata filtering."""
        results = []
        if self.client:
            try:
                must_clauses: list[Any] = [
                    qmodels.FieldCondition(
                        key="tenant_id",
                        match=qmodels.MatchValue(value=tenant_id),
                    )
                ]
                if metadata_filter and hasattr(metadata_filter, "must") and metadata_filter.must:
                    for cond in metadata_filter.must:
                        if getattr(cond, "key", "") != "tenant_id":
                            must_clauses.append(cond)

                tenant_filter = qmodels.Filter(must=must_clauses)
                if hasattr(self.client, "query_points"):
                    query_res = self.client.query_points(
                        collection_name=self.collection_name,
                        query=query_vector,
                        query_filter=tenant_filter,
                        limit=top_k,
                        with_vectors=True,
                        with_payload=True,
                    )
                    search_res = query_res.points
                else:
                    search_res = self.client.search(  # type: ignore[attr-defined]
                        collection_name=self.collection_name,
                        query_vector=query_vector,
                        query_filter=tenant_filter,
                        limit=top_k,
                        with_vectors=True,
                    )
                for hit in search_res:
                    payload = hit.payload or {}
                    results.append(
                        {
                            "chunk_id": payload.get("chunk_id", ""),
                            "document_id": payload.get("document_id", ""),
                            "content": payload.get("content", ""),
                            "score": float(hit.score),
                            "vector": hit.vector if hasattr(hit, "vector") and hit.vector else [],
                            "payload": payload,
                        }
                    )
                return results
            except Exception as e:
                logger.warning(f"Qdrant search error: {e}. Searching memory fallback.")

        # In-memory search fallback with metadata filtering
        for cid, item in self._memory_store.items():
            c = item["chunk"]
            payload = item.get("payload") or {
                "document_id": c.document_id,
                "chunk_id": c.chunk_id,
                "content": c.content,
                "tenant_id": c.tenant_id,
            }
            if c.tenant_id == tenant_id:
                if filter_conditions:
                    from src.retrieval.self_query import get_self_query_compiler

                    compiler = get_self_query_compiler()
                    if not all(
                        compiler.matches_payload(payload, cond) for cond in filter_conditions
                    ):
                        continue

                # Cosine similarity simulation
                v = item["vector"]
                score = sum(q * r for q, r in zip(query_vector, v))
                results.append(
                    {
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "content": c.content,
                        "score": score,
                        "vector": v,
                        "payload": payload,
                    }
                )

        # Continuous Retrieval Tuning: Apply user feedback boost multiplier (Phase 36)
        if apply_feedback_boost and tenant_id:
            try:
                from src.storage.history import get_history_store

                store = get_history_store()
                for r in results:
                    cid = r.get("chunk_id")
                    if cid:
                        boost = store.get_chunk_boost_factor(chunk_id=cid, tenant_id=tenant_id)
                        r["score"] = float(r["score"] * boost)
                        r["feedback_boost"] = boost
            except Exception as e:
                logger.debug(f"Failed to apply feedback boost in vector search: {e}")

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def delete_document(self, document_id: str, tenant_id: str = "default_tenant") -> bool:
        """Deletes all chunks belonging to a document under tenant_id."""
        if self.client:
            try:
                doc_filter = qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="document_id", match=qmodels.MatchValue(value=document_id)
                        ),
                        qmodels.FieldCondition(
                            key="tenant_id", match=qmodels.MatchValue(value=tenant_id)
                        ),
                    ]
                )
                self.client.delete(collection_name=self.collection_name, points_selector=doc_filter)
                return True
            except Exception as e:
                logger.error(f"Failed to delete document from Qdrant: {e}")

        # In-memory delete fallback
        to_del = [
            cid
            for cid, item in self._memory_store.items()
            if item["chunk"].document_id == document_id
        ]
        for cid in to_del:
            del self._memory_store[cid]
        return True


_vector_store_instance: QdrantVectorStore | None = None


def get_vector_store() -> QdrantVectorStore:
    """Singleton getter for shared QdrantVectorStore instance across routes and strategies."""
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = QdrantVectorStore()
    return _vector_store_instance

