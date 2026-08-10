from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True, slots=True)
class TranslationResult:
    title_english: str | None
    summary_english: str | None
    status: str
    notes: str | None = None

class Translator(Protocol):
    def translate(self, title_original: str, body_original: str | None) -> TranslationResult: ...
