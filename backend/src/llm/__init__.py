"""LLM module initialization supporting Sarvam AI and Mock LLM providers."""

import os

from src.llm.base import LLMProvider, LLMResponse
from src.llm.mock import MockLLMProvider
from src.llm.sarvam import SarvamLLMProvider


def get_llm_provider(mock: bool = False) -> LLMProvider:
    """Factory function returning the configured LLM provider."""
    mock_env = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")
    if mock or mock_env or not os.getenv("SARVAM_API_KEY"):
        return MockLLMProvider()
    return SarvamLLMProvider()


__all__ = ["LLMProvider", "LLMResponse", "SarvamLLMProvider", "MockLLMProvider", "get_llm_provider"]
