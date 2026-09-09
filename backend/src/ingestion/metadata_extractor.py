"""Enterprise Metadata Extractor using structural rules and header inspection."""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ExtendedDocumentMetadata(BaseModel):
    file_size_human: str = "0 KB"
    file_size_bytes: int = 0
    word_count: int = 0
    char_count: int = 0
    author: str = "System"
    title: str = ""
    creation_date: str = "N/A"
    language: str = "en"
    security_classification: str = "Internal"
    has_pii: bool = False
    redacted_count: int = 0
    section_count: int = 0
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class EnterpriseMetadataExtractor:
    """Production 3-Tier Rule & Heuristic Metadata Extraction Engine."""

    @staticmethod
    def extract_metadata(
        file_bytes: bytes,
        filename: str,
        full_text: str,
        sanitized_text: str,
        parsed_metadata: dict[str, Any] | None = None,
    ) -> ExtendedDocumentMetadata:
        parsed_meta = parsed_metadata or {}
        file_size = len(file_bytes)
        if file_size < 1024 * 1024:
            size_human = f"{file_size / 1024:.1f} KB"
        else:
            size_human = f"{file_size / (1024 * 1024):.2f} MB"

        word_count = len(sanitized_text.split())
        char_count = len(sanitized_text)

        # Header Inspection (PDF / DOCX properties)
        author = parsed_meta.get("author") or "Enterprise User"
        title = parsed_meta.get("title") or filename
        creation_date = parsed_meta.get("creationDate") or parsed_meta.get("creation_date") or "N/A"

        # PII Detection Heuristic
        redacted_matches = re.findall(r"<REDACTED_[A-Z_]+>", sanitized_text)
        redacted_count = len(redacted_matches)
        has_pii = redacted_count > 0

        # Section Heading Heuristic
        section_headers = re.findall(r"(?:^|\n)(?:#+\s*|[A-Z0-9._\s]{3,30}:)", full_text)
        section_count = max(1, len(section_headers))

        # Rule-based Security Classification
        fn_upper = filename.upper()
        if "POLICY" in fn_upper or "RESTRICTED" in fn_upper or "CONFIDENTIAL" in fn_upper:
            sec_class = "Confidential"
        elif "PUBLIC" in fn_upper or "LICENSE" in fn_upper or "README" in fn_upper:
            sec_class = "Public"
        else:
            sec_class = "Internal"

        # Simple Rule-based Language Heuristic
        lang = "en"
        if re.search(r"[\u0900-\u097F]", full_text):
            lang = "hi"
        elif re.search(r"[\u0C00-\u0C7F]", full_text):
            lang = "te"

        return ExtendedDocumentMetadata(
            file_size_human=size_human,
            file_size_bytes=file_size,
            word_count=word_count,
            char_count=char_count,
            author=str(author),
            title=str(title),
            creation_date=str(creation_date),
            language=lang,
            security_classification=sec_class,
            has_pii=has_pii,
            redacted_count=redacted_count,
            section_count=section_count,
            raw_metadata=parsed_meta,
        )
