"""Unit tests for Web Search Providers and Schemas."""

import pytest
from src.retrieval.web_search import (
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    WebSearchResult,
    get_search_provider,
)


def test_web_search_result_domain_extraction():
    """Verifies that WebSearchResult extracts domain from URL automatically."""
    res1 = WebSearchResult(
        title="Reuters Market Report",
        url="https://finance.reuters.com/markets/stocks/test",
        snippet="Markets rose 1.2% today.",
    )
    assert res1.domain == "finance.reuters.com"
    assert res1.score == 1.0

    res2 = WebSearchResult(
        title="NIST Standard",
        url="https://csrc.nist.gov/publications/sp800",
        snippet="NIST guidelines for AI systems.",
        domain="csrc.nist.gov",
    )
    assert res2.domain == "csrc.nist.gov"


@pytest.mark.asyncio
async def test_mock_search_provider_financial_query():
    """Verifies that MockSearchProvider returns relevant financial web results."""
    provider = MockSearchProvider()
    results = await provider.search("what is the current stock market trend?", top_k=5)
    assert len(results) > 0
    assert any("reuters" in r.domain or "bloomberg" in r.domain for r in results)
    assert any("S&P 500" in r.snippet or "Markets" in r.title for r in results)


@pytest.mark.asyncio
async def test_mock_search_provider_regulatory_query():
    """Verifies that MockSearchProvider returns relevant regulatory web results."""
    provider = MockSearchProvider()
    results = await provider.search("latest NIST AI safety standards 2026", top_k=5)
    assert len(results) > 0
    assert any("nist.gov" in r.domain for r in results)
    assert any("NIST" in r.title for r in results)


@pytest.mark.asyncio
async def test_mock_search_provider_domain_filtering():
    """Verifies that domain filtering works correctly."""
    provider = MockSearchProvider()
    results = await provider.search(
        "global financial markets and currencies",
        top_k=5,
        domains=["bloomberg.com"],
    )
    for r in results:
        assert "bloomberg.com" in r.domain


@pytest.mark.asyncio
async def test_duckduckgo_search_provider_fallback():
    """Verifies that DuckDuckGoSearchProvider falls back gracefully to MockSearchProvider."""
    provider = DuckDuckGoSearchProvider(timeout_sec=0.001)  # intentional near-zero timeout
    results = await provider.search("latest artificial intelligence news", top_k=3)
    assert len(results) > 0
    assert isinstance(results[0], WebSearchResult)
    assert results[0].snippet


def test_get_search_provider_factory(monkeypatch):
    """Verifies that get_search_provider respects environment variables and flags."""
    monkeypatch.setenv("MOCK_WEB_SEARCH", "true")
    provider = get_search_provider()
    assert isinstance(provider, MockSearchProvider)

    monkeypatch.setenv("MOCK_WEB_SEARCH", "false")
    monkeypatch.setenv("MOCK_LLM", "false")
    ddg_provider = get_search_provider("duckduckgo")
    assert isinstance(ddg_provider, DuckDuckGoSearchProvider)
