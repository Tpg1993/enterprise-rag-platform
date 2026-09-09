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
  {{"subject": "FastAPI", "predicate": "SUPPORTS", "object": "Asynchronous Endpoints", "subject_type": "Framework", "object_type": "Feature"}},
  {{"subject": "Neo4j", "predicate": "STORES", "object": "Knowledge Graph", "subject_type": "Database", "object_type": "DataStructure"}}
]

Return ONLY the JSON array, with no Markdown fences, comments, or other text.

Text to analyze:
{text}
"""


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
            llm_res = await self.llm.agenerate(
                prompt=prompt,
                system_prompt="You are an expert knowledge graph extractor. Return valid JSON only.",
                temperature=0.0,
                max_tokens=1024,
            )
            raw_text = llm_res.content.strip()
            triples = self._parse_json_triples(raw_text)

            if not triples:
                # Fallback to heuristic extraction
                triples = self._heuristic_extract(text)

        except Exception as e:
            logger.warning(f"LLM graph extraction encountered issue ({e}), using heuristic fallback.")
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
            "from", "up", "down", "in", "out", "on", "off", "over", "under", "again",
            "further", "then", "once", "here", "there", "when", "where", "why",
            "all", "any", "both", "each", "few", "more", "most", "other", "some",
            "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too",
            "very", "s", "t", "can", "will", "just", "don", "should", "now", "its",
        }
        tokens = [w.strip('?,.!":;()[]{}') for w in text.split()]
        cleaned_tokens = [w for w in tokens if w.lower() not in stopwords and len(w) > 1]

        # Add single tokens and 2-grams
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
        # Strip markdown fences if present
        clean_text = re.sub(r"^```(?:json)?\s*", "", raw_text, flags=re.MULTILINE)
        clean_text = re.sub(r"```\s*$", "", clean_text, flags=re.MULTILINE).strip()

        # Find JSON array bracket boundaries
        start = clean_text.find("[")
        end = clean_text.rfind("]")
        if start != -1 and end != -1 and end > start:
            clean_text = clean_text[start : end + 1]

        try:
            data = json.loads(clean_text)
            if isinstance(data, list):
                valid_triples = []
                for item in data:
                    if isinstance(item, dict) and "subject" in item and "predicate" in item and "object" in item:
                        valid_triples.append(
                            EntityTriple(
                                subject=str(item["subject"]).strip(),
                                predicate=str(item["predicate"]).strip().upper().replace(" ", "_"),
                                object=str(item["object"]).strip(),
                                subject_type=str(item.get("subject_type", "Concept")).strip(),
                                object_type=str(item.get("object_type", "Concept")).strip(),
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
            (r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:is a|is an|acts as|serves as)\s+([A-Za-z0-9_\-\s]{2,40})", "IS_A"),
            (r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:uses|utilizes|leverages|applies)\s+([A-Za-z0-9_\-\s]{2,40})", "USES"),
            (r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:contains|includes|consists of|stores)\s+([A-Za-z0-9_\-\s]{2,40})", "CONTAINS"),
            (r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:supports|provides|enables|offers)\s+([A-Za-z0-9_\-\s]{2,40})", "SUPPORTS"),
            (r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:depends on|relies on|requires)\s+([A-Za-z0-9_\-\s]{2,40})", "DEPENDS_ON"),
            (r"([A-Z][A-Za-z0-9_\-\s]{2,30}?)\s+(?:connects to|integrates with|communicates with)\s+([A-Za-z0-9_\-\s]{2,40})", "CONNECTS_TO"),
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
                        triples.append(
                            EntityTriple(
                                subject=subj,
                                predicate=relation,
                                object=obj,
                                subject_type="Entity",
                                object_type="Entity",
                                confidence=0.85,
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
