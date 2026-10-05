"""Unit tests for Phase 47: Self-Query RAG & Metadata Filter Synthesizer."""

import pytest
from src.chunking.base import Chunk
from src.llm.mock import MockLLMProvider
from src.rag.base import RAGRequest
from src.rag.self_query.strategy import SelfQueryRAGStrategy
from src.retrieval.self_query import (
    FilterCondition,
    FilterOperator,
    SelfQueryCompiler,
    get_self_query_compiler,
)
from src.retrieval.vector_store import QdrantVectorStore


class TestSelfQueryCompiler:
    """Test suite verifying natural language parsing and structured filter compilation."""

    def setup_method(self) -> None:
        self.compiler = SelfQueryCompiler()

    def test_compile_sla_penalty_filter(self) -> None:
        q = "Find all clauses with SLA penalty > 10000"
        parsed = self.compiler.compile(q)
        assert len(parsed.filters) >= 1
        f = next((x for x in parsed.filters if x.field == "sla_penalty_usd"), None)
        assert f is not None
        assert f.operator == FilterOperator.GT
        assert f.value == 10000.0
        assert "penalty" not in parsed.semantic_query.lower()

    def test_compile_uptime_sla_percentage(self) -> None:
        q = "Show service commitments with uptime > 99.9%"
        parsed = self.compiler.compile(q)
        f = next((x for x in parsed.filters if x.field == "uptime_sla_pct"), None)
        assert f is not None
        assert f.operator == FilterOperator.GT
        assert f.value == 99.9

    def test_compile_classification_filter(self) -> None:
        q = "List data governance guidelines in CONFIDENTIAL documents"
        parsed = self.compiler.compile(q)
        f = next((x for x in parsed.filters if x.field == "classification"), None)
        assert f is not None
        assert f.operator == FilterOperator.EQ
        assert f.value == "CONFIDENTIAL"

    def test_compile_doc_type_filter(self) -> None:
        q = "Retrieve policy documents regarding incident reporting"
        parsed = self.compiler.compile(q)
        f = next((x for x in parsed.filters if x.field == "doc_type"), None)
        assert f is not None
        assert f.operator == FilterOperator.EQ
        assert f.value == "policy"

    def test_compile_year_filter_exact_and_relative(self) -> None:
        q1 = "What was the liability ceiling in 2024?"
        parsed1 = self.compiler.compile(q1)
        f1 = next((x for x in parsed1.filters if x.field == "year"), None)
        assert f1 is not None
        assert f1.operator == FilterOperator.EQ
        assert f1.value == 2024

        q2 = "Agreements executed after 2023"
        parsed2 = self.compiler.compile(q2)
        f2 = next((x for x in parsed2.filters if x.field == "year"), None)
        assert f2 is not None
        assert f2.operator == FilterOperator.GTE
        assert f2.value == 2023

    def test_compile_page_filter(self) -> None:
        q = "What are the definitions on page 4?"
        parsed = self.compiler.compile(q)
        f = next((x for x in parsed.filters if x.field == "page_number"), None)
        assert f is not None
        assert f.operator == FilterOperator.EQ
        assert f.value == 4

    def test_compile_document_id_filter(self) -> None:
        q = "Summarize terms in document Master_SLA_2024.pdf"
        parsed = self.compiler.compile(q)
        f = next((x for x in parsed.filters if x.field == "document_id"), None)
        assert f is not None
        assert f.operator == FilterOperator.EQ
        assert f.value == "Master_SLA_2024.pdf"

    def test_compile_composite_multiple_filters(self) -> None:
        q = "Find confidential contracts from 2024 with penalty > $5,000"
        parsed = self.compiler.compile(q)
        fields = {f.field for f in parsed.filters}
        assert "classification" in fields
        assert "doc_type" in fields
        assert "year" in fields
        assert "sla_penalty_usd" in fields
        assert parsed.semantic_query != ""

    def test_compile_pure_semantic_query_no_filters(self) -> None:
        q = "What are our enterprise disaster recovery goals?"
        parsed = self.compiler.compile(q)
        assert len(parsed.filters) == 0
        assert parsed.semantic_query == q
        assert "No explicit metadata" in parsed.explanation


