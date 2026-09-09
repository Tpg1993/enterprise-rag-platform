"""Local Ollama container embedding provider."""

import logging

import httpx
from src.embeddings.base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class OllamaEmbeddingProvider(BaseEmbeddingProvider):
    """Client for local Ollama embedding service (e.g. bge-m3, nomic-embed-text)."""

    def __init__(
        self,
        endpoint_url: str = "http://localhost:11434",
        model_name: str = "bge-m3",
        dim: int = 1024,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model_name = model_name
        self._dimension = dim

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = []
        try:
            with httpx.Client(timeout=10.0) as client:
                for text in texts:
                    res = client.post(
                        f"{self.endpoint_url}/api/embeddings",
                        json={"model": self.model_name, "prompt": text},
                    )
                    if res.status_code == 200:
                        embeddings.append(res.json().get("embedding", [0.0] * self._dimension))
                    else:
                        break
            if len(embeddings) == len(texts):
                return embeddings
        except Exception as e:
            logger.warning(
                f"Ollama embedding failed at {self.endpoint_url} ({e}). Falling back to BGE-M3."
            )

        from src.embeddings.bge import BGEEmbeddingProvider

        return BGEEmbeddingProvider(dim=self._dimension).embed_documents(texts)

    def embed_query(self, query: str) -> list[float]:
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(
                    f"{self.endpoint_url}/api/embeddings",
                    json={"model": self.model_name, "prompt": query},
                )
                if res.status_code == 200:
                    raw_vec = res.json().get("embedding", [0.0] * self._dimension)
                    return [float(v) for v in raw_vec]
        except Exception as e:
            logger.warning(f"Ollama query embedding failed ({e}). Falling back to BGE-M3.")

        from src.embeddings.bge import BGEEmbeddingProvider

        return BGEEmbeddingProvider(dim=self._dimension).embed_query(query)
