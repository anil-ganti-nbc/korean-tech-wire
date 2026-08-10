from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class DiscoveredArticle:
    source_id: str
    source_url: str
    canonical_url: str
    title_original: str
    published_at: datetime | None
    discovered_at: datetime
    source_article_id: str | None = None
    author: str | None = None
    category: str | None = None
    body_original: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

