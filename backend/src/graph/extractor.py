"""Entity and Relationship extractor leveraging Sarvam-105B LLM with heuristic fallbacks."""

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field
from src.llm import LLMProvider, get_llm_provider

logger = logging.getLogger(__name__)


class EntityTriple(BaseModel):
    """Knowledge graph relation triple representation."""

    subject: str
    predicate: str
    object: str
    subject_type: str = "Concept"
    object_type: str = "Concept"
    confidence: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """Result of entity and relationship extraction."""

    triples: list[EntityTriple] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    raw_response: str = ""


GRAPH_EXTRACTION_PROMPT = """You are a knowledge graph entity and relationship extractor.
Extract factual entities and relationships from the provided text as a valid JSON array of triples.
Each triple must have: "subject", "predicate", "object", "subject_type", "object_type".

Example Output:
[
  {{"subject": "FastAPI", "predicate": "SUPPORTS", "object": "Asynchronous Endpoints",
    "subject_type": "Framework", "object_type": "Feature"}},
  {{"subject": "Neo4j", "predicate": "STORES", "object": "Knowledge Graph",
    "subject_type": "Database", "object_type": "DataStructure"}}
]

Return ONLY the JSON array, with no Markdown fences, comments, or other text.

Text to analyze:
{text}
"""


TECH_KEYWORDS = {
    "fastapi", "qdrant", "postgresql", "postgres", "neo4j", "redis", "docker",
    "kubernetes", "python", "uvicorn", "bge", "bge-m3", "langchain", "langgraph",
    "sentence-transformers", "transformers", "opensearch", "prometheus", "grafana",
    "opentelemetry", "bm25", "cross-encoder", "ast", "sqlglot", "rest", "api",
    "jwt", "presidio", "opa", "embedding", "vector", "cache", "llm", "sqlite",
}

METRIC_KEYWORDS = {
    "latency", "ttft", "itl", "throughput", "uptime", "sla", "cost", "tokens",
    "precision", "recall", "faithfulness", "relevancy", "p95", "p99", "percent",
    "ms", "seconds", "multiplier", "ratio", "score", "ndcg", "mrr",
}

ORG_KEYWORDS = {
    "sarvam", "sarvam ai", "microsoft", "google", "deepmind", "openai", "baai",
    "anthropic", "meta", "huggingface", "iso", "nist", "enterprise", "organization",
    "corporation", "corp", "inc", "ltd", "company",
}

POLICY_KEYWORDS = {
    "gdpr", "hipaa", "soc2", "zero trust", "rbac", "abac", "pii", "redaction",
    "audit", "governance", "indemnity", "liability", "warranty", "breach", "penalty",
    "compliance", "security", "guardrail", "policy", "encryption",
}

PERSON_KEYWORDS = {
    "admin", "analyst", "viewer", "user", "author", "auditor", "architect",
    "engineer", "supervisor", "specialist", "agent", "dr", "prof", "mr", "ms",
    "mrs", "ceo", "cto", "cfo", "director", "manager", "chief", "lead", "scientist",
}


def _matches_keywords(text: str, keywords: set[str]) -> bool:
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text):
            return True
    return False


def classify_entity_type(entity_name: str) -> str:
    """Classifies an entity into a semantic category based on keywords and patterns."""
    clean = entity_name.strip().lower()
    if re.search(r"(\d+(\.\d+)?%|\d+\s*(ms|s|sec|tokens?|usd|\$))", clean):
        return "METRIC"
    if re.search(r"^(dr|prof|mr|ms|mrs)\.?\s+[a-z]", clean):
        return "PERSON"
    if _matches_keywords(clean, POLICY_KEYWORDS):
        return "POLICY"
    if _matches_keywords(clean, ORG_KEYWORDS):
        return "ORG"
    if _matches_keywords(clean, TECH_KEYWORDS):
        return "TECH"
    if _matches_keywords(clean, METRIC_KEYWORDS):
        return "METRIC"
    if _matches_keywords(clean, PERSON_KEYWORDS):
        return "PERSON"
    return "CONCEPT"


