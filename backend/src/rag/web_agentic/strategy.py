"""Agentic Web RAG Strategy combining internal enterprise retrieval with live web search."""

import inspect
import logging
import time
import uuid
from typing import Any

from src.context.builder import ContextBuilder
from src.embeddings.factory import get_embedding_provider
from src.llm import get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, Citation, RAGRequest, RAGResponse
from src.retrieval.vector_store import get_vector_store
from src.retrieval.web_search import BaseSearchProvider, WebSearchResult, get_search_provider

logger = logging.getLogger(__name__)

# Keywords indicating temporal, external, or live information needs
REALTIME_TRIGGER_KEYWORDS = {
    "latest",
    "current",
    "today",
    "yesterday",
    "now",
    "live",
    "recent",
    "news",
    "stock",
    "price",
    "market",
    "weather",
    "forecast",
    "trending",
    "external",
    "real-time",
    "2025",
    "2026",
    "update",
    "release",
}


class AgenticWebRAGStrategy(BaseRAGStrategy):
    """Strategy 17: Agentic Web RAG with real-time web search fallback and hybrid grounding."""

    def __init__(
        self,
        search_provider: BaseSearchProvider | None = None,
        confidence_threshold: float = 0.65,
    ) -> None:
        self.search_provider = search_provider or get_search_provider()
        self.confidence_threshold = confidence_threshold
        self.vector_store = get_vector_store()
        self.embedding_provider = get_embedding_provider()
        self.llm_provider = get_llm_provider()
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()

    def _should_trigger_web_search(
        self, query: str, internal_hits: list[dict[str, Any]], force_flag: bool
    ) -> tuple[bool, str]:
        """Evaluates whether external web retrieval should be invoked."""
        if force_flag:
            return True, "force_web_search_flag"

        q_words = set(query.lower().split())
        matched_triggers = q_words.intersection(REALTIME_TRIGGER_KEYWORDS)
        if matched_triggers:
            return True, f"temporal_keywords_detected: {list(matched_triggers)}"

        if not internal_hits:
            return True, "no_internal_documents_found"

        max_score = max((float(h.get("score", 0.0)) for h in internal_hits), default=0.0)
        if max_score < self.confidence_threshold:
            msg = (
                f"internal_confidence_below_threshold: "
                f"{max_score:.2f} < {self.confidence_threshold}"
            )
            return True, msg

        return False, "sufficient_internal_confidence"

    async def execute(self, request: RAGRequest) -> RAGResponse:
        """Executes Agentic Web RAG retrieval, optional web search, and synthesis."""
        start_time = time.perf_counter()
        trace_id = f"trace_web_{uuid.uuid4().hex[:12]}"
        force_flag = bool(request.metadata.get("force_web_search", False))

        # 1. Retrieve internal tenant chunks
        internal_hits: list[dict[str, Any]] = []
        try:
            embed_res = self.embedding_provider.embed_query(request.query)
            if inspect.isawaitable(embed_res):
                query_embedding = await embed_res
            else:
                query_embedding = embed_res

            internal_hits = self.vector_store.search(
                query_vector=query_embedding,
                tenant_id=request.tenant_id,
                top_k=request.top_k,
            )
        except Exception as exc:
            logger.warning(f"Internal vector store search failed or empty ({exc})")

        # 2. Evaluate trigger condition
        web_triggered, trigger_reason = self._should_trigger_web_search(
            query=request.query,
            internal_hits=internal_hits,
            force_flag=force_flag,
        )

        web_results: list[WebSearchResult] = []
        web_citations: list[Citation] = []

        # 3. Execute external web retrieval if triggered
        if web_triggered:
            logger.info(f"Agentic Web RAG triggered web search: reason='{trigger_reason}'")
            try:
                web_results = await self.search_provider.search(
                    query=request.query,
                    top_k=min(request.top_k, 5),
                )
            except Exception as exc:
                logger.error(f"External web search failed ({exc})")

            for idx, res in enumerate(web_results):
                web_citations.append(
                    Citation(
                        document_id=f"web_doc_{idx + 1}",
                        filename=f"Web: {res.domain}",
                        chunk_id=f"web_chunk_{idx + 1}",
                        content_snippet=res.snippet,
                        relevance_score=res.score,
                        is_web=True,
                        url=res.url,
                        domain=res.domain,
                    )
                )

        # 4. Assemble search hits for ContextBuilder
        search_hits = list(internal_hits)
        for idx, w in enumerate(web_results):
            search_hits.append(
                {
                    "chunk_id": f"web_chunk_{idx + 1}",
                    "content": (
                        f"[LIVE WEB SEARCH: {w.title} ({w.domain})]\n"
                        f"{w.snippet}\nSource URL: {w.url}"
                    ),
                    "score": w.score,
                    "filename": f"Web: {w.domain}",
                    "payload": {
                        "chunk_id": f"web_chunk_{idx + 1}",
                        "document_id": f"web_doc_{idx + 1}",
                        "filename": f"Web: {w.domain}",
                        "url": w.url,
                        "domain": w.domain,
                        "is_web": True,
                    },
                }
            )

        # Build context through ContextBuilder
        build_result = self.context_builder.build_context(
            search_hits=search_hits,
            max_context_tokens=request.max_context_tokens,
            enable_compression=request.enable_compression,
            compression_target_ratio=request.compression_target_ratio,
            query=request.query,
        )
        context_text = build_result.formatted_context

        # Collect internal citations from build_result
        all_citations: list[Citation] = []
        for c in build_result.citations:
            all_citations.append(
                Citation(
                    document_id=c.document_id,
                    filename=c.filename,
                    chunk_id=c.chunk_id,
                    content_snippet=c.content_snippet,
                    page_number=c.page_number,
                    section_title=c.section_title,
                    relevance_score=c.relevance_score,
                    bbox=c.bbox,
                    page_dimensions=c.page_dimensions,
                    is_web=False,
                )
            )
        # Append external web citations
        all_citations.extend(web_citations)

        # 5. Build Grounded Prompt
        prompts = self.prompt_builder.build_prompt(
            query=request.query,
            context=context_text,
        )

        # 6. LLM Generation
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
            rag_strategy="Agentic-Web-RAG",
            citations=all_citations,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens,
            estimated_cost_usd=round(
                (llm_res.prompt_tokens * 0.000001) + (llm_res.completion_tokens * 0.000003), 6
            ),
            model="sarvam-105b",
            trace_id=trace_id,
            tenant_id=request.tenant_id,
            compression_ratio=build_result.compression_ratio,
            tokens_saved=build_result.tokens_saved,
            metadata={
                "web_search_triggered": web_triggered,
                "trigger_reason": trigger_reason,
                "web_results_count": len(web_results),
                "web_domains": [r.domain for r in web_results],
                "internal_chunks_count": len(internal_hits),
            },
        )
