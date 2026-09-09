"""Parser for plain text (.txt) and Markdown (.md) documents."""

import hashlib

from src.documents.base import DocumentParser, ParsedChunk, ParsedDocument


class TextParser(DocumentParser):
    """Parses plain text and Markdown files."""

    def parse(self, file_bytes: bytes, filename: str, document_id: str) -> ParsedDocument:
        text = file_bytes.decode("utf-8", errors="replace")
        checksum = hashlib.md5(file_bytes).hexdigest()

        # Simple initial line/paragraph splitting for chunk candidates
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks = [
            ParsedChunk(
                chunk_index=i,
                content=para,
                metadata={"filename": filename},
            )
            for i, para in enumerate(paragraphs)
        ]

        return ParsedDocument(
            document_id=document_id,
            filename=filename,
            file_type="markdown" if filename.endswith(".md") else "text",
            full_text=text,
            chunks=chunks,
            checksum=checksum,
        )
