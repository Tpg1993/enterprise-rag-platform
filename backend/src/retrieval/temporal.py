"""Temporal-Aware Time-Travel RAG & Version Diff Retrieval Engine.

Provides temporal query parsing, point-in-time state locking, version
timeline tracking, and side-by-side revision diff synthesis.
"""

from __future__ import annotations

import difflib
import logging
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TemporalFilter(BaseModel):
    """Filter parameters for point-in-time and range-based temporal retrieval."""

    as_of_date: str | None = Field(
        default=None,
        description="Snapshot target date in YYYY-MM-DD format for point-in-time retrieval",
    )
    start_date: str | None = Field(
        default=None,
        description="Range start date in YYYY-MM-DD format",
    )
    end_date: str | None = Field(
        default=None,
        description="Range end date in YYYY-MM-DD format",
    )
    temporal_mode: str = Field(
        default="point_in_time",
        description="Mode: point_in_time, range, latest_active, or all",
    )
    target_version: str | None = Field(
        default=None,
        description="Explicit document revision or version tag (e.g. v1, v2, 2.0)",
    )
    extracted_expressions: list[str] = Field(
        default_factory=list,
        description="Raw temporal expressions parsed from user query",
    )


class TemporalQueryParser:
    """Parses natural language queries to extract dates, quarters, and version tags."""

    # Patterns
    RE_AS_OF = re.compile(
        r"\b(?:as of|as-of|time travel to|snapshot at)\s+([0-9]{4}(?:-[0-9]{2}-[0-9]{2})?)\b",
        re.IGNORECASE,
    )
    RE_QUARTER = re.compile(
        r"\b(?:in|during|for)?\s*(Q[1-4])\s*(20[0-9]{2})\b|\b(20[0-9]{2})\s*(Q[1-4])\b",
        re.IGNORECASE,
    )
    RE_YEAR_RANGE = re.compile(
        r"\b(?:from|between)\s+(20[0-9]{2}(?:-[0-9]{2}-[0-9]{2})?)\s+(?:to|and)\s+"
        r"(20[0-9]{2}(?:-[0-9]{2}-[0-9]{2})?)\b",
        re.IGNORECASE,
    )
    RE_BEFORE_AFTER = re.compile(
        r"\b(before|prior to|until|after|since)\s+(20[0-9]{2}(?:-[0-9]{2}-[0-9]{2})?)\b",
        re.IGNORECASE,
    )
    RE_YEAR_ONLY = re.compile(
        r"\b(?:in|during|for year|year)\s+(20[0-9]{2})\b",
        re.IGNORECASE,
    )
    RE_VERSION = re.compile(
        r"\b(?:version|v|amendment|rev|revision)\s*([0-9]+(?:\.[0-9]+)?)\b",
        re.IGNORECASE,
    )

    QUARTER_MAP = {
        "Q1": ("-01-01", "-03-31"),
        "Q2": ("-04-01", "-06-30"),
        "Q3": ("-07-01", "-09-30"),
        "Q4": ("-10-01", "-12-31"),
    }

    def parse(
        self,
        query: str,
        default_as_of: str | None = None,
        default_mode: str | None = None,
    ) -> tuple[str, TemporalFilter]:
        """Extracts temporal boundaries from query string.

        Returns (cleaned_query, temporal_filter).
        """
        extracted: list[str] = []
        as_of_date: str | None = default_as_of
        start_date: str | None = None
        end_date: str | None = None
        target_version: str | None = None
        mode: str = default_mode or ("point_in_time" if default_as_of else "latest_active")

        # 1. As-of date pattern
        m_as_of = self.RE_AS_OF.search(query)
        if m_as_of:
            raw_date = m_as_of.group(1)
            extracted.append(m_as_of.group(0))
            as_of_date = self._normalize_date(raw_date)
            mode = "point_in_time"

        # 2. Year Range: 'from 2023 to 2024' or 'between 2022-01-01 and 2023-12-31'
        m_range = self.RE_YEAR_RANGE.search(query)
        if m_range:
            extracted.append(m_range.group(0))
            start_date = self._normalize_date(m_range.group(1), is_end=False)
            end_date = self._normalize_date(m_range.group(2), is_end=True)
            mode = "range"

        # 3. Quarter: 'in Q2 2024' or '2023 Q4'
        m_q = self.RE_QUARTER.search(query)
        if m_q and not start_date:
            q_num = (m_q.group(1) or m_q.group(4)).upper()
            year = m_q.group(2) or m_q.group(3)
            extracted.append(m_q.group(0))
            q_bounds = self.QUARTER_MAP.get(q_num)
            if q_bounds:
                start_date = f"{year}{q_bounds[0]}"
                end_date = f"{year}{q_bounds[1]}"
                as_of_date = end_date
                mode = "range"

        # 4. Before / After: 'before 2024'
        m_ba = self.RE_BEFORE_AFTER.search(query)
        if m_ba and not start_date and not as_of_date:
            rel = m_ba.group(1).lower()
            val = self._normalize_date(m_ba.group(2))
            extracted.append(m_ba.group(0))
            if rel in ("before", "prior to", "until"):
                end_date = val
                as_of_date = val
                mode = "range"
            else:
                start_date = val
                mode = "range"

        # 5. Year only: 'in 2023'
        m_year = self.RE_YEAR_ONLY.search(query)
        if m_year and not as_of_date and not start_date:
            year = m_year.group(1)
            extracted.append(m_year.group(0))
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
            as_of_date = f"{year}-12-31"
            mode = "range"

        # 6. Version: 'version 2' or 'v2.1'
        m_ver = self.RE_VERSION.search(query)
        if m_ver:
            target_version = m_ver.group(1)
            extracted.append(m_ver.group(0))

        cleaned_query = query
        for expr in extracted:
            cleaned_query = re.sub(re.escape(expr), "", cleaned_query, flags=re.IGNORECASE)
        cleaned_query = re.sub(r"\s+", " ", cleaned_query).strip()
        if not cleaned_query:
            cleaned_query = query

        temporal_filter = TemporalFilter(
            as_of_date=as_of_date,
            start_date=start_date,
            end_date=end_date,
            temporal_mode=mode,
            target_version=target_version,
            extracted_expressions=extracted,
        )
        return cleaned_query, temporal_filter

    def _normalize_date(self, raw: str, is_end: bool = False) -> str:
        """Converts year or YYYY-MM-DD into a standard YYYY-MM-DD string."""
        raw = raw.strip()
        if len(raw) == 4 and raw.isdigit():
            return f"{raw}-12-31" if is_end else f"{raw}-01-01"
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d")
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return raw


