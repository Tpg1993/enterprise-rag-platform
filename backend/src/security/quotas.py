"""Tenant Quotas, Rate Limiting, and Financial Budget Management Service (Phase 32)."""

import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger("TenantQuotaService")


class TenantQuotaConfig(BaseModel):
    """Configuration limits for a tenant."""

    daily_token_limit: int = 500_000
    monthly_token_limit: int = 10_000_000
    daily_spend_limit_usd: float = 5.00
    monthly_spend_limit_usd: float = 50.00
    rate_limit_rpm: int = 60
    max_context_tokens: int = 4096


class TenantUsageState(BaseModel):
    """In-memory tracking of tenant consumption and request timestamps."""

    daily_tokens: int = 0
    monthly_tokens: int = 0
    daily_spend_usd: float = 0.0
    monthly_spend_usd: float = 0.0
    total_requests: int = 0
    request_timestamps: list[float] = Field(default_factory=list)
    last_reset_day: str = ""
    last_reset_month: str = ""


class TenantQuotaStatus(BaseModel):
    """Detailed quota status response for APIs and UI."""

    tenant_id: str
    rate_limit_rpm: int
    current_rpm: int
    rpm_remaining: int
    daily_tokens_used: int
    daily_token_limit: int
    daily_token_percent: float
    monthly_tokens_used: int
    monthly_token_limit: int
    daily_spend_usd: float
    daily_spend_limit_usd: float
    daily_spend_percent: float
    monthly_spend_usd: float
    monthly_spend_limit_usd: float
    is_budget_exceeded: bool
    rejection_reason: str | None = None


