"""REST API routes for Cross-Lingual & Multi-Indic Linguistic Bridge."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field
from src.multilingual.bridge import (
    SUPPORTED_INDIC_LANGUAGES,
    LanguageDetectionResult,
    LanguageInfo,
    ScriptNormalizer,
    get_language_detector,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/multilingual", tags=["Multilingual & Indic Bridge"])


class DetectLanguageRequest(BaseModel):
    """Payload to detect text language and script."""

    text: str = Field(..., description="Query or text string to classify")


class NormalizeTextRequest(BaseModel):
    """Payload to normalize and derive search query from text."""

    text: str = Field(..., description="Input text to normalize")


class NormalizeTextResponse(BaseModel):
    """Normalized text and derived semantic search query."""

    original: str
    normalized: str
    derived_query: str
    detected: LanguageDetectionResult


@router.post("/detect", response_model=LanguageDetectionResult)
async def detect_language(payload: DetectLanguageRequest) -> LanguageDetectionResult:
    """Identifies Indic script, Latin transliteration, or code-mixed Hinglish."""
    detector = get_language_detector()
    return detector.detect(payload.text)


@router.get("/supported-languages", response_model=list[LanguageInfo])
async def list_supported_languages() -> list[LanguageInfo]:
    """Returns catalog of supported Indic languages and scripts for Sarvam AI."""
    return list(SUPPORTED_INDIC_LANGUAGES.values())


@router.post("/normalize", response_model=NormalizeTextResponse)
async def normalize_text(payload: NormalizeTextRequest) -> NormalizeTextResponse:
    """Normalizes Unicode text and strips code-mixed conversational noise."""
    detector = get_language_detector()
    detected = detector.detect(payload.text)
    norm = ScriptNormalizer.normalize_text(payload.text)
    derived = ScriptNormalizer.derive_semantic_query(norm, detected)
    return NormalizeTextResponse(
        original=payload.text,
        normalized=norm,
        derived_query=derived,
        detected=detected,
    )
