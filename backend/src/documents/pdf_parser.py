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
                rect = page.rect
                page_dims = {"width": round(rect.width, 2), "height": round(rect.height, 2)}
                blocks = page.get_text("blocks")
                has_blocks = False

                for b in blocks:
                    if len(b) >= 5 and b[4].strip():
                        has_blocks = True
                        block_text = b[4].strip()
                        bbox = [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)]
                        chunks.append(
                            ParsedChunk(
                                chunk_index=chunk_idx,
                                content=block_text,
                                page_number=page_num + 1,
                                bbox=bbox,
                                page_dimensions=page_dims,
                                metadata={
                                    "filename": filename,
                                    "page": page_num + 1,
                                    "page_number": page_num + 1,
                                    "bbox": bbox,
                                    "page_dimensions": page_dims,
                                },
                            )
                        )
                        full_text_list.append(block_text)
                        chunk_idx += 1

                if not has_blocks:
                    page_text = page.get_text("text").strip()
                    if page_text:
                        full_text_list.append(page_text)
                        bbox = [
                            round(rect.x0 + 36, 2),
                            round(rect.y0 + 36, 2),
                            round(rect.x1 - 36, 2),
                            round(rect.y1 - 36, 2),
                        ]
                        chunks.append(
                            ParsedChunk(
                                chunk_index=chunk_idx,
                                content=page_text,
                                page_number=page_num + 1,
                                bbox=bbox,
                                page_dimensions=page_dims,
                                metadata={
                                    "filename": filename,
                                    "page": page_num + 1,
                                    "page_number": page_num + 1,
                                    "bbox": bbox,
                                    "page_dimensions": page_dims,
                                },
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
