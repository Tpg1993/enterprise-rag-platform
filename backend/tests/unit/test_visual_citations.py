"""Unit tests for Visual Bounding-Box Coordinates and Document Previews (Phase 34)."""

from src.context.builder import ContextBuilder
from src.documents.base import ParsedChunk
from src.documents.pdf_parser import PDFParser
from src.rag.base import Citation


def test_pdf_parser_extracts_bounding_boxes():
    """Verify PDFParser produces chunks with bounding-box geometry and page dimensions."""
    parser = PDFParser()
    # Create a minimal synthetic PDF via PyMuPDF in memory
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(
        fitz.Point(54, 72),
        "Enterprise Architecture Specification: Microservices and Vector Retrieval Systems.",
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    parsed = parser.parse(pdf_bytes, filename="arch_spec.pdf", document_id="doc_arch_01")
    assert parsed.total_pages == 1
    assert len(parsed.chunks) > 0

    chunk = parsed.chunks[0]
    assert chunk.bbox is not None
    assert len(chunk.bbox) == 4
    # Ensure coordinates are within page bounds
    assert chunk.bbox[0] >= 0
    assert chunk.bbox[1] >= 0
    assert chunk.bbox[2] <= 595
    assert chunk.bbox[3] <= 842

    assert chunk.page_dimensions is not None
    assert chunk.page_dimensions["width"] == 595.0
    assert chunk.page_dimensions["height"] == 842.0


def test_context_builder_preserves_visual_citation_metadata():
    """Verify ContextBuilder transfers chunk bbox and page dimensions into Citations."""
    builder = ContextBuilder()
    hits = [
        {
            "chunk_id": "chk_visual_01",
            "content": "Net Revenue exceeded $50M with 99.9% uptime SLA.",
            "score": 0.94,
            "payload": {
                "document_id": "doc_fin_01",
                "filename": "annual_report.pdf",
                "page_number": 2,
                "bbox": [54.0, 120.0, 540.0, 220.0],
                "page_dimensions": {"width": 612.0, "height": 792.0},
            },
        }
    ]

    res = builder.build_context(hits)
    assert len(res.citations) == 1
    cit = res.citations[0]
    assert isinstance(cit, Citation)
    assert cit.bbox == [54.0, 120.0, 540.0, 220.0]
    assert cit.page_dimensions == {"width": 612.0, "height": 792.0}
    assert cit.page_number == 2


def test_parsed_chunk_bbox_schema_defaults():
    """Verify ParsedChunk model allows optional bbox and page_dimensions."""
    chunk = ParsedChunk(chunk_index=0, content="General text without explicit visual coordinates.")
    assert chunk.bbox is None
    assert chunk.page_dimensions is None