class TemporalPayloadValidator:
    """Validates chunk payloads against temporal snapshot and range constraints."""

    @staticmethod
    def extract_bounds(payload: dict[str, Any]) -> tuple[str, str, str]:
        """Extracts (effective_from, effective_until, version) from chunk payload."""
        meta = payload.get("metadata", {})
        eff_from = (
            payload.get("effective_from")
            or meta.get("effective_from")
            or "1900-01-01"
        )
        eff_until = (
            payload.get("effective_until")
            or meta.get("effective_until")
            or "9999-12-31"
        )
        version = str(
            payload.get("version")
            or meta.get("version")
            or "1.0"
        )
        return str(eff_from), str(eff_until), version

    @classmethod
    def determine_status(
        cls,
        effective_from: str,
        effective_until: str,
        as_of_date: str | None = None,
    ) -> str:
        """Computes chunk status (active, deprecated, or future) relative to as_of_date."""
        target = as_of_date or datetime.now().strftime("%Y-%m-%d")
        if target < effective_from:
            return "future"
        if target > effective_until:
            return "deprecated"
        return "active"

    @classmethod
    def evaluate_chunk(
        cls,
        payload: dict[str, Any],
        temporal_filter: TemporalFilter,
    ) -> tuple[bool, str]:
        """Returns (is_valid, temporal_status) for a chunk given a TemporalFilter."""
        eff_from, eff_until, version = cls.extract_bounds(payload)

        # Version match if requested
        if temporal_filter.target_version:
            req_ver = temporal_filter.target_version.lower().lstrip("v")
            cur_ver = version.lower().lstrip("v")
            if req_ver != cur_ver:
                return False, "version_mismatch"

        # Mode check
        if temporal_filter.temporal_mode == "all":
            status = cls.determine_status(eff_from, eff_until, temporal_filter.as_of_date)
            return True, status

        # Point in time
        if temporal_filter.as_of_date:
            as_of = temporal_filter.as_of_date
            status = cls.determine_status(eff_from, eff_until, as_of)
            is_valid = status == "active"
            return is_valid, status

        # Range filter
        if temporal_filter.start_date or temporal_filter.end_date:
            start = temporal_filter.start_date or "1900-01-01"
            end = temporal_filter.end_date or "9999-12-31"
            # Overlaps if not completely before or completely after
            overlaps = not (eff_until < start or eff_from > end)
            status = "active" if overlaps else "out_of_range"
            return overlaps, status

        # Default: latest_active relative to current date
        status = cls.determine_status(eff_from, eff_until, datetime.now().strftime("%Y-%m-%d"))
        return True, status


