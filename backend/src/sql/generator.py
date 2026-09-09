"""Text-to-SQL query generator leveraging Sarvam-105B LLM with schema grounding."""

import logging
import re

from src.llm import LLMProvider, get_llm_provider

logger = logging.getLogger(__name__)

ENTERPRISE_DB_SCHEMA_PROMPT = """You are an expert PostgreSQL DBA and Text-to-SQL engineer.
Generate a syntactically correct, read-only PostgreSQL query to answer the user request.
Adhere strictly to the provided database schema.

### Database Schema:
1. documents:
   - document_id (VARCHAR(64), PRIMARY KEY)
   - filename (VARCHAR(255))
   - file_type (VARCHAR(32))
   - total_chunks (INTEGER)
   - word_count (INTEGER)
   - author (VARCHAR(128))
   - security_classification (VARCHAR(32)) -- 'Public', 'Internal', 'Confidential'
   - version (INTEGER)
   - tenant_id (VARCHAR(64))
   - created_at (TIMESTAMP)

2. document_chunks:
   - chunk_id (VARCHAR(64), PRIMARY KEY)
   - document_id (VARCHAR(64), FOREIGN KEY -> documents.document_id)
   - content (TEXT)
   - token_count (INTEGER)
   - page_number (INTEGER)
   - section_title (VARCHAR(255))
   - tenant_id (VARCHAR(64))

3. rag_traces:
   - trace_id (VARCHAR(64), PRIMARY KEY)
   - strategy_name (VARCHAR(64))
   - query (TEXT)
   - latency_ms (FLOAT)
   - total_tokens (INTEGER)
   - estimated_cost_usd (FLOAT)
   - status (VARCHAR(32))
   - tenant_id (VARCHAR(64))
   - timestamp (TIMESTAMP)

4. evaluations:
   - eval_id (VARCHAR(64), PRIMARY KEY)
   - strategy_name (VARCHAR(64))
   - context_precision (FLOAT)
   - context_recall (FLOAT)
   - faithfulness (FLOAT)
   - answer_relevancy (FLOAT)
   - overall_score (FLOAT)
   - tenant_id (VARCHAR(64))

### Rules:
- Generate ONLY a SELECT query. Never use INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE.
- Filter by tenant_id = '{tenant_id}' when tenant data isolation applies.
- Always include a LIMIT clause (max 1000).
- Return ONLY the raw SQL query with no explanation, comments, or Markdown fences.

User Question: {query}
"""


class SQLGenerator:
    """Generates PostgreSQL queries from natural language questions using LLM."""

    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm = llm_provider or get_llm_provider()

    async def agenerate_sql(self, query: str, tenant_id: str = "default_tenant") -> str:
        """Asynchronously translates a natural language question into PostgreSQL query."""
        prompt = ENTERPRISE_DB_SCHEMA_PROMPT.format(query=query.strip(), tenant_id=tenant_id)

        try:
            llm_res = await self.llm.agenerate(
                prompt=prompt,
                system_prompt="You are a PostgreSQL query generator. Return only clean executable SQL.",
                temperature=0.0,
                max_tokens=512,
            )
            raw_sql = self._clean_sql_output(llm_res.content)
            if self._is_valid_sql_like(raw_sql):
                return raw_sql
        except Exception as e:
            logger.warning(f"LLM SQL generation error ({e}). Using deterministic rule fallback.")

        # Deterministic fallback heuristics for common analytical queries
        return self._heuristic_fallback_sql(query, tenant_id)

    def _clean_sql_output(self, raw_text: str) -> str:
        """Strips markdown code fences, comments, and extra whitespace."""
        clean = re.sub(r"^```(?:sql)?\s*", "", raw_text.strip(), flags=re.MULTILINE)
        clean = re.sub(r"```\s*$", "", clean, flags=re.MULTILINE).strip()
        # Remove single line comments
        clean = re.sub(r"--.*$", "", clean, flags=re.MULTILINE).strip()
        return clean.rstrip(";")

    def _is_valid_sql_like(self, text: str) -> bool:
        """Quick validation check if output looks like a SQL SELECT statement."""
        t = text.strip().upper()
        return t.startswith("SELECT") or t.startswith("WITH")

    def _heuristic_fallback_sql(self, query: str, tenant_id: str) -> str:
        """Generates standard PostgreSQL query using keyword patterns when LLM is in mock mode."""
        q_lower = query.lower()

        if "how many" in q_lower or "count" in q_lower or "number of" in q_lower:
            if "chunk" in q_lower:
                return f"SELECT COUNT(*) AS total_chunks FROM document_chunks WHERE tenant_id = '{tenant_id}' LIMIT 1"
            elif "trace" in q_lower or "quer" in q_lower:
                return f"SELECT COUNT(*) AS total_queries FROM rag_traces WHERE tenant_id = '{tenant_id}' LIMIT 1"
            else:
                return f"SELECT COUNT(*) AS total_documents FROM documents WHERE tenant_id = '{tenant_id}' LIMIT 1"

        if "latency" in q_lower or "fastest" in q_lower or "slowest" in q_lower or "performance" in q_lower:
            return f"SELECT strategy_name, AVG(latency_ms) AS avg_latency_ms, COUNT(*) AS sample_count FROM rag_traces WHERE tenant_id = '{tenant_id}' GROUP BY strategy_name ORDER BY avg_latency_ms ASC LIMIT 20"

        if "cost" in q_lower or "token" in q_lower:
            return f"SELECT strategy_name, SUM(total_tokens) AS total_tokens, SUM(estimated_cost_usd) AS total_cost_usd FROM rag_traces WHERE tenant_id = '{tenant_id}' GROUP BY strategy_name ORDER BY total_cost_usd DESC LIMIT 20"

        if "evaluation" in q_lower or "precision" in q_lower or "score" in q_lower or "faithfulness" in q_lower:
            return f"SELECT strategy_name, AVG(overall_score) AS avg_score, AVG(faithfulness) AS avg_faithfulness FROM evaluations WHERE tenant_id = '{tenant_id}' GROUP BY strategy_name ORDER BY avg_score DESC LIMIT 20"

        # Default query lists uploaded documents
        return f"SELECT document_id, filename, file_type, total_chunks, word_count, security_classification, created_at FROM documents WHERE tenant_id = '{tenant_id}' ORDER BY created_at DESC LIMIT 50"
