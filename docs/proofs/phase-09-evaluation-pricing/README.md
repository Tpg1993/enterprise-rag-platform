# Phase 9 — Evaluation Suite + Pricing Engine

**Feature**: RAGAS-based retrieval/generation metrics + YAML-driven cost calculation  
**Status**: ✅ Complete  
**Git Branch**: `main`  
**Version**: v1.6.0

## What Was Built
- `backend/src/evaluation/engine.py` — `RAGEvaluationEngine`
  - Context Precision: relevant_chunks / retrieved_chunks
  - Context Recall: retrieved_relevant / ground_truth_relevant
  - Faithfulness: LLM answer grounded in context (hallucination detection)
  - Answer Relevancy: semantic match of answer to query
  - Latency breakdown (P50, P95, P99)
  - Cost per request
- `backend/config/pricing.yaml` — model pricing for sarvam-105b, qdrant ops, redis ops
- `backend/src/config/pricing.py` — `calculate_llm_cost` from YAML
- Unit tests: `backend/tests/unit/test_sarvam_pricing_eval.py`

## Test Evidence
- Screenshot: [evaluation-results.png](evaluation-results.png)
