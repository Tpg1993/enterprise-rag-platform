"""Unit tests for MockLLMProvider and LLM base abstractions."""

import pytest
from src.llm import MockLLMProvider, get_llm_provider


@pytest.mark.asyncio
async def test_mock_llm_agenerate():
    provider = get_llm_provider(mock=True)
    assert isinstance(provider, MockLLMProvider)

    res = await provider.agenerate(prompt="What is enterprise RAG?")
    assert res.content != ""
    assert res.model_name == "sarvam-105b-mock"
    assert res.prompt_tokens > 0
    assert res.completion_tokens > 0
    assert res.estimated_cost_usd >= 0.0


@pytest.mark.asyncio
async def test_mock_llm_astream():
    provider = MockLLMProvider()
    chunks = []
    async for chunk in provider.astream(prompt="Test stream"):
        chunks.append(chunk)

    assert len(chunks) > 0
    full_text = "".join(chunks)
    assert "Sarvam" in full_text
