from __future__ import annotations

import re
from urllib.parse import urlparse

from .base import Collector
from .html_index import LinkIndexParser
from ..models import DiscoveredArticle


class TheElecCollector(Collector):
    """Conservative index collector; individual articles are fetched only when new."""
    def discover(self) -> list[DiscoveredArticle]:
        articles: list[DiscoveredArticle] = []
        seen: set[str] = set()
        indexes = self.source.options.get("index_urls") or [{"url": self.source.url, "section": "unclassified"}]
        for index in indexes:
            index_url, section = index["url"], index["section"]
            parser = LinkIndexParser(index_url, "/news/articleView.html")
            parser.feed(self.fetcher.get(index_url))
            for url, title in parser.links:
                if url in seen: continue
                seen.add(url)
                query = urlparse(url).query
                article_id = re.search(r"idxno=(\d+)", query)
                articles.append(DiscoveredArticle(self.source.id, url, url, title, None, self.now(), article_id.group(1) if article_id else None, metadata={"section": section, "index_url": index_url}))
        return articles
