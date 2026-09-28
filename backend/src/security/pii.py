"""Presidio PII Redactor for SSNs, credit cards, emails, phone numbers, IP addresses, and API keys."""

import logging
import re
from typing import Any
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Fallback regex patterns for common enterprise PII entities
PII_PATTERNS = {
    "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
    "API_KEY": r"\b(?:sk-[a-zA-Z0-9]{24,32}|Bearer\s+[a-zA-Z0-9_.-]+)\b",
    "IP_ADDRESS": r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b",
}


class PIIDetectionReport(BaseModel):
    """Structured report of PII detection and redaction operations."""

    original_text: str
    redacted_text: str
    total_redacted: int
    has_pii: bool
    entities_found: dict[str, int] = Field(default_factory=dict)
    entity_map: dict[str, str] = Field(default_factory=dict)


class PresidioPIIRedactor:
    """PII detection and redaction engine enforcing Zero Trust data privacy."""

    def __init__(self, use_presidio: bool = True):
        self.use_presidio = use_presidio
        self._analyzer: Any = None
        self._anonymizer: Any = None

        if use_presidio:
            try:
                from presidio_analyzer import AnalyzerEngine
                from presidio_anonymizer import AnonymizerEngine

                self._analyzer = AnalyzerEngine()
                self._anonymizer = AnonymizerEngine()
                logger.info("Presidio Analyzer & Anonymizer loaded successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Presidio ({e}). Using regex PII redactor.")

    def analyze_and_redact(self, text: str) -> PIIDetectionReport:
        """Comprehensive analysis producing structured PIIDetectionReport."""
        if not text:
            return PIIDetectionReport(
                original_text="",
                redacted_text="",
                total_redacted=0,
                has_pii=False,
                entities_found={},
                entity_map={},
            )

        entities_found: dict[str, int] = {}
        entity_map: dict[str, str] = {}

        # 1. Try Presidio engine if initialized
        if self._analyzer is not None and self._anonymizer is not None:
            try:
                results = self._analyzer.analyze(text=text, language="en")
                if results:
                    for res in results:
                        etype = res.entity_type
                        entities_found[etype] = entities_found.get(etype, 0) + 1
                    anonymized = self._anonymizer.anonymize(text=text, analyzer_results=results)
                    return PIIDetectionReport(
                        original_text=text,
                        redacted_text=anonymized.text,
                        total_redacted=len(results),
                        has_pii=True,
                        entities_found=entities_found,
                        entity_map=entity_map,
                    )
            except Exception as e:
                logger.warning(f"Presidio redaction failed ({e}). Falling back to regex.")

        # 2. Deterministic Regex Redaction
        anonymized_text = text
        total_redacted = 0
        tag_counter = 1

        for pii_type, pattern in PII_PATTERNS.items():
            matches = list(re.finditer(pattern, anonymized_text))
            if matches:
                entities_found[pii_type] = len(matches)
                total_redacted += len(matches)
                for m in matches:
                    val = m.group(0)
                    placeholder = f"[REDACTED_{pii_type}_{tag_counter}]"
                    entity_map[placeholder] = val
                    tag_counter += 1
                anonymized_text = re.sub(pattern, f"[REDACTED_{pii_type}]", anonymized_text)

        return PIIDetectionReport(
            original_text=text,
            redacted_text=anonymized_text,
            total_redacted=total_redacted,
            has_pii=total_redacted > 0,
            entities_found=entities_found,
            entity_map=entity_map,
        )

    def redact(self, text: str) -> tuple[str, int]:
        """Backward-compatible tuple return: (anonymized_text, total_redacted_count)."""
        report = self.analyze_and_redact(text)
        return report.redacted_text, report.total_redacted

    def restore_redactions(self, text: str, entity_map: dict[str, str]) -> str:
        """Restores original values from entity map if authorized."""
        restored = text
        for placeholder, original in entity_map.items():
            restored = restored.replace(placeholder, original)
        return restored


_pii_redactor_instance: PresidioPIIRedactor | None = None


def get_pii_redactor() -> PresidioPIIRedactor:
    """Returns singleton PresidioPIIRedactor instance."""
    global _pii_redactor_instance
    if _pii_redactor_instance is None:
        _pii_redactor_instance = PresidioPIIRedactor()
    return _pii_redactor_instance
