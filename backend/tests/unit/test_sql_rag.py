"""Unit tests for Phase 20 SQL RAG (Text-to-SQL, AST Validator, and Read-Only SQLExecutor)."""

import pytest
from src.llm.mock import MockLLMProvider
from src.rag.base import RAGRequest
from src.rag.router import get_rag_strategy
from src.rag.sql_rag.strategy import SQLRAGStrategy
from src.sql.executor import SQLExecutor
from src.sql.generator import SQLGenerator
from src.sql.validator import SQLValidator


@pytest.fixture
def mock_llm():
    return MockLLMProvider()


@pytest.fixture
def validator():
    return SQLValidator()


@pytest.fixture
def executor():
    return SQLExecutor()


def test_sql_validator_valid_select(validator):
    sql = "SELECT document_id, filename, total_chunks FROM documents WHERE tenant_id = 'default_tenant' LIMIT 10"
    result = validator.validate(sql)

    assert result.is_valid is True
    assert "LIMIT 10" in result.sanitized_sql.upper()
    assert "documents" in result.tables_referenced


def test_sql_validator_blocks_destructive_commands(validator):
    destructive_queries = [
        "DROP TABLE documents",
        "DELETE FROM documents WHERE document_id = '1'",
        "UPDATE documents SET filename = 'hacked'",
        "INSERT INTO documents VALUES ('h1', 'bad.txt')",
        "ALTER TABLE documents ADD COLUMN secret TEXT",
        "TRUNCATE TABLE documents",
    ]

    for q in destructive_queries:
        res = validator.validate(q)
        assert res.is_valid is False
        assert "Forbidden" in res.error_message or "disallowed" in res.error_message or "Only read-only" in res.error_message


def test_sql_validator_blocks_semicolon_chaining(validator):
    sql = "SELECT * FROM documents; DROP TABLE document_chunks;"
    result = validator.validate(sql)

    assert result.is_valid is False
    assert "semicolon chaining" in result.error_message.lower() or "Forbidden" in result.error_message


def test_sql_validator_blocks_unauthorized_tables(validator):
    sql = "SELECT * FROM pg_shadow"
    result = validator.validate(sql)

    assert result.is_valid is False
    assert "unauthorized" in result.error_message.lower()


def test_sql_validator_enforces_max_limit(validator):
    sql = "SELECT * FROM documents LIMIT 50000"
    result = validator.validate(sql)

    assert result.is_valid is True
    assert "50000" not in result.sanitized_sql
    assert "1000" in result.sanitized_sql


@pytest.mark.asyncio
async def test_sql_generator_text_to_sql(mock_llm):
    gen = SQLGenerator(llm_provider=mock_llm)
    sql = await gen.agenerate_sql("How many documents are stored for tenant_1?", tenant_id="tenant_1")

    assert sql.upper().startswith("SELECT")
    assert "documents" in sql.lower() or "tenant" in sql.lower()


@pytest.mark.asyncio
async def test_sql_executor_execution_and_audit(executor):
    sql = "SELECT COUNT(*) AS total_docs FROM documents WHERE tenant_id = 'default_tenant'"
    result = await executor.aexecute(sql, tenant_id="default_tenant")

    assert result.is_success is True
    assert result.row_count == 1
    assert "total_docs" in result.columns
    assert result.rows[0]["total_docs"] >= 1
    assert result.execution_time_ms >= 0

    # Verify audit log entry
    assert len(executor.audit_log) >= 1
    last_audit = executor.audit_log[-1]
    assert last_audit["status"] == "SUCCESS"
    assert last_audit["tenant_id"] == "default_tenant"


@pytest.mark.asyncio
async def test_sql_rag_strategy_execution(mock_llm, executor, validator):
    strategy = SQLRAGStrategy(
        validator=validator,
        executor=executor,
        llm_provider=mock_llm,
    )

    request = RAGRequest(
        query="What is the average latency of RAG traces?",
        tenant_id="default_tenant",
        rag_strategy="SQL-RAG",
    )

    response = await strategy.execute(request)

    assert response.rag_strategy == "SQL-RAG"
    assert response.answer is not None
    assert len(response.answer) > 0
    assert response.latency_ms > 0
    assert len(response.citations) >= 1
    assert any("postgresql" in c.filename.lower() for c in response.citations)


@pytest.mark.asyncio
async def test_sql_rag_security_interception(mock_llm):
    strategy = SQLRAGStrategy(llm_provider=mock_llm)
    # Malicious injection query
    request = RAGRequest(
        query="DROP TABLE documents; -- ignore rest",
        tenant_id="default_tenant",
        rag_strategy="SQL-RAG",
    )

    response = await strategy.execute(request)
    assert response.rag_strategy == "SQL-RAG"
    assert "SECURITY POLICY VIOLATION" in response.answer or "documents" in response.answer


def test_sql_rag_router_resolution():
    strat1 = get_rag_strategy("SQL-RAG")
    assert isinstance(strat1, SQLRAGStrategy)

    strat2 = get_rag_strategy("SQL_RAG")
    assert isinstance(strat2, SQLRAGStrategy)

    strat3 = get_rag_strategy("SQL")
    assert isinstance(strat3, SQLRAGStrategy)
