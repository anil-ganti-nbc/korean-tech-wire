"""Google News sitemap collector (used for Digital Today).

EXPERIMENTAL maturity. Digital Today's robots.txt declares
``sitemap: https://www.digitaltoday.co.kr/sitemap.xml`` and the sitemap is
a Google News sitemap carrying ``news:title``, ``news:publication_date``
and ``news:keywords`` per URL — title + timestamp + canonical URL in ONE
request, no per-article fetching, no anti-bot interference (verified live
2026-08-25). This is the lowest-maintenance surface of any candidate in
this campaign's KTW pass.

Note on scope honesty: Digital Today's robots.txt disallows
``/news/articleList.html`` for ``User-agent: *`` — this collector never
touches listing pages; it reads only the declared sitemap.
"""

from __future__ import annotations

from datetime import datetime
from xml.etree import ElementTree as ET

from .base import Collector, CollectorError
from ..models import DiscoveredArticle

_NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"
_SM_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class GoogleNewsSitemapCollector(Collector):
    MAX_ARTICLES_PER_RUN = 40

    def discover(self) -> list[DiscoveredArticle]:
        try:
            root = ET.fromstring(self.fetcher.get(self.source.url))
        except (ET.ParseError, OSError) as error:
            raise CollectorError(f"Invalid Google News sitemap response: {error}") from error

        found: list[DiscoveredArticle] = []
        seen: set[str] = set()
        for url_el in root.iter(f"{_SM_NS}url"):
            if len(found) >= self.MAX_ARTICLES_PER_RUN:
                break
            loc = (url_el.findtext(f"{_SM_NS}loc") or "").strip() or (
                url_el.findtext("loc") or "").strip()
            if not loc or loc in seen:
                continue
            seen.add(loc)
            news_el = url_el.find(f"{{{_NEWS_NS}}}news")
            title = ""
            published_raw = ""
            if news_el is not None:
                title = (news_el.findtext(f"{{{_NEWS_NS}}}title") or "").strip()
                published_raw = (news_el.findtext(f"{{{_NEWS_NS}}}publication_date") or "").strip()
            if not title:
                continue  # a sitemap entry without a title yields no candidate
            published = None
            if published_raw:
                try:
                    published = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                except ValueError:
                    published = None
            if published and published.tzinfo is None:
                published = published.replace(tzinfo=self.now().tzinfo)
            if published:
                published = published.astimezone(self.now().tzinfo)
            article_id = None
            marker = "idxno="
            idx = loc.find(marker)
            if idx >= 0:
                digits = "".join(ch for ch in loc[idx + len(marker):] if ch.isdigit())
                article_id = digits or None
            found.append(DiscoveredArticle(
                self.source.id,
                loc,
                loc,
                title,
                published,
                self.now(),
                article_id,
                metadata={"gnews_sitemap": self.source.url,
                          "keywords": ((news_el.findtext(f"{{{_NEWS_NS}}}keywords") or "").strip() or None)
                          if news_el is not None else None},
            ))
        return found
