"""Semantic Context Compressor (Phase 33).

Applies information-entropy scoring and entity-preserving token pruning
(inspired by LLMLingua) to compress retrieved context chunks by 30%–50%
while strictly preserving named entities, numbers, dates, and query terms.
"""

import logging
import math
import re
from typing import ClassVar

from pydantic import BaseModel

logger = logging.getLogger("SemanticContextCompressor")


class CompressionResult(BaseModel):
    """Result of semantic context compression with backward-compatible tuple unpacking."""

    compressed_text: str
    compression_ratio: float
    original_token_count: int
    compressed_token_count: int
    tokens_saved: int = 0
    is_compressed: bool = False

    def __iter__(self):
        """Allows unpacking as (compressed_text, ratio, orig_toks, comp_toks)."""
        return iter(
            (
                self.compressed_text,
                self.compression_ratio,
                self.original_token_count,
                self.compressed_token_count,
            )
        )


class SemanticContextCompressor:
    """Selective semantic token compressor for retrieved RAG contexts."""

    # Low-entropy conversational preambles and filler phrases to strip first
    FILLER_PHRASES: ClassVar[list[str]] = [
        r"\bit is important to note that\b",
        r"\bit should be noted that\b",
        r"\bas previously mentioned\b",
        r"\bas previously stated\b",
        r"\bas a matter of fact\b",
        r"\bfor the purpose of\b",
        r"\bin order to\b",
        r"\bneedless to say\b",
        r"\bwith that being said\b",
        r"\bat the end of the day\b",
        r"\bit goes without saying\b",
        r"\ball things considered\b",
        r"\bin summary,\b",
        r"\bto summarize,\b",
        r"\bessentially,\b",
        r"\bbasically,\b",
        r"\bfrankly speaking,\b",
        r"\bto put it simply,\b",
        r"\bin light of the fact that\b",
        r"\bdue to the fact that\b",
    ]

    # Stopwords eligible for pruning if they don't form protected entity names
    PRUNABLE_STOPWORDS: ClassVar[set[str]] = {
        "very", "quite", "really", "basically", "actually", "literally",
        "somewhat", "somehow", "perhaps", "maybe", "furthermore", "moreover",
        "additionally", "likewise", "consequently", "hence", "therefore",
        "thereby", "wherein", "whereupon", "heretofore", "aforementioned",
        "respective", "particular", "certain", "various", "several",
    }

    def __init__(self, default_target_ratio: float = 0.6) -> None:
        self.default_target_ratio = default_target_ratio

    def _is_protected_token(self, token: str, query_terms: set[str]) -> bool:
        """Determines if a token must never be pruned (numbers, entities, acronyms, query terms)."""
        clean = token.strip(".,;:!?()[]{}\"'`")
        if not clean:
            return False

        # 1. Matches query keyword
        if clean.lower() in query_terms:
            return True

        # 2. Numerical values, currency, percentages, dimensions (e.g. 1024, 0.7, $5.00, 95%, 50ms)
        if re.match(r"^[\$€£]?\d+(?:[\.,]\d+)*[%a-zA-Z]*$", clean):
            return True

        # 3. All uppercase acronyms or hyphenated codes (e.g. RAG, BGE-M3, JWT, OPA, RRF, Neo4j)
        if re.match(r"^[A-Z0-9_\-]+$", clean) and len(clean) >= 2:
            return True

        # 4. Capitalized Proper Noun (e.g. Sarvam, Qdrant, PostgreSQL)
        if clean[0].isupper() and len(clean) >= 3 and clean.isalpha():
            return True

        # 5. Version strings (e.g. v1.0.0)
        if re.match(r"^v?\d+\.\d+(?:\.\d+)?", clean, re.IGNORECASE):
            return True

        return False

    def _estimate_token_entropy(self, token: str, query_terms: set[str]) -> float:
        """Computes heuristic semantic information entropy score [0.0 - 1.0]."""
        clean = token.strip(".,;:!?()[]{}\"'`").lower()
        if not clean:
            return 0.0

        if self._is_protected_token(token, query_terms):
            return 1.0

        if clean in self.PRUNABLE_STOPWORDS:
            return 0.15

        # Word length and character diversity as proxy for lexical specificity
        length_factor = min(1.0, len(clean) / 10.0)
        unique_chars = len(set(clean))
        char_entropy = unique_chars / max(1, len(clean))

        score = (0.5 * length_factor) + (0.3 * char_entropy)
        return min(0.85, max(0.2, score))

    def compress(
        self,
        text: str,
        query: str = "",
        target_ratio: float | None = None,
    ) -> CompressionResult:
        """Compresses context text towards target_ratio (e.g. 0.6 = 40% reduction).

        Returns: CompressionResult with tuple unpacking support.
        """
        if not text or not text.strip():
            return CompressionResult(
                compressed_text=text,
                compression_ratio=1.0,
                original_token_count=0,
                compressed_token_count=0,
                tokens_saved=0,
                is_compressed=False,
            )

        ratio = target_ratio if target_ratio is not None else self.default_target_ratio
        ratio = max(0.2, min(1.0, ratio))

        # If ratio is 1.0, return original
        orig_words = text.split()
        original_tokens = int(len(orig_words) * 1.3) + 1
        if ratio >= 0.99 or len(orig_words) <= 15:
            return CompressionResult(
                compressed_text=text,
                compression_ratio=1.0,
                original_token_count=original_tokens,
                compressed_token_count=original_tokens,
                tokens_saved=0,
                is_compressed=False,
            )

        # Step 1: Pre-process query keywords
        query_terms = set(re.findall(r"\w+", query.lower())) if query else set()

        # Step 2: Strip conversational preambles and low-entropy filler phrases
        cleaned_text = text
        for filler in self.FILLER_PHRASES:
            cleaned_text = re.sub(filler, "", cleaned_text, flags=re.IGNORECASE)

        # Collapse redundant whitespace while keeping paragraph breaks
        cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

        # Step 3: Sentence-level token importance pruning
        sentences = re.split(r"(?<=[.!?])\s+", cleaned_text)
        compressed_sentences = []

        for sent in sentences:
            tokens = sent.split()
            if len(tokens) <= 5:
                compressed_sentences.append(sent)
                continue

            # Score each token
            scored_tokens = []
            for idx, tok in enumerate(tokens):
                is_prot = self._is_protected_token(tok, query_terms)
                score = 1.0 if is_prot else self._estimate_token_entropy(tok, query_terms)
                scored_tokens.append((idx, tok, score, is_prot))

            # Determine number of tokens to keep in this sentence
            target_keep = max(3, math.ceil(len(tokens) * ratio))

            # Always keep all protected tokens
            protected_indices = {idx for idx, _, _, is_p in scored_tokens if is_p}

            # If protected tokens already meet/exceed target, keep them all
            if len(protected_indices) >= target_keep:
                kept_indices = protected_indices
            else:
                # Rank non-protected tokens by entropy score
                non_prot = [item for item in scored_tokens if not item[3]]
                non_prot.sort(key=lambda x: x[2], reverse=True)
                needed = target_keep - len(protected_indices)
                selected_non_prot = {item[0] for item in non_prot[:needed]}
                kept_indices = protected_indices.union(selected_non_prot)

            # Reconstruct sentence in original token order
            kept_tokens = [tok for idx, tok, _, _ in scored_tokens if idx in kept_indices]

            # Rebuild sentence and preserve terminal punctuation
            rebuilt_sent = " ".join(kept_tokens)
            if rebuilt_sent and rebuilt_sent[-1] not in ".!?":
                if sent.endswith((".", "!", "?")):
                    rebuilt_sent += sent[-1]

            compressed_sentences.append(rebuilt_sent)

        compressed_text = " ".join(s for s in compressed_sentences if s.strip())
        compressed_text = re.sub(r"\s+([.,;:!?])", r"\1", compressed_text)

        comp_words = compressed_text.split()
        compressed_tokens = int(len(comp_words) * 1.3) + 1
        actual_ratio = round(compressed_tokens / max(1, original_tokens), 3)

        saved = max(0, original_tokens - compressed_tokens)
        is_comp = saved > 0 and actual_ratio < 1.0

        logger.debug(
            f"Context compressed: {original_tokens} -> {compressed_tokens} tokens "
            f"({(1.0 - actual_ratio) * 100:.1f}% reduction, target {ratio})"
        )

        return CompressionResult(
            compressed_text=compressed_text,
            compression_ratio=actual_ratio,
            original_token_count=original_tokens,
            compressed_token_count=compressed_tokens,
            tokens_saved=saved,
            is_compressed=is_comp,
        )
