"""Security & Guardrails API router handling OPA policy inspection and Presidio PII analysis."""

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.api.schemas import FactCheckRequest, FactCheckResponse
from src.security.opa_engine import OPAEvalRequest, OPAEvalResponse, get_opa_engine
from src.security.pii import PIIDetectionReport, get_pii_redactor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Security & Guardrails"])


class SecurityInspectRequest(BaseModel):
    """Input payload to inspect against OPA policies and Presidio PII detection."""

    text: str = Field(..., description="Query or text to inspect")
    role: str = Field(default="USER", description="User role to validate against RBAC policies")
    tenant_id: str = Field(default="default_tenant", description="Tenant ID context")
    rag_strategy: str = Field(default="Basic", description="Target RAG strategy")


class SecurityInspectResponse(BaseModel):
    """Inspection result combining OPA verdict and Presidio PII report."""

    is_safe: bool
    verdict: str  # "ALLOWED" or "BLOCKED"
    block_reason: str = ""
    opa_evaluation: OPAEvalResponse
    pii_report: PIIDetectionReport


@router.post("/inspect", response_model=SecurityInspectResponse)
async def inspect_security_payload(payload: SecurityInspectRequest) -> SecurityInspectResponse:
    """Evaluates text against OPA Rego policies and detects sensitive PII entities."""
    opa_engine = get_opa_engine()
    pii_redactor = get_pii_redactor()

    opa_req = OPAEvalRequest(
        query=payload.text,
        role=payload.role,
        tenant_id=payload.tenant_id,
        rag_strategy=payload.rag_strategy,
    )
    opa_res = await opa_engine.evaluate_async(opa_req)

    pii_report = pii_redactor.analyze_and_redact(payload.text)

    is_safe = opa_res.allow
    verdict = "ALLOWED" if is_safe else "BLOCKED"

    return SecurityInspectResponse(
        is_safe=is_safe,
        verdict=verdict,
        block_reason=opa_res.block_reason,
        opa_evaluation=opa_res,
        pii_report=pii_report,
    )


@router.get("/status")
async def get_security_status() -> dict[str, Any]:
    """Returns runtime security configuration, OPA policy status, and PII guardrails."""
    return {
        "status": "active",
        "opa_guardrail": {
            "mode": "enforcing",
            "policy_package": "rag.security",
            "rego_file": "docker/opa/policies/prompt_policy.rego",
            "injection_defense": "OWASP LLM01 compliant",
        },
        "pii_redaction": {
            "engine": "Microsoft Presidio + Regex Fallbacks",
            "entities_supported": ["EMAIL", "PHONE", "SSN", "CREDIT_CARD", "API_KEY", "IP_ADDRESS"],
            "redact_on_chat": True,
        },
        "ast_sql_guardrail": {
            "engine": "sqlglot",
            "read_only_enforced": True,
            "max_rows": 1000,
            "timeout_seconds": 5.0,
        },
        "fact_checker_guardrail": {
            "engine": "NLI Entailment & Claim Extractor",
            "active": True,
            "grounding_modes": ["AUDIT", "STRICT_CORRECTION"],
        },
    }


@router.post("/fact-check", response_model=FactCheckResponse)
async def fact_check_payload(payload: FactCheckRequest) -> FactCheckResponse:
    """Verifies atomic propositions in an answer against provided context chunks."""
    from src.security.fact_checker import get_fact_checker

    checker = get_fact_checker()
    report = checker.verify(
        answer=payload.answer,
        context_chunks=payload.context_chunks,
        strict_correction=payload.strict_correction,
    )

    return FactCheckResponse(
        total_claims=report.total_claims,
        supported_claims=report.supported_claims,
        contradicted_claims=report.contradicted_claims,
        neutral_claims=report.neutral_claims,
        grounding_score=report.grounding_score,
        risk_level=report.risk_level,
        claims=[c.model_dump() for c in report.claims],
        corrected_answer=report.corrected_answer,
    )
