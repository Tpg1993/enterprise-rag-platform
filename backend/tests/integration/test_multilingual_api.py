"""Integration test suite for Cross-Lingual & Multi-Indic REST APIs."""

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


class TestMultilingualAPIIntegration:
    """Tests multilingual REST endpoints and chat integration."""

    def test_detect_language_endpoint_hindi(self) -> None:
        payload = {"text": "हमारी क्लाउड इंफ्रास्ट्रक्चर सुरक्षा नीति क्या है?"}
        res = client.post("/api/v1/multilingual/detect", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["language_code"] == "hi"
        assert data["script"] == "Devanagari"
        assert data["is_indic"] is True

    def test_detect_language_endpoint_hinglish(self) -> None:
        payload = {"text": "mujhe server downtime compensation policy samjhao"}
        res = client.post("/api/v1/multilingual/detect", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["language_code"] == "hinglish"
        assert data["is_code_mixed"] is True

    def test_supported_languages_catalog(self) -> None:
        res = client.get("/api/v1/multilingual/supported-languages")
        assert res.status_code == 200
        langs = res.json()
        assert isinstance(langs, list)
        assert len(langs) >= 10
        codes = [item["code"] for item in langs]
        assert "hi" in codes
        assert "ta" in codes
        assert "te" in codes
        assert "kn" in codes
        assert "bn" in codes
        assert "en" in codes

    def test_normalize_endpoint(self) -> None:
        payload = {"text": "mujhe enterprise data policy batao"}
        res = client.post("/api/v1/multilingual/normalize", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "normalized" in data
        assert "derived_query" in data
        assert "enterprise data policy" in data["derived_query"]

    def test_chat_with_explicit_indic_target_language(self) -> None:
        payload = {
            "query": "What is our uptime SLA guarantee?",
            "rag_strategy": "Basic",
            "target_language": "hi",
            "user_role": "ADMIN",
        }
        res = client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert data["target_language"] == "hi"

    def test_chat_with_auto_indic_detection(self) -> None:
        payload = {
            "query": "कंपनी की सुरक्षा नीति क्या है?",
            "rag_strategy": "Basic",
            "target_language": "auto",
            "user_role": "USER",
        }
        res = client.post("/api/v1/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["detected_language"] == "hi"
        assert data["target_language"] == "hi"
