"""Autonomous Self-Querying & Metadata Filter Synthesizer for structured Qdrant retrieval."""

import logging
import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

try:
    from qdrant_client.http import models as qmodels
except ImportError:
    qmodels = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class FilterOperator(StrEnum):
    """Comparison operators for structured metadata filtering."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    CONTAINS = "contains"


class LogicalOperator(StrEnum):
    """Logical conjunction operators."""

    AND = "and"
    OR = "or"
    NOT = "not"


class MetadataFieldSchema(BaseModel):
    """Definition of an indexed document attribute available for query filtering."""

    name: str
    data_type: str  # str, int, float, date
    description: str
    allowed_values: list[str] | None = None


# Enterprise document metadata schema available for self-querying
DEFAULT_METADATA_CATALOG: list[MetadataFieldSchema] = [
    MetadataFieldSchema(
        name="doc_type",
        data_type="str",
        description="Category of the document",
        allowed_values=["contract", "policy", "report", "technical", "financial", "compliance"],
    ),
    MetadataFieldSchema(
        name="classification",
        data_type="str",
        description="Zero-Trust security classification level",
        allowed_values=["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED_LEGAL", "SECRET"],
    ),
    MetadataFieldSchema(
        name="year",
        data_type="int",
        description="Calendar year of publication or contract execution (e.g. 2023, 2024, 2025)",
    ),
    MetadataFieldSchema(
        name="page_number",
        data_type="int",
        description="Specific page number within document",
    ),
    MetadataFieldSchema(
        name="sla_penalty_usd",
        data_type="float",
        description="Financial penalty in USD for SLA breach or non-performance",
    ),
    MetadataFieldSchema(
        name="uptime_sla_pct",
        data_type="float",
        description="Service level agreement uptime commitment percentage (e.g. 99.9)",
    ),
    MetadataFieldSchema(
        name="author",
        data_type="str",
        description="Signatory, owner, or organization that authored the document",
    ),
    MetadataFieldSchema(
        name="document_id",
        data_type="str",
        description="Exact document filename or identifier",
    ),
]


class FilterCondition(BaseModel):
    """Single attribute condition extracted from a natural language query."""

    field: str
    operator: FilterOperator = FilterOperator.EQ
    value: Any
    original_text: str = ""


class ParsedSelfQuery(BaseModel):
    """Decomposed query with clean semantic query and synthesized filter criteria."""

    raw_query: str
    semantic_query: str
    filters: list[FilterCondition] = Field(default_factory=list)
    logical_operator: LogicalOperator = LogicalOperator.AND
    explanation: str = ""
    qdrant_filter_dict: dict[str, Any] = Field(default_factory=dict)


class SelfQueryCompiler:
    """Parses natural language queries to synthesize semantic queries & Qdrant filters."""

    def __init__(self, catalog: list[MetadataFieldSchema] | None = None):
        self.catalog = catalog or DEFAULT_METADATA_CATALOG
        self.catalog_map = {f.name: f for f in self.catalog}

    @staticmethod
    def _strip_span(text: str, match: re.Match[str]) -> str:
        return f"{text[:match.start()]} {text[match.end():]}"

    def compile(self, query: str) -> ParsedSelfQuery:
        """Extracts structured filter predicates and strips them from the semantic query."""
        if not query or not query.strip():
            return ParsedSelfQuery(raw_query="", semantic_query="")

        raw_query = query.strip()
        remaining_query = raw_query
        extracted_filters: list[FilterCondition] = []

        # 1. Extract SLA Penalty filter (e.g. "SLA penalty > 10000", "penalty >= $5,000")
        penalty_pattern = re.compile(
            r"\b(?:sla\s+)?penalty\s*(>|>=|<|<=|=|==|under|over|above|below)?\s*\$?"
            r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(?:k|usd|dollars)?\b",
            re.IGNORECASE,
        )
        match = penalty_pattern.search(remaining_query)
        if match:
            op_sym = match.group(1) or ">"
            val_str = match.group(2).replace(",", "")
            val = float(val_str)
            if "k" in match.group(0).lower() and val < 1000:
                val *= 1000.0

            op = self._map_operator(op_sym)
            cond = FilterCondition(
                field="sla_penalty_usd",
                operator=op,
                value=val,
                original_text=match.group(0),
            )
            extracted_filters.append(cond)
            remaining_query = self._strip_span(remaining_query, match)

        # 2. Extract Uptime SLA percentage (e.g. "uptime > 99.9%", "uptime sla >= 99.5")
        uptime_pattern = re.compile(
            r"\b(?:uptime(?:\s+sla)?|sla\s+uptime)\s*(>|>=|<|<=|=|==)?\s*"
            r"([0-9]{2}(?:\.[0-9]+)?)\s*%?\b",
            re.IGNORECASE,
        )
        match = uptime_pattern.search(remaining_query)
        if match:
            op_sym = match.group(1) or ">="
            val = float(match.group(2))
            op = self._map_operator(op_sym)
            cond = FilterCondition(
                field="uptime_sla_pct",
                operator=op,
                value=val,
                original_text=match.group(0),
            )
            extracted_filters.append(cond)
            remaining_query = self._strip_span(remaining_query, match)

        # 3. Extract Document Classification (e.g. "confidential", "SECRET classification")
        class_pattern = re.compile(
            r"\b(PUBLIC|INTERNAL|CONFIDENTIAL|RESTRICTED_LEGAL|SECRET)(?:\s+classification)?\b",
            re.IGNORECASE,
        )
        match = class_pattern.search(remaining_query)
        if match:
            val = match.group(1).upper()
            cond = FilterCondition(
                field="classification",
                operator=FilterOperator.EQ,
                value=val,
                original_text=match.group(0),
            )
            extracted_filters.append(cond)
            remaining_query = self._strip_span(remaining_query, match)

        # 4. Extract Document Type (e.g. "contracts", "policy", "financial report")
        doc_type_pattern = re.compile(
            r"\b(contract|policy|report|technical|financial|compliance)s?\b",
            re.IGNORECASE,
        )
        match = doc_type_pattern.search(remaining_query)
        if match:
            val = match.group(1).lower()
            cond = FilterCondition(
                field="doc_type",
                operator=FilterOperator.EQ,
                value=val,
                original_text=match.group(0),
            )
            extracted_filters.append(cond)
            remaining_query = self._strip_span(remaining_query, match)

        # 5. Extract Calendar Year (e.g. "in 2024", "from 2023", "year 2025", "after 2023")
        year_pattern = re.compile(
            r"\b(?:in|year|from|after|before|since)?\s*(after|before|since)?\s*(20[2-9][0-9])\b",
            re.IGNORECASE,
        )
        match = year_pattern.search(remaining_query)
        if match:
            qualifier = (match.group(1) or "").lower()
            year_val = int(match.group(2))
            op = FilterOperator.EQ
            if qualifier in ("after", "since"):
                op = FilterOperator.GTE
            elif qualifier == "before":
                op = FilterOperator.LT

            cond = FilterCondition(
                field="year",
                operator=op,
                value=year_val,
                original_text=match.group(0),
            )
            extracted_filters.append(cond)
            remaining_query = self._strip_span(remaining_query, match)

        # 6. Extract Page Number (e.g. "page 3", "on page 12")
        page_pattern = re.compile(r"\b(?:on\s+)?page\s+([0-9]+)\b", re.IGNORECASE)
        match = page_pattern.search(remaining_query)
        if match:
            page_val = int(match.group(1))
            cond = FilterCondition(
                field="page_number",
                operator=FilterOperator.EQ,
                value=page_val,
                original_text=match.group(0),
            )
            extracted_filters.append(cond)
            remaining_query = self._strip_span(remaining_query, match)

        # 7. Extract Document ID / Filename (e.g. "in document Cloud_SLA.pdf")
        doc_pattern = re.compile(
            r"\b(?:in\s+)?document\s+([a-zA-Z0-9_\-\.]+\.(?:pdf|docx|txt|md))\b",
            re.IGNORECASE,
        )
        match = doc_pattern.search(remaining_query)
        if match:
            doc_val = match.group(1)
            cond = FilterCondition(
                field="document_id",
                operator=FilterOperator.EQ,
                value=doc_val,
                original_text=match.group(0),
            )
            extracted_filters.append(cond)
            remaining_query = self._strip_span(remaining_query, match)

        # Clean up remaining semantic query
        clean_semantic = re.sub(r"\s+", " ", remaining_query).strip()
        if not clean_semantic:
            clean_semantic = raw_query

        qdrant_dict = self._build_qdrant_filter_dict(extracted_filters)

        explanation = (
            f"Extracted {len(extracted_filters)} metadata filter(s): "
            + ", ".join(f"{f.field} {f.operator.value} {f.value}" for f in extracted_filters)
            if extracted_filters
            else "No explicit metadata filter predicates detected; dense semantic query retained."
        )

        return ParsedSelfQuery(
            raw_query=raw_query,
            semantic_query=clean_semantic,
            filters=extracted_filters,
            logical_operator=LogicalOperator.AND,
            explanation=explanation,
            qdrant_filter_dict=qdrant_dict,
        )

    def _map_operator(self, sym: str | None) -> FilterOperator:
        if not sym:
            return FilterOperator.EQ
        s = sym.strip().lower()
        if s in (">", "over", "above"):
            return FilterOperator.GT
        elif s == ">=":
            return FilterOperator.GTE
        elif s in ("<", "under", "below"):
            return FilterOperator.LT
        elif s == "<=":
            return FilterOperator.LTE
        elif s in ("!=", "ne"):
            return FilterOperator.NE
        return FilterOperator.EQ

    def _build_qdrant_filter_dict(self, filters: list[FilterCondition]) -> dict[str, Any]:
        """Creates a JSON-serializable dictionary representation of Qdrant filter."""
        must_list = []
        for cond in filters:
            if cond.operator == FilterOperator.EQ:
                must_list.append({"key": cond.field, "match": {"value": cond.value}})
            elif cond.operator == FilterOperator.GT:
                must_list.append({"key": cond.field, "range": {"gt": cond.value}})
            elif cond.operator == FilterOperator.GTE:
                must_list.append({"key": cond.field, "range": {"gte": cond.value}})
            elif cond.operator == FilterOperator.LT:
                must_list.append({"key": cond.field, "range": {"lt": cond.value}})
            elif cond.operator == FilterOperator.LTE:
                must_list.append({"key": cond.field, "range": {"lte": cond.value}})
        return {"must": must_list} if must_list else {}

    def to_qdrant_filter(
        self,
        parsed: ParsedSelfQuery,
        tenant_id: str = "default_tenant",
    ) -> Any:
        """Translates ParsedSelfQuery into native Qdrant models.Filter object."""
        if qmodels is None:
            return None

        must_clauses: list[Any] = [
            qmodels.FieldCondition(
                key="tenant_id",
                match=qmodels.MatchValue(value=tenant_id),
            )
        ]

        for cond in parsed.filters:
            key = cond.field
            if cond.operator == FilterOperator.EQ:
                must_clauses.append(
                    qmodels.FieldCondition(
                        key=key,
                        match=qmodels.MatchValue(value=cond.value),
                    )
                )
            elif cond.operator == FilterOperator.GT:
                must_clauses.append(
                    qmodels.FieldCondition(
                        key=key,
                        range=qmodels.Range(gt=float(cond.value)),
                    )
                )
            elif cond.operator == FilterOperator.GTE:
                must_clauses.append(
                    qmodels.FieldCondition(
                        key=key,
                        range=qmodels.Range(gte=float(cond.value)),
                    )
                )
            elif cond.operator == FilterOperator.LT:
                must_clauses.append(
                    qmodels.FieldCondition(
                        key=key,
                        range=qmodels.Range(lt=float(cond.value)),
                    )
                )
            elif cond.operator == FilterOperator.LTE:
                must_clauses.append(
                    qmodels.FieldCondition(
                        key=key,
                        range=qmodels.Range(lte=float(cond.value)),
                    )
                )

        return qmodels.Filter(must=must_clauses)

    def matches_payload(self, payload: dict[str, Any], condition: FilterCondition) -> bool:
        """Evaluates whether an arbitrary chunk payload matches a FilterCondition."""
        field = condition.field
        val = payload.get(field)
        if val is None and "metadata" in payload and isinstance(payload["metadata"], dict):
            val = payload["metadata"].get(field)

        if val is None:
            if field == "doc_type":
                val = payload.get("document_type") or payload.get("category")
            elif field == "page_number":
                val = payload.get("page")
            elif field == "year":
                date_str = str(payload.get("effective_from") or payload.get("date") or "")
                if date_str and len(date_str) >= 4 and date_str[:4].isdigit():
                    val = int(date_str[:4])

        if val is None:
            return False

        target = condition.value
        op = condition.operator

        try:
            if op == FilterOperator.EQ:
                if isinstance(target, str):
                    return str(val).lower() == str(target).lower()
                return val == target
            elif op == FilterOperator.NE:
                if isinstance(target, str):
                    return str(val).lower() != str(target).lower()
                return val != target
            elif op == FilterOperator.GT:
                return float(val) > float(target)
            elif op == FilterOperator.GTE:
                return float(val) >= float(target)
            elif op == FilterOperator.LT:
                return float(val) < float(target)
            elif op == FilterOperator.LTE:
                return float(val) <= float(target)
            elif op == FilterOperator.CONTAINS:
                return str(target).lower() in str(val).lower()
        except (ValueError, TypeError):
            return False

        return False


_global_compiler: SelfQueryCompiler | None = None


def get_self_query_compiler() -> SelfQueryCompiler:
    """Singleton getter for SelfQueryCompiler."""
    global _global_compiler
    if _global_compiler is None:
        _global_compiler = SelfQueryCompiler()
    return _global_compiler