class TenantQuotaService:
    """Enterprise multi-tenant quota, rate limiting, and financial budget controller."""

    _instance: "TenantQuotaService | None" = None

    def __init__(self, config_path: str | Path | None = None) -> None:
        self.config_path = Path(config_path) if config_path else self._resolve_config_path()
        self.tenant_configs: dict[str, TenantQuotaConfig] = {}
        self.default_config = TenantQuotaConfig()
        self.usage_records: dict[str, TenantUsageState] = {}
        self._load_config()

    @classmethod
    def get_instance(cls, config_path: str | Path | None = None) -> "TenantQuotaService":
        if cls._instance is None:
            cls._instance = cls(config_path)
        return cls._instance

    def _resolve_config_path(self) -> Path:
        """Finds tenants.yaml configuration file."""
        candidates = [
            Path("backend/config/tenants.yaml"),
            Path("config/tenants.yaml"),
            Path(__file__).resolve().parent.parent.parent / "config" / "tenants.yaml",
        ]
        for p in candidates:
            if p.exists():
                return p
        return Path("backend/config/tenants.yaml")

    def _load_config(self) -> None:
        """Loads tenant budget limits from YAML file."""
        if not self.config_path.exists():
            logger.warning(f"Tenants config not found at {self.config_path}; using default limits.")
            return

        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            if "default_quota" in data:
                self.default_config = TenantQuotaConfig(**data["default_quota"])

            tenants_data = data.get("tenants", {})
            for t_id, t_cfg in tenants_data.items():
                self.tenant_configs[t_id] = TenantQuotaConfig(
                    daily_token_limit=t_cfg.get(
                        "daily_token_limit", self.default_config.daily_token_limit
                    ),
                    monthly_token_limit=t_cfg.get(
                        "monthly_token_limit", self.default_config.monthly_token_limit
                    ),
                    daily_spend_limit_usd=t_cfg.get(
                        "daily_spend_limit_usd", self.default_config.daily_spend_limit_usd
                    ),
                    monthly_spend_limit_usd=t_cfg.get(
                        "monthly_spend_limit_usd", self.default_config.monthly_spend_limit_usd
                    ),
                    rate_limit_rpm=t_cfg.get(
                        "rate_limit_rpm", self.default_config.rate_limit_rpm
                    ),
                    max_context_tokens=t_cfg.get(
                        "max_context_tokens", self.default_config.max_context_tokens
                    ),
                )
            logger.info(f"Loaded quota rules for {len(self.tenant_configs)} tenants.")
        except Exception as e:
            logger.error(f"Error loading tenant quota configuration: {e}")

    def get_tenant_config(self, tenant_id: str) -> TenantQuotaConfig:
        """Returns configured limits for tenant or fallback default."""
        return self.tenant_configs.get(tenant_id, self.default_config)

    def _get_or_create_usage(self, tenant_id: str) -> TenantUsageState:
        """Retrieves usage state, automatically rolling over day/month boundaries."""
        now = datetime.now(UTC)
        today_str = now.strftime("%Y-%m-%d")
        month_str = now.strftime("%Y-%m")

        if tenant_id not in self.usage_records:
            self.usage_records[tenant_id] = TenantUsageState(
                last_reset_day=today_str,
                last_reset_month=month_str,
            )
            return self.usage_records[tenant_id]

        usage = self.usage_records[tenant_id]
        if usage.last_reset_day != today_str:
            usage.daily_tokens = 0
            usage.daily_spend_usd = 0.0
            usage.last_reset_day = today_str

        if usage.last_reset_month != month_str:
            usage.monthly_tokens = 0
            usage.monthly_spend_usd = 0.0
            usage.last_reset_month = month_str

        return usage

    def check_rate_limit(self, tenant_id: str) -> tuple[bool, int, float]:
        """Sliding window token-bucket rate limiter.

        Returns: (is_allowed, remaining_rpm, reset_seconds)
        """
        cfg = self.get_tenant_config(tenant_id)
        usage = self._get_or_create_usage(tenant_id)

        now = time.time()
        window_start = now - 60.0
        # Prune timestamps older than 60 seconds
        usage.request_timestamps = [ts for ts in usage.request_timestamps if ts > window_start]

        current_rpm = len(usage.request_timestamps)
        remaining = max(0, cfg.rate_limit_rpm - current_rpm)

        if current_rpm >= cfg.rate_limit_rpm:
            earliest = usage.request_timestamps[0]
            retry_after = max(1.0, round(60.0 - (now - earliest), 1))
            return False, 0, retry_after

        return True, remaining, 0.0

    def check_budget(
        self, tenant_id: str, estimated_tokens: int = 500
    ) -> tuple[bool, str | None, dict[str, Any]]:
        """Validates daily & monthly token and financial budget constraints."""
        cfg = self.get_tenant_config(tenant_id)
        usage = self._get_or_create_usage(tenant_id)

        details = {
            "daily_tokens_used": usage.daily_tokens,
            "daily_token_limit": cfg.daily_token_limit,
            "daily_spend_usd": usage.daily_spend_usd,
            "daily_spend_limit_usd": cfg.daily_spend_limit_usd,
            "monthly_spend_usd": usage.monthly_spend_usd,
            "monthly_spend_limit_usd": cfg.monthly_spend_limit_usd,
        }

        # Check Daily Spend Limit
        if usage.daily_spend_usd >= cfg.daily_spend_limit_usd:
            msg = (
                f"Tenant '{tenant_id}' daily budget limit of "
                f"${cfg.daily_spend_limit_usd:.2f} exceeded."
            )
            return False, msg, details

        # Check Monthly Spend Limit
        if usage.monthly_spend_usd >= cfg.monthly_spend_limit_usd:
            msg = (
                f"Tenant '{tenant_id}' monthly budget limit of "
                f"${cfg.monthly_spend_limit_usd:.2f} exceeded."
            )
            return False, msg, details

        # Check Daily Token Limit
        if usage.daily_tokens + estimated_tokens > cfg.daily_token_limit:
            msg = (
                f"Tenant '{tenant_id}' daily token quota of "
                f"{cfg.daily_token_limit:,} tokens exceeded."
            )
            return False, msg, details

        # Check Monthly Token Limit
        if usage.monthly_tokens + estimated_tokens > cfg.monthly_token_limit:
            msg = (
                f"Tenant '{tenant_id}' monthly token quota of "
                f"{cfg.monthly_token_limit:,} tokens exceeded."
            )
            return False, msg, details

        return True, None, details

    def record_usage(
        self,
        tenant_id: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        """Records executed request telemetry into the tenant's usage state."""
        usage = self._get_or_create_usage(tenant_id)
        total_tokens = prompt_tokens + completion_tokens

        usage.daily_tokens += total_tokens
        usage.monthly_tokens += total_tokens
        usage.daily_spend_usd = round(usage.daily_spend_usd + cost_usd, 6)
        usage.monthly_spend_usd = round(usage.monthly_spend_usd + cost_usd, 6)
        usage.total_requests += 1
        usage.request_timestamps.append(time.time())

        logger.debug(
            f"Usage recorded for tenant '{tenant_id}': +{total_tokens} tokens, +${cost_usd:.6f} | "
            f"Day total: {usage.daily_tokens} tokens, ${usage.daily_spend_usd:.4f}"
        )

    def get_quota_status(self, tenant_id: str) -> TenantQuotaStatus:
        """Calculates live quota status for UI and APIs."""
        cfg = self.get_tenant_config(tenant_id)
        usage = self._get_or_create_usage(tenant_id)

        now = time.time()
        active_timestamps = [ts for ts in usage.request_timestamps if ts > (now - 60.0)]
        current_rpm = len(active_timestamps)
        rpm_remaining = max(0, cfg.rate_limit_rpm - current_rpm)

        daily_token_pct = round((usage.daily_tokens / max(1, cfg.daily_token_limit)) * 100, 2)
        daily_spend_limit = max(0.0001, cfg.daily_spend_limit_usd)
        daily_spend_pct = round((usage.daily_spend_usd / daily_spend_limit) * 100, 2)

        is_allowed, reason, _ = self.check_budget(tenant_id, estimated_tokens=0)

        return TenantQuotaStatus(
            tenant_id=tenant_id,
            rate_limit_rpm=cfg.rate_limit_rpm,
            current_rpm=current_rpm,
            rpm_remaining=rpm_remaining,
            daily_tokens_used=usage.daily_tokens,
            daily_token_limit=cfg.daily_token_limit,
            daily_token_percent=min(100.0, daily_token_pct),
            monthly_tokens_used=usage.monthly_tokens,
            monthly_token_limit=cfg.monthly_token_limit,
            daily_spend_usd=usage.daily_spend_usd,
            daily_spend_limit_usd=cfg.daily_spend_limit_usd,
            daily_spend_percent=min(100.0, daily_spend_pct),
            monthly_spend_usd=usage.monthly_spend_usd,
            monthly_spend_limit_usd=cfg.monthly_spend_limit_usd,
            is_budget_exceeded=not is_allowed,
            rejection_reason=reason,
        )

    def reset_tenant_usage(self, tenant_id: str) -> None:
        """Resets all usage metrics for a tenant (Admin action)."""
        if tenant_id in self.usage_records:
            del self.usage_records[tenant_id]
        logger.info(f"Quota usage reset for tenant '{tenant_id}'.")
