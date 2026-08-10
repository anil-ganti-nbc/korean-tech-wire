from datetime import datetime, timezone
from korean_tech_wire.models import DiscoveredArticle
from korean_tech_wire.storage import Database

def test_article_identity_prevents_duplicate_rows(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    article = DiscoveredArticle("s", "https://a", "https://a", "원문 제목", datetime.now(timezone.utc), datetime.now(timezone.utc))
    assert database.persist_articles([article]) == (1, 0)
    assert database.persist_articles([article]) == (0, 1)
    assert database.status()["articles"] == 1
