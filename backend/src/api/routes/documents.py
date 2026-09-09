"""FastAPI routes for document upload, ingestion, CDC, and index management."""

import time
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from src.chunking import get_chunker
from src.documents import get_parser_for_file
from src.embeddings import get_embedding_provider
from src.ingestion import (
    ChangeDataCaptureEngine,
    EnterpriseMetadataExtractor,
    PIIRedactor,
    TextCleaner,
)
from src.rag.hybrid.strategy import global_bm25_retriever
from src.retrieval import get_vector_store

router = APIRouter(tags=["Documents"])

# Global shared singletons
cdc_engine = ChangeDataCaptureEngine()
vector_store = get_vector_store()
bm25_retriever = global_bm25_retriever

# In-memory document registry
document_db: dict[str, dict[str, Any]] = {}


class DocumentIngestionResponse(BaseModel):
    document_id: str
    filename: str
    status: str  # e.g., 'ingested', 'unchanged', 'reindexed'
    chunk_strategy: str
    embedding_provider: str
    total_chunks: int
    total_tokens: int
    checksum: str
    version: int
    latency_ms: float
    tenant_id: str
    file_size_human: str = "0 KB"
    word_count: int = 0
    author: str = "Enterprise User"
    security_classification: str = "Internal"
    has_pii: bool = False
    redacted_count: int = 0
    language: str = "en"


class DocumentSummary(BaseModel):
    document_id: str
    filename: str
    file_type: str
    total_chunks: int
    checksum: str
    version: int
    tenant_id: str
    chunk_strategy: str = "recursive"
    chunk_size: int = 512
    chunk_overlap: int = 50
    embedding_provider: str = "bge-m3"
    file_size_human: str = "0 KB"
    word_count: int = 0
    author: str = "Enterprise User"
    security_classification: str = "Internal"
    has_pii: bool = False
    redacted_count: int = 0
    language: str = "en"


@router.post("/documents", response_model=DocumentIngestionResponse)
async def upload_document(
    file: UploadFile = File(...),
    chunk_strategy: str = Form("recursive"),
    chunk_size: int = Form(512),
    chunk_overlap: int = Form(50),
    embedding_provider: str = Form("bge-m3"),
    tenant_id: str = Form("default_tenant"),
) -> DocumentIngestionResponse:
    """Uploads, parses, cleans, redacts PII, extracts metadata, embeds, and indexes a document."""
    start_time = time.perf_counter()
    filename = file.filename or "file.txt"
    file_bytes = await file.read()

    checksum = cdc_engine.compute_checksum(file_bytes)
    doc_id = f"doc_{uuid.uuid5(uuid.NAMESPACE_DNS, filename + tenant_id).hex[:12]}"

    # Default fallback to bge-m3 if empty or unselected
    chosen_embedder = embedding_provider or "bge-m3"

    # CDC Change inspection
    change_type = cdc_engine.inspect_change(doc_id, checksum, tenant_id=tenant_id)

    # 1. Parse
    parser = get_parser_for_file(filename)
    parsed_doc = parser.parse(file_bytes, filename, doc_id)

    # 2. Clean & Redact PII
    cleaner = TextCleaner()
    pii = PIIRedactor()

    cleaned_text = cleaner.clean_text(parsed_doc.full_text)
    sanitized_text = pii.redact(cleaned_text)

    # 3. Enterprise Rich Metadata Extraction (3-Tier Rules & Heuristics)
    meta_info = EnterpriseMetadataExtractor.extract_metadata(
        file_bytes=file_bytes,
        filename=filename,
        full_text=cleaned_text,
        sanitized_text=sanitized_text,
        parsed_metadata=parsed_doc.metadata,
    )

    # 4. Chunk
    chunker = get_chunker(
        strategy=chunk_strategy, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = chunker.chunk(sanitized_text, doc_id, tenant_id=tenant_id)

    # Attach document-level metadata to chunk metadata
    for c in chunks:
        c.metadata.update(meta_info.model_dump())

    # 5. Embed using selected provider
    embedder_instance = get_embedding_provider(chosen_embedder)
    chunk_texts = [c.content for c in chunks]
    vectors = embedder_instance.embed_documents(chunk_texts)

    # 6. Index in Qdrant Vector DB & BM25 Lexical Index
    vector_store.upsert_chunks(chunks, vectors)
    bm25_retriever.index_chunks(chunks, tenant_id=tenant_id)

    # 7. Record CDC version (Increments version v1 -> v2 -> v3 on re-upload)
    version = cdc_engine.record_ingestion(doc_id, checksum, tenant_id=tenant_id)

    total_tokens = sum(c.token_count for c in chunks)
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    document_db[doc_id] = {
        "document_id": doc_id,
        "filename": filename,
        "file_type": parsed_doc.file_type,
        "total_chunks": len(chunks),
        "total_tokens": total_tokens,
        "checksum": checksum,
        "version": version,
        "tenant_id": tenant_id,
        "chunk_strategy": chunk_strategy,
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "embedding_provider": chosen_embedder,
        "file_size_human": meta_info.file_size_human,
        "word_count": meta_info.word_count,
        "author": meta_info.author,
        "security_classification": meta_info.security_classification,
        "has_pii": meta_info.has_pii,
        "redacted_count": meta_info.redacted_count,
        "language": meta_info.language,
    }

    return DocumentIngestionResponse(
        document_id=doc_id,
        filename=filename,
        status="ingested" if change_type == "NEW" else "reindexed",
        chunk_strategy=chunk_strategy,
        embedding_provider=chosen_embedder,
        total_chunks=len(chunks),
        total_tokens=total_tokens,
        checksum=checksum,
        version=version,
        latency_ms=elapsed_ms,
        tenant_id=tenant_id,
        file_size_human=meta_info.file_size_human,
        word_count=meta_info.word_count,
        author=meta_info.author,
        security_classification=meta_info.security_classification,
        has_pii=meta_info.has_pii,
        redacted_count=meta_info.redacted_count,
        language=meta_info.language,
    )


@router.get("/documents", response_model=list[DocumentSummary])
async def list_documents(tenant_id: str = Query("default_tenant")) -> list[DocumentSummary]:
    """Lists all ingested documents filtered by tenant_id."""
    return [
        DocumentSummary(**doc) for doc in document_db.values() if doc.get("tenant_id") == tenant_id
    ]


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str, tenant_id: str = Query("default_tenant")
) -> dict[str, str]:
    """Deletes a document and invalidates vector indexes."""
    if document_id not in document_db:
        raise HTTPException(status_code=404, detail="Document not found")

    vector_store.delete_document(document_id, tenant_id=tenant_id)
    bm25_retriever.delete_document(document_id, tenant_id=tenant_id)
    cdc_engine.invalidate(document_id)
    del document_db[document_id]

    return {"status": "deleted", "document_id": document_id}
