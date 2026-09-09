"""Factory router for matching filenames to appropriate document parsers."""

from src.documents.base import DocumentParser
from src.documents.docx_parser import DocxParser
from src.documents.html_parser import HTMLParser
from src.documents.multimodal_parser import MultimodalParser
from src.documents.structured_parser import StructuredParser
from src.documents.text_parser import TextParser


def get_parser_for_file(filename: str) -> DocumentParser:
    """Returns matching DocumentParser instance based on file extension."""
    fn_lower = filename.lower()
    if fn_lower.endswith(".pdf"):
        return MultimodalParser()
    elif fn_lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")):
        return MultimodalParser()
    elif fn_lower.endswith(".docx"):
        return DocxParser()
    elif fn_lower.endswith((".html", ".htm")):
        return HTMLParser()
    elif fn_lower.endswith((".csv", ".json")):
        return StructuredParser()
    else:
        return TextParser()
