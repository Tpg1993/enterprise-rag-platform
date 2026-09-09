"""Unit tests for document parsers and parser factory."""

from src.documents import get_parser_for_file
from src.documents.pdf_parser import PDFParser
from src.documents.structured_parser import StructuredParser
from src.documents.text_parser import TextParser


def test_parser_factory_matching():
    assert isinstance(get_parser_for_file("sample.pdf"), PDFParser)
    assert isinstance(get_parser_for_file("doc.txt"), TextParser)
    assert isinstance(get_parser_for_file("data.csv"), StructuredParser)


def test_text_parser():
    parser = TextParser()
    content = b"Paragraph 1 text.\n\nParagraph 2 text."
    doc = parser.parse(content, "test.md", "doc_1")
    assert doc.file_type == "markdown"
    assert len(doc.chunks) == 2
    assert doc.chunks[0].content == "Paragraph 1 text."


def test_structured_csv_parser():
    parser = StructuredParser()
    csv_bytes = b"name,role\nAlice,Engineer\nBob,Analyst"
    doc = parser.parse(csv_bytes, "team.csv", "doc_2")
    assert doc.file_type == "csv"
    assert len(doc.chunks) == 2
    assert "Alice" in doc.chunks[0].content
