# Phase 5 — MMR RAG

**Feature**: Maximal Marginal Relevance diversity-aware retrieval  
**Status**: ✅ Complete  
**Git Branch**: `sarvam-105b-mmr-rag-v1.0.0-none`  
**Version**: v1.3.0

## What Was Built
- `backend/src/retrieval/mmr.py` — `MaximalMarginalRelevance` algorithm
- Configurable: λ (lambda), candidate_k (50), final_k (5-10)
- Formula: MMR(d) = λ·sim(q,d) − (1−λ)·max(sim(d,d_i)) for d_i ∈ Selected
- `backend/src/rag/mmr/strategy.py` — `MMRRAGStrategy`
- Unit tests: `backend/tests/unit/test_mmr.py`

## Test Evidence
- Screenshot: [chat-results.png](chat-results.png)
