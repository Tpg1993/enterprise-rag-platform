"""PyMuPDF parser for PDF documents with page numbers and metadata."""

import hashlib
import logging

import fitz  # PyMuPDF
from src.documents.base import DocumentParser, ParsedChunk, ParsedDocument

logger = logging.getLogger(__name__)


class PDFParser(DocumentParser):
    """Parses PDF documents using PyMuPDF (fitz)."""

    def parse(self, file_bytes: bytes, filename: str, document_id: str) -> ParsedDocument:
        checksum = hashlib.md5(file_bytes).hexdigest()
        full_text_list = []
        chunks = []
        chunk_idx = 0

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)

            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                page_text = page.get_text("text").strip()
                if page_text:
                    full_text_list.append(page_text)
                    chunks.append(
                        ParsedChunk(
                            chunk_index=chunk_idx,
                            content=page_text,
                            page_number=page_num + 1,
                            metadata={"filename": filename, "page": page_num + 1},
                        )
                    )
                    chunk_idx += 1
            doc.close()

            full_text = "\n\n".join(full_text_list)
        except Exception as e:
            logger.warning(f"PyMuPDF parse error for {filename}: {e}. Fallback to plain decoding.")
            full_text = file_bytes.decode("utf-8", errors="ignore")
            total_pages = 1
            chunks = [ParsedChunk(chunk_index=0, content=full_text, page_number=1)]

        return ParsedDocument(
            document_id=document_id,
            filename=filename,
            file_type="pdf",
            total_pages=total_pages,
            full_text=full_text,
            chunks=chunks,
            checksum=checksum,
        )
