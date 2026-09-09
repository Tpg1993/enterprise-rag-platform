"""SQL RAG Strategy combining Text-to-SQL generation, AST security validation, and grounded answer synthesis."""

import logging
import time
import uuid

from src.context.builder import ContextBuilder
from src.llm import LLMProvider, get_llm_provider
from src.prompting.builder import PromptBuilder
from src.rag.base import BaseRAGStrategy, Citation, RAGRequest, RAGResponse
from src.sql.executor import SQLExecutor, get_sql_executor
from src.sql.generator import SQLGenerator
from src.sql.validator import SQLValidator

logger = logging.getLogger(__name__)


class SQLRAGStrategy(BaseRAGStrategy):
    """Text-to-SQL RAG strategy generating validated, read-only queries against relational databases."""

    def __init__(
        self,
        generator: SQLGenerator | None = None,
        validator: SQLValidator | None = None,
        executor: SQLExecutor | None = None,
        llm_provider: LLMProvider | None = None,
    ):
        self.llm_provider = llm_provider or get_llm_provider()
        self.generator = generator or SQLGenerator(self.llm_provider)
        self.validator = validator or SQLValidator()
        self.executor = executor or get_sql_executor()
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder()

    async def execute(self, request: RAGRequest) -> RAGResponse:
        start_time = time.perf_counter()
        trace_id = f"trace_sql_{uuid.uuid4().hex[:12]}"

        # 1. Translate natural language question into PostgreSQL query or pass raw SQL if provided
        query_upper = request.query.strip().upper()
        destructive_ops = ("DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ", "TRUNCATE ", "CREATE ", "GRANT ", "REVOKE ")
        if any(query_upper.startswith(op) for op in destructive_ops):
            raw_sql = request.query.strip()
        else:
            raw_sql = await self.generator.agenerate_sql(request.query, tenant_id=request.tenant_id)

        # 2. Enforce AST Security & Read-Only Validation via sqlglot
        val_result = self.validator.validate(raw_sql, tenant_id=request.tenant_id)
        if not val_result.is_valid:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            error_answer = (
                f"⚠️ [SQL SECURITY POLICY VIOLATION]: The generated query could not be executed.\n"
                f"Reason: {val_result.error_message}\n"
                f"Attempted SQL: `{raw_sql}`"
            )
            return RAGResponse(
                answer=error_answer,
                query=request.query,
                rag_strategy="SQL-RAG",
                citations=[],
                latency_ms=elapsed_ms,
                prompt_tokens=0,
                completion_tokens=len(error_answer.split()),
                estimated_cost_usd=0.0,
                model="sql-guardrail",
                trace_id=trace_id,
                tenant_id=request.tenant_id,
            )

        sanitized_sql = val_result.sanitized_sql

        # 3. Asynchronously Execute Query (5s timeout + row limit 1000)
        exec_result = await self.executor.aexecute(
            sanitized_sql=sanitized_sql,
            tenant_id=request.tenant_id,
        )

        if not exec_result.is_success:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return RAGResponse(
                answer=f"Database query execution error: {exec_result.error_message}",
                query=request.query,
                rag_strategy="SQL-RAG",
                citations=[],
                latency_ms=elapsed_ms,
                prompt_tokens=0,
                completion_tokens=20,
                estimated_cost_usd=0.0,
                model="sql-executor",
                trace_id=trace_id,
                tenant_id=request.tenant_id,
            )

        # 4. Format SQL Tabular Data into Markdown Context Representation
        md_table = self._rows_to_markdown(exec_result.columns, exec_result.rows)
        context_chunk = {
            "content": (
                f"PostgreSQL Query Executed:\n```sql\n{sanitized_sql}\n```\n\n"
                f"Query Results ({exec_result.row_count} rows in {exec_result.execution_time_ms:.1f}ms):\n"
                f"{md_table}"
            ),
            "payload": {
                "filename": "postgresql_relational_db",
                "document_id": "doc_sql_postgresql",
                "chunk_id": f"chunk_sql_{uuid.uuid4().hex[:8]}",
                "section_title": f"SQL Query: {sanitized_sql[:60]}",
            },
            "score": 0.99,
        }

        # 5. Build Context and Citations
        context_str, citations = self.context_builder.build_context(
            [context_chunk], max_context_tokens=request.max_context_tokens
        )

        # 6. Build Grounding Prompt and Synthesize Final Business Answer
        prompts = self.prompt_builder.build_prompt(request.query, context_str)
        llm_res = await self.llm_provider.agenerate(
            prompt=prompts["user"],
            system_prompt=(
                "You are an expert financial and business data analyst. "
                "Synthesize a clear, accurate, professional answer based strictly on the provided SQL query results. "
                "Quote exact metrics, numbers, and dates where applicable."
            ),
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Ensure citation has details
        if not citations:
            citations = [
                Citation(
                    document_id="doc_sql_postgresql",
                    filename="postgresql_relational_db",
                    chunk_id="chunk_sql_result",
                    content_snippet=f"SQL: {sanitized_sql} ({exec_result.row_count} rows)",
                    relevance_score=0.99,
                    section_title="PostgreSQL Relational DB",
                )
            ]

        answer_text = llm_res.content.strip()
        if not answer_text:
            answer_text = (
                f"Based on the PostgreSQL relational database query (`{sanitized_sql}`), "
                f"the database returned {exec_result.row_count} record(s):\n\n"
                f"{md_table}"
            )

        return RAGResponse(
            answer=answer_text,
            query=request.query,
            rag_strategy="SQL-RAG",
            citations=citations,
            latency_ms=elapsed_ms,
            prompt_tokens=llm_res.prompt_tokens,
            completion_tokens=llm_res.completion_tokens or len(answer_text.split()),
            estimated_cost_usd=llm_res.estimated_cost_usd,
            model=llm_res.model_name,
            trace_id=trace_id,
            tenant_id=request.tenant_id,
        )

    def _rows_to_markdown(self, columns: list[str], rows: list[dict]) -> str:
        """Converts dictionary rows into an aligned Markdown table string."""
        if not columns or not rows:
            return "*(No rows returned)*"

        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join(["---"] * len(columns)) + " |"
        row_lines = []

        for r in rows[:100]:  # Cap prompt context rows at 100
            values = [str(r.get(c, "")) for c in columns]
            row_lines.append("| " + " | ".join(values) + " |")

        return "\n".join([header, separator] + row_lines)
