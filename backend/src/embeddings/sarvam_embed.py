"""Sarvam AI Cloud Embedding API Provider."""

import logging
import os

import httpx
from src.embeddings.base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class SarvamEmbeddingProvider(BaseEmbeddingProvider):
    """Sarvam AI Cloud API embedding provider (m2-mBERT-v1 / sarvam-embedding)."""

    def __init__(self, api_key: str | None = None, dim: int = 1024):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        self._dimension = dim
        self.endpoint_url = "https://api.sarvam.ai/v1/embeddings"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self.api_key:
            logger.info(
                "SARVAM_API_KEY not set for Sarvam embeddings. Falling back to local BGE-M3."
            )
            from src.embeddings.bge import BGEEmbeddingProvider

            return BGEEmbeddingProvider(dim=self._dimension).embed_documents(texts)

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(
                    self.endpoint_url,
                    headers={
                        "api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={"inputs": texts, "model": "sarvam-embedding-v1"},
                )
                if res.status_code == 200:
                    raw_embeds = res.json().get("embeddings", [])
                    return [[float(v) for v in vec] for vec in raw_embeds]
        except Exception as e:
            logger.warning(f"Sarvam AI embedding API error ({e}). Falling back to BGE-M3.")

        from src.embeddings.bge import BGEEmbeddingProvider

        return BGEEmbeddingProvider(dim=self._dimension).embed_documents(texts)

    def embed_query(self, query: str) -> list[float]:
        results = self.embed_documents([query])
        return results[0] if results else [0.0] * self._dimension