class GraphEntityExtractor:
    """Extracts entities and relationships from text documents and queries."""

    def __init__(self, llm_provider: LLMProvider | None = None):
        self.llm = llm_provider or get_llm_provider()

    async def aextract(self, text: str) -> ExtractionResult:
        """Asynchronously extracts relation triples from text using LLM with heuristic fallbacks."""
        if not text or not text.strip():
            return ExtractionResult()

        prompt = GRAPH_EXTRACTION_PROMPT.format(text=text.strip()[:3000])

        try:
            sys_prompt = "You are an expert knowledge graph extractor. Return valid JSON only."
            llm_res = await self.llm.agenerate(
                prompt=prompt,
                system_prompt=sys_prompt,
                temperature=0.0,
                max_tokens=1024,
            )
            raw_text = llm_res.content.strip()
            triples = self._parse_json_triples(raw_text)

            if not triples:
                triples = self._heuristic_extract(text)

        except Exception as e:
            logger.warning(
                f"LLM graph extraction encountered issue ({e}), using heuristic fallback."
            )
            triples = self._heuristic_extract(text)
            raw_text = "fallback_heuristics"

        entities = sorted(
            list(
                {t.subject.strip() for t in triples if t.subject.strip()}
                | {t.object.strip() for t in triples if t.object.strip()}
            )
        )

        # If entities are few, also extract candidate key phrases/entities from text
        stopwords = {
            "what", "which", "how", "does", "do", "is", "are", "the", "a", "an",
            "in", "on", "at", "by", "for", "with", "about", "against", "between",
            "into", "through", "during", "before", "after", "above", "below", "to",
            "from", "up", "down", "out", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where", "why",
            "all", "any", "both", "each", "few", "more", "most", "other", "some",
            "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "s", "t", "can", "will", "just", "don", "should", "now", "its",
        }
        tokens = [w.strip('?,.!":;()[]{}') for w in text.split()]
        cleaned_tokens = [w for w in tokens if w.lower() not in stopwords and len(w) > 1]

        extra_entities = set()
        for i, tok in enumerate(cleaned_tokens):
            extra_entities.add(tok)
            if i + 1 < len(cleaned_tokens):
                extra_entities.add(f"{tok} {cleaned_tokens[i+1]}")
                extra_entities.add(f"{tok}{cleaned_tokens[i+1]}")

        combined_entities = sorted(list(set(entities) | extra_entities))

        return ExtractionResult(
            triples=triples,
            entities=combined_entities,
            raw_response=raw_text,
        )

    def extract_sync(self, text: str) -> ExtractionResult:
        """Synchronous heuristic extraction without LLM calls (useful for instant ingestion)."""
        triples = self._heuristic_extract(text)
        entities = sorted(
            list(
                {t.subject.strip() for t in triples if t.subject.strip()}
                | {t.object.strip() for t in triples if t.object.strip()}
            )
        )
        return ExtractionResult(triples=triples, entities=entities, raw_response="sync_heuristic")

    def _parse_json_triples(self, raw_text: str) -> list[EntityTriple]:
        """Safely parses JSON array from LLM response text."""
        clean_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
        clean_text = re.sub(r"```\s*$", "", clean_text, flags=re.MULTILINE).strip()

        start = clean_text.find("[")
        end = clean_text.rfind("]")
        if start != -1 and end != -1 and end > start:
            clean_text = clean_text[start : end + 1]

        try:
            data = json.loads(clean_text)
            if isinstance(data, list):
                valid_triples = []
                for item in data:
                    if (
                        isinstance(item, dict)
                        and "subject" in item
                        and "predicate" in item
                        and "object" in item
                    ):
                        s_name = str(item["subject"]).strip()
                        o_name = str(item["object"]).strip()
                        s_type = str(
                            item.get("subject_type") or classify_entity_type(s_name)
                        ).strip()
                        o_type = str(
                            item.get("object_type") or classify_entity_type(o_name)
                        ).strip()
                        valid_triples.append(
                            EntityTriple(
                                subject=s_name,
                                predicate=str(item["predicate"]).strip().upper().replace(" ", "_"),
                                object=o_name,
                                subject_type=s_type,
                                object_type=o_type,
                                confidence=float(item.get("confidence", 0.95)),
                            )
                        )
                return valid_triples
        except Exception:
            pass

        return []

    def _heuristic_extract(self, text: str) -> list[EntityTriple]:
        """Deterministic linguistic heuristic pattern matcher for entity-relationship triples."""
        triples: list[EntityTriple] = []
        sentences = re.split(r"[.\n;]+", text)

        patterns = [
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:is a|is an|acts as|serves as)\s+"
                r"([A-Za-z0-9_\-\s]{2,40})",
                "IS_A",
            ),
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:uses|utilizes|leverages|applies)\s+"
                r"([A-Za-z0-9_\-\s]{2,40})",
                "USES",
            ),
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:contains|includes|consists of|stores)\s+"
                r"([A-Za-z0-9_\-\s]{2,40})",
                "CONTAINS",
            ),
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:supports|provides|enables|offers)\s+"
                r"([A-Za-z0-9_\-\s]{2,40})",
                "SUPPORTS",
            ),
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:depends on|relies on|requires)\s+"
                r"([A-Za-z0-9_\-\s]{2,40})",
                "DEPENDS_ON",
            ),
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+"
                r"(?:connects to|integrates with|communicates with)\s+"
                r"([A-Za-z0-9_\-\s]{2,40})",
                "CONNECTS_TO",
            ),
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:achieves|guarantees|targets|records)\s+"
                r"([A-Za-z0-9_\-\s\.\%]{2,40})",
                "ACHIEVES",
            ),
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:enforces|governs|complies with)\s+"
                r"([A-Za-z0-9_\-\s]{2,40})",
                "ENFORCES",
            ),
            (
                r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:deployed on|hosted on|runs on)\s+"
                r"([A-Za-z0-9_\-\s]{2,40})",
                "RUNS_ON",
            ),
        ]

        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            for pat, relation in patterns:
                matches = re.finditer(pat, s_clean, flags=re.IGNORECASE)
                for m in matches:
                    subj = m.group(1).strip()
                    obj = m.group(2).strip()
                    if len(subj) > 1 and len(obj) > 1 and subj.lower() != obj.lower():
                        s_type = classify_entity_type(subj)
                        o_type = classify_entity_type(obj)
                        triples.append(
                            EntityTriple(
                                subject=subj,
                                predicate=relation,
                                object=obj,
                                subject_type=s_type,
                                object_type=o_type,
                                confidence=0.88,
                            )
                        )

        # Deduplicate triples
        seen = set()
        unique_triples = []
        for t in triples:
            key = (t.subject.lower(), t.predicate.lower(), t.object.lower())
            if key not in seen:
                seen.add(key)
                unique_triples.append(t)

        return unique_triples
