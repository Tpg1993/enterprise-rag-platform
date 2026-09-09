"""Local BGE-M3 embedding provider using sentence-transformers with fallback vector generator."""

import logging
import math

from src.embeddings.base import BaseEmbeddingProvider

logger = logging.getLogger(__name__)


class BGEEmbeddingProvider(BaseEmbeddingProvider):
    """Local BGE-M3 embedding generator supporting 1024-dimensional normalized vectors."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        dim: int = 1024,
        use_sentence_transformers: bool = True,
    ):
        self._model_name = model_name
        self._dimension = dim
        self._model = None

        if use_sentence_transformers:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"Loading local embedding model '{model_name}'...")
                self._model = SentenceTransformer(model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"Model '{model_name}' loaded (dim: {self._dimension}).")
            except Exception as e:
                logger.warning(
                    f"Could not load SentenceTransformer '{model_name}': {e}. Using local vectors."
                )

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if self._model:
            try:
                embeddings = self._model.encode(
                    texts, normalize_embeddings=True, show_progress_bar=False
                )
                return [e.tolist() for e in embeddings]
            except Exception as e:
                logger.warning(f"SentenceTransformer encoding failed: {e}. Falling back.")

        return [self._generate_fallback_vector(t) for t in texts]

    def embed_query(self, query: str) -> list[float]:
        if self._model:
            try:
                embedding = self._model.encode(
                    query, normalize_embeddings=True, show_progress_bar=False
                )
                return [float(x) for x in embedding]
            except Exception as e:
                logger.warning(f"SentenceTransformer query encoding failed: {e}. Falling back.")

        return self._generate_fallback_vector(query)

    def _generate_fallback_vector(self, text: str) -> list[float]:
        """Generates a deterministic 1024-dimensional normalized vector for offline mode."""
        vector = [0.0] * self._dimension
        hash_val = sum(ord(c) for c in text)
        for i in range(self._dimension):
            angle = (hash_val + i * 31) % 360
            vector[i] = math.sin(math.radians(angle))

        # Normalize
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]
