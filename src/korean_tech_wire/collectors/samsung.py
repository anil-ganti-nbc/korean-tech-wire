from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from .base import Collector
from ..models import DiscoveredArticle


class SamsungArticleIndexParser(HTMLParser):
    """Extract only the homepage's explicit newsroom article-card list items."""
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.depth = 0
        self.card: dict[str, object] | None = None
        self.capture: str | None = None
        self.articles: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "li" and {"article_lists", "article_lists_color"} & classes:
            self.card = {"depth": self.depth, "url": "", "title": "", "category": "", "date": ""}
        if not self.card:
            return
        if tag == "a" and values.get("href") and not self.card["url"]:
            self.card["url"] = urljoin(self.base_url, values["href"])
        if tag == "p":
            if "article_title" in classes: self.capture = "title"
            elif "article_category" in classes: self.capture = "category"
            elif "article_data" in classes: self.capture = "date"

    def handle_data(self, data: str) -> None:
        if self.card and self.capture:
            self.card[self.capture] = str(self.card[self.capture]) + data

    def handle_endtag(self, tag: str) -> None:
        if self.card and tag == "p":
            self.capture = None
        if self.card and tag == "li" and self.depth == self.card["depth"]:
            article = {key: " ".join(str(value).split()) for key, value in self.card.items() if key != "depth"}
            if article["url"] and article["title"] and article["date"]:
                self.articles.append(article)
            self.card = None
            self.capture = None
        self.depth -= 1


class SamsungNewsroomCollector(Collector):
    def discover(self) -> list[DiscoveredArticle]:
        parser = SamsungArticleIndexParser(self.source.url)
        parser.feed(self.fetcher.get(self.source.url))
        articles: list[DiscoveredArticle] = []
        for item in parser.articles:
            path = urlparse(item["url"]).path.rstrip("/")
            slug = path.rsplit("/", 1)[-1]
            articles.append(DiscoveredArticle(
                self.source.id, item["url"], item["url"], item["title"], None, self.now(), slug,
                category=item["category"], metadata={"index_date": item["date"], "index_container": "article_lists"},
            ))
        return articles