class DocumentVersionEntry(BaseModel):
    """Chronological document version record."""

    document_id: str
    filename: str
    version: str
    effective_from: str
    effective_until: str
    status: str = "active"
    summary: str = ""
    change_description: str = ""
    author: str = "Enterprise User"
    tenant_id: str = "default_tenant"
    created_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class DocumentVersionTimelineRegistry:
    """Registry maintaining chronological version timelines across documents."""

    def __init__(self) -> None:
        self._entries: list[DocumentVersionEntry] = []
        self._seed_default_timelines()

    def _seed_default_timelines(self) -> None:
        """Seeds benchmark SLA & MSA version history for out-of-the-box time travel."""
        defaults = [
            DocumentVersionEntry(
                document_id="doc_msa_v1",
                filename="Master_Services_Agreement_2023.pdf",
                version="1.0",
                effective_from="2023-01-01",
                effective_until="2023-12-31",
                status="deprecated",
                summary="Standard enterprise MSA baseline with 99.5% uptime commitment.",
                change_description="Initial corporate agreement baseline.",
                author="Legal Counsel",
            ),
            DocumentVersionEntry(
                document_id="doc_msa_v2",
                filename="Master_Services_Agreement_2024.pdf",
                version="2.0",
                effective_from="2024-01-01",
                effective_until="2024-12-31",
                status="deprecated",
                summary="Amended enterprise MSA with 99.9% uptime and $5M liability cap.",
                change_description="Upgraded uptime SLA and increased liability limit.",
                author="Legal Counsel",
            ),
            DocumentVersionEntry(
                document_id="doc_msa_v3",
                filename="Master_Services_Agreement_2025_Current.pdf",
                version="3.0",
                effective_from="2025-01-01",
                effective_until="9999-12-31",
                status="active",
                summary="Current active MSA with 99.99% multi-region uptime and AI guardrails.",
                change_description="Added AI safety and multi-region disaster recovery SLAs.",
                author="Chief Legal Officer",
            ),
            DocumentVersionEntry(
                document_id="doc_sec_2023",
                filename="Information_Security_Policy_v1.pdf",
                version="1.0",
                effective_from="2023-01-01",
                effective_until="2024-06-30",
                status="deprecated",
                summary="Password rotation policy and AES-128 minimum encryption requirements.",
                change_description="Baseline security standard.",
                author="CISO Office",
            ),
            DocumentVersionEntry(
                document_id="doc_sec_2024",
                filename="Information_Security_Policy_v2.pdf",
                version="2.0",
                effective_from="2024-07-01",
                effective_until="9999-12-31",
                status="active",
                summary="Zero Trust architecture, FIDO2 passkeys, and AES-256 with quantum-safe.",
                change_description="Mandated passkeys and post-quantum encryption readiness.",
                author="CISO Office",
            ),
        ]
        self._entries.extend(defaults)

    def record_version(self, entry: DocumentVersionEntry) -> None:
        """Appends a new document version entry."""
        self._entries.append(entry)

    def get_timeline(
        self,
        document_id: str | None = None,
        tenant_id: str = "default_tenant",
    ) -> list[DocumentVersionEntry]:
        """Returns sorted chronological timeline for a document or tenant."""
        res = [
            e for e in self._entries
            if (not document_id or e.document_id == document_id)
            and (e.tenant_id == tenant_id or e.tenant_id == "default_tenant")
        ]
        res.sort(key=lambda x: (x.effective_from, x.version))
        return res

    def get_version(self, document_id: str, version: str) -> DocumentVersionEntry | None:
        """Finds specific version entry by doc_id and version string."""
        for e in self._entries:
            if e.document_id == document_id and e.version == version:
                return e
        return None


