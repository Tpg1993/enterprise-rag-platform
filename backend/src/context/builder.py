"""ContextBuilder engine for token budgeting, text overlap deduplication, rich metadata headers, and citation formatting."""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field
from src.rag.base import Citation

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Estimates token count for text using standard word-to-token ratio (approx 1.3 tokens per word)."""
    if not text:
        return 0
    words = len(text.split())
    return int(words * 1.3) + 1


def jaccard_similarity(text1: str, text2: str) -> float:
    """Computes word-level Jaccard similarity between two text strings."""
    if not text1 or not text2:
        return 0.0
    s1 = set(re.findall(r"\w+", text1.lower()))
    s2 = set(re.findall(r"\w+", text2.lower()))
    if not s1 or not s2:
        return 0.0
    union = s1.union(s2)
    intersection = s1.intersection(s2)
    return len(intersection) / float(len(union))


class ContextBuildResult(BaseModel):
    """Structured result returned by ContextBuilder."""

    formatted_context: str
    citations: list[Citation] = Field(default_factory=list)
    total_tokens: int = 0
    deduplicated_count: int = 0
    trimmed_count: int = 0

    def __iter__(self):
        """Allows backwards compatible tuple unpacking (formatted_context, citations)."""
        return iter((self.formatted_context, self.citations))


class ContextBuilder:
    """Assembles and formats vector search hits into grounded LLM prompt context."""

    def __init__(
        self,
        max_context_tokens: int = 2048,
        overlap_threshold: float = 0.85,
    ):
        self.max_context_tokens = max_context_tokens
        self.overlap_threshold = overlap_threshold

    def build_context(
        self, search_hits: list[dict[str, Any]], max_context_tokens: int | None = None
    ) -> ContextBuildResult:
        """Deduplicates hits, enforces token limits, extracts citations, and builds formatted context."""
        effective_max_tokens = max_context_tokens or self.max_context_tokens
        if not search_hits:
            return ContextBuildResult(
                formatted_context="No relevant context found in knowledge base.",
                citations=[],
                total_tokens=7,
                deduplicated_count=0,
                trimmed_count=0,
            )

        citations: list[Citation] = []
        context_blocks: list[str] = []
        seen_chunk_ids: set[str] = set()
        seen_texts: list[str] = []

        accumulated_tokens = 0
        dedup_count = 0
        trimmed_count = 0

        for idx, hit in enumerate(search_hits):
            payload = hit.get("payload", {})
            chunk_id = hit.get("chunk_id") or payload.get("chunk_id") or f"hit_{idx}"

            # 1. Exact Chunk ID Deduplication
            if chunk_id in seen_chunk_ids:
                dedup_count += 1
                continue

            content = hit.get("content") or payload.get("content", "")
            if not content.strip():
                continue

            # 2. Jaccard Overlap Deduplication (Semantic text duplication check)
            if any(
                jaccard_similarity(content, prev_text) > self.overlap_threshold
                for prev_text in seen_texts
            ):
                dedup_count += 1
                continue

            chunk_tokens = estimate_tokens(content)

            # 3. Token Budgeting Check
            if accumulated_tokens + chunk_tokens > effective_max_tokens and context_blocks:
                logger.info(
                    f"Context token budget ({effective_max_tokens}) reached at hit {idx}. Truncating."
                )
                trimmed_count += len(search_hits) - idx
                break

            seen_chunk_ids.add(chunk_id)
            seen_texts.append(content)

            doc_id = hit.get("document_id") or payload.get("document_id", "doc_unknown")
            filename = (
                payload.get("metadata", {}).get("filename")
                or payload.get("filename")
                or doc_id
            )
            page = payload.get("page_number") or payload.get("page")
            section = (
                payload.get("metadata", {}).get("section_title")
                or payload.get("section_title")
            )
            security_class = payload.get("metadata", {}).get(
                "security_classification", "Internal"
            )
            score = float(hit.get("score", 0.0))

            # 4. Rich Metadata Header Assembly
            header_parts = [f"SOURCE {len(context_blocks) + 1}: {filename}"]
            if section:
                header_parts.append(f"Section: {section}")
            if page:
                header_parts.append(f"Page {page}")
            header_parts.append(f"Class: {security_class}")
            header_parts.append(f"Relevance: {round(score, 4)}")

            block_header = f"--- [ {' | '.join(header_parts)} ] ---"
            context_blocks.append(f"{block_header}\n{content.strip()}")
            accumulated_tokens += chunk_tokens

            citations.append(
                Citation(
                    document_id=doc_id,
                    filename=filename,
                    chunk_id=chunk_id,
                    content_snippet=content[:150] + ("..." if len(content) > 150 else ""),
                    page_number=page,
                    section_title=section,
                    relevance_score=round(score, 4),
                )
            )

        formatted_context = "\n\n".join(context_blocks)

        return ContextBuildResult(
            formatted_context=formatted_context,
            citations=citations,
            total_tokens=estimate_tokens(formatted_context),
            deduplicated_count=dedup_count,
            trimmed_count=trimmed_count,
        )
