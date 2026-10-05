import logging
import re
from enum import IntEnum, StrEnum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ClearanceLevel(IntEnum):
    """User security clearance levels ordered hierarchically."""

    VIEWER = 1
    USER = 2
    ANALYST = 3
    ADMIN = 4

    @classmethod
    def from_str(cls, role: str | None) -> "ClearanceLevel":
        """Maps user role string to clearance level."""
        role_upper = (role or "").strip().upper()
        if "ADMIN" in role_upper:
            return cls.ADMIN
        if "ANALYST" in role_upper:
            return cls.ANALYST
        if "VIEWER" in role_upper:
            return cls.VIEWER
        return cls.USER


class ClassificationTag(StrEnum):
    """Standardized enterprise data classification tags."""

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED_LEGAL = "RESTRICTED_LEGAL"
    SECRET = "SECRET"

    @classmethod
    def from_str(cls, tag: str | None) -> "ClassificationTag":
        """Normalizes free-form classification strings."""
        t_upper = (tag or "").strip().upper().replace(" ", "_")
        if "SECRET" in t_upper:
            return cls.SECRET
        if "LEGAL" in t_upper or "RESTRICTED" in t_upper:
            return cls.RESTRICTED_LEGAL
        if "CONFIDENTIAL" in t_upper or "FINANCIAL" in t_upper or "EXECUTIVE" in t_upper:
            return cls.CONFIDENTIAL
        if "INTERNAL" in t_upper:
            return cls.INTERNAL
        return cls.PUBLIC


# Required minimum clearance for each classification tag
CLEARANCE_POLICY: dict[ClassificationTag, ClearanceLevel] = {
    ClassificationTag.PUBLIC: ClearanceLevel.VIEWER,
    ClassificationTag.INTERNAL: ClearanceLevel.USER,
    ClassificationTag.CONFIDENTIAL: ClearanceLevel.ANALYST,
    ClassificationTag.RESTRICTED_LEGAL: ClearanceLevel.ADMIN,
    ClassificationTag.SECRET: ClearanceLevel.ADMIN,
}


class ABACPolicyMatrix(BaseModel):
    """Declarative specification of active ABAC clearance levels and classification rules."""

    clearance_hierarchy: dict[str, int]
    classification_rules: dict[str, str]
    differential_privacy_rules: list[str]


class ABACSimulationRequest(BaseModel):
    """Simulation test payload for ABAC chunk masking."""

    text: str = Field(..., description="Text snippet to inspect and redact")
    user_role: str = Field(default="USER", description="Target simulated user role")
    classification: str = Field(default="PUBLIC", description="Chunk classification tag")


class ABACSimulationResponse(BaseModel):
    """Outcome of ABAC chunk masking simulation."""

    original_text: str
    masked_text: str
    user_role: str
    clearance_level: int
    classification: str
    required_clearance: str
    has_redactions: bool
    redaction_reasons: list[str]
    tokens_masked: int


