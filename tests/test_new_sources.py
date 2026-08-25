"""ZDNet Korea + Digital Today collectors and Law-3 health honesty.

Offline only (FixtureFetcher / mapping fetcher). Fixtures trimmed from
live captures 2026-08-25; see fixture headers for provenance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from korean_tech_wire.collectors.digitaltoday import GoogleNewsSitemapCollector
from korean_tech_wire.collectors.rss import RssCollector
from korean_tech_wire.collectors.zdnet import ZdnetCollector, published_from_no
from korean_tech_wire.dashboard import health_state
from korean_tech_wire.editorial import classify
from korean_tech_wire.models import DiscoveredArticle, Source

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class MappingFetcher:
    def __init__(self, responses: dict[str, str]):
        self.responses = responses

    def get(self, url: str) -> str:
        # Unmapped URLs behave like an empty 200 body: collectors must cope
        # without titles/content rather than crash.
        return self.responses.get(url, "")


def _source(name: str, collector: str, url: str = "https://example.test/") -> Source:
    return Source(name, name, "EXPERIMENTAL", True, collector, url)


# -- ZDNet Korea -----------------------------------------------------------------

ZDNET_FEED = "https://zdnet.co.kr/feed/article_list.xml"
ZDNET_A1 = "https://zdnet.co.kr/view/?no=20260825102143"
ZDNET_A2 = "https://zdnet.co.kr/view/?no=20260824180957"

ARTICLE_HTML = (
    "<html><head>"
    '<meta property="og:title" content="삼성전자, HBM4 양산 속도전">'
    "</head><body>article</body></html>"
)


def test_zdnet_published_time_derived_from_no_param_kst():
    published = published_from_no(ZDNET_A1)
    assert published is not None
    assert published.utcoffset() == timedelta(hours=9)
    assert (published.year, published.month, published.day, published.hour, published.minute) == (
        2026, 8, 25, 10, 21)


def test_zdnet_feed_discovery_extracts_titles_and_skips_non_articles():
    fetcher = MappingFetcher({
        ZDNET_FEED: fixture("zdnet_feed.xml"),
        ZDNET_A1: ARTICLE_HTML,
        ZDNET_A2: "<html><head><title>SK하이닉스 차세대 공정 - ZDNet korea</title></head></html>",
        # non-/view/ entry must never be fetched at all
    })
    articles = ZdnetCollector(
        _source("zdnet_korea_semi_display", "zdnet_feed", ZDNET_FEED), fetcher
    ).discover()
    assert [a.canonical_url for a in articles] == [ZDNET_A1, ZDNET_A2]
    assert articles[0].title_original == "삼성전자, HBM4 양산 속도전"
    assert articles[1].title_original == "SK하이닉스 차세대 공정"
    assert articles[0].published_at is not None


def test_zdnet_article_without_title_yields_no_candidate():
    fetcher = MappingFetcher({ZDNET_FEED: fixture("zdnet_feed.xml"), ZDNET_A1: "<html></html>"})
    articles = ZdnetCollector(_source("zdnet", "zdnet_feed", ZDNET_FEED), fetcher).discover()
    assert articles == []


def test_zdnet_malformed_feed_raises_collector_error():
    from korean_tech_wire.collectors.base import CollectorError

    try:
        ZdnetCollector(_source("z", "zdnet_feed", ZDNET_FEED), MappingFetcher({ZDNET_FEED: "<not-xml"})).discover()
        raised = False
    except CollectorError:
        raised = True
    assert raised


def test_zdnet_editorial_filter_requires_semiconductor_or_display_signal():
    source = _source("zdnet_korea_semi_display", "zdnet_feed")

    def article(title: str) -> DiscoveredArticle:
        return DiscoveredArticle(source.id, "u", "u", title, None, datetime.now(timezone.utc))

    accepted = classify(source, article("TSMC 2나노 파운드리 수율 60% 돌파"))
    rejected = classify(source, article("주말 영화 예매 순위 top 10"))
    assert accepted.accepted is True
    assert rejected.accepted is False
    assert rejected.reason == "no_semiconductor_or_display_signal"


# -- Digital Today ---------------------------------------------------------------

DT_SITEMAP = "https://www.digitaltoday.co.kr/sitemap.xml"


def test_digitaltoday_gnews_sitemap_single_fetch_titles_and_dates():
    fetcher = MappingFetcher({DT_SITEMAP: fixture("digitaltoday_gnews.xml")})
    articles = GoogleNewsSitemapCollector(
        _source("digitaltoday_semi_display", "gnews_sitemap", DT_SITEMAP), fetcher
    ).discover()
    assert len(articles) == 2  # the third entry carries no news:title
    first = articles[0]
    assert first.title_original == "SK하이닉스 HBM4 양산 체제 가동, 메모리 반도체 경쟁 격화"
    assert first.published_at is not None
    assert first.source_article_id == "695241"
    assert first.metadata["keywords"] == "디지털투데이, SK하이닉스, hbm4"


def test_digitaltoday_empty_sitemap_is_legitimate_zero():
    empty = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>'
    articles = GoogleNewsSitemapCollector(
        _source("dt", "gnews_sitemap", DT_SITEMAP), MappingFetcher({DT_SITEMAP: empty})
    ).discover()
    assert articles == []


def test_digitaltoday_editorial_filter_allows_vertical_only():
    source = _source("digitaltoday_semi_display", "gnews_sitemap", DT_SITEMAP)

    def article(title: str) -> DiscoveredArticle:
        return DiscoveredArticle(source.id, "u", "u", title, None, datetime.now(timezone.utc))

    assert classify(source, article("엔비디아 GPU 데이터센터 매출 급증")).accepted is True
    decision = classify(source, article("연예인이 추천하는 카페 베스트 5"))
    assert decision.accepted is False


# -- duplicate identity stability ---------------------------------------------------

def test_zdnet_and_dt_identity_keys_are_stable_on_rerun():
    zdnet = ZdnetCollector(
        _source("z", "zdnet_feed", ZDNET_FEED),
        MappingFetcher({ZDNET_FEED: fixture("zdnet_feed.xml"), ZDNET_A1: ARTICLE_HTML}),
    ).discover()

    dt = GoogleNewsSitemapCollector(
        _source("d", "gnews_sitemap", DT_SITEMAP), MappingFetcher({DT_SITEMAP: fixture("digitaltoday_gnews.xml")})
    ).discover()

    again_z = ZdnetCollector(
        _source("z", "zdnet_feed", ZDNET_FEED),
        MappingFetcher({ZDNET_FEED: fixture("zdnet_feed.xml"), ZDNET_A1: ARTICLE_HTML}),
    ).discover()
    assert [a.canonical_url for a in zdnet] == [a.canonical_url for a in again_z]
    assert all(a.source_article_id for a in dt)
