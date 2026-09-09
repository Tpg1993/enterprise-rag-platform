"""Mock LLM Provider for offline testing, CI/CD, and fast development iteration."""

import asyncio
import time
from collections.abc import AsyncGenerator

from src.llm.base import LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    """Deterministic Mock LLM provider that simulates Sarvam AI responses offline."""

    def __init__(self, default_response: str | None = None):
        self.default_response = (
            default_response
            or "This is a deterministic mock response from Sarvam AI (MOCK_LLM=true)."
        )

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        # Standard Sarvam-105b pricing estimate
        return (prompt_tokens * 0.0015 / 1000) + (completion_tokens * 0.0030 / 1000)

    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        correlation_id: str | None = None,
    ) -> LLMResponse:
        start_time = time.perf_counter()
        await asyncio.sleep(0.05)  # Simulate fast latency
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        content = f"{self.default_response} Answer for query: '{prompt[:50]}...'"
        p_tokens = len(prompt.split()) + (len(system_prompt.split()) if system_prompt else 0)
        c_tokens = len(content.split())
        cost = self.calculate_cost(p_tokens, c_tokens)

        return LLMResponse(
            content=content,
            model_name="sarvam-105b-mock",
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens,
            total_tokens=p_tokens + c_tokens,
            estimated_cost_usd=cost,
            latency_ms=elapsed_ms,
            ttft_ms=10.0,
            metadata={"correlation_id": correlation_id or "mock-id", "mock": "true"},
        )

    async def astream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        correlation_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        chunks = [
            "This ",
            "is ",
            "a ",
            "streaming ",
            "mock ",
            "response ",
            "from ",
            "Sarvam ",
            "AI.",
        ]
        for chunk in chunks:
            await asyncio.sleep(0.02)
            yield chunk
