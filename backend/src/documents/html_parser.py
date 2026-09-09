"""HTML document parser using BeautifulSoup."""

import hashlib

from bs4 import BeautifulSoup
from src.documents.base import DocumentParser, ParsedChunk, ParsedDocument


class HTMLParser(DocumentParser):
    """Parses HTML documents and extracts text content while stripping tags."""

    def parse(self, file_bytes: bytes, filename: str, document_id: str) -> ParsedDocument:
        checksum = hashlib.md5(file_bytes).hexdigest()
        soup = BeautifulSoup(file_bytes, "html.parser")

        # Strip scripts and styling
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()

        text = soup.get_text(separator="\n\n").strip()
        lines = [line.strip() for line in text.split("\n\n") if line.strip()]
        full_text = "\n\n".join(lines)

        chunks = [
            ParsedChunk(
                chunk_index=i,
                content=line,
                metadata={"filename": filename},
            )
            for i, line in enumerate(lines)
        ]

        return ParsedDocument(
            document_id=document_id,
            filename=filename,
            file_type="html",
            full_text=full_text,
            chunks=chunks,
            checksum=checksum,
        )
