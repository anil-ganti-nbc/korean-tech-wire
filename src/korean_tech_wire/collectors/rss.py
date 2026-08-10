from __future__ import annotations

from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from .base import Collector, CollectorError
from ..models import DiscoveredArticle


class RssCollector(Collector):
    def discover(self) -> list[DiscoveredArticle]:
        try:
            root = ET.fromstring(self.fetcher.get(self.source.url))
        except (ET.ParseError, OSError) as error:
            raise CollectorError(f"Invalid RSS response: {error}") from error
        namespace = {"content": "http://purl.org/rss/1.0/modules/content/"}
        found: list[DiscoveredArticle] = []
        for item in root.findall(".//item"):
            title, link = (item.findtext("title") or "").strip(), (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            raw_date = (item.findtext("pubDate") or "").strip()
            try:
                published = parsedate_to_datetime(raw_date) if raw_date else None
            except (TypeError, ValueError):
                published = None
            if published and published.tzinfo is None:
                published = published.replace(tzinfo=self.now().tzinfo)
            if published:
                published = published.astimezone(self.now().tzinfo)
            guid = (item.findtext("guid") or "").strip() or None
            body = item.findtext("content:encoded", namespaces=namespace)
            found.append(DiscoveredArticle(self.source.id, link, link, title, published, self.now(), guid, body_original=body, metadata={"feed_date": raw_date}))
        return found