class TestQdrantFilterTranslationAndMatching:
    """Test suite for Qdrant filter translation and in-memory payload matching."""

    def setup_method(self) -> None:
        self.compiler = get_self_query_compiler()

    def test_qdrant_filter_generation(self) -> None:
        q = "Contracts with penalty > 10000"
        parsed = self.compiler.compile(q)
        qdrant_filter = self.compiler.to_qdrant_filter(parsed, tenant_id="tenant_alpha")
        assert qdrant_filter is not None
        assert hasattr(qdrant_filter, "must")
        keys = [getattr(c, "key", "") for c in qdrant_filter.must]
        assert "tenant_id" in keys
        assert "sla_penalty_usd" in keys

    def test_matches_payload_numeric_and_categorical(self) -> None:
        payload = {
            "document_id": "sla_2024.pdf",
            "doc_type": "contract",
            "classification": "CONFIDENTIAL",
            "sla_penalty_usd": 15000.0,
            "year": 2024,
            "metadata": {"author": "LegalOps"},
        }

        cond_penalty = FilterCondition(
            field="sla_penalty_usd", operator=FilterOperator.GT, value=10000.0
        )
        assert self.compiler.matches_payload(payload, cond_penalty) is True

        cond_penalty_high = FilterCondition(
            field="sla_penalty_usd", operator=FilterOperator.GT, value=20000.0
        )
        assert self.compiler.matches_payload(payload, cond_penalty_high) is False

        cond_class = FilterCondition(
            field="classification", operator=FilterOperator.EQ, value="CONFIDENTIAL"
        )
        assert self.compiler.matches_payload(payload, cond_class) is True

        cond_author = FilterCondition(
            field="author", operator=FilterOperator.EQ, value="LegalOps"
        )
        assert self.compiler.matches_payload(payload, cond_author) is True


@pytest.mark.asyncio
class TestSelfQueryRAGStrategy:
    """Integration test suite executing SelfQueryRAGStrategy."""

    async def test_self_query_strategy_end_to_end(self) -> None:
        store = QdrantVectorStore()
        chunks = [
            Chunk(
                chunk_id="chunk_sq_1",
                document_id="master_sla.pdf",
                tenant_id="tenant_sq",
                chunk_index=0,
                content="The contractor guarantees 99.9% uptime SLA with a $15,000 penalty.",
                metadata={
                    "doc_type": "contract",
                    "classification": "CONFIDENTIAL",
                    "sla_penalty_usd": 15000.0,
                },
            ),
            Chunk(
                chunk_id="chunk_sq_2",
                document_id="marketing.pdf",
                tenant_id="tenant_sq",
                chunk_index=0,
                content="Marketing brand colors and typography guidelines for 2024 campaign.",
                metadata={
                    "doc_type": "report",
                    "classification": "PUBLIC",
                    "sla_penalty_usd": 0.0,
                },
            ),
        ]
        vectors = [[0.1] * 1024, [0.9] * 1024]
        store.upsert_chunks(chunks, vectors)

        mock_llm = MockLLMProvider()
        strategy = SelfQueryRAGStrategy(vector_store=store, llm_provider=mock_llm)

        req = RAGRequest(
            query="Find confidential contracts with penalty > 10000",
            tenant_id="tenant_sq",
            rag_strategy="Self-Query-RAG",
            top_k=2,
        )
        res = await strategy.execute(req)

        assert res.rag_strategy == "Self-Query-RAG"
        assert res.answer is not None
        assert len(res.citations) >= 1
        # The retrieved citation must be the matching contract, not the marketing report
        assert res.citations[0].document_id == "master_sla.pdf"
