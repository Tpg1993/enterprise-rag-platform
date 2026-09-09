# Phase 2 — Ingestion Pipeline

**Feature**: Multi-format document parsers, CDC engine, BGE-M3 embeddings, Qdrant indexing  
**Status**: ✅ Complete  
**Git Branch**: `sarvam-105b-basic-rag-v1.0.0-none`  
**Version**: v1.1.0

## What Was Built
- **Parsers**: PDF (PyMuPDF), DOCX (python-docx), HTML (BeautifulSoup4), CSV, JSON, TXT/Markdown
- **CDC Engine**: MD5 checksum tracking, version incrementing (v1→v2→v3), idempotent upserts
- **Metadata Extractor**: file size, word count, author, language, security classification (Public/Internal/Confidential)
- **Embedding Factory**: local `BAAI/bge-m3` (default), TEI, Ollama, Sarvam API, mock-fast
- **QdrantVectorStore**: HNSW (M=16, ef_construction=128), tenant_id filtering, metadata payloads
- **API**: `POST/GET/DELETE /api/v1/documents`
- **UI**: Documents & Ingestion tab with drag-and-drop, embedding provider selector

## Test Evidence
- Screenshots: [documents-tab.png](documents-tab.png), [documents-tab-content.png](documents-tab-content.png)
- Recording: [ingestion-live-demo.webp](ingestion-live-demo.webp)
- Documents ingested, chunked, embedded, and indexed into Qdrant successfully
