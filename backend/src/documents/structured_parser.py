"""Parser for structured documents (CSV and JSON)."""

import csv
import hashlib
import io
import json

from src.documents.base import DocumentParser, ParsedChunk, ParsedDocument


class StructuredParser(DocumentParser):
    """Parses CSV and JSON structured documents into searchable chunks."""

    def parse(self, file_bytes: bytes, filename: str, document_id: str) -> ParsedDocument:
        checksum = hashlib.md5(file_bytes).hexdigest()
        text_content = file_bytes.decode("utf-8", errors="replace")
        chunks = []

        if filename.endswith(".csv"):
            file_type = "csv"
            reader = csv.DictReader(io.StringIO(text_content))
            rows = list(reader)
            full_text = "\n".join([json.dumps(row) for row in rows])
            for i, row in enumerate(rows):
                chunk_str = ", ".join([f"{k}: {v}" for k, v in row.items() if v])
                chunks.append(
                    ParsedChunk(
                        chunk_index=i,
                        content=chunk_str,
                        metadata={"filename": filename, "row": i + 1},
                    )
                )
        else:
            file_type = "json"
            try:
                data = json.loads(text_content)
                if isinstance(data, list):
                    full_text = "\n".join([json.dumps(item) for item in data])
                    for i, item in enumerate(data):
                        chunks.append(
                            ParsedChunk(
                                chunk_index=i,
                                content=json.dumps(item) if isinstance(item, dict) else str(item),
                                metadata={"filename": filename, "item": i},
                            )
                        )
                else:
                    full_text = json.dumps(data, indent=2)
                    chunks.append(
                        ParsedChunk(
                            chunk_index=0, content=full_text, metadata={"filename": filename}
                        )
                    )
            except Exception:
                full_text = text_content
                chunks.append(ParsedChunk(chunk_index=0, content=full_text))

        return ParsedDocument(
            document_id=document_id,
            filename=filename,
            file_type=file_type,
            full_text=full_text,
            chunks=chunks,
            checksum=checksum,
        )
