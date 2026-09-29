"""Semantic Drift Detector for Speculative RAG Execution."""

import logging
import re
from typing import Any

from src.rag.speculative.models import DriftAssessment

logger = logging.getLogger(__name__)

STOPWORDS = {
    "a", "an", "the", "in", "on", "at", "by", "for", "with", "about",
    "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "and", "but", "if", "or", "because", "as", "until", "while", "of", "at",
    "this", "that", "these", "those", "i", "we", "you", "they", "it",
}

CRITICAL_KEYWORDS = {
    "liability", "penalty", "breach", "indemnity", "unlimited", "capped",
    "sla", "uptime", "latency", "prohibited", "mandatory", "guarantee",
    "terminate", "warranty", "exclusive", "gdpr", "hipaa", "audit",
}


class SpeculativeDriftDetector:
    """Evaluates semantic divergence between rapid draft text and verified deep context."""

    def __init__(self, drift_threshold: float = 0.35) -> None:
        self.drift_threshold = drift_threshold

    def _tokenize(self, text: str) -> set[str]:
        """Cleans and extracts meaningful lowercase alphanumeric tokens."""
        words = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", text.lower())
        return {w for w in words if w not in STOPWORDS}

    def evaluate_drift(
        self,
        draft_text: str,
        verified_chunks: list[dict[str, Any]] | list[str],
    ) -> DriftAssessment:
        """Calculates token overlap and identifies missing critical clauses."""
        draft_tokens = self._tokenize(draft_text)

        # Extract text from verified chunks
        verified_texts: list[str] = []
        for ch in verified_chunks:
            if isinstance(ch, dict):
                content = ch.get("content") or ch.get("text") or ch.get("snippet", "")
                verified_texts.append(content)
            elif isinstance(ch, str):
                verified_texts.append(ch)

        combined_verified = " ".join(verified_texts)
        verified_tokens = self._tokenize(combined_verified)

        if not draft_tokens or not verified_tokens:
            return DriftAssessment(
                drift_score=0.1,
                status="ALIGNED",
                overlapping_terms=[],
                missing_critical_terms=[],
                correction_needed=False,
                metadata={"reason": "Empty draft or verified context; defaulting to aligned."},
            )

        overlapping = draft_tokens.intersection(verified_tokens)
        overlap_ratio = len(overlapping) / max(1, len(draft_tokens))

        # Raw drift score is inverse of draft token coverage in verified context
        raw_drift = round(max(0.0, min(1.0, 1.0 - overlap_ratio)), 3)

        # Check for critical keywords present in verified context but missing in draft
        missing_critical = sorted(
            [kw for kw in CRITICAL_KEYWORDS if kw in verified_tokens and kw not in draft_tokens]
        )

        # If critical clauses are omitted, elevate drift score slightly
        adjusted_drift = raw_drift
        if missing_critical:
            adjusted_drift = min(1.0, round(raw_drift + 0.15 * len(missing_critical), 3))

        # Categorize status
        if adjusted_drift < self.drift_threshold:
            status = "ALIGNED"
            correction_needed = False
        elif adjusted_drift < 0.65:
            status = "MODERATE_DRIFT"
            correction_needed = True
        else:
            status = "HIGH_DRIFT"
            correction_needed = True

        return DriftAssessment(
            drift_score=adjusted_drift,
            status=status,
            overlapping_terms=sorted(list(overlapping))[:20],
            missing_critical_terms=missing_critical[:10],
            correction_needed=correction_needed,
            metadata={
                "overlap_count": len(overlapping),
                "draft_token_count": len(draft_tokens),
                "verified_token_count": len(verified_tokens),
                "raw_drift": raw_drift,
            },
        )
