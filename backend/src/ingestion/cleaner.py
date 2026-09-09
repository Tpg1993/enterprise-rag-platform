"""Document text cleaning and normalization routines."""

import re


class TextCleaner:
    """Normalizes document whitespace, strips boilerplate characters, and sanitizes text."""

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""

        # Normalize unicode whitespace
        cleaned = re.sub(r"[\r\t\f\v]", " ", text)
        # Collapse multiple spaces
        cleaned = re.sub(r"[ ]+", " ", cleaned)
        # Remove null bytes or non-printable ASCII/Unicode control chars
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
        # Collapse excessive newlines
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()
