from datetime import datetime, timezone
from korean_tech_wire.models import DiscoveredArticle
from korean_tech_wire.storage import Database

def test_article_identity_prevents_duplicate_rows(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    article = DiscoveredArticle("s", "https://a", "https://a", "원문 제목", datetime.now(timezone.utc), datetime.now(timezone.utc))
    assert database.persist_articles([article]) == (1, 0)
    assert database.persist_articles([article]) == (0, 1)
    assert database.status()["articles"] == 1

def test_legacy_samsung_cleanup_only_deletes_url_proven_noise(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    now = datetime.now(timezone.utc)
    noise = DiscoveredArticle("samsung_newsroom_kr", "https://news.samsung.com/medialibrary/kr/album/1", "https://news.samsung.com/medialibrary/kr/album/1", "앨범", now, now)
    ambiguous = DiscoveredArticle("samsung_newsroom_kr", "https://news.samsung.com/kr/topic-hub", "https://news.samsung.com/kr/topic-hub", "주제", now, now)
    database.persist_articles([noise, ambiguous])
    assert database.quarantine_legacy_samsung_records() == (2, 1)
    with database.connect() as con:
        row = con.execute("SELECT record_status FROM articles WHERE canonical_url=?", (ambiguous.canonical_url,)).fetchone()
    assert row["record_status"] == "legacy_unverified"

def test_unverified_row_requires_reenrichment_when_it_becomes_an_article(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    now = datetime.now(timezone.utc)
    article = DiscoveredArticle("samsung_newsroom_kr", "https://news.samsung.com/kr/topic-hub", "https://news.samsung.com/kr/topic-hub", "주제", None, now)
    database.persist_articles([article]); database.quarantine_legacy_samsung_records()
    assert database.needs_enrichment(article.source_id, article.canonical_url)

def test_the_elec_historical_records_are_quarantined_not_deleted(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    now = datetime.now(timezone.utc)
    article = DiscoveredArticle("the_elec", "https://example/article", "https://example/article", "일반 기사", now, now)
    database.persist_articles([article])
    assert database.quarantine_legacy_theelec_records() == 1
    assert database.status()["articles"] == 1
