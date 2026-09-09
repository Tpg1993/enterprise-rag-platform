"""PII detection and redaction module using Presidio and regex fallbacks."""

import logging
import re

logger = logging.getLogger(__name__)


class PIIRedactor:
    """Detects and redacts sensitive PII (SSNs, emails, phone numbers, credit cards)."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._presidio_analyzer = None
        self._presidio_anonymizer = None

        if self.enabled:
            try:
                from presidio_analyzer import AnalyzerEngine
                from presidio_anonymizer import AnonymizerEngine

                self._presidio_analyzer = AnalyzerEngine()
                self._presidio_anonymizer = AnonymizerEngine()
            except Exception as e:
                logger.info(f"Presidio model not loaded ({e}). Using robust regex fallbacks.")

    def redact(self, text: str) -> str:
        if not self.enabled or not text:
            return text

        if self._presidio_analyzer and self._presidio_anonymizer:
            try:
                results = self._presidio_analyzer.analyze(text=text, language="en")
                anonymized = self._presidio_anonymizer.anonymize(
                    text=text, analyzer_results=results
                )
                return str(anonymized.text)
            except Exception as e:
                logger.warning(f"Presidio analysis failed: {e}. Falling back to regex.")

        # Robust Regex Redaction Fallbacks
        redacted = text
        # Email
        redacted = re.sub(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "<REDACTED_EMAIL>", redacted
        )
        # SSN (US)
        redacted = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "<REDACTED_SSN>", redacted)
        # Phone
        redacted = re.sub(
            r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
            "<REDACTED_PHONE>",
            redacted,
        )
        # Credit Card
        redacted = re.sub(r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "<REDACTED_CREDIT_CARD>", redacted)

        return redacted
