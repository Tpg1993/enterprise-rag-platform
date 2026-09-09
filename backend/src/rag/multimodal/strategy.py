"""Multimodal RAG Strategy combining text, structured tables, and visual image figures."""

import logging
import time
import uuid

from src.context.builder import ContextBuilder
from src.embeddings.base import BaseEmbeddingProvider
from src.embeddings.factory import get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)

TABLE_KEYWORDS = {
    "table",
    "tables",
    "tabular",
    "row",
    "rows",
    "column",
    "columns",
    "cells",
    "grid",
    "matrix",
    "metrics",
    "stats",
    "financials",
    "breakdown",
    "quarterly",
    "revenue",
    "summary table",
}

VISUAL_KEYWORDS = {
    "figure",
    "figures",
    "image",
    "images",
    "picture",
    "pictures",
    "diagram",
    "diagrams",
    "chart",
    "charts",
    "graph",
    "graphs",
    "visual",
    "visuals",
    "screenshot",
    "plot",
    "illustration",
}


class MultimodalRAGStrategy(BaseRAGStrategy):
    """Multimodal RAG retrieving and synthesizing across text, tables, and visual figures."""

    def __init__(
        self,
        vector_store: QdrantVectorStore | None = None,
        embedding_provider: BaseEmbeddingProvider | None = None,
        embedding_provider_name: str = "bge-m3",
        llm_provider: LLMProvider | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        self.vector_store = vector_store or get_vector_store()
        self.embedding_provider = embedding_provider or get_embedding_provider(embedding_provider_name)
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.llm_provider = llm_provider or get_llm_provider()

    def _is_table_focused(self, query: str) -> bool:
        tokens = set(query.lower().split())
        return bool(tokens & TABLE_KEYWORDS)

    def _is_visual_focused(self, query: str) -> bool:
        tokens = set(query.lower().split())
        return bool(tokens & VISUAL_KEYWORDS)

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        query = request.query.strip()
        tenant_id = request.tenant_id

        is_table_query = self._is_table_focused(query)
        is_visual_query = self._is_visual_focused(query)

        # 1. Generate query embedding
        query_vector = self.embedding_provider.embed_query(query)

        # 2. Fetch candidate chunks from vector store
        fetch_k = max(request.top_k * 2, 10)
        candidates = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=tenant_id,
            top_k=fetch_k,
        )

        # 3. Modality-aware reranking and boosting
        scored_candidates = []
        for hit in candidates:
            payload = hit.get("payload", {})
            chunk_type = payload.get("chunk_type", hit.get("metadata", {}).get("chunk_type", "text"))
            content = hit.get("content", "")
            base_score = float(hit.get("score", 0.0))
            boost = 0.0

            if is_table_query and (
                chunk_type == "table"
                or "[Structured Table:" in content
                or ("|" in content and "---" in content)
            ):
                boost += 0.25

            if is_visual_query and (
                chunk_type == "image_figure"
                or "[Figure:" in content
                or "[Visual Document:" in content
            ):
                boost += 0.25

            boosted_score = min(base_score + boost, 1.0)
            updated_hit = dict(hit)
            updated_hit["score"] = boosted_score
            scored_candidates.append((boosted_score, updated_hit))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        top_hits = [hit for _, hit in scored_candidates[: request.top_k]]

        # 4. Context assembly & citation extraction
        context_str, citations = self.context_builder.build_context(
            top_hits,
            max_context_tokens=request.max_context_tokens,
        )

        # Refine citation titles with table/figure identifiers if detected
        for idx, hit in enumerate(top_hits):
            if idx < len(citations):
                payload = hit.get("payload", {})
                chunk_type = payload.get("chunk_type", hit.get("metadata", {}).get("chunk_type"))
                if chunk_type == "table":
                    tbl_idx = payload.get("table_index", 1)
                    citations[idx].section_title = f"Table {tbl_idx} (Tabular Data)"
                elif chunk_type == "image_figure":
                    img_idx = payload.get("image_index", 1)
                    citations[idx].section_title = f"Figure {img_idx} (Visual Diagram)"

        # 5. Build prompt
        prompts = self.prompt_builder.build_prompt(query, context_str)

        # 6. Synthesize answer via Sarvam-105B or MockLLM
        llm_res = await self.llm_provider.agenerate(
            prompt=prompts["user"],
            system_prompt=prompts["system"],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return RAGResponse(
            answer=llm_res.content,
            query=request.query,
            rag_strategy="Multimodal",
            citations=citations,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            estimated_cost_usd=llm_res.estimated_cost_usd,
            model=llm_res.model_name,
            trace_id=trace_id,
            tenant_id=tenant_id,
        )