class ABACChunkMasker:
    """Zero-Trust sub-document & chunk-level masking engine applying ABAC policies."""

    def __init__(self):
        # Differential privacy regex rules for in-line sensitive spans
        self.secret_token_pattern = re.compile(
            r"(?i)\b(sk-[a-zA-Z0-9_\-]{16,}|bearer\s+[a-zA-Z0-9_\-\.]{16,}|"
            r"(?:api[_-]?key|client[_-]?secret|password|auth[_-]?token)\s*[:=]\s*['\"][^\s'\"]{6,}['\"])"
        )
        self.compensation_pattern = re.compile(
            r"(?i)(\$\s*\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*(?:salary|base|bonus|compensation|annually|package)|"
            r"(?:salary|compensation|package)\s*(?:is|of|:)\s*\$\s*\d{1,3}(?:,\d{3})+)"
        )
        self.liability_terms_pattern = re.compile(
            r"(?i)\b((?:maximum liability|indemnification cap|liability limit)\s*"
            r"(?:is|shall be|of)\s*\$\s*[\d,]+)"
        )

    def mask_text(
        self,
        text: str,
        user_role: str | None = "USER",
        chunk_classification: str | None = "PUBLIC",
    ) -> tuple[str, bool, list[str]]:
        """Applies ABAC clearance enforcement and differential privacy redaction to text."""
        if not text:
            return "", False, []

        user_clearance = ClearanceLevel.from_str(user_role)
        target_tag = ClassificationTag.from_str(chunk_classification)
        required_clearance = CLEARANCE_POLICY[target_tag]

        reasons: list[str] = []
        masked_text = text

        # 1. ADMIN has complete unrestricted access (raw fidelity)
        if user_clearance >= ClearanceLevel.ADMIN:
            return text, False, []

        # 2. Complete Chunk Replacement if clearance is insufficient by >= 2 levels
        # (e.g. VIEWER accessing CONFIDENTIAL, RESTRICTED_LEGAL, or SECRET)
        if user_clearance < required_clearance and (required_clearance - user_clearance) >= 2:
            reasons.append(
                f"Full chunk masked: {target_tag.value} requires "
                f"{required_clearance.name}+ clearance (User has {user_clearance.name})."
            )
            return (
                f"[REDACTED: CLEARANCE_REQUIRED - Restricted to {required_clearance.name}+ role]",
                True,
                reasons,
            )

        # 3. If user clearance is below required clearance by 1 level
        # (e.g. USER accessing CONFIDENTIAL, or ANALYST accessing RESTRICTED_LEGAL)
        if user_clearance < required_clearance:
            reasons.append(
                f"Confidential data masked: {target_tag.value} exceeds {user_clearance.name}."
            )
            # Mask sensitive sentences containing numbers, currency, or contractual obligations
            sentences = re.split(r"(?<=[.!?])\s+", masked_text)
            sanitized_sentences = []
            for s in sentences:
                if re.search(r"(\$|\d{2,}|obligation|liability|penalty|audit|patent)", s, re.I):
                    sanitized_sentences.append(
                        f"[REDACTED: {target_tag.value}_CLEARANCE_REQUIRED]"
                    )
                else:
                    sanitized_sentences.append(s)
            masked_text = " ".join(sanitized_sentences)

        # 4. In-line Differential Privacy Spans (Tokens, Secrets, Salaries, Liability Caps)
        # Secret API tokens & credentials (masked for all except ADMIN)
        if self.secret_token_pattern.search(masked_text):
            masked_text = self.secret_token_pattern.sub(
                "[REDACTED: SENSITIVE_CREDENTIAL]", masked_text
            )
            reasons.append("Redacted in-line API credential/token span.")

        # Compensation & Salary figures (masked for USER and VIEWER)
        if user_clearance < ClearanceLevel.ANALYST:
            if self.compensation_pattern.search(masked_text):
                masked_text = self.compensation_pattern.sub(
                    "[REDACTED: EXECUTIVE_COMPENSATION]", masked_text
                )
                reasons.append("Redacted in-line executive compensation figures.")

            if self.liability_terms_pattern.search(masked_text):
                masked_text = self.liability_terms_pattern.sub(
                    "[REDACTED: CONFIDENTIAL_LIABILITY_TERMS]", masked_text
                )
                reasons.append("Redacted contractual liability clause.")

        was_redacted = len(reasons) > 0 or masked_text != text
        return masked_text, was_redacted, reasons

    def simulate(
        self,
        text: str,
        user_role: str = "USER",
        classification: str = "PUBLIC",
    ) -> ABACSimulationResponse:
        """Executes a diagnostic simulation of ABAC masking for testing."""
        masked, was_redacted, reasons = self.mask_text(
            text=text,
            user_role=user_role,
            chunk_classification=classification,
        )
        tag = ClassificationTag.from_str(classification)
        req_level = CLEARANCE_POLICY[tag]
        u_level = ClearanceLevel.from_str(user_role)

        # Count redaction tags
        redaction_count = len(re.findall(r"\[REDACTED:[^\]]+\]", masked))

        return ABACSimulationResponse(
            original_text=text,
            masked_text=masked,
            user_role=user_role.upper(),
            clearance_level=int(u_level),
            classification=tag.value,
            required_clearance=req_level.name,
            has_redactions=was_redacted,
            redaction_reasons=reasons,
            tokens_masked=redaction_count,
        )

    def get_policy_matrix(self) -> ABACPolicyMatrix:
        """Returns active clearance hierarchy and classification mappings."""
        return ABACPolicyMatrix(
            clearance_hierarchy={lvl.name: int(lvl) for lvl in ClearanceLevel},
            classification_rules={
                tag.value: CLEARANCE_POLICY[tag].name for tag in ClassificationTag
            },
            differential_privacy_rules=[
                "SECRET / API Credentials: Redacted for VIEWER, USER, ANALYST (ADMIN only)",
                "EXECUTIVE COMPENSATION: Redacted for VIEWER, USER (ANALYST+ permitted)",
                "CONFIDENTIAL LIABILITY TERMS: Redacted for VIEWER, USER (ANALYST+ permitted)",
                "RESTRICTED LEGAL / PATENT: Redacted for VIEWER, USER, ANALYST (ADMIN only)",
            ],
        )


_GLOBAL_ABAC_MASKER: ABACChunkMasker | None = None


def get_abac_masker() -> ABACChunkMasker:
    """Returns singleton instance of ABACChunkMasker."""
    global _GLOBAL_ABAC_MASKER
    if _GLOBAL_ABAC_MASKER is None:
        _GLOBAL_ABAC_MASKER = ABACChunkMasker()
    return _GLOBAL_ABAC_MASKER
