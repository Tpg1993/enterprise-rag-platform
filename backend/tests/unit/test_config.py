"""Unit tests for configuration loader and settings schema."""

from src.config.loader import load_settings
from src.config.schema import PlatformSettings


def test_load_settings_defaults():
    settings = load_settings()
    assert isinstance(settings, PlatformSettings)
    assert settings.app.port == 8000
    assert settings.llm.default_model == "sarvam-105b"
    assert settings.embeddings.dimension == 1024
    assert settings.hnsw.m == 16
