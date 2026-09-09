# Phase 4 — Hybrid RAG

**Feature**: Dense (Qdrant) + Sparse (BM25) concurrent retrieval with Reciprocal Rank Fusion  
**Status**: ✅ Complete  
**Git Branch**: `sarvam-105b-hybrid-rag-v1.0.0-none`  
**Version**: v1.2.0

## What Was Built
- `backend/src/retrieval/bm25.py` — `BM25Retriever` with `rank-bm25` (BM25Okapi), multi-tenant index isolation
- `backend/src/retrieval/fusion.py` — `ReciprocalRankFusion`: RRF_Score(d) = Σ 1/(60+r(d))
- `backend/src/rag/hybrid/strategy.py` — `HybridRAGStrategy` with `asyncio.gather` for concurrent retrieval
- BM25 index auto-synced on document upload/delete
- Unit tests: `backend/tests/unit/test_hybrid_rag.py`

## Test Evidence
- Screenshot: [chat-tab.png](chat-tab.png)
- Recording: [hybrid-rag-grounded-queries-demo.webp](hybrid-rag-grounded-queries-demo.webp)
