"""AST-based SQL Validator using sqlglot to strictly enforce read-only statements and security policies."""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SQLValidationResult(BaseModel):
    """Result of SQL AST security analysis."""

    is_valid: bool
    sanitized_sql: str = ""
    error_message: str = ""
    tables_referenced: list[str] = Field(default_factory=list)
    statement_type: str = "SELECT"


# Disallowed expression keywords and AST types
FORBIDDEN_KEYWORDS = {
    "DROP",
    "DELETE",
    "UPDATE",
    "INSERT",
    "TRUNCATE",
    "ALTER",
    "CREATE",
    "GRANT",
    "REVOKE",
    "EXECUTE",
    "EXEC",
    "CALL",
    "REPLACE",
    "SHUTDOWN",
}

# Tables allowed for querying in the enterprise platform
ALLOWED_TABLES = {
    "documents",
    "document_chunks",
    "rag_traces",
    "evaluations",
    "tenants",
    "audit_logs",
    "metrics",
}


class SQLValidator:
    """Validates and sanitizes SQL queries using Abstract Syntax Tree (AST) inspection."""

    def __init__(self, allowed_tables: set[str] | None = None, max_row_limit: int = 1000):
        self.allowed_tables = {t.lower() for t in (allowed_tables or ALLOWED_TABLES)}
        self.max_row_limit = max_row_limit

    def validate(self, sql_query: str, tenant_id: str | None = None) -> SQLValidationResult:
        """Parses and validates SQL query against security policies and read-only constraints."""
        if not sql_query or not sql_query.strip():
            return SQLValidationResult(
                is_valid=False,
                error_message="Empty SQL query provided.",
            )

        clean_sql = sql_query.strip().rstrip(";")

        # 1. Quick regex keyword check for dangerous commands
        for kw in FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{kw}\b", clean_sql, flags=re.IGNORECASE):
                logger.warning(f"Security Alert: Forbidden keyword '{kw}' detected in SQL: {clean_sql}")
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Forbidden operation: '{kw}' statements are strictly disallowed.",
                )

        # 2. Prevent semicolon statement chaining (prevent batch injection)
        statements = [s.strip() for s in sql_query.split(";") if s.strip()]
        if len(statements) > 1:
            return SQLValidationResult(
                is_valid=False,
                error_message="Multiple statement execution (semicolon chaining) is forbidden.",
            )

        # 3. AST Parsing via sqlglot
        try:
            import sqlglot
            from sqlglot import exp

            parsed = sqlglot.parse_one(clean_sql, read="postgres")
        except Exception as e:
            return SQLValidationResult(
                is_valid=False,
                error_message=f"SQL syntax error: Unable to parse query ({e}).",
            )

        # 4. Enforce Read-Only AST Type (Select, Union, or With/CTE)
        if not isinstance(parsed, (exp.Select, exp.Union)):
            return SQLValidationResult(
                is_valid=False,
                error_message=f"Only read-only SELECT queries are permitted (got {parsed.__class__.__name__}).",
            )

        # 5. Extract and Validate Referenced Tables
        tables: set[str] = set()
        for table in parsed.find_all(exp.Table):
            t_name = table.name.lower()
            if t_name:
                tables.add(t_name)

        # If specific allowed tables are configured, verify tables
        if self.allowed_tables and tables:
            unauthorized = [t for t in tables if t not in self.allowed_tables]
            if unauthorized:
                return SQLValidationResult(
                    is_valid=False,
                    error_message=f"Unauthorized table access: Table(s) '{', '.join(unauthorized)}' not in allowlist.",
                    tables_referenced=sorted(list(tables)),
                )

        # 6. Ensure row LIMIT does not exceed max_row_limit
        limit_exp = parsed.args.get("limit")
        if limit_exp is not None:
            try:
                limit_val = int(str(limit_exp.expression))
                if limit_val > self.max_row_limit:
                    parsed = parsed.limit(self.max_row_limit)
            except Exception:
                parsed = parsed.limit(self.max_row_limit)
        else:
            parsed = parsed.limit(self.max_row_limit)

        sanitized = parsed.sql(dialect="postgres")

        return SQLValidationResult(
            is_valid=True,
            sanitized_sql=sanitized,
            tables_referenced=sorted(list(tables)),
            statement_type="SELECT",
        )
