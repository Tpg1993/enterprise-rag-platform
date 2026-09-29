"""Hierarchical Multi-Agent RAG Strategy (Phase 37).

Orchestrates a specialized multi-agent team in LangGraph under a central Supervisor
to decompose, research, aggregate relational metrics, verify compliance, and synthesize answers.
"""

import logging
import time
import uuid

from src.agents.hierarchical.graph import build_hierarchical_multi_agent_graph
from src.agents.hierarchical.state import HierarchicalTeamState
from src.config.pricing import calculate_llm_cost
from src.rag.base import BaseRAGStrategy, Citation, RAGRequest, RAGResponse

logger = logging.getLogger("HierarchicalMultiAgentStrategy")


class HierarchicalMultiAgentStrategy(BaseRAGStrategy):
    """Production-grade Hierarchical Multi-Agent Strategy orchestrated by LangGraph."""

    def __init__(self) -> None:
        self.app = build_hierarchical_multi_agent_graph()

    async def execute(self, request: RAGRequest) -> RAGResponse:
        """Executes full multi-agent team workflow and returns synthesized response."""
        start_time = time.perf_counter()

        initial_state: HierarchicalTeamState = {
            "query": request.query,
            "tenant_id": request.tenant_id,
            "plan": [],
            "current_step": 0,
            "research_results": [],
            "sql_results": [],
            "critique_notes": [],
            "final_answer": "",
            "citations": [],
            "agent_traces": [],
            "iteration": 0,
            "next_worker": "SUPERVISOR",
        }

        # Invoke LangGraph stateful multi-agent execution
        result_state: HierarchicalTeamState = await self.app.ainvoke(initial_state)

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Construct citations
        citations = []
        for c in result_state.get("citations", []):
            citations.append(
                Citation(
                    document_id=c.get("document_id", "doc_hierarchical"),
                    filename=c.get("source", "Knowledge Base"),
                    chunk_id=c.get("chunk_id", f"chk_{uuid.uuid4().hex[:8]}"),
                    content_snippet=c.get("content_snippet", ""),
                    page_number=c.get("page", 1),
                    relevance_score=c.get("relevance_score", 0.92),
                )
            )

        # Calculate estimated token consumption and costs
        answer = result_state.get("final_answer", "No synthesis generated.")
        prompt_tokens = len(request.query.split()) * 4 + 200
        completion_tokens = len(answer.split()) * 2
        cost_usd = calculate_llm_cost(
            model="sarvam-105b",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return RAGResponse(
            answer=answer,
            query=request.query,
            rag_strategy="Hierarchical-Multi-Agent",
            citations=citations,
            latency_ms=elapsed_ms,
            estimated_cost_usd=cost_usd,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            metadata={
                "plan": result_state.get("plan", []),
                "agent_traces": result_state.get("agent_traces", []),
                "total_iterations": result_state.get("iteration", 1),
            },
        )
