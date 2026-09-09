"""Unit test suite for Phase 21 Multimodal RAG (Tables, Images, PDFs)."""

import pytest
import pymupdf
from unittest.mock import AsyncMock, MagicMock
from src.documents.multimodal_parser import MultimodalParser, table_to_markdown
from src.llm.base import LLMResponse
from src.rag.base import RAGRequest
from src.rag.multimodal.strategy import MultimodalRAGStrategy
from src.rag.router import get_rag_strategy


def test_table_to_markdown():
    """Verifies matrix to markdown table formatting."""
    matrix = [
        ["Quarter", "Revenue", "Profit"],
        ["Q1", "$10M", "$2M"],
        ["Q2", "$14M", "$3.5M"],
    ]
    md = table_to_markdown(matrix)
    assert "| Quarter | Revenue | Profit |" in md
    assert "| --- | --- | --- |" in md
    assert "| Q1 | $10M | $2M |" in md
    assert "| Q2 | $14M | $3.5M |" in md


def test_multimodal_parser_pdf_with_table():
    """Verifies that MultimodalParser detects vector tables in PDFs."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 40), "Enterprise Revenue Report")

    # Draw vector table borders
    rect = pymupdf.Rect(50, 60, 250, 160)
    page.draw_rect(rect)
    page.draw_line(pymupdf.Point(50, 110), pymupdf.Point(250, 110))
    page.draw_line(pymupdf.Point(150, 60), pymupdf.Point(150, 160))
    page.insert_text((60, 90), "Metric")
    page.insert_text((160, 90), "Value")
    page.insert_text((60, 140), "ARR")
    page.insert_text((160, 140), "$50M")

    pdf_bytes = doc.tobytes()
    doc.close()

    parser = MultimodalParser()
    parsed = parser.parse(pdf_bytes, "financials.pdf", "doc_fin_1")

    assert parsed.file_type == "pdf"
    assert len(parsed.chunks) >= 1
    has_table = any(c.metadata.get("chunk_type") == "table" for c in parsed.chunks)
    assert has_table is True
    table_chunk = next(c for c in parsed.chunks if c.metadata.get("chunk_type") == "table")
    assert "ARR" in table_chunk.content
    assert "$50M" in table_chunk.content


def test_multimodal_parser_image_file():
    """Verifies parsing standalone image file."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 1)
    img_bytes = pix.tobytes("png")

    parser = MultimodalParser()
    parsed = parser.parse(img_bytes, "architecture_diagram.png", "doc_img_1")

    assert parsed.file_type == "png"
    assert parsed.metadata["is_multimodal"] is True
    assert len(parsed.chunks) == 1
    assert parsed.chunks[0].metadata["chunk_type"] == "image_figure"
    assert "architecture_diagram.png" in parsed.chunks[0].content


@pytest.mark.asyncio
async def test_multimodal_strategy_table_boosting():
    """Verifies that table-focused queries boost table chunks over text chunks."""
    llm = MagicMock()
    llm.agenerate = AsyncMock(
        return_value=LLMResponse(
            content="According to the quarterly table, revenue was $14M.",
            model_name="sarvam-105b",
            prompt_tokens=100,
            completion_tokens=20,
            estimated_cost_usd=0.0003,
            latency_ms=150.0,
        )
    )

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1] * 128

    text_hit = {
        "chunk_id": "c1",
        "document_id": "d1",
        "content": "General overview of quarterly updates.",
        "score": 0.85,
        "payload": {"filename": "doc.pdf", "chunk_type": "text"},
    }
    table_hit = {
        "chunk_id": "c2",
        "document_id": "d1",
        "content": "[Structured Table: Table 1 on Page 2]\n| Metric | Q2 |\n| Revenue | $14M |",
        "score": 0.70,
        "payload": {"filename": "doc.pdf", "chunk_type": "table", "table_index": 1, "page": 2},
    }

    vector_store = MagicMock()
    vector_store.search.return_value = [text_hit, table_hit]

    strategy = MultimodalRAGStrategy(
        vector_store=vector_store,
        embedding_provider=embedder,
        llm_provider=llm,
    )

    req = RAGRequest(
        query="What is the revenue in the financial summary table?",
        rag_strategy="Multimodal",
        top_k=1,
    )

    res = await strategy.execute(req)
    assert res.rag_strategy == "Multimodal"
    assert len(res.citations) == 1
    # Table hit boosted by +0.25 (0.70 + 0.25 = 0.95), overtaking text hit (0.85)
    assert res.citations[0].chunk_id == "c2"
    assert "Table" in (res.citations[0].section_title or "")


@pytest.mark.asyncio
async def test_multimodal_strategy_visual_boosting():
    """Verifies that visual-focused queries boost visual image figure chunks."""
    llm = MagicMock()
    llm.agenerate = AsyncMock(
        return_value=LLMResponse(
            content="The system architecture figure illustrates the pipeline.",
            model_name="sarvam-105b",
            prompt_tokens=100,
            completion_tokens=20,
            estimated_cost_usd=0.0003,
            latency_ms=150.0,
        )
    )

    embedder = MagicMock()
    embedder.embed_query.return_value = [0.1] * 128

    text_hit = {
        "chunk_id": "c1",
        "document_id": "d1",
        "content": "Some descriptive paragraphs about system layout.",
        "score": 0.80,
        "payload": {"filename": "arch.pdf", "chunk_type": "text"},
    }
    figure_hit = {
        "chunk_id": "c2",
        "document_id": "d1",
        "content": "[Figure: Visual Image 1 on Page 3]\nProperties: 1920x1080 px RGB diagram.",
        "score": 0.70,
        "payload": {"filename": "arch.pdf", "chunk_type": "image_figure", "image_index": 1, "page": 3},
    }

    vector_store = MagicMock()
    vector_store.search.return_value = [text_hit, figure_hit]

    strategy = MultimodalRAGStrategy(
        vector_store=vector_store,
        embedding_provider=embedder,
        llm_provider=llm,
    )

    req = RAGRequest(
        query="Explain the architecture diagram figure",
        rag_strategy="Multimodal",
        top_k=1,
    )

    res = await strategy.execute(req)
    assert res.rag_strategy == "Multimodal"
    assert res.citations[0].chunk_id == "c2"
    assert "Figure" in (res.citations[0].section_title or "")


def test_multimodal_router_registration():
    """Verifies that router returns MultimodalRAGStrategy for Multimodal strategy name."""
    strategy = get_rag_strategy("Multimodal")
    assert isinstance(strategy, MultimodalRAGStrategy)
