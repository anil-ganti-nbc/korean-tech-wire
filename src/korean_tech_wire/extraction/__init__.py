"""Article-body extraction boundary; deliberately not coupled to discovery."""
from .basic_html import extract_text
from .metadata import ExtractedMetadata, extract_metadata

__all__ = ["ExtractedMetadata", "extract_metadata", "extract_text"]
