"""Abstract LLMProvider interface for Sarvam AI and extensible LLM backends."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    content: str
    model_name: str = "sarvam-105b"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: float = 0.0
    ttft_ms: float | None = None
    finish_reason: str = "stop"
    metadata: dict[str, str] = Field(default_factory=dict)


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def agenerate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        correlation_id: str | None = None,
    ) -> LLMResponse:
        """Asynchronously generate LLM completion."""
        pass

    @abstractmethod
    def astream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        correlation_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Asynchronously stream LLM completion chunks."""
        pass

    @abstractmethod
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculates cost in USD based on pricing definitions."""
        pass
