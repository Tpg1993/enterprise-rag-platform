"""Multi-Document Comparative Synthesis Engine Package."""

from src.rag.comparative.comparator import MultiDocumentComparator, get_document_comparator
from src.rag.comparative.models import ComparisonDimension, ComparisonMatrixResult

__all__ = [
    "MultiDocumentComparator",
    "ComparisonDimension",
    "ComparisonMatrixResult",
    "get_document_comparator",
]
