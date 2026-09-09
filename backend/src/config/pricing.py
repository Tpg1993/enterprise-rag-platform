"""YAML-driven pricing configuration loader for dynamic LLM, vector store, and cache cost calculation."""

import logging
from pathlib import Path
import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default pricing fallback if config file is missing
DEFAULT_PRICING = {
    "models": {
        "sarvam-105b": {
            "input_cost_per_1k_tokens": 0.0015,
            "output_cost_per_1k_tokens": 0.0030,
            "cached_input_cost_per_1k_tokens": 0.0005,
        }
    },
    "infrastructure": {
        "qdrant_operation_cost_per_1k": 0.0001,
        "redis_operation_cost_per_1k": 0.00001,
    },
}

_pricing_cache: dict | None = None


def get_pricing_config() -> dict:
    """Loads and caches dynamic pricing rules from config/pricing.yaml."""
    global _pricing_cache

    if _pricing_cache is not None:
        return _pricing_cache

    config_path = Path(__file__).resolve().parent.parent.parent / "config" / "pricing.yaml"

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                _pricing_cache = yaml.safe_load(f) or DEFAULT_PRICING
                logger.info(f"Loaded pricing configuration from '{config_path}'.")
                return _pricing_cache
        except Exception as e:
            logger.warning(f"Could not parse '{config_path}': {e}. Using default pricing.")

    _pricing_cache = DEFAULT_PRICING
    return _pricing_cache


def calculate_llm_cost(
    model: str = "sarvam-105b",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    cached_tokens: int = 0,
) -> float:
    """Calculates estimated request cost in USD based on pricing configuration."""
    cfg = get_pricing_config()
    model_cfg = cfg.get("models", {}).get(model, DEFAULT_PRICING["models"]["sarvam-105b"])

    in_cost_rate = model_cfg.get("input_cost_per_1k_tokens", 0.0015)
    out_cost_rate = model_cfg.get("output_cost_per_1k_tokens", 0.0030)
    cached_cost_rate = model_cfg.get("cached_input_cost_per_1k_tokens", 0.0005)

    uncached_prompt_tokens = max(0, prompt_tokens - cached_tokens)

    cost = (
        (uncached_prompt_tokens * in_cost_rate / 1000.0)
        + (cached_tokens * cached_cost_rate / 1000.0)
        + (completion_tokens * out_cost_rate / 1000.0)
    )

    return round(cost, 6)
