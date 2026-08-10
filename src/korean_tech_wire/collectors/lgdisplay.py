from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

from .base import Collector
from ..models import DiscoveredArticle


class LGDisplayLatestNewsParser(HTMLParser):
    """Parse only cards from LG Display's Korean Latest News archive."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.depth = 0
        self.in_archive = False
        self.card: dict[str, object] | None = None
        self.capture: str | None = None
        self.articles: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "ul" and {"board_col_list", "type2"}.issubset(classes):
            self.in_archive = True
        elif self.in_archive and tag == "li":
            self._finish_card()
            self.card = {"depth": self.depth, "url": "", "title": "", "date": ""}
        if not self.card:
            return
        if tag == "a" and "link" in classes and values.get("href"):
            self.card["url"] = urljoin(self.base_url, values["href"])
        elif tag == "dfn" and "tit" in classes:
            self.capture = "title"
        elif tag == "span" and "date" in classes:
            self.capture = "date"

    def handle_data(self, data: str) -> None:
        if self.card and self.capture:
            self.card[self.capture] = str(self.card[self.capture]) + data

    def handle_endtag(self, tag: str) -> None:
        if self.card and tag in {"dfn", "span"}:
            self.capture = None
        # Publisher markup contains non-self-closed <img> tags.  HTMLParser then
        # cannot reliably balance the card depth, so a new archive <li> terminates
        # the prior card instead.
        if self.in_archive and tag == "ul":
            self._finish_card()
            self.in_archive = False
        self.depth -= 1

    def _finish_card(self) -> None:
        if not self.card:
            return
        article = {key: " ".join(str(value).split()) for key, value in self.card.items() if key != "depth"}
        if article["url"] and article["title"] and article["date"]:
            self.articles.append(article)
        self.card, self.capture = None, None


class LGDisplayCollector(Collector):
    """LG Display Korean media-centre archive; dates are publisher-supplied KST dates."""

    def discover(self) -> list[DiscoveredArticle]:
        parser = LGDisplayLatestNewsParser(self.source.url)
        parser.feed(self.fetcher.get(self.source.url))
        zone = ZoneInfo(self.source.timezone)
        discovered: list[DiscoveredArticle] = []
        for item in parser.articles:
            try:
                # The publisher exposes a date but no clock time; preserve its day at KST midnight.
                published_at = datetime.strptime(item["date"], "%Y-%m-%d").replace(tzinfo=zone)
            except ValueError:
                continue
            parsed = urlparse(item["url"])
            content_id = parse_qs(parsed.query).get("contentId", [None])[0]
            if not content_id:
                continue
            discovered.append(DiscoveredArticle(
                self.source.id, item["url"], item["url"], item["title"], published_at,
                self.now(), content_id, metadata={"index_date": item["date"], "index_container": "board_col_list type2"},
            ))
        return discovered
