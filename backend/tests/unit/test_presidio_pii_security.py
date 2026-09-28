"""Unit tests for Presidio PII Redactor & Anonymization Engine."""

import pytest
from src.security.pii import (
    PIIDetectionReport,
    PresidioPIIRedactor,
    get_pii_redactor,
)


def test_pii_singleton():
    """Verifies that get_pii_redactor returns a singleton instance."""
    redactor1 = get_pii_redactor()
    redactor2 = get_pii_redactor()
    assert redactor1 is redactor2
    assert isinstance(redactor1, PresidioPIIRedactor)


def test_pii_no_entities_unaltered():
    """Verifies that standard text without PII is unaltered."""
    redactor = PresidioPIIRedactor(use_presidio=False)
    text = "Sarvam AI is developing state-of-the-art language models for India."
    report = redactor.analyze_and_redact(text)
    assert report.has_pii is False
    assert report.total_redacted == 0
    assert report.redacted_text == text


def test_pii_email_redaction():
    """Verifies email address detection and redaction."""
    redactor = PresidioPIIRedactor(use_presidio=False)
    text = "Contact our lead architect at contact.user@sarvam.ai for enterprise support."
    report = redactor.analyze_and_redact(text)
    assert report.has_pii is True
    assert "[REDACTED_EMAIL" in report.redacted_text
    assert "contact.user@sarvam.ai" not in report.redacted_text
    assert report.entities_found.get("EMAIL", 0) >= 1


def test_pii_ssn_and_phone_redaction():
    """Verifies SSN and US phone number redactions."""
    redactor = PresidioPIIRedactor(use_presidio=False)
    text = "Client SSN is 123-45-6789 and mobile is 555-867-5309."
    report = redactor.analyze_and_redact(text)
    assert report.has_pii is True
    assert "123-45-6789" not in report.redacted_text
    assert "555-867-5309" not in report.redacted_text
    assert "[REDACTED_SSN]" in report.redacted_text
    assert "[REDACTED_PHONE]" in report.redacted_text


def test_pii_credit_card_and_ip_redaction():
    """Verifies credit card numbers and IP address redactions."""
    redactor = PresidioPIIRedactor(use_presidio=False)
    text = "Billing card 4532 1234 5678 9010 from internal server 192.168.1.50."
    report = redactor.analyze_and_redact(text)
    assert report.has_pii is True
    assert "4532 1234 5678 9010" not in report.redacted_text
    assert "192.168.1.50" not in report.redacted_text
    assert "[REDACTED_CREDIT_CARD]" in report.redacted_text
    assert "[REDACTED_IP_ADDRESS]" in report.redacted_text


def test_pii_api_key_redaction():
    """Verifies API secret key redaction."""
    redactor = PresidioPIIRedactor(use_presidio=False)
    text = "Use secret token sk-abcdef1234567890abcdef12 for Sarvam API."
    report = redactor.analyze_and_redact(text)
    assert report.has_pii is True
    assert "sk-abcdef1234567890abcdef12" not in report.redacted_text
    assert "[REDACTED_API_KEY]" in report.redacted_text


def test_pii_backward_compatible_redact_tuple():
    """Verifies backward compatible redact() method returning (text, count)."""
    redactor = PresidioPIIRedactor(use_presidio=False)
    text = "Customer email is john@corp.com with phone 555-123-4567."
    anonymized, count = redactor.redact(text)
    assert count == 2
    assert "john@corp.com" not in anonymized
    assert "555-123-4567" not in anonymized
