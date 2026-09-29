"""Automated Claim-Level Hallucination Guardrail & Natural Language Inference (NLI) Fact-Checker."""

import logging
import re
import uuid
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ClaimItem(BaseModel):
    """Schema representing an individual atomic factual claim extracted from an answer."""

    claim_id: str
    text: str
    verdict: str = Field(..., description="SUPPORTED, NEUTRAL, or CONTRADICTED")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    grounding_chunk_ids: list[str] = Field(default_factory=list)
    explanation: str | None = None


class FactCheckReport(BaseModel):
    """Structured report produced by the NLI Fact-Checker."""

    total_claims: int
    supported_claims: int
    contradicted_claims: int
    neutral_claims: int
    grounding_score: float = Field(default=1.0, ge=0.0, le=1.0)
    risk_level: str = Field(default="LOW", description="LOW, MEDIUM, or HIGH")
    claims: list[ClaimItem] = Field(default_factory=list)
    corrected_answer: str | None = None


class ClaimExtractor:
    """Decomposes generative answers into discrete, atomic factual statements."""

    # Conversational filler phrases that do not represent factual propositions
    FILLER_PATTERNS = [
        r"^(sure|certainly|of course|hello|hi|greetings),?\s*",
        r"^(based on (the )?(provided|retrieved|context|documents)[\w\s]*,?\s*)",
        r"^(according to (the )?[\w\s]*,?\s*)",
        r"^(in summary|in conclusion|overall|to summarize),?\s*",
        r"^(here is (the|an)?[\w\s]*:\s*)",
    ]

    def extract_claims(self, text: str) -> list[str]:
        """Extracts individual factual sentences/clauses from answer text."""
        if not text or not text.strip():
            return []

        # Split on sentence boundaries (. ! ?) while handling list item markers
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
        claims: list[str] = []

        for raw_s in raw_sentences:
            s_clean = raw_s.strip()
            # Remove list numbering prefixes like "1. ", "- ", "* "
            s_clean = re.sub(r"^(\d+[\.\)]|[-*•])\s*", "", s_clean).strip()

            # Strip conversational preamble
            for pattern in self.FILLER_PATTERNS:
                s_clean = re.sub(pattern, "", s_clean, flags=re.IGNORECASE).strip()

            if len(s_clean.split()) >= 4:  # At least 4 words to constitute an assertive claim
                claims.append(s_clean)

        return claims if claims else [text.strip()]


class NLIFactChecker:
    """Verifies atomic propositions against retrieved context chunks using NLI heuristics."""

    def __init__(self, extractor: ClaimExtractor | None = None) -> None:
        self.extractor = extractor or ClaimExtractor()

    def _compute_overlap_confidence(
        self, claim: str, context_text: str
    ) -> tuple[float, list[str]]:
        """Calculates semantic-token overlap and extracts matching keywords."""
        claim_words = set(re.findall(r"\w{3,}", claim.lower()))
        context_words = set(re.findall(r"\w{3,}", context_text.lower()))

        if not claim_words:
            return 0.0, []

        intersection = claim_words.intersection(context_words)
        overlap_ratio = len(intersection) / len(claim_words)
        return overlap_ratio, list(intersection)

    def verify_claim(
        self, claim: str, chunks: list[dict[str, Any]]
    ) -> ClaimItem:
        """Evaluates a single claim against available context chunks."""
        best_overlap = 0.0
        best_chunk_id: str | None = None
        claim_id = f"claim_{uuid.uuid4().hex[:8]}"

        # Look for direct negation or contradiction tripwires
        c_lower = claim.lower()
        has_negative_assertion = any(
            neg in c_lower for neg in ("never", "nowhere", "fake", "disproved", "cannot", "refused")
        )

        for c in chunks:
            content = c.get("content", "")
            chunk_id = c.get("chunk_id") or c.get("id") or "chunk_unknown"
            overlap, _ = self._compute_overlap_confidence(claim, content)

            if overlap > best_overlap:
                best_overlap = overlap
                best_chunk_id = str(chunk_id)

        # Classification thresholds
        if best_overlap >= 0.45:
            verdict = "SUPPORTED"
            confidence = min(round(best_overlap + 0.35, 2), 1.0)
            explanation = f"Grounded in context with {int(best_overlap * 100)}% key term overlap."
            matched_chunks = [best_chunk_id] if best_chunk_id else []
        elif best_overlap >= 0.20:
            verdict = "NEUTRAL"
            confidence = 0.60
            explanation = "Partially supported with moderate contextual overlap."
            matched_chunks = [best_chunk_id] if best_chunk_id else []
        else:
            if has_negative_assertion:
                verdict = "CONTRADICTED"
                confidence = 0.85
                explanation = "Direct contradiction or unsupported absolute claim."
            else:
                verdict = "NEUTRAL"
                confidence = 0.40
                explanation = "Unverified statement with minimal grounding in retrieved sources."
            matched_chunks = []

        return ClaimItem(
            claim_id=claim_id,
            text=claim,
            verdict=verdict,
            confidence=confidence,
            grounding_chunk_ids=matched_chunks,
            explanation=explanation,
        )

    def verify(
        self,
        answer: str,
        context_chunks: list[dict[str, Any]],
        strict_correction: bool = False,
    ) -> FactCheckReport:
        """Runs end-to-end claim extraction and NLI verification on answer."""
        claims_text = self.extractor.extract_claims(answer)
        if not claims_text:
            return FactCheckReport(
                total_claims=0,
                supported_claims=0,
                contradicted_claims=0,
                neutral_claims=0,
                grounding_score=1.0,
                risk_level="LOW",
                claims=[],
                corrected_answer=answer,
            )

        claim_items: list[ClaimItem] = []
        supported = 0
        contradicted = 0
        neutral = 0

        for c_text in claims_text:
            item = self.verify_claim(c_text, context_chunks)
            claim_items.append(item)
            if item.verdict == "SUPPORTED":
                supported += 1
            elif item.verdict == "CONTRADICTED":
                contradicted += 1
            else:
                neutral += 1

        total = len(claim_items)
        # Weighted score: supported=1.0, neutral=0.5, contradicted=0.0
        grounding_score = round(
            (supported * 1.0 + neutral * 0.5 + contradicted * 0.0) / max(total, 1), 3
        )

        if grounding_score >= 0.80 and contradicted == 0:
            risk = "LOW"
        elif grounding_score >= 0.50 and contradicted <= 1:
            risk = "MEDIUM"
        else:
            risk = "HIGH"

        # Optional strict correction: strip contradicted claims from answer
        corrected_answer = answer
        if strict_correction and contradicted > 0:
            contradicted_texts = [ci.text for ci in claim_items if ci.verdict == "CONTRADICTED"]
            for bad_text in contradicted_texts:
                corrected_answer = corrected_answer.replace(bad_text, "").strip()

        return FactCheckReport(
            total_claims=total,
            supported_claims=supported,
            contradicted_claims=contradicted,
            neutral_claims=neutral,
            grounding_score=grounding_score,
            risk_level=risk,
            claims=claim_items,
            corrected_answer=corrected_answer,
        )


_checker: NLIFactChecker | None = None


def get_fact_checker() -> NLIFactChecker:
    """Singleton provider for NLIFactChecker."""
    global _checker
    if _checker is None:
        _checker = NLIFactChecker()
    return _checker
