from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from .base import Collector
from ..models import DiscoveredArticle


class ETNewsSectionParser(HTMLParser):
    """Extract only publisher section-list cards, never sidebar/recommendation links."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.in_list = False
        self.card: dict[str, str] | None = None
        self.capture: str | None = None
        self.articles: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs); classes = set((values.get("class") or "").split())
        if tag == "ul" and "news_list" in classes:
            self.in_list = True
        elif self.in_list and tag == "li":
            self._finish_card(); self.card = {"url": "", "title": "", "date": ""}
        if not self.card:
            return
        if tag == "strong":
            self.capture = "title"
        elif tag == "a" and self.capture == "title" and values.get("href"):
            self.card["url"] = urljoin(self.base_url, values["href"])
        elif tag == "span" and "date" in classes:
            self.capture = "date"

    def handle_data(self, data: str) -> None:
        if self.card and self.capture:
            self.card[self.capture] += data

    def handle_endtag(self, tag: str) -> None:
        if tag in {"strong", "span"}:
            self.capture = None
        if self.in_list and tag == "ul":
            self._finish_card(); self.in_list = False

    def _finish_card(self) -> None:
        if not self.card:
            return
        article = {key: " ".join(value.split()) for key, value in self.card.items()}
        if article["url"] and article["title"] and article["date"]:
            self.articles.append(article)
        self.card, self.capture = None, None


class ETNewsCollector(Collector):
    """Publisher-taxonomy ETNews collector for selected hardware sections only."""

    def discover(self) -> list[DiscoveredArticle]:
        articles: list[DiscoveredArticle] = []; seen: set[str] = set(); zone = ZoneInfo(self.source.timezone)
        indexes = self.source.options.get("index_urls") or [{"url": self.source.url, "section": "unclassified"}]
        for index in indexes:
            index_url, section = index["url"], index["section"]
            parser = ETNewsSectionParser(index_url); parser.feed(self.fetcher.get(index_url))
            for item in parser.articles:
                parsed = urlparse(item["url"]); article_id = parsed.path.strip("/")
                if not article_id.isdigit() or item["url"] in seen:
                    continue
                try:
                    published_at = datetime.strptime(item["date"], "%Y-%m-%d %H:%M").replace(tzinfo=zone)
                except ValueError:
                    continue
                seen.add(item["url"])
                articles.append(DiscoveredArticle(
                    self.source.id, item["url"], item["url"], item["title"], published_at,
                    self.now(), article_id, category=section,
                    metadata={"section": section, "index_url": index_url, "index_date": item["date"], "index_container": "news_list"},
                ))
        return articles
