"""Multilingual package initialization."""

from src.multilingual.bridge import (
    SUPPORTED_INDIC_LANGUAGES,
    CrossLingualBridge,
    LanguageDetectionResult,
    LanguageDetector,
    LanguageInfo,
    ScriptNormalizer,
    get_language_detector,
    get_multilingual_bridge,
)

__all__ = [
    "LanguageDetector",
    "LanguageDetectionResult",
    "LanguageInfo",
    "SUPPORTED_INDIC_LANGUAGES",
    "ScriptNormalizer",
    "CrossLingualBridge",
    "get_language_detector",
    "get_multilingual_bridge",
]
