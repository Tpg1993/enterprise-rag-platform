# Phase 3 — Basic RAG

**Feature**: Baseline vector search → Context Builder → Prompt Builder → Sarvam AI  
**Status**: ✅ Complete  
**Git Branch**: `sarvam-105b-basic-rag-v1.0.0-none`  
**Version**: v1.0.0

## What Was Built
- `backend/src/rag/basic/strategy.py` — `BasicRAGStrategy`
- Flow: Query → BGE-M3 embed → Qdrant dense search → ContextBuilder → PromptBuilder → Sarvam-105b → Answer with citations
- Unit tests: `backend/tests/unit/test_basic_rag.py`

## Sample Query Tested
- **Query**: "What is RAG and how does it work?"
- **Strategy**: Basic
- **Response**: Grounded answer with [filename (Page X)] citations

## Test Evidence
- Screenshot: [chat-ui-basic-rag-response.png](chat-ui-basic-rag-response.png)
- Recording: [basic-rag-live-demo.webp](basic-rag-live-demo.webp)
