from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser


@dataclass(frozen=True, slots=True)
class ExtractedMetadata:
    published_at: datetime | None = None


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.published: str | None = None; self.jsonld: list[str] = []; self._jsonld = False; self._parts: list[str] = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "meta" and values.get("property") == "article:published_time": self.published = values.get("content")
        if tag == "script" and values.get("type") == "application/ld+json": self._jsonld = True; self._parts = []
    def handle_data(self, data):
        if self._jsonld: self._parts.append(data)
    def handle_endtag(self, tag):
        if tag == "script" and self._jsonld: self.jsonld.append("".join(self._parts)); self._jsonld = False

def _date_from_jsonld(value: object) -> str | None:
    if isinstance(value, list):
        for item in value:
            found = _date_from_jsonld(item)
            if found: return found
    if isinstance(value, dict):
        kind = value.get("@type")
        if kind == "NewsArticle" or (isinstance(kind, list) and "NewsArticle" in kind):
            date = value.get("datePublished")
            return date if isinstance(date, str) else None
        graph = value.get("@graph")
        if graph: return _date_from_jsonld(graph)
    return None

def extract_metadata(html: str) -> ExtractedMetadata:
    parser = _MetadataParser(); parser.feed(html)
    raw = parser.published
    if not raw:
        for block in parser.jsonld:
            try: raw = _date_from_jsonld(json.loads(block))
            except json.JSONDecodeError: continue
            if raw: break
    if not raw: return ExtractedMetadata()
    try: return ExtractedMetadata(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError: return ExtractedMetadata()
