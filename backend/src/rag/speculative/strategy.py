"""Speculative Draft-and-Verify RAG Strategy (Low-Latency Acceleration)."""

import asyncio
import inspect
import logging
import time
import uuid
from typing import Any

from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.rag.speculative.drift_detector import SpeculativeDriftDetector
from src.reranking import BaseReranker, get_reranker
from src.retrieval import BM25Retriever, QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)

global_bm25_retriever = BM25Retriever()


class SpeculativeDraftVerifyRAGStrategy(BaseRAGStrategy):
    """Dual-path speculative RAG strategy delivering accelerated initial TTFT
    combined with asynchronous dense cross-encoder verification.
    """

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        bm25_retriever: BM25Retriever | None = None,
        reranker: BaseReranker | None = None,
        embedding_provider_name: str = "bge-m3",
        llm_provider: LLMProvider | None = None,
        drift_threshold: float = 0.35,
    ) -> None:
        self.vector_store = vector_store or get_vector_store()
        self.bm25_retriever = bm25_retriever or global_bm25_retriever
        self.reranker = reranker or get_reranker()
        self.embedding_provider = get_embedding_provider(embedding_provider_name)
        self.llm_provider = llm_provider or get_llm_provider()
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()
        self.drift_detector = SpeculativeDriftDetector(drift_threshold=drift_threshold)

    async def execute(self, request: RAGRequest) -> RAGResponse:
        """Executes concurrent speculative draft path and verified deep retrieval."""
        start_time = time.perf_counter()
        trace_id = f"trace_speculative_{uuid.uuid4().hex[:12]}"

        # --- Path 1: Fast Speculative Draft Path ---
        async def _run_draft_path() -> tuple[str, float]:
            t0 = time.perf_counter()
            # Rapid top-1 retrieval via BM25
            fast_hits = self.bm25_retriever.search(
                query=request.query,
                tenant_id=request.tenant_id,
                top_k=1,
            )

            # Fallback to in-memory/raw vector hit if BM25 index has no matches
            draft_context = ""
            if fast_hits:
                draft_context = fast_hits[0].get("content", "")
            else:
                embed_res = self.embedding_provider.embed_query(request.query)
                query_vec = await embed_res if inspect.isawaitable(embed_res) else embed_res
                quick_hits = self.vector_store.search(
                    query_vector=query_vec,
                    tenant_id=request.tenant_id,
                    top_k=1,
                )
                if quick_hits:
                    draft_context = (
                        quick_hits[0].get("content")
                        or quick_hits[0].get("payload", {}).get("content", "")
                    )

            draft_prompts = self.prompt_builder.build_prompt(
                request.query,
                draft_context or "Direct domain knowledge extract.",
            )
            draft_res = await self.llm_provider.agenerate(
                prompt=draft_prompts["user"],
                system_prompt=draft_prompts["system"],
                temperature=request.temperature,
                max_tokens=min(128, request.max_tokens),
            )
            draft_ttft = (time.perf_counter() - t0) * 1000
            return draft_res.content, draft_ttft

        # --- Path 2: Deep Accurate Verification Path ---
        async def _run_verification_path() -> tuple[Any, float]:
            t0 = time.perf_counter()
            embed_res = self.embedding_provider.embed_query(request.query)
            query_vec = await embed_res if inspect.isawaitable(embed_res) else embed_res

            # Dense Vector Search
            raw_hits = self.vector_store.search(
                query_vector=query_vec,
                tenant_id=request.tenant_id,
                top_k=request.top_k * 2,
            )

            # Cross-Encoder Reranking
            verified_hits = self.reranker.rerank(
                query=request.query,
                hits=raw_hits,
                top_n=request.top_k,
            )

            # Context Assembly & Compression
            ctx_res = self.context_builder.build_context(
                verified_hits,
                max_context_tokens=request.max_context_tokens,
                enable_compression=request.enable_compression,
                compression_target_ratio=request.compression_target_ratio,
                query=request.query,
            )
            verified_ttft = (time.perf_counter() - t0) * 1000
            return ctx_res, verified_ttft

        # Run dual pathways concurrently
        (draft_answer, draft_ttft_ms), (ctx_res, verified_ttft_ms) = await asyncio.gather(
            _run_draft_path(),
            _run_verification_path(),
        )

        # 3. Assess Semantic Drift & Missing Critical Clauses
        verified_context_str = ctx_res.formatted_context
        drift = self.drift_detector.evaluate_drift(
            draft_text=draft_answer,
            verified_chunks=[verified_context_str],
        )

        # 4. Final Answer Synthesis (Refinement if drift detected)
        final_answer = draft_answer
        tokens_used_prompt = 0
        tokens_used_completion = 0
        total_cost = 0.0

        if drift.correction_needed and drift.missing_critical_terms:
            refine_query = (
                f"{request.query} (Verified clauses to integrate: "
                f"{', '.join(drift.missing_critical_terms)})"
            )
            refine_prompts = self.prompt_builder.build_prompt(refine_query, verified_context_str)
            refine_res = await self.llm_provider.agenerate(
                prompt=refine_prompts["user"],
                system_prompt=refine_prompts["system"],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            if drift.status == "HIGH_DRIFT":
                final_answer = refine_res.content
            else:
                final_answer = f"{draft_answer}\n\n[Verified Refinement: {refine_res.content}]"
            tokens_used_prompt = refine_res.prompt_tokens
            tokens_used_completion = refine_res.completion_tokens
            total_cost = refine_res.estimated_cost_usd

        # 5. Telemetry & Acceleration Metrics
        speedup_ratio = round(max(1.0, verified_ttft_ms / max(1.0, draft_ttft_ms)), 2)
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return RAGResponse(
            answer=final_answer,
            query=request.query,
            rag_strategy="Speculative-Draft-Verify",
            citations=ctx_res.citations,
            latency_ms=elapsed_ms,
            prompt_tokens=tokens_used_prompt,
            completion_tokens=tokens_used_completion,
            estimated_cost_usd=total_cost,
            model=getattr(self.llm_provider, "model_name", "sarvam-105b"),
            trace_id=trace_id,
            tenant_id=request.tenant_id,
            compression_ratio=ctx_res.compression_ratio,
            tokens_saved=ctx_res.tokens_saved,
            metadata={
                "speculative_ttft_ms": round(draft_ttft_ms, 1),
                "verified_ttft_ms": round(verified_ttft_ms, 1),
                "speedup_ratio": speedup_ratio,
                "drift_score": drift.drift_score,
                "drift_status": drift.status,
                "correction_needed": drift.correction_needed,
            },
        )
