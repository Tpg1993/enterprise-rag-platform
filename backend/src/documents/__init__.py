"""Documents package initialization."""

from src.documents.base import DocumentParser, ParsedChunk, ParsedDocument
from src.documents.factory import get_parser_for_file

__all__ = ["DocumentParser", "ParsedDocument", "ParsedChunk", "get_parser_for_file"]
