"""Unit tests for Multi-Level ABAC Chunk Masking and Differential Privacy Redaction."""

from src.context.builder import ContextBuilder
from src.security.abac_masker import (
    ABACChunkMasker,
    ClassificationTag,
    ClearanceLevel,
    get_abac_masker,
)


def test_clearance_hierarchy():
    """Verifies clearance level numeric hierarchy and string parsing."""
    assert ClearanceLevel.ADMIN > ClearanceLevel.ANALYST
    assert ClearanceLevel.ANALYST > ClearanceLevel.USER
    assert ClearanceLevel.USER > ClearanceLevel.VIEWER

    assert ClearanceLevel.from_str("admin") == ClearanceLevel.ADMIN
    assert ClearanceLevel.from_str("lead_analyst") == ClearanceLevel.ANALYST
    assert ClearanceLevel.from_str("viewer") == ClearanceLevel.VIEWER
    assert ClearanceLevel.from_str("unknown") == ClearanceLevel.USER


def test_classification_tag_normalization():
    """Verifies normalization of classification strings."""
    assert ClassificationTag.from_str("confidential") == ClassificationTag.CONFIDENTIAL
    assert ClassificationTag.from_str("financial_report") == ClassificationTag.CONFIDENTIAL
    assert ClassificationTag.from_str("restricted_legal") == ClassificationTag.RESTRICTED_LEGAL
    assert ClassificationTag.from_str("secret_keys") == ClassificationTag.SECRET
    assert ClassificationTag.from_str("public_doc") == ClassificationTag.PUBLIC


def test_admin_unrestricted_raw_access():
    """Verifies ADMIN users receive unmasked raw content with full fidelity."""
    masker = get_abac_masker()
    text = (
        "Internal executive compensation: $500,000 annually. "
        "Production secret token sk-prod-live-992817263541."
    )
    masked, was_redacted, reasons = masker.mask_text(
        text=text,
        user_role="ADMIN",
        chunk_classification="CONFIDENTIAL",
    )
    assert was_redacted is False
    assert masked == text
    assert len(reasons) == 0


def test_user_confidential_chunk_masking():
    """Verifies USER role receives sentence-level redaction on CONFIDENTIAL chunks."""
    masker = get_abac_masker()
    text = (
        "General introduction to our platform. "
        "The executive base salary is $450,000 per year. "
        "System maintenance is scheduled for Sunday."
    )
    masked, was_redacted, reasons = masker.mask_text(
        text=text,
        user_role="USER",
        chunk_classification="CONFIDENTIAL",
    )
    assert was_redacted is True
    assert "[REDACTED: CONFIDENTIAL_CLEARANCE_REQUIRED]" in masked
    assert "$450,000" not in masked
    assert "General introduction" in masked


def test_viewer_full_chunk_redaction():
    """Verifies VIEWER role receives full chunk redaction for CONFIDENTIAL or SECRET chunks."""
    masker = get_abac_masker()
    text = "Secret architectural diagrams and patent documentation."
    masked, was_redacted, reasons = masker.mask_text(
        text=text,
        user_role="VIEWER",
        chunk_classification="CONFIDENTIAL",
    )
    assert was_redacted is True
    assert "[REDACTED: CLEARANCE_REQUIRED" in masked
    assert "Secret architectural" not in masked


def test_in_line_secret_token_redaction():
    """Verifies secret tokens are redacted for non-admin roles even in PUBLIC chunks."""
    masker = get_abac_masker()
    text = "Public guide: connect using bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    masked, was_redacted, reasons = masker.mask_text(
        text=text,
        user_role="USER",
        chunk_classification="PUBLIC",
    )
    assert was_redacted is True
    assert "[REDACTED: SENSITIVE_CREDENTIAL]" in masked
    assert "eyJhbGci" not in masked


def test_context_builder_abac_redaction():
    """Verifies ContextBuilder sanitizes chunks and sets citation redaction flags."""
    builder = ContextBuilder()
    hits = [
        {
            "chunk_id": "chunk_conf_1",
            "document_id": "doc_conf_sla",
            "content": "Confidential executive bonus pool is $2,000,000 for FY2026.",
            "score": 0.95,
            "payload": {
                "security_classification": "Confidential",
                "filename": "Executive_Compensation_2026.pdf",
            },
        }
    ]

    # For USER role: should be redacted
    res_user = builder.build_context(hits, user_role="USER")
    assert "ABAC: 🛡️ REDACTED" in res_user.formatted_context
    assert "$2,000,000" not in res_user.formatted_context
    assert len(res_user.citations) == 1
    assert res_user.citations[0].is_redacted is True
    assert res_user.citations[0].redaction_level == "Confidential"
    assert "$2,000,000" not in res_user.citations[0].content_snippet

    # For ADMIN role: unmasked
    res_admin = builder.build_context(hits, user_role="ADMIN")
    assert "$2,000,000" in res_admin.formatted_context
    assert res_admin.citations[0].is_redacted is False


def test_abac_simulation_payload():
    """Verifies diagnostic simulation method generates detailed telemetry."""
    masker = ABACChunkMasker()
    sim_res = masker.simulate(
        text="Corporate liability limit shall be $10,000,000 in damages.",
        user_role="USER",
        classification="CONFIDENTIAL",
    )
    assert sim_res.has_redactions is True
    assert sim_res.user_role == "USER"
    assert sim_res.clearance_level == 2
    assert sim_res.required_clearance == "ANALYST"
    assert sim_res.tokens_masked >= 1
