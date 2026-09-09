"""Prompt Injection & Security Guardrails engine enforcing OWASP LLM Top 10 defenses."""

import logging
import re
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Patterns indicative of prompt injection, jailbreaks, or instruction override attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior)\s+rules",
    r"override\s+system\s+prompt",
    r"reveal\s+(your\s+)?system\s+(prompt|instructions)",
    r"print\s+(your\s+)?initial\s+instructions",
    r"you\s+are\s+now\s+in\s+(dan|jailbreak)\s+mode",
    r"bypass\s+security\s+filter",
]


class SecurityCheckResult(BaseModel):
    """Result of prompt injection security scan."""

    is_safe: bool
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    detected_patterns: list[str] = []
    sanitized_prompt: str


class PromptInjectionGuardrail:
    """Interceptor evaluating incoming user queries against malicious prompt injection patterns."""

    def __init__(self, block_high_risk: bool = True):
        self.block_high_risk = block_high_risk

    def inspect(self, prompt: str) -> SecurityCheckResult:
        if not prompt:
            return SecurityCheckResult(is_safe=True, risk_level="LOW", detected_patterns=[], sanitized_prompt="")

        detected = []
        p_lower = prompt.lower()

        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, p_lower):
                detected.append(pattern)

        if detected:
            logger.warning(f"Prompt injection detected! Patterns: {detected}")
            return SecurityCheckResult(
                is_safe=False,
                risk_level="HIGH",
                detected_patterns=detected,
                sanitized_prompt="[SECURITY ALERT: User query contained potential prompt injection instructions.]",
            )

        return SecurityCheckResult(
            is_safe=True,
            risk_level="LOW",
            detected_patterns=[],
            sanitized_prompt=prompt,
        )
