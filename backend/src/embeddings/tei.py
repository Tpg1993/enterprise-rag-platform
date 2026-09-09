"""HuggingFace Text Embeddings Inference (TEI) Rust container client provider."""

import logging

import httpx
from src.embeddings.base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class TEIEmbeddingProvider(BaseEmbeddingProvider):
    """Client for TEI high-performance Rust embedding microservice."""

    def __init__(self, endpoint_url: str = "http://localhost:8080", dim: int = 1024):
        self.endpoint_url = endpoint_url.rstrip("/")
        self._dimension = dim

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(f"{self.endpoint_url}/embed", json={"inputs": texts})
                if res.status_code == 200:
                    data = res.json()
                    return [[float(v) for v in vec] for vec in data]
        except Exception as e:
            logger.warning(
                f"TEI service unavailable at {self.endpoint_url} ({e}). Falling back to BGE-M3."
            )

        from src.embeddings.bge import BGEEmbeddingProvider

        return BGEEmbeddingProvider(dim=self._dimension).embed_documents(texts)

    def embed_query(self, query: str) -> list[float]:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(f"{self.endpoint_url}/embed", json={"inputs": [query]})
                if res.status_code == 200:
                    data = res.json()
                    return [float(v) for v in data[0]]
        except Exception as e:
            logger.warning(f"TEI query embedding failed ({e}). Falling back to BGE-M3.")

        from src.embeddings.bge import BGEEmbeddingProvider

        return BGEEmbeddingProvider(dim=self._dimension).embed_query(query)
