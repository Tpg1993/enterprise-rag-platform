"""FastAPI routes for Phase 9 RAGAS and DeepEval Evaluation Suite."""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.evaluation.engine import RAGEvaluationEngine
from src.rag import RAGRequest, get_rag_strategy

router = APIRouter(tags=["Evaluations"])

eval_engine = RAGEvaluationEngine()


class EvaluationRequest(BaseModel):
    query: str = Field(..., description="Target query text to evaluate")
    ground_truth: str | None = Field(default=None, description="Optional ground truth answer")
    rag_strategy: str = Field(default="Basic", description="Target RAG strategy name")
    tenant_id: str = Field(default="default_tenant", description="Tenant ID")


class EvaluationResponse(BaseModel):
    strategy: str
    query: str
    context_precision: float
    context_recall: float
    faithfulness: float
    answer_relevancy: float
    overall_score: float
    latency_ms: float
    total_cost_usd: float
    answer: str
    contexts_count: int


@router.post("/evaluations/run", response_model=EvaluationResponse)
async def run_evaluation(payload: EvaluationRequest) -> EvaluationResponse:
    """Executes a full evaluation run on a target RAG strategy calculating
    Quality, Latency, and Cost.
    """
    strategy = get_rag_strategy(payload.rag_strategy)
    rag_req = RAGRequest(
        query=payload.query,
        tenant_id=payload.tenant_id,
        rag_strategy=payload.rag_strategy,
    )
    rag_res = await strategy.execute(rag_req)

    contexts = [c.content_snippet for c in rag_res.citations]
    eval_res = await eval_engine.evaluate(
        query=payload.query,
        answer=rag_res.answer,
        contexts=contexts,
        ground_truth=payload.ground_truth,
        strategy=rag_res.rag_strategy,
        latency_ms=rag_res.latency_ms,
        total_cost_usd=rag_res.estimated_cost_usd,
    )

    from src.storage.history import get_history_store

    get_history_store().save_evaluation(
        user_id="usr_default",
        tenant_id=payload.tenant_id,
        strategy=eval_res.strategy,
        query=eval_res.query,
        answer=rag_res.answer,
        context_precision=eval_res.context_precision,
        context_recall=eval_res.context_recall,
        faithfulness=eval_res.faithfulness,
        answer_relevancy=eval_res.answer_relevancy,
        overall_score=eval_res.overall_score,
        latency_ms=eval_res.latency_ms,
        total_cost_usd=eval_res.total_cost_usd,
        contexts_count=len(contexts),
    )

    return EvaluationResponse(
        strategy=eval_res.strategy,
        query=eval_res.query,
        context_precision=eval_res.context_precision,
        context_recall=eval_res.context_recall,
        faithfulness=eval_res.faithfulness,
        answer_relevancy=eval_res.answer_relevancy,
        overall_score=eval_res.overall_score,
        latency_ms=eval_res.latency_ms,
        total_cost_usd=eval_res.total_cost_usd,
        answer=rag_res.answer,
        contexts_count=len(contexts),
    )


@router.get("/evaluations/history")
async def get_evaluation_history(
    tenant_id: str = "default_tenant",
    strategy: str | None = None,
    limit: int = 50,
):
    """Returns persistent historical RAG evaluation runs."""
    from src.storage.history import get_history_store

    runs = get_history_store().list_evaluation_history(
        tenant_id=tenant_id, strategy=strategy, limit=limit
    )
    return {
        "tenant_id": tenant_id,
        "total_runs": len(runs),
        "history": runs,
    }


class GenerateSyntheticRequest(BaseModel):
    tenant_id: str = "default_tenant"
    count: int = Field(default=5, ge=1, le=25)


@router.post("/evaluations/generate-synthetic")
async def generate_synthetic_dataset(payload: GenerateSyntheticRequest):
    """Generates an autonomous synthetic QA evaluation dataset from tenant documents."""
    from src.evaluation.synthetic_generator import SyntheticQAGenerator

    gen = SyntheticQAGenerator()
    pairs = gen.generate_for_tenant(tenant_id=payload.tenant_id, target_count=payload.count)
    return {
        "status": "SUCCESS",
        "tenant_id": payload.tenant_id,
        "total_generated": len(pairs),
        "samples": [p.model_dump() for p in pairs],
    }


class TenantBenchmarkRequest(BaseModel):
    tenant_id: str = "default_tenant"
    strategies: list[str] = Field(default_factory=lambda: ["Basic", "Hybrid", "MMR"])
    num_samples: int = Field(default=4, ge=1, le=10)


@router.post("/evaluations/tenant-benchmark")
async def run_tenant_benchmark(payload: TenantBenchmarkRequest):
    """Executes multi-strategy benchmark against tenant documents and returns ranked leaderboard.
    """
    from src.evaluation.tenant_benchmark import TenantBenchmarkRunner

    runner = TenantBenchmarkRunner()
    report = await runner.run_benchmark(
        tenant_id=payload.tenant_id,
        strategies=payload.strategies,
        num_samples=payload.num_samples,
    )
    return report.model_dump()


