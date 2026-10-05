"""ContextBuilder engine for token budgeting, deduplication, headers, and citations."""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field
from src.rag.base import Citation
from src.security.abac_masker import get_abac_masker

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Estimates token count for text using standard word-to-token ratio (approx 1.3/word)."""
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
    compression_ratio: float = 1.0
    tokens_saved: int = 0
    is_compressed: bool = False

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
        self,
        search_hits: list[dict[str, Any]],
        max_context_tokens: int | None = None,
        enable_compression: bool = False,
        compression_target_ratio: float = 0.6,
        query: str = "",
        user_role: str = "USER",
    ) -> ContextBuildResult:
        """Deduplicates hits, enforces token limits, extracts citations,

        and builds formatted context.
        """
        effective_max_tokens = max_context_tokens or self.max_context_tokens
        if not search_hits:
            return ContextBuildResult(
                formatted_context="No relevant context found in knowledge base.",
                citations=[],
                total_tokens=7,
                deduplicated_count=0,
                trimmed_count=0,
                compression_ratio=1.0,
                tokens_saved=0,
                is_compressed=False,
            )

        citations: list[Citation] = []
        context_blocks: list[str] = []
        seen_chunk_ids: set[str] = set()
        seen_texts: list[str] = []

        accumulated_tokens = 0
        dedup_count = 0
        trimmed_count = 0
        total_raw_tokens = 0
        total_compressed_tokens = 0

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

            chunk_content = content
            orig_toks = estimate_tokens(content)
            comp_toks = orig_toks

            if enable_compression:
                from src.context.compression import SemanticContextCompressor

                compressor = SemanticContextCompressor(
                    default_target_ratio=compression_target_ratio
                )
                comp_text, _, _, c_toks = compressor.compress(
                    content, query=query, target_ratio=compression_target_ratio
                )
                chunk_content = comp_text
                comp_toks = c_toks

            chunk_tokens = estimate_tokens(chunk_content)
            total_raw_tokens += orig_toks
            total_compressed_tokens += comp_toks

            # 3. Token Budgeting Check
            if accumulated_tokens + chunk_tokens > effective_max_tokens and context_blocks:
                msg = f"Context token budget ({effective_max_tokens}) reached at hit {idx}."
                logger.info(msg)
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
            security_class = (
                payload.get("metadata", {}).get("security_classification")
                or payload.get("security_classification")
                or "Internal"
            )
            score = float(hit.get("score", 0.0))

            # Apply Zero-Trust ABAC Chunk Masking
            abac_masker = get_abac_masker()
            chunk_content, was_redacted, _ = abac_masker.mask_text(
                chunk_content,
                user_role=user_role,
                chunk_classification=security_class,
            )

            # 4. Rich Metadata Header Assembly
            header_parts = [f"SOURCE {len(context_blocks) + 1}: {filename}"]
            if section:
                header_parts.append(f"Section: {section}")
            if page:
                header_parts.append(f"Page {page}")
            header_parts.append(f"Class: {security_class}")
            if was_redacted:
                header_parts.append("ABAC: 🛡️ REDACTED")
            header_parts.append(f"Relevance: {round(score, 4)}")
            if enable_compression:
                header_parts.append("Compressed: 🗜️")

            block_header = f"--- [ {' | '.join(header_parts)} ] ---"
            context_blocks.append(f"{block_header}\n{chunk_content.strip()}")
            accumulated_tokens += chunk_tokens

            bbox = payload.get("bbox") or hit.get("bbox")
            page_dims = (
                payload.get("page_dimensions")
                or payload.get("metadata", {}).get("page_dimensions")
                or hit.get("page_dimensions")
            )

            # Sanitize citation content snippet
            snippet_raw = content[:150]
            masked_snippet, snippet_redacted, _ = abac_masker.mask_text(
                snippet_raw,
                user_role=user_role,
                chunk_classification=security_class,
            )
            is_cit_redacted = was_redacted or snippet_redacted

            citations.append(
                Citation(
                    document_id=doc_id,
                    filename=filename,
                    chunk_id=chunk_id,
                    content_snippet=masked_snippet + ("..." if len(content) > 150 else ""),
                    page_number=page,
                    section_title=section,
                    relevance_score=round(score, 4),
                    bbox=bbox,
                    page_dimensions=page_dims,
                    is_redacted=is_cit_redacted,
                    redaction_level=security_class if is_cit_redacted else None,
                )
            )

        formatted_context = "\n\n".join(context_blocks)

        actual_ratio = (
            round(total_compressed_tokens / max(1, total_raw_tokens), 3)
            if enable_compression and total_raw_tokens > 0
            else 1.0
        )
        tokens_saved = (
            max(0, total_raw_tokens - total_compressed_tokens) if enable_compression else 0
        )

        return ContextBuildResult(
            formatted_context=formatted_context,
            citations=citations,
            total_tokens=estimate_tokens(formatted_context),
            deduplicated_count=dedup_count,
            trimmed_count=trimmed_count,
            compression_ratio=actual_ratio,
            tokens_saved=tokens_saved,
            is_compressed=enable_compression,
        )
