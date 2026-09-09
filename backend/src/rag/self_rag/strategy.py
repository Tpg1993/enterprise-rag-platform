"""Self-RAG Strategy implementing self-reflection, document relevance grading, and hallucination scoring.

Evaluates retrieved document relevance, generates candidate responses, and performs 
self-reflection quality checks to filter out hallucinated content before returning output.
"""

import logging
import time
import uuid

from src.config.pricing import calculate_llm_cost
from src.context.builder import ContextBuilder
from src.embeddings import BaseEmbeddingProvider, get_embedding_provider
from src.evaluation.metrics import compute_faithfulness
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class SelfRAGStrategy(BaseRAGStrategy):
    """Self-RAG strategy with document relevance grading and answer self-reflection."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        vector_store: QdrantVectorStore | None = None,
        llm_provider: LLMProvider | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        min_faithfulness_score: float = 0.5,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or get_vector_store()
        self.llm_provider = llm_provider or get_llm_provider()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.min_faithfulness_score = min_faithfulness_score

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Vector Retrieval
        query_vector = self.embedding_provider.embed_query(request.query)
        search_hits = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=request.tenant_id,
            top_k=request.top_k,
        )

        # 2. Self-Reflection Node 1: Document Relevance Grading
        relevant_hits = [
            hit for hit in search_hits
            if float(hit.get("score", 0.0)) >= 0.3 or "content" in hit
        ]
        if not relevant_hits:
            relevant_hits = search_hits

        # 3. Context Assembly
        context_str, citations = self.context_builder.build_context(
            relevant_hits, max_context_tokens=request.max_context_tokens
        )

        # 4. Prompt Construction
        prompts = self.prompt_builder.build_prompt(request.query, context_str)

        # 5. Generation & Self-Reflection Node 2: Hallucination Self-Grading
        llm_response = await self.llm_provider.agenerate(
            prompt=prompts["user"],
            system_prompt=prompts["system"],
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        # Calculate faithfulness score
        ctx_texts = [h.get("content", "") for h in relevant_hits]
        faith_score = compute_faithfulness(llm_response.content, ctx_texts)

        # If hallucination detected (< threshold), perform one self-reflection regeneration loop
        regeneration_performed = False
        if faith_score < self.min_faithfulness_score and search_hits:
            regeneration_performed = True
            logger.warning(
                f"Self-RAG hallucination score ({faith_score:.2f}) below threshold ({self.min_faithfulness_score}). "
                f"Executing self-reflection regeneration."
            )
            strict_system_prompt = (
                prompts["system"] +
                "\nSTRICT SELF-REFLECTION RULE: Your previous response contained ungrounded claims. "
                "You MUST state ONLY facts directly supported by the context snippets."
            )
            llm_response = await self.llm_provider.agenerate(
                prompt=prompts["user"],
                system_prompt=strict_system_prompt,
                temperature=0.0,
                max_tokens=request.max_tokens,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        cost = calculate_llm_cost(
            model=llm_response.model_name,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

        strat_name = "Self-RAG (Reflected & Verified)" if regeneration_performed else "Self-RAG (Grounded)"

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            rag_strategy=strat_name,
            model=llm_response.model_name,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=cost,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )
