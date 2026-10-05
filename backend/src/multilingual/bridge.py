"""Cross-Lingual & Multi-Indic Linguistic Bridge for Sarvam AI.

Provides Unicode script identification, code-mixed Hinglish/vernacular
detection, script normalization, and cross-lingual RAG prompt alignment.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LanguageInfo(BaseModel):
    """Metadata describing a supported Indic language."""

    code: str
    name: str
    native_name: str
    script: str
    iso_639_1: str
    family: str = "Indo-Aryan"


SUPPORTED_INDIC_LANGUAGES: dict[str, LanguageInfo] = {
    "en": LanguageInfo(
        code="en",
        name="English",
        native_name="English",
        script="Latin",
        iso_639_1="en",
        family="Germanic",
    ),
    "hi": LanguageInfo(
        code="hi",
        name="Hindi",
        native_name="हिन्दी",
        script="Devanagari",
        iso_639_1="hi",
        family="Indo-Aryan",
    ),
    "ta": LanguageInfo(
        code="ta",
        name="Tamil",
        native_name="தமிழ்",
        script="Tamil",
        iso_639_1="ta",
        family="Dravidian",
    ),
    "te": LanguageInfo(
        code="te",
        name="Telugu",
        native_name="తెలుగు",
        script="Telugu",
        iso_639_1="te",
        family="Dravidian",
    ),
    "kn": LanguageInfo(
        code="kn",
        name="Kannada",
        native_name="ಕನ್ನಡ",
        script="Kannada",
        iso_639_1="kn",
        family="Dravidian",
    ),
    "bn": LanguageInfo(
        code="bn",
        name="Bengali",
        native_name="বাংলা",
        script="Bengali",
        iso_639_1="bn",
        family="Indo-Aryan",
    ),
    "mr": LanguageInfo(
        code="mr",
        name="Marathi",
        native_name="मराठी",
        script="Devanagari",
        iso_639_1="mr",
        family="Indo-Aryan",
    ),
    "gu": LanguageInfo(
        code="gu",
        name="Gujarati",
        native_name="ગુજરાતી",
        script="Gujarati",
        iso_639_1="gu",
        family="Indo-Aryan",
    ),
    "ml": LanguageInfo(
        code="ml",
        name="Malayalam",
        native_name="മലയാളം",
        script="Malayalam",
        iso_639_1="ml",
        family="Dravidian",
    ),
    "pa": LanguageInfo(
        code="pa",
        name="Punjabi",
        native_name="ਪੰਜਾਬੀ",
        script="Gurmukhi",
        iso_639_1="pa",
        family="Indo-Aryan",
    ),
    "or": LanguageInfo(
        code="or",
        name="Odia",
        native_name="ଓଡ଼ିଆ",
        script="Odia",
        iso_639_1="or",
        family="Indo-Aryan",
    ),
    "hinglish": LanguageInfo(
        code="hinglish",
        name="Hinglish",
        native_name="Hinglish (Hindi in Latin script)",
        script="Latin",
        iso_639_1="hi-Latn",
        family="Code-Mixed",
    ),
}


class LanguageDetectionResult(BaseModel):
    """Result of script and language classification."""

    language_code: str
    language_name: str
    script: str
    confidence: float
    is_indic: bool
    is_code_mixed: bool
    details: dict[str, Any] = Field(default_factory=dict)


class LanguageDetector:
    """Detects native Indic scripts, Latin transliteration, and code-mixed Hinglish."""

    # Unicode script ranges
    SCRIPT_RANGES = {
        "Devanagari": (0x0900, 0x097F),
        "Bengali": (0x0980, 0x09FF),
        "Gurmukhi": (0x0A00, 0x0A7F),
        "Gujarati": (0x0A80, 0x0AFF),
        "Odia": (0x0B00, 0x0B7F),
        "Tamil": (0x0B80, 0x0BFF),
        "Telugu": (0x0C00, 0x0C7F),
        "Kannada": (0x0C80, 0x0CFF),
        "Malayalam": (0x0D00, 0x0D7F),
    }

    # Lexicon for Hinglish code-mixed query detection
    HINGLISH_WORDS = {
        "kya", "hai", "hain", "kaise", "karo", "karna", "chahiye", "kitna", "kitne",
        "samjhao", "batao", "aur", "lekin", "kyun", "hoga", "hogi", "tha", "thi", "kuch",
        "mujhe", "humein", "aapka", "apna", "nahi", "matlab", "shukriya", "namaste",
        "dhanyavad", "bhi", "toh", "sirf", "yahan", "wahan", "kaun", "kiska", "kab",
    }

    # Lexicon for Tanglish code-mixed query detection
    TANGLISH_WORDS = {
        "enna", "eppadi", "venum", "pannunga", "irukku", "solunga", "epdi", "romba",
        "illai", "aama", "ungalukku", "idhu", "adhu", "nandri", "vanakkam",
    }

    def detect(self, text: str) -> LanguageDetectionResult:
        """Classifies text into Indic script, code-mixed vernacular, or English."""
        if not text or not text.strip():
            return LanguageDetectionResult(
                language_code="en",
                language_name="English",
                script="Latin",
                confidence=1.0,
                is_indic=False,
                is_code_mixed=False,
            )

        # Count character frequencies across Unicode script blocks
        script_counts: dict[str, int] = {k: 0 for k in self.SCRIPT_RANGES}
        latin_count = 0
        total_chars = 0

        for ch in text:
            code_point = ord(ch)
            if ch.isalpha():
                total_chars += 1
                matched = False
                for script_name, (start, end) in self.SCRIPT_RANGES.items():
                    if start <= code_point <= end:
                        script_counts[script_name] += 1
                        matched = True
                        break
                is_latin = (0x0041 <= code_point <= 0x005A) or (0x0061 <= code_point <= 0x007A)
                if not matched and is_latin:
                    latin_count += 1

        # Check native Indic scripts first
        for script_name, count in script_counts.items():
            if count > 0 and (count / max(1, total_chars)) >= 0.25:
                lang_code = self._map_script_to_language(script_name, text)
                info = SUPPORTED_INDIC_LANGUAGES.get(lang_code, SUPPORTED_INDIC_LANGUAGES["hi"])
                conf = round(count / max(1, total_chars), 3)
                return LanguageDetectionResult(
                    language_code=info.code,
                    language_name=info.name,
                    script=script_name,
                    confidence=conf,
                    is_indic=True,
                    is_code_mixed=False,
                    details={"matched_chars": count, "total_chars": total_chars},
                )

        # Check for Latin-script Code-Mixed Vernacular (Hinglish / Tanglish)
        tokens = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
        hinglish_matches = tokens.intersection(self.HINGLISH_WORDS)
        tanglish_matches = tokens.intersection(self.TANGLISH_WORDS)

        if len(hinglish_matches) >= 1:
            ratio = len(hinglish_matches) / max(1, len(tokens))
            return LanguageDetectionResult(
                language_code="hinglish",
                language_name="Hinglish",
                script="Latin",
                confidence=round(min(1.0, ratio * 2.5), 3),
                is_indic=True,
                is_code_mixed=True,
                details={"indic_tokens": list(hinglish_matches)},
            )

        if len(tanglish_matches) >= 1:
            return LanguageDetectionResult(
                language_code="ta",
                language_name="Tamil (Tanglish)",
                script="Latin",
                confidence=0.85,
                is_indic=True,
                is_code_mixed=True,
                details={"indic_tokens": list(tanglish_matches)},
            )

        # Default fallback to English
        return LanguageDetectionResult(
            language_code="en",
            language_name="English",
            script="Latin",
            confidence=0.95,
            is_indic=False,
            is_code_mixed=False,
        )

    def _map_script_to_language(self, script: str, text: str) -> str:
        """Disambiguates language for shared scripts (e.g., Devanagari for Hindi vs Marathi)."""
        if script == "Devanagari":
            # Marathi distinctive characters / markers
            if "ळ" in text or any(w in text for w in ("आहे", "नाही", "करा", "झाले", "म्हणून")):
                return "mr"
            return "hi"
        mapping = {
            "Tamil": "ta",
            "Telugu": "te",
            "Kannada": "kn",
            "Bengali": "bn",
            "Gujarati": "gu",
            "Malayalam": "ml",
            "Gurmukhi": "pa",
            "Odia": "or",
        }
        return mapping.get(script, "hi")


class ScriptNormalizer:
    """Normalizes Unicode characters and derives semantic search queries."""

    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalizes Unicode characters into NFC canonical composition."""
        if not text:
            return ""
        norm = unicodedata.normalize("NFC", text)
        return re.sub(r"\s+", " ", norm).strip()

    @staticmethod
    def derive_semantic_query(text: str, detected: LanguageDetectionResult) -> str:
        """Derives a normalized query for dense vector retrieval.

        BGE-M3 is multilingual, but stripping conversational code-mixed filler words
        (e.g., 'mujhe batao', 'kya hai') improves retrieval precision.
        """
        if not detected.is_code_mixed:
            return text

        tokens = text.split()
        cleaned_tokens = [
            t for t in tokens
            if t.lower().strip("?,.") not in LanguageDetector.HINGLISH_WORDS
        ]
        derived = " ".join(cleaned_tokens).strip()
        return derived if derived else text


