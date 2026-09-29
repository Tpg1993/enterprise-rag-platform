"""Unit tests for Tenant Quotas, Sliding-Window Rate Limiting, and Budget Control (Phase 32)."""

import pytest
from src.security.quotas import (
    TenantQuotaConfig,
    TenantQuotaService,
    TenantQuotaStatus,
)


@pytest.fixture
def quota_service():
    """Provides an isolated TenantQuotaService instance for testing."""
    svc = TenantQuotaService()
    # Configure an isolated test tenant with tight limits
    svc.tenant_configs["test_quota_tenant"] = TenantQuotaConfig(
        daily_token_limit=1000,
        monthly_token_limit=5000,
        daily_spend_limit_usd=0.05,
        monthly_spend_limit_usd=0.50,
        rate_limit_rpm=3,
        max_context_tokens=1024,
    )
    svc.reset_tenant_usage("test_quota_tenant")
    return svc


def test_tenant_quota_config_loading(quota_service):
    """Verifies that tenant configurations and fallbacks load correctly."""
    cfg = quota_service.get_tenant_config("test_quota_tenant")
    assert cfg.daily_token_limit == 1000
    assert cfg.daily_spend_limit_usd == 0.05
    assert cfg.rate_limit_rpm == 3

    # Fallback default tenant
    def_cfg = quota_service.get_tenant_config("unknown_random_tenant")
    assert def_cfg.daily_token_limit == quota_service.default_config.daily_token_limit


def test_sliding_window_rate_limiting(quota_service):
    """Verifies sliding-window RPM rate limiter enforcement."""
    tenant = "test_quota_tenant"

    # First 3 requests must be allowed (limit is 3 RPM)
    for _ in range(3):
        allowed, remaining, _ = quota_service.check_rate_limit(tenant)
        assert allowed is True
        quota_service.record_usage(tenant, prompt_tokens=10, completion_tokens=10, cost_usd=0.0001)

    # 4th request must be rejected with 429 logic
    allowed, remaining, retry_after = quota_service.check_rate_limit(tenant)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0.0


def test_daily_token_budget_exceeded(quota_service):
    """Verifies that requests are blocked when daily token consumption exceeds limit."""
    tenant = "test_quota_tenant"

    # Limit is 1000 tokens. Record 900 tokens.
    quota_service.record_usage(tenant, prompt_tokens=450, completion_tokens=450, cost_usd=0.001)

    # Estimated 200 tokens would bring total to 1100 > 1000 limit -> Rejected
    allowed, reason, details = quota_service.check_budget(tenant, estimated_tokens=200)
    assert allowed is False
    assert "daily token quota" in reason
    assert details["daily_tokens_used"] == 900


def test_daily_spend_limit_exceeded(quota_service):
    """Verifies that requests are blocked when financial dollar budget is exhausted."""
    tenant = "test_quota_tenant"

    # Daily limit is $0.05. Record $0.06 spend.
    quota_service.record_usage(tenant, prompt_tokens=100, completion_tokens=100, cost_usd=0.06)

    allowed, reason, details = quota_service.check_budget(tenant, estimated_tokens=10)
    assert allowed is False
    assert "daily budget limit" in reason
    assert details["daily_spend_usd"] >= 0.05


def test_record_usage_and_status(quota_service):
    """Verifies that record_usage correctly computes live percentages and quota status."""
    tenant = "test_quota_tenant"

    quota_service.record_usage(tenant, prompt_tokens=250, completion_tokens=250, cost_usd=0.025)
    status = quota_service.get_quota_status(tenant)

    assert isinstance(status, TenantQuotaStatus)
    assert status.daily_tokens_used == 500
    assert status.daily_token_percent == 50.0  # 500 / 1000 = 50%
    assert status.daily_spend_usd == 0.025
    assert status.daily_spend_percent == 50.0  # 0.025 / 0.05 = 50%
    assert status.is_budget_exceeded is False


def test_reset_tenant_usage(quota_service):
    """Verifies that resetting usage clears all accumulated counters back to zero."""
    tenant = "test_quota_tenant"

    quota_service.record_usage(tenant, prompt_tokens=500, completion_tokens=500, cost_usd=0.03)
    quota_service.reset_tenant_usage(tenant)

    status = quota_service.get_quota_status(tenant)
    assert status.daily_tokens_used == 0
    assert status.daily_spend_usd == 0.0
    assert status.daily_token_percent == 0.0
    assert status.is_budget_exceeded is False
