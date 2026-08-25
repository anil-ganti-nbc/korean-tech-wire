"""ZDNet Korea collector — official article feed + per-article og:title.

EXPERIMENTAL maturity (see docs/source-research.md addendum and
config/sources.yaml status field).

Extraction contract (verified live 2026-08-25):
- ``https://zdnet.co.kr/feed/article_list.xml`` (+ ``_2``) is declared in
  ZDNet Korea's own robots.txt as a sitemap-style feed of recent articles:
  ``<loc>`` article URL and ``<lastmod>`` modification time per entry.
- Article URLs carry ``no=YYYYMMDDHHMMSS`` — ZDNet Korea's own publish
  timestamp in KST (UTC+9). This is used as the authoritative publication
  time; ``lastmod`` is retained in metadata only (it reflects edits too).
- Each article page server-renders ``og:title`` / ``og:description``;
  titles come from there and are never fabricated. An article whose page
  cannot be fetched yields no candidate rather than an invented title.

The semiconductor/display vertical filter lives downstream in
editorial/filtering.py (ZDNET_SIGNAL_TERMS), consistent with how The Elec
is filtered — collectors stay dumb.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree as ET

from .base import Collector, CollectorError
from ..models import DiscoveredArticle

_KST = timezone(timedelta(hours=9))
_NO_RE = re.compile(r"^(\d{14})$")
_SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_OG_TITLE_RE = re.compile(
    r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_TITLE_TAG_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL | re.IGNORECASE)


def published_from_no(url: str) -> datetime | None:
    """Derive the KST publish instant from a /view/?no=YYYYMMDDHHMMSS URL."""
    query = parse_qs(urlparse(url).query)
    values = query.get("no") or []
    if not values:
        return None
    match = _NO_RE.match(values[0])
    if not match:
        return None
    raw = match.group(1)
    try:
        return datetime(
            int(raw[0:4]), int(raw[4:6]), int(raw[6:8]),
            int(raw[8:10]), int(raw[10:12]), int(raw[12:14]),
            tzinfo=_KST,
        )
    except ValueError:
        return None


class ZdnetCollector(Collector):
    """Feed-driven discovery; article pages fetched for titles."""

    MAX_ARTICLES_PER_RUN = 20

    def _extract_title(self, html: str) -> str | None:
        match = _OG_TITLE_RE.search(html)
        if match and match.group(1).strip():
            return match.group(1).strip()
        fallback = _TITLE_TAG_RE.search(html)
        if fallback and " - " in fallback.group(1):
            # <title>TITLE - ZDNet korea</title> — strip only the site suffix.
            title = fallback.group(1).strip()
            suffix = " - zdnet korea"
            lowered = title.lower()
            if lowered.endswith(suffix):
                return title[: len(title) - len(suffix)].strip()
        return None

    def discover(self) -> list[DiscoveredArticle]:
        try:
            root = ET.fromstring(self.fetcher.get(self.source.url))
        except (ET.ParseError, OSError) as error:
            raise CollectorError(f"Invalid sitemap-feed response: {error}") from error

        entries: list[tuple[str, str]] = []  # (loc, lastmod)
        for url_el in root.iter(f"{_SITEMAP_NS}url"):
            loc = (url_el.findtext(f"{_SITEMAP_NS}loc") or "").strip()
            if not loc:
                loc = (url_el.findtext("loc") or "").strip()
            lastmod = (url_el.findtext(f"{_SITEMAP_NS}lastmod") or "").strip()
            if loc and "/view/" in loc:
                entries.append((loc, lastmod))
        if not entries:
            return []

        extra_feeds = self.source.options.get("extra_feed_urls") or []

        articles: list[DiscoveredArticle] = []
        seen: set[str] = set()

        def _feed_entries(feed_url: str) -> None:
            try:
                feed_root = ET.fromstring(self.fetcher.get(feed_url))
            except (ET.ParseError, OSError):
                return
            for url_el in feed_root.iter(f"{_SITEMAP_NS}url"):
                loc = (url_el.findtext(f"{_SITEMAP_NS}loc") or "").strip() or (
                    url_el.findtext("loc") or "").strip()
                lastmod = (url_el.findtext(f"{_SITEMAP_NS}lastmod") or "").strip()
                if loc and "/view/" in loc and loc not in seen:
                    entries.append((loc, lastmod))

        for feed_url in extra_feeds:
            _feed_entries(feed_url)

        # Newest first by the source's own publish timestamp where derivable,
        # falling back to feed order (stable) for undated entries.
        dated = [(url, lm, published_from_no(url)) for url, lm in entries]
        dated.sort(key=lambda item: item[2] or datetime.min.replace(tzinfo=_KST), reverse=True)

        fetched = 0
        for url, lastmod, published in dated:
            if fetched >= self.MAX_ARTICLES_PER_RUN:
                break
            if url in seen:
                continue
            seen.add(url)
            try:
                html = self.fetcher.get(url)
            except OSError:
                # A single article page failing must not kill the cycle; the
                # runner records the fetch attempt outcome separately.
                continue
            fetched += 1
            title = self._extract_title(html)
            if not title:
                continue
            articles.append(DiscoveredArticle(
                self.source.id,
                url,
                url,
                title,
                published.astimezone(self.now().tzinfo) if published else None,
                self.now(),
                source_article_id=(parse_qs(urlparse(url).query).get("no") or [None])[0],
                metadata={"feed_lastmod": lastmod, "feed_url": self.source.url},
            ))
        return articles
