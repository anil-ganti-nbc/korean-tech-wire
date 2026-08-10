from __future__ import annotations

import re
from urllib.parse import urlparse

from .base import Collector
from .html_index import LinkIndexParser
from ..models import DiscoveredArticle


class SamsungNewsroomCollector(Collector):
    def discover(self) -> list[DiscoveredArticle]:
        parser = LinkIndexParser(self.source.url, "/kr/")
        parser.feed(self.fetcher.get(self.source.url))
        articles: list[DiscoveredArticle] = []
        seen: set[str] = set()
        for url, title in parser.links:
            path = urlparse(url).path.rstrip("/")
            if url in seen or path in {"/kr", ""} or "/page/" in path: continue
            seen.add(url)
            slug = path.rsplit("/", 1)[-1]
            if not re.fullmatch(r"[a-z0-9-]+", slug): continue
            articles.append(DiscoveredArticle(self.source.id, url, url, title, None, self.now(), slug))
        return articles
