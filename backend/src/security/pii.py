"""Presidio PII Redactor for SSNs, credit cards, emails, phone numbers, and API tokens."""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Fallback regex patterns for common PII
PII_PATTERNS = {
    "EMAIL": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    "PHONE": r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
    "API_KEY": r"\b(?:sk-[a-zA-Z0-9]{24,32}|Bearer\s+[a-zA-Z0-9_.-]+)\b",
}


class PresidioPIIRedactor:
    """PII detection and redaction engine enforcing Zero Trust data privacy."""

    def __init__(self, use_presidio: bool = True):
        self.use_presidio = use_presidio
        self._analyzer = None
        self._anonymizer = None

        if use_presidio:
            try:
                from presidio_analyzer import AnalyzerEngine
                from presidio_anonymizer import AnonymizerEngine

                self._analyzer = AnalyzerEngine()
                self._anonymizer = AnonymizerEngine()
                logger.info("Presidio Analyzer & Anonymizer loaded successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize Presidio ({e}). Using regex PII redactor.")

    def redact(self, text: str) -> tuple[str, int]:
        """Redacts PII entities from text and returns (anonymized_text, redacted_count)."""
        if not text:
            return "", 0

        if self._analyzer is not None and self._anonymizer is not None:
            try:
                results = self._analyzer.analyze(text=text, language="en")
                if results:
                    anonymized = self._anonymizer.anonymize(text=text, analyzer_results=results)
                    return anonymized.text, len(results)
            except Exception as e:
                logger.warning(f"Presidio redaction failed ({e}). Falling back to regex.")

        # Regex fallback
        anonymized_text = text
        total_redacted = 0

        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, anonymized_text)
            if matches:
                total_redacted += len(matches)
                anonymized_text = re.sub(pattern, f"[REDACTED_{pii_type}]", anonymized_text)

        return anonymized_text, total_redacted
