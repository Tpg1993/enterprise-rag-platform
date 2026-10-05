"""Unit test suite for Cross-Lingual & Multi-Indic Linguistic Bridge."""

from src.multilingual.bridge import (
    CrossLingualBridge,
    LanguageDetector,
    ScriptNormalizer,
)
from src.prompting.builder import PromptBuilder


class TestLanguageDetector:
    """Tests script classification and code-mixed vernacular detection."""

    def setup_method(self) -> None:
        self.detector = LanguageDetector()

    def test_detect_hindi_devanagari(self) -> None:
        text = "हमारी कंपनी की डेटा सुरक्षा नीति और सेवा स्तर का विवरण क्या है?"
        res = self.detector.detect(text)
        assert res.language_code == "hi"
        assert res.script == "Devanagari"
        assert res.is_indic is True
        assert res.is_code_mixed is False

    def test_detect_tamil(self) -> None:
        text = "எங்கள் நிறுவனத்தின் தகவல் பாதுகாப்பு மற்றும் விதிகள் என்ன?"
        res = self.detector.detect(text)
        assert res.language_code == "ta"
        assert res.script == "Tamil"
        assert res.is_indic is True

    def test_detect_telugu(self) -> None:
        text = "కంపెనీ డేటా భద్రతా నిబంధనలు మరియు ఒప్పందం ఏమిటి?"
        res = self.detector.detect(text)
        assert res.language_code == "te"
        assert res.script == "Telugu"
        assert res.is_indic is True

    def test_detect_kannada(self) -> None:
        text = "ಕಂಪನಿಯ ಡೇಟಾ ಸುರಕ್ಷತಾ ನೀತಿ ಮತ್ತು ನಿಯಮಗಳು ಏನು?"
        res = self.detector.detect(text)
        assert res.language_code == "kn"
        assert res.script == "Kannada"
        assert res.is_indic is True

    def test_detect_bengali(self) -> None:
        text = "আমাদের কোম্পানির ডেটা সুরক্ষা নীতি এবং চুক্তি কি?"
        res = self.detector.detect(text)
        assert res.language_code == "bn"
        assert res.script == "Bengali"
        assert res.is_indic is True

    def test_detect_gujarati(self) -> None:
        text = "અમારી કંપનીની સુરક્ષા નીતિ અને સેવા સ્તર શું છે?"
        res = self.detector.detect(text)
        assert res.language_code == "gu"
        assert res.script == "Gujarati"
        assert res.is_indic is True

    def test_detect_marathi(self) -> None:
        text = "आमच्या कंपनीचे सुरक्षा धोरण काय आहे आणि नियम काय आहेत?"
        res = self.detector.detect(text)
        assert res.language_code == "mr"
        assert res.is_indic is True

    def test_detect_code_mixed_hinglish(self) -> None:
        text = "mujhe company ki SLA uptime commitment samjhao aur penalty kitna hai batao"
        res = self.detector.detect(text)
        assert res.language_code == "hinglish"
        assert res.is_indic is True
        assert res.is_code_mixed is True
        assert "sla" in text.lower()

    def test_detect_english_standard(self) -> None:
        text = "What is the enterprise cloud uptime service level agreement?"
        res = self.detector.detect(text)
        assert res.language_code == "en"
        assert res.is_indic is False
        assert res.is_code_mixed is False


class TestScriptNormalizer:
    """Tests script canonicalization and search query optimization."""

    def test_unicode_normalization(self) -> None:
        text = "सुरक्षा   \t  \n  नीति"
        norm = ScriptNormalizer.normalize_text(text)
        assert norm == "सुरक्षा नीति"

    def test_derive_semantic_query_hinglish(self) -> None:
        detector = LanguageDetector()
        text = "mujhe enterprise cloud security policy batao"
        det = detector.detect(text)
        derived = ScriptNormalizer.derive_semantic_query(text, det)
        assert "mujhe" not in derived.lower()
        assert "batao" not in derived.lower()
        assert "enterprise cloud security policy" in derived


class TestCrossLingualBridgeAndPrompts:
    """Tests multilingual bridge prompt injection and language resolution."""

    def setup_method(self) -> None:
        self.bridge = CrossLingualBridge()
        self.prompt_builder = PromptBuilder()

    def test_resolve_target_language_auto_indic(self) -> None:
        query = "ನಮ್ಮ ಕಂಪನಿಯ ನೀತಿ ಏನು?"
        lang_info, det = self.bridge.resolve_target_language(query, "auto")
        assert lang_info.code == "kn"
        assert lang_info.name == "Kannada"
        assert det.is_indic is True

    def test_resolve_target_language_explicit_hindi(self) -> None:
        query = "What is the maximum liability cap?"
        lang_info, _ = self.bridge.resolve_target_language(query, "hi")
        assert lang_info.code == "hi"
        assert lang_info.native_name == "हिन्दी"

    def test_multilingual_prompt_builder_integration(self) -> None:
        query = "Explain our incident response protocol"
        context = "Incident response requires notification within 1 hour."
        res = self.prompt_builder.build_prompt(
            query=query,
            context=context,
            target_language="ta",
        )
        assert "Tamil (தமிழ்)" in res.system_prompt
        assert "LINGUISTIC DIRECTIVE:" in res.user_prompt
        assert "Tamil" in res.user_prompt
