from datetime import timezone
from pathlib import Path

from korean_tech_wire.collectors.rss import RssCollector
from korean_tech_wire.collectors.samsung import SamsungNewsroomCollector
from korean_tech_wire.collectors.thelec import TheElecCollector
from korean_tech_wire.models import Source

class FixtureFetcher:
    def __init__(self, text): self.text = text
    def get(self, url): return self.text

def source(name, collector):
    return Source(name, name, "EXPERIMENTAL", True, collector, "https://example.test/")

def fixture(name): return (Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8")

def test_rss_preserves_korean_and_normalises_timestamp():
    article = RssCollector(source("sk", "rss"), FixtureFetcher(fixture("sk_hynix_feed.xml"))).discover()[0]
    assert article.title_original == "SK하이닉스, HBM4 개발"
    assert article.published_at.utcoffset() == timezone.utc.utcoffset(article.published_at)
    assert article.source_article_id == "post-1"

def test_the_elec_deduplicates_index_links():
    articles = TheElecCollector(source("elec", "thelec_html"), FixtureFetcher(fixture("thelec_index.html"))).discover()
    assert len(articles) == 1 and articles[0].source_article_id == "12345"

def test_samsung_skips_navigation_links():
    articles = SamsungNewsroomCollector(source("samsung", "samsung_html"), FixtureFetcher(fixture("samsung_index.html"))).discover()
    assert [article.title_original for article in articles] == ["새 갤럭시 공개"]
