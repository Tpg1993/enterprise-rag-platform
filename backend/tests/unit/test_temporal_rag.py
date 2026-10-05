"""Unit test suite for Temporal-Aware Time-Travel RAG & Version Diff Retrieval."""

from src.context.builder import ContextBuilder
from src.retrieval.temporal import (
    DocumentVersionEntry,
    DocumentVersionTimelineRegistry,
    TemporalFilter,
    TemporalPayloadValidator,
    TemporalQueryParser,
    VersionDiffSynthesizer,
)


class TestTemporalQueryParser:
    """Tests natural language temporal query parsing."""

    def setup_method(self) -> None:
        self.parser = TemporalQueryParser()

    def test_parse_as_of_date(self) -> None:
        query = "What were our SLA liabilities as of 2024-05-01?"
        cleaned, t_filter = self.parser.parse(query)
        assert t_filter.as_of_date == "2024-05-01"
        assert t_filter.temporal_mode == "point_in_time"
        assert "2024-05-01" in t_filter.extracted_expressions[0]
        assert "SLA liabilities" in cleaned

    def test_parse_quarter_expression(self) -> None:
        query = "Show data retention requirements in Q2 2024 for European branches"
        cleaned, t_filter = self.parser.parse(query)
        assert t_filter.start_date == "2024-04-01"
        assert t_filter.end_date == "2024-06-30"
        assert t_filter.temporal_mode == "range"
        assert "European branches" in cleaned

    def test_parse_year_expression(self) -> None:
        query = "Summarize the IT budget policy in 2023"
        cleaned, t_filter = self.parser.parse(query)
        assert t_filter.start_date == "2023-01-01"
        assert t_filter.end_date == "2023-12-31"
        assert t_filter.temporal_mode == "range"

    def test_parse_version_tag(self) -> None:
        query = "What was stated in amendment version 2 regarding uptime?"
        cleaned, t_filter = self.parser.parse(query)
        assert t_filter.target_version == "2"

    def test_parse_before_bound(self) -> None:
        query = "Review security measures implemented before 2024"
        _, t_filter = self.parser.parse(query)
        assert t_filter.end_date == "2024-01-01"
        assert t_filter.temporal_mode == "range"

    def test_parse_non_temporal_query(self) -> None:
        query = "How do I configure employee access permissions?"
        cleaned, t_filter = self.parser.parse(query)
        assert t_filter.as_of_date is None
        assert t_filter.start_date is None
        assert len(t_filter.extracted_expressions) == 0
        assert cleaned == query


class TestTemporalPayloadValidator:
    """Tests chunk temporal validity evaluation and status assignment."""

    def test_point_in_time_active(self) -> None:
        payload = {
            "effective_from": "2024-01-01",
            "effective_until": "2024-12-31",
            "version": "2.0",
        }
        t_filter = TemporalFilter(as_of_date="2024-06-15", temporal_mode="point_in_time")
        is_valid, status = TemporalPayloadValidator.evaluate_chunk(payload, t_filter)
        assert is_valid is True
        assert status == "active"

    def test_point_in_time_deprecated(self) -> None:
        payload = {
            "effective_from": "2023-01-01",
            "effective_until": "2023-12-31",
            "version": "1.0",
        }
        t_filter = TemporalFilter(as_of_date="2024-06-15", temporal_mode="point_in_time")
        is_valid, status = TemporalPayloadValidator.evaluate_chunk(payload, t_filter)
        assert is_valid is False
        assert status == "deprecated"

    def test_point_in_time_future(self) -> None:
        payload = {
            "effective_from": "2025-01-01",
            "effective_until": "2025-12-31",
            "version": "3.0",
        }
        t_filter = TemporalFilter(as_of_date="2024-06-15", temporal_mode="point_in_time")
        is_valid, status = TemporalPayloadValidator.evaluate_chunk(payload, t_filter)
        assert is_valid is False
        assert status == "future"

    def test_version_mismatch(self) -> None:
        payload = {
            "effective_from": "2024-01-01",
            "effective_until": "2024-12-31",
            "version": "1.0",
        }
        t_filter = TemporalFilter(target_version="2.0")
        is_valid, status = TemporalPayloadValidator.evaluate_chunk(payload, t_filter)
        assert is_valid is False
        assert status == "version_mismatch"


class TestTimelineRegistryAndDiff:
    """Tests timeline tracking and revision diff synthesis."""

    def test_timeline_registry_seed_and_retrieval(self) -> None:
        registry = DocumentVersionTimelineRegistry()
        timeline = registry.get_timeline(document_id="doc_msa_v1")
        assert len(timeline) == 1
        assert timeline[0].version == "1.0"
        assert timeline[0].status == "deprecated"

    def test_timeline_record_custom_version(self) -> None:
        registry = DocumentVersionTimelineRegistry()
        custom = DocumentVersionEntry(
            document_id="doc_custom",
            filename="Custom_Agreement_v4.pdf",
            version="4.0",
            effective_from="2026-01-01",
            effective_until="9999-12-31",
            status="active",
            summary="Custom amendment test",
            change_description="Upgraded custom terms",
        )
        registry.record_version(custom)
        entry = registry.get_version("doc_custom", "4.0")
        assert entry is not None
        assert entry.summary == "Custom amendment test"

    def test_version_diff_synthesizer(self) -> None:
        text_v1 = "1. Uptime commitment is 99.5%.\n2. Liability cap is $1,000,000."
        text_v2 = (
            "1. Uptime commitment is 99.9%.\n"
            "2. Liability cap is $5,000,000.\n"
            "3. AI guardrails."
        )
        result = VersionDiffSynthesizer.synthesize_diff(text_v1, text_v2, "v1", "v2")
        assert result.added_count >= 1
        assert result.modified_count >= 1
        assert result.similarity_ratio > 0.0
        assert "Comparison between 'v1' and 'v2'" in result.summary


class TestContextBuilderTemporalAnnotations:
    """Tests temporal status tagging in ContextBuilder."""

    def test_context_builder_temporal_annotations(self) -> None:
        builder = ContextBuilder()
        hits = [
            {
                "chunk_id": "c1",
                "document_id": "doc1",
                "content": "Clause 1: 99.9% availability is guaranteed across enterprise clusters.",
                "score": 0.95,
                "payload": {
                    "filename": "SLA_2024.pdf",
                    "effective_from": "2024-01-01",
                    "effective_until": "2024-12-31",
                    "security_classification": "Internal",
                },
            },
            {
                "chunk_id": "c2",
                "document_id": "doc2",
                "content": "Legacy Clause: 99.0% availability for standard clusters.",
                "score": 0.88,
                "payload": {
                    "filename": "SLA_2022.pdf",
                    "effective_from": "2022-01-01",
                    "effective_until": "2022-12-31",
                    "security_classification": "Internal",
                },
            },
        ]
        res = builder.build_context(hits, as_of_date="2024-06-01")
        assert "Temporal: ⏳ ACTIVE" in res.formatted_context
        assert "Temporal: ⌛ DEPRECATED" in res.formatted_context
        assert len(res.citations) == 2
        assert res.citations[0].temporal_status == "active"
        assert res.citations[1].temporal_status == "deprecated"