class CrossLingualBridge:
    """Orchestrates multilingual prompt synthesis and bilingual citations."""

    def __init__(self) -> None:
        self.detector = LanguageDetector()
        self.normalizer = ScriptNormalizer()

    def resolve_target_language(
        self,
        query: str,
        requested_target: str | None = None,
    ) -> tuple[LanguageInfo, LanguageDetectionResult]:
        """Resolves effective target language (defaults to query language if AUTO)."""
        detection = self.detector.detect(query)
        if requested_target and requested_target.lower() != "auto":
            code = requested_target.lower()
            lang_info = SUPPORTED_INDIC_LANGUAGES.get(code, SUPPORTED_INDIC_LANGUAGES["en"])
            return lang_info, detection

        # If auto, use detected language (or English if en)
        code = detection.language_code
        lang_info = SUPPORTED_INDIC_LANGUAGES.get(code, SUPPORTED_INDIC_LANGUAGES["en"])
        return lang_info, detection

    def build_multilingual_system_prompt(
        self,
        base_system_prompt: str,
        target_lang: LanguageInfo,
        detected_lang: LanguageDetectionResult,
    ) -> str:
        """Injects explicit multilingual synthesis instructions for Sarvam-105B."""
        if target_lang.code == "en" and not detected_lang.is_indic:
            return base_system_prompt

        lang_name = target_lang.name
        native_script = target_lang.native_name

        directive = (
            f"\n\n[LINGUISTIC REQUIREMENT]: You MUST generate your complete final answer in "
            f"{lang_name} ({native_script}). "
            f"Ground your answer strictly on the provided context. "
            f"Preserve technical terms, numbers, metrics, and legal names accurately while "
            f"writing natural, fluent, professional {lang_name}."
        )
        if target_lang.code == "hinglish":
            directive = (
                "\n\n[LINGUISTIC REQUIREMENT]: The user asked in Hinglish. You MUST generate "
                "your response in natural, professional Hinglish (Hindi in Latin script), "
                "strictly grounded on the provided context."
            )

        return base_system_prompt + directive


# Global singleton instances
_global_detector: LanguageDetector | None = None
_global_bridge: CrossLingualBridge | None = None


def get_language_detector() -> LanguageDetector:
    """Returns the singleton LanguageDetector instance."""
    global _global_detector
    if _global_detector is None:
        _global_detector = LanguageDetector()
    return _global_detector


def get_multilingual_bridge() -> CrossLingualBridge:
    """Returns the singleton CrossLingualBridge instance."""
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = CrossLingualBridge()
    return _global_bridge
