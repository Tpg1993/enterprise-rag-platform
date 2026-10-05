"""Tool-Calling Agentic RAG Strategy (Strategy 19).

Integrates dynamic tool execution (mathematical calculation, SLA penalties,
system time oracles, and OpenAPI functions) with grounded vector retrieval.
"""

import logging
import re
import time
import uuid
from typing import Any

from src.agents.tools.models import ToolExecutionResult
from src.agents.tools.registry import DynamicToolRegistry, get_tool_registry
from src.config.pricing import calculate_llm_cost
from src.context.builder import ContextBuilder
from src.embeddings import BaseEmbeddingProvider, get_embedding_provider
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, RAGRequest, RAGResponse
from src.reranking import BaseReranker, get_reranker
from src.retrieval.vector_store import QdrantVectorStore, get_vector_store

logger = logging.getLogger(__name__)


class ToolCallingAgenticRAGStrategy(BaseRAGStrategy):
    """Strategy 19: Tool-Calling Agentic RAG combining live functions and vector retrieval."""

    def __init__(
        self,
        embedding_provider: BaseEmbeddingProvider | None = None,
        vector_store: QdrantVectorStore | None = None,
        llm_provider: LLMProvider | None = None,
        tool_registry: DynamicToolRegistry | None = None,
        reranker: BaseReranker | None = None,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
    ):
        self.embedding_provider = embedding_provider or get_embedding_provider()
        self.vector_store = vector_store or get_vector_store()
        self.llm_provider = llm_provider or get_llm_provider()
        self.tool_registry = tool_registry or get_tool_registry()
        self.reranker = reranker or get_reranker()
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()

    def _detect_and_prepare_tools(self, query: str) -> list[tuple[str, dict[str, Any]]]:
        """Identifies applicable tools and extracts structured arguments from the query."""
        tool_calls: list[tuple[str, dict[str, Any]]] = []
        q_lower = query.lower()

        # 1. SLA Penalty Calculator
        sla_words = ("downtime", "sla penalty", "credit penalty", "outage penalty")
        if any(w in q_lower for w in sla_words):
            # Extract hours and rate if present
            hours_match = re.search(r"(\d+(\.\d+)?)\s*(?:hours?|hrs?)", q_lower)
            hours = float(hours_match.group(1)) if hours_match else 2.5
            rate_match = re.search(r"\$\s*(\d+(?:,\d+)*(?:\.\d+)?|\d+)", q_lower)
            hourly_rate = float(rate_match.group(1).replace(",", "")) if rate_match else 1200.0
            tool_calls.append(
                (
                    "calculate_sla_penalty",
                    {
                        "downtime_hours": hours,
                        "hourly_rate_usd": hourly_rate,
                        "penalty_multiplier": 1.5,
                    },
                )
            )

        # 2. General Math Calculator
        math_match = re.search(
            r"(?:calculate|eval|math|compute|what is)\s+([0-9\.\s\+\-\*\/\(\)\^\%]+)",
            query,
            flags=re.IGNORECASE,
        )
        if math_match:
            expr = math_match.group(1).strip()
            if any(op in expr for op in ("+", "-", "*", "/", "%")):
                tool_calls.append(("calculate", {"expression": expr}))

        # 3. System Time / Date Oracle
        time_words = ("what time", "current date", "today's date", "which quarter")
        if any(w in q_lower for w in time_words):
            tool_calls.append(("get_system_time", {"timezone": "UTC"}))

        # 4. Service Catalog Lookup
        for svc in ("qdrant", "neo4j", "fastapi", "redis", "sarvam-105b"):
            if svc in q_lower:
                tool_calls.append(("query_service_catalog", {"service_name": svc}))
                break

        # 5. Unit Converter
        unit_match = re.search(
            r"convert\s+(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+to\s+([a-zA-Z]+)",
            q_lower,
        )
        if unit_match:
            val = float(unit_match.group(1))
            from_u = unit_match.group(2)
            to_u = unit_match.group(3)
            tool_calls.append(
                (
                    "unit_converter",
                    {"value": val, "from_unit": from_u, "to_unit": to_u},
                )
            )

        return tool_calls

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"

        # 1. Detect and execute agentic tools
        detected = self._detect_and_prepare_tools(request.query)
        tool_results: list[ToolExecutionResult] = []

        for tool_name, args in detected:
            res = await self.tool_registry.aexecute_tool(tool_name, args)
            tool_results.append(res)

        # 2. Vector Retrieval & Grounding Context
        query_vector = self.embedding_provider.embed_query(request.query)
        raw_hits = self.vector_store.search(
            query_vector=query_vector,
            tenant_id=request.tenant_id,
            top_k=max(request.top_k, 5),
        )

        reranked_hits = self.reranker.rerank(
            query=request.query,
            hits=raw_hits,
            top_n=request.top_k,
        )

        context_str, citations = self.context_builder.build_context(
            reranked_hits, max_context_tokens=request.max_context_tokens
        )

        # 3. Format Tool Observations for Prompt Grounding
        tool_context_blocks = []
        for tr in tool_results:
            if tr.success:
                tool_context_blocks.append(
                    f"TOOL OBSERVATION [{tr.tool_name}]:\n"
                    f"Output: {tr.output}\n"
                    f"Execution Latency: {tr.latency_ms:.1f}ms"
                )
            else:
                tool_context_blocks.append(
                    f"TOOL OBSERVATION [{tr.tool_name}]: ERROR: {tr.error}"
                )

        combined_context = context_str
        if tool_context_blocks:
            combined_context = (
                "--- LIVE TOOL OBSERVATIONS ---\n"
                + "\n\n".join(tool_context_blocks)
                + "\n\n--- RETRIEVED KNOWLEDGE BASE CONTEXT ---\n"
                + context_str
            )

        # 4. Prompt Generation and LLM Synthesis
        prompts = self.prompt_builder.build_prompt(request.query, combined_context)
        directive = (
            "\n\nTOOL-CALLING AGENT DIRECTIVE: You have access to deterministic tool outputs "
            "and vector context. Prioritize precise calculations from tool observations while "
            "maintaining complete fidelity to retrieved document citations."
        )
        system_prompt = prompts["system"] + directive

        llm_response = await self.llm_provider.agenerate(
            prompt=prompts["user"],
            system_prompt=system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        cost = calculate_llm_cost(
            model=llm_response.model_name,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
        )

        tool_exec_data = [
            {
                "tool_name": tr.tool_name,
                "call_id": tr.call_id,
                "success": tr.success,
                "output": tr.output,
                "error": tr.error,
                "latency_ms": tr.latency_ms,
            }
            for tr in tool_results
        ]

        logger.info(
            f"Tool-Calling Agentic RAG completed in {elapsed_ms:.1f}ms | "
            f"Tools executed: {len(tool_results)} | Cost: ${cost:.5f}"
        )

        return RAGResponse(
            query=request.query,
            answer=llm_response.content,
            citations=citations,
            rag_strategy="Tool-Calling-Agentic",
            latency_ms=elapsed_ms,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            estimated_cost_usd=cost,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
            model=llm_response.model_name,
            metadata={
                "tool_executions": tool_exec_data,
                "strategy": "Tool-Calling-Agentic",
                "framework": "langgraph",
            },
        )
