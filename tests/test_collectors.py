from datetime import timezone
from pathlib import Path

from korean_tech_wire.collectors.rss import RssCollector
from korean_tech_wire.collectors.lgdisplay import LGDisplayCollector
from korean_tech_wire.collectors.etnews import ETNewsCollector
from korean_tech_wire.collectors.samsung import SamsungNewsroomCollector
from korean_tech_wire.collectors.thelec import TheElecCollector
from korean_tech_wire.editorial import classify
from korean_tech_wire.extraction import extract_metadata
from korean_tech_wire.models import DiscoveredArticle
from korean_tech_wire.models import Source

class FixtureFetcher:
    def __init__(self, text): self.text = text
    def get(self, url): return self.text

def source(name, collector):
    return Source(name, name, "EXPERIMENTAL", True, collector, "https://example.test/")

def fixture(name): return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")

def test_korean_rss_preserves_korean_and_normalises_timestamp():
    article = RssCollector(source("sk", "rss"), FixtureFetcher(fixture("sk_hynix_korean_feed.xml"))).discover()[0]
    assert article.title_original == "[AI Infrastructure Insight] AI 데이터센터 안에서는 무엇이 달라지고 있는가?"
    assert article.published_at.utcoffset() == timezone.utc.utcoffset(article.published_at)
    assert article.source_article_id == "https://news.skhynix.co.kr/?p=12345"

def test_the_elec_deduplicates_index_links():
    articles = TheElecCollector(source("elec", "thelec_html"), FixtureFetcher(fixture("thelec_index.html"))).discover()
    assert len(articles) == 1 and articles[0].source_article_id == "12345"

def test_samsung_skips_navigation_links():
    articles = SamsungNewsroomCollector(source("samsung", "samsung_html"), FixtureFetcher(fixture("samsung_index.html"))).discover()
    assert len(articles) == 1
    assert articles[0].title_original == "삼성전자, 차세대 메모리 기술 공개"
    assert articles[0].category == "프레스센터"
    assert articles[0].metadata["index_date"] == "2026/08/10"

def test_samsung_detail_timestamp_converts_kst_to_utc():
    metadata = extract_metadata(fixture("samsung_article_valid.html"))
    assert metadata.published_at.isoformat() == "2026-08-10T10:00:00+09:00"
    assert metadata.published_at.astimezone(timezone.utc).isoformat() == "2026-08-10T01:00:00+00:00"

def test_missing_or_malformed_structured_timestamp_is_not_inferred():
    assert extract_metadata(fixture("samsung_article_missing_date.html")).published_at is None
    assert extract_metadata(fixture("samsung_article_malformed_date.html")).published_at is None
    assert extract_metadata(fixture("samsung_video_only.html")).published_at is None

def test_the_elec_detail_timestamp_is_extracted():
    assert extract_metadata(fixture("thelec_article.html")).published_at.isoformat() == "2026-08-09T16:50:27+09:00"

def test_the_elec_editorial_filter_rejects_outside_selected_section():
    relevant = DiscoveredArticle("the_elec", "https://example/a", "https://example/a", "HBM 생산 확대", None, RssCollector.now())
    irrelevant = DiscoveredArticle("the_elec", "https://example/b", "https://example/b", "배달 제휴", None, RssCollector.now())
    assert classify(source("the_elec", "thelec_html"), relevant).accepted
    assert not classify(source("the_elec", "thelec_html"), irrelevant).accepted

def test_lgdisplay_structured_archive_preserves_korean_canonical_and_kst_date():
    articles = LGDisplayCollector(source("lg_display_newsroom", "lgdisplay_html"), FixtureFetcher(fixture("lgdisplay_latest_news.html"))).discover()
    assert len(articles) == 2
    article = articles[0]
    assert article.title_original == "PR LG디스플레이, 27인치 720Hz OLED 패널 양산 투자 확대"
    assert article.canonical_url == "https://example.test/kor/company/media-center/latest-news?contentId=5563"
    assert article.source_article_id == "5563"
    assert article.published_at.astimezone(timezone.utc).isoformat() == "2026-08-09T15:00:00+00:00"

def test_lgdisplay_rejects_employer_pr_and_empty_archive_is_safe():
    articles = LGDisplayCollector(source("lg_display_newsroom", "lgdisplay_html"), FixtureFetcher(fixture("lgdisplay_latest_news.html"))).discover()
    assert not classify(source("lg_display_newsroom", "lgdisplay_html"), articles[1]).accepted
    assert LGDisplayCollector(source("lg_display_newsroom", "lgdisplay_html"), FixtureFetcher(fixture("lgdisplay_empty.html"))).discover() == []

def test_lgdisplay_canonical_identity_is_stable_on_repeat_discovery():
    collector = LGDisplayCollector(source("lg_display_newsroom", "lgdisplay_html"), FixtureFetcher(fixture("lgdisplay_latest_news.html")))
    assert [article.canonical_url for article in collector.discover()] == [article.canonical_url for article in collector.discover()]

def test_etnews_section_card_preserves_korean_url_section_and_kst_timestamp():
    source_config = Source("etnews_hardware", "ETNews", "EXPERIMENTAL", True, "etnews_html", "https://example.test/", options={"index_urls": [{"url": "https://example.test/section", "section": "semiconductors"}]})
    articles = ETNewsCollector(source_config, FixtureFetcher(fixture("etnews_section.html"))).discover()
    assert len(articles) == 2
    article = articles[0]
    assert article.title_original == "LX세미콘, 차량용 MCU 'LX61101' 현대차·기아에 공급"
    assert article.canonical_url == "https://example.test/20260810000234"
    assert article.source_article_id == "20260810000234" and article.category == "semiconductors"
    assert article.published_at.astimezone(timezone.utc).isoformat() == "2026-08-10T04:13:00+00:00"

def test_etnews_section_filter_empty_structure_and_repeat_identity_are_safe():
    source_config = Source("etnews_hardware", "ETNews", "EXPERIMENTAL", True, "etnews_html", "https://example.test/", options={"index_urls": [{"url": "https://example.test/section", "section": "semiconductors"}]})
    collector = ETNewsCollector(source_config, FixtureFetcher(fixture("etnews_section.html")))
    articles = collector.discover()
    assert not classify(source_config, DiscoveredArticle("etnews_hardware", "https://example/a", "https://example/a", "[알림] 기술 포럼", None, collector.now())).accepted
    assert [article.canonical_url for article in articles] == [article.canonical_url for article in collector.discover()]
    assert ETNewsCollector(source_config, FixtureFetcher(fixture("etnews_empty.html"))).discover() == []

def test_etnews_detail_open_graph_timestamp_is_authoritative_and_utc_convertible():
    metadata = extract_metadata(fixture("etnews_article.html"))
    assert metadata.published_at.astimezone(timezone.utc).isoformat() == "2026-08-10T04:13:26+00:00"
