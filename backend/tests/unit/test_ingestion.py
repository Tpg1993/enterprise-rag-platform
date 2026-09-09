"""Unit tests for text cleaner, PII redactor, and CDC engine."""

from src.ingestion import ChangeDataCaptureEngine, PIIRedactor, TextCleaner


def test_text_cleaner():
    raw = "  Hello \t world!\n\n\n\nNew paragraph.  "
    clean = TextCleaner.clean_text(raw)
    assert clean == "Hello world!\n\nNew paragraph."


def test_pii_redactor():
    redactor = PIIRedactor(enabled=True)
    text = "Contact Alice at alice@example.com or 555-123-4567, SSN 123-45-6789."
    redacted = redactor.redact(text)
    assert "alice@example.com" not in redacted
    assert "123-45-6789" not in redacted


def test_cdc_engine():
    cdc = ChangeDataCaptureEngine()
    bytes_v1 = b"Version 1 document content"
    checksum_v1 = cdc.compute_checksum(bytes_v1)

    # First inspection
    status1 = cdc.inspect_change("doc_1", checksum_v1)
    assert status1 == "NEW"

    cdc.record_ingestion("doc_1", checksum_v1)

    # Re-inspection with same content
    status2 = cdc.inspect_change("doc_1", checksum_v1)
    assert status2 == "UNCHANGED"

    # Inspection with modified content
    bytes_v2 = b"Version 2 document content updated"
    checksum_v2 = cdc.compute_checksum(bytes_v2)
    status3 = cdc.inspect_change("doc_1", checksum_v2)
    assert status3 == "MODIFIED"