class VersionDiffResult(BaseModel):
    """Structured diff summary between two document versions or time points."""

    source_label: str
    target_label: str
    similarity_ratio: float
    added_count: int
    removed_count: int
    modified_count: int
    added_clauses: list[str] = Field(default_factory=list)
    removed_clauses: list[str] = Field(default_factory=list)
    modified_clauses: list[dict[str, str]] = Field(default_factory=list)
    unified_diff: str = ""
    summary: str = ""


class VersionDiffSynthesizer:
    """Synthesizes chunk-level and line-level diffs between document revisions."""

    @staticmethod
    def synthesize_diff(
        text_a: str,
        text_b: str,
        label_a: str = "Revision A (Old)",
        label_b: str = "Revision B (New)",
    ) -> VersionDiffResult:
        """Computes unified diff, clause differences, and semantic delta."""
        lines_a = [line.strip() for line in text_a.splitlines() if line.strip()]
        lines_b = [line.strip() for line in text_b.splitlines() if line.strip()]

        line_matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        char_matcher = difflib.SequenceMatcher(None, " ".join(lines_a), " ".join(lines_b))
        similarity = round(char_matcher.ratio(), 4)

        diff_lines = list(
            difflib.unified_diff(
                lines_a,
                lines_b,
                fromfile=label_a,
                tofile=label_b,
                lineterm="",
            )
        )
        unified_diff_str = "\n".join(diff_lines)

        added: list[str] = []
        removed: list[str] = []
        modified: list[dict[str, str]] = []

        for tag, i1, i2, j1, j2 in line_matcher.get_opcodes():
            if tag == "insert":
                added.extend(lines_b[j1:j2])
            elif tag == "delete":
                removed.extend(lines_a[i1:i2])
            elif tag == "replace":
                sub_a = lines_a[i1:i2]
                sub_b = lines_b[j1:j2]
                min_len = min(len(sub_a), len(sub_b))
                for idx in range(min_len):
                    modified.append({"from": sub_a[idx], "to": sub_b[idx]})
                if len(sub_b) > min_len:
                    added.extend(sub_b[min_len:])
                elif len(sub_a) > min_len:
                    removed.extend(sub_a[min_len:])

        summary = (
            f"Comparison between '{label_a}' and '{label_b}': "
            f"{len(added)} clauses added, {len(removed)} clauses removed, "
            f"{len(modified)} modified. Overall content similarity: {round(similarity * 100, 1)}%."
        )

        return VersionDiffResult(
            source_label=label_a,
            target_label=label_b,
            similarity_ratio=similarity,
            added_count=len(added),
            removed_count=len(removed),
            modified_count=len(modified),
            added_clauses=added[:15],
            removed_clauses=removed[:15],
            modified_clauses=modified[:10],
            unified_diff=unified_diff_str[:4000],
            summary=summary,
        )



# Global singleton instances
_global_timeline_registry: DocumentVersionTimelineRegistry | None = None
_global_query_parser: TemporalQueryParser | None = None
_global_diff_synthesizer: VersionDiffSynthesizer | None = None


def get_timeline_registry() -> DocumentVersionTimelineRegistry:
    """Returns the singleton DocumentVersionTimelineRegistry instance."""
    global _global_timeline_registry
    if _global_timeline_registry is None:
        _global_timeline_registry = DocumentVersionTimelineRegistry()
    return _global_timeline_registry


def get_temporal_parser() -> TemporalQueryParser:
    """Returns the singleton TemporalQueryParser instance."""
    global _global_query_parser
    if _global_query_parser is None:
        _global_query_parser = TemporalQueryParser()
    return _global_query_parser


def get_diff_synthesizer() -> VersionDiffSynthesizer:
    """Returns the singleton VersionDiffSynthesizer instance."""
    global _global_diff_synthesizer
    if _global_diff_synthesizer is None:
        _global_diff_synthesizer = VersionDiffSynthesizer()
    return _global_diff_synthesizer
