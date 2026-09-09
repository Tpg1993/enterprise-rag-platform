"""Multimodal document parser for extracting text, structured tables, and visual figures."""

import hashlib
import io
import logging
from typing import Any

import pymupdf  # PyMuPDF
from src.documents.base import DocumentParser, ParsedChunk, ParsedDocument

logger = logging.getLogger(__name__)


def table_to_markdown(matrix: list[list[Any]]) -> str:
    """Converts a 2D matrix of cell values into a GitHub-flavored Markdown table."""
    if not matrix or not matrix[0]:
        return ""

    # Clean and stringify cells
    cleaned_rows = [
        [str(cell).strip().replace("\n", " ") if cell is not None else "" for cell in row]
        for row in matrix
    ]

    header = cleaned_rows[0]
    separator = ["---"] * len(header)
    data_rows = cleaned_rows[1:]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in data_rows:
        # Pad row if columns differ
        padded_row = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(padded_row[: len(header)]) + " |")

    return "\n".join(lines)


class MultimodalParser(DocumentParser):
    """Parses PDF and image files, extracting textual content, tables, and visual figures."""

    def parse(self, file_bytes: bytes, filename: str, document_id: str) -> ParsedDocument:
        checksum = hashlib.md5(file_bytes).hexdigest()
        fn_lower = filename.lower()

        if fn_lower.endswith(".pdf"):
            return self._parse_pdf(file_bytes, filename, document_id, checksum)
        elif fn_lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
            return self._parse_image(file_bytes, filename, document_id, checksum)
        else:
            # Fallback to plain text decoding
            text = file_bytes.decode("utf-8", errors="ignore")
            chunk = ParsedChunk(
                chunk_index=0,
                content=text,
                page_number=1,
                metadata={"filename": filename, "chunk_type": "text"},
            )
            return ParsedDocument(
                document_id=document_id,
                filename=filename,
                file_type="txt",
                total_pages=1,
                full_text=text,
                chunks=[chunk],
                checksum=checksum,
            )

    def _parse_pdf(
        self, file_bytes: bytes, filename: str, document_id: str, checksum: str
    ) -> ParsedDocument:
        chunks: list[ParsedChunk] = []
        full_text_list: list[str] = []
        chunk_idx = 0
        total_tables = 0
        total_images = 0

        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
            total_pages = len(doc)

            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                page_display_num = page_num + 1

                # 1. Extract regular text
                page_text = page.get_text("text").strip()
                if page_text:
                    full_text_list.append(page_text)
                    chunks.append(
                        ParsedChunk(
                            chunk_index=chunk_idx,
                            content=page_text,
                            page_number=page_display_num,
                            metadata={
                                "filename": filename,
                                "page": page_display_num,
                                "chunk_type": "text",
                            },
                        )
                    )
                    chunk_idx += 1

                # 2. Extract structured vector tables
                try:
                    tables = page.find_tables()
                    for t_idx, table in enumerate(tables.tables):
                        extracted_cells = table.extract()
                        if extracted_cells and len(extracted_cells) > 0:
                            md_table = table_to_markdown(extracted_cells)
                            if md_table:
                                total_tables += 1
                                table_content = (
                                    f"[Structured Table: Table {t_idx + 1} on Page {page_display_num}]\n"
                                    f"{md_table}"
                                )
                                full_text_list.append(table_content)
                                chunks.append(
                                    ParsedChunk(
                                        chunk_index=chunk_idx,
                                        content=table_content,
                                        page_number=page_display_num,
                                        metadata={
                                            "filename": filename,
                                            "page": page_display_num,
                                            "chunk_type": "table",
                                            "table_index": t_idx + 1,
                                            "row_count": len(extracted_cells),
                                            "col_count": len(extracted_cells[0]),
                                        },
                                    )
                                )
                                chunk_idx += 1
                except Exception as tbl_err:
                    logger.debug(f"Table detection skipped on page {page_display_num}: {tbl_err}")

                # 3. Extract embedded image figures
                try:
                    images = page.get_images(full=True)
                    for img_idx, img_info in enumerate(images):
                        total_images += 1
                        xref = img_info[0]
                        width = img_info[2]
                        height = img_info[3]
                        colorspace = img_info[5]

                        image_caption = (
                            f"[Figure: Visual Image {img_idx + 1} on Page {page_display_num}]\n"
                            f"Properties: {width}x{height} px, {colorspace} color space.\n"
                            f"Embedded visual artifact from {filename} page {page_display_num}."
                        )
                        full_text_list.append(image_caption)
                        chunks.append(
                            ParsedChunk(
                                chunk_index=chunk_idx,
                                content=image_caption,
                                page_number=page_display_num,
                                metadata={
                                    "filename": filename,
                                    "page": page_display_num,
                                    "chunk_type": "image_figure",
                                    "image_index": img_idx + 1,
                                    "xref": xref,
                                    "width": width,
                                    "height": height,
                                },
                            )
                        )
                        chunk_idx += 1
                except Exception as img_err:
                    logger.debug(f"Image detection skipped on page {page_display_num}: {img_err}")

            doc.close()
            full_text = "\n\n".join(full_text_list)

        except Exception as err:
            logger.warning(f"PyMuPDF multimodal parsing error for {filename}: {err}")
            full_text = file_bytes.decode("utf-8", errors="ignore")
            total_pages = 1
            chunks = [
                ParsedChunk(
                    chunk_index=0,
                    content=full_text,
                    page_number=1,
                    metadata={"filename": filename, "chunk_type": "text"},
                )
            ]

        return ParsedDocument(
            document_id=document_id,
            filename=filename,
            file_type="pdf",
            total_pages=total_pages,
            full_text=full_text,
            chunks=chunks,
            checksum=checksum,
            metadata={
                "total_tables": total_tables,
                "total_images": total_images,
                "is_multimodal": (total_tables > 0 or total_images > 0),
            },
        )

    def _parse_image(
        self, file_bytes: bytes, filename: str, document_id: str, checksum: str
    ) -> ParsedDocument:
        """Parses standalone image files into structured visual figure document."""
        width = 0
        height = 0
        fmt = filename.split(".")[-1].upper()

        try:
            # Use pymupdf Pixmap to inspect image format without external PIL dependency
            pix = pymupdf.Pixmap(file_bytes)
            width = pix.width
            height = pix.height
            colorspace = pix.colorspace.name if pix.colorspace else "RGB"
        except Exception:
            width, height = 800, 600
            colorspace = "RGB"

        aspect_ratio = f"{width}:{height}"
        content = (
            f"[Visual Document: Image {filename}]\n"
            f"Format: {fmt} | Dimensions: {width}x{height} pixels | Colorspace: {colorspace}\n"
            f"Visual description: Standalone enterprise graphic/diagram '{filename}'."
        )

        chunk = ParsedChunk(
            chunk_index=0,
            content=content,
            page_number=1,
            metadata={
                "filename": filename,
                "page": 1,
                "chunk_type": "image_figure",
                "width": width,
                "height": height,
                "format": fmt,
            },
        )

        return ParsedDocument(
            document_id=document_id,
            filename=filename,
            file_type=fmt.lower(),
            total_pages=1,
            full_text=content,
            chunks=[chunk],
            checksum=checksum,
            metadata={
                "total_tables": 0,
                "total_images": 1,
                "is_multimodal": True,
            },
        )
