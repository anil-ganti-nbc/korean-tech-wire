from __future__ import annotations

import re
from urllib.parse import urlparse

from .base import Collector
from .html_index import LinkIndexParser
from ..models import DiscoveredArticle


class TheElecCollector(Collector):
    """Conservative index collector; individual articles are fetched only when new."""
    def discover(self) -> list[DiscoveredArticle]:
        parser = LinkIndexParser(self.source.url, "/news/articleView.html")
        parser.feed(self.fetcher.get(self.source.url))
        articles: list[DiscoveredArticle] = []
        seen: set[str] = set()
        for url, title in parser.links:
            if url in seen: continue
            seen.add(url)
            query = urlparse(url).query
            article_id = re.search(r"idxno=(\d+)", query)
            articles.append(DiscoveredArticle(self.source.id, url, url, title, None, self.now(), article_id.group(1) if article_id else None))
        return articles
