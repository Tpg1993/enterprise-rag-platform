"""YAML configuration loader supporting environment overrides and relative file paths."""

import os
from pathlib import Path
from typing import Any

import yaml
from src.config.schema import PlatformSettings


def get_project_root() -> Path:
    """Returns absolute path to workspace root directory."""
    return Path(__file__).resolve().parent.parent.parent.parent


def load_yaml_config(file_path: Path) -> dict[str, Any]:
    """Loads a YAML configuration file safely."""
    if not file_path.exists():
        return {}
    with open(file_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(config_dir: Path | None = None) -> PlatformSettings:
    """Loads all YAML configuration files and returns validated PlatformSettings."""
    root = get_project_root()
    cfg_dir = config_dir or (root / "backend" / "config")

    settings_dict = load_yaml_config(cfg_dir / "settings.yaml")
    models_dict = load_yaml_config(cfg_dir / "models.yaml")
    retrieval_dict = load_yaml_config(cfg_dir / "retrieval.yaml")
    security_dict = load_yaml_config(cfg_dir / "security.yaml")

    merged = {
        **settings_dict,
        "llm": models_dict.get("llm", {}).get("sarvam", {}),
        "embeddings": models_dict.get("embeddings", {}).get("bge_m3", {}),
        "reranker": models_dict.get("reranker", {}).get("bge_reranker", {}),
        "hnsw": retrieval_dict.get("hnsw", {}),
        "bm25": retrieval_dict.get("bm25", {}),
        "hybrid_fusion": retrieval_dict.get("hybrid_fusion", {}),
        "mmr": retrieval_dict.get("mmr", {}),
        "security": security_dict.get("agent_guardrails", {}),
    }

    # Environment variable overrides
    mock_llm_env = os.getenv("MOCK_LLM")
    if mock_llm_env is not None:
        if "app" not in merged:
            merged["app"] = {}
        merged["app"]["mock_llm"] = mock_llm_env.lower() in ("true", "1", "yes")

    return PlatformSettings.model_validate(merged)


# Global singleton instance for settings
get_settings = load_settings
