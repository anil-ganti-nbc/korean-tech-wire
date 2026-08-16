from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from korean_tech_wire.config import load_settings
from korean_tech_wire.dashboard import serve
from korean_tech_wire.discovery.runner import RunSummary
from korean_tech_wire.models import DiscoveredArticle
from korean_tech_wire.storage import Database


def _seed(monkeypatch, tmp_path: Path) -> Database:
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "KTW Field Test"))
    settings = load_settings(Path("config/config.example.yaml"))
    database = Database(settings.database_path)
    database.migrate()
    now = datetime.now(timezone.utc)
    database.persist_articles([
        DiscoveredArticle("sk_hynix_newsroom", "https://news.skhynix.co.kr/a", "https://news.skhynix.co.kr/a", "SK하이닉스, 차세대 메모리 공개", now, now, body_original="한국어 원문 증거와 긴 설명입니다.", category="memory"),
        DiscoveredArticle("samsung_newsroom_kr", "https://news.samsung.com/kr/a", "https://news.samsung.com/kr/a", "삼성전자, 새로운 기술 발표", now, now, body_original="삼성 뉴스룸 한국어 본문입니다.", category="mobile"),
        DiscoveredArticle("the_elec", "https://www.thelec.kr/a", "https://www.thelec.kr/a", "디스플레이 산업 장기 헤드라인 테스트", now, now, body_original="디일렉 원문입니다.", category="displays"),
        DiscoveredArticle("lg_display_newsroom", "https://www.lgdisplay.com/a", "https://www.lgdisplay.com/a", "LG디스플레이 OLED 투자", now, now, body_original="LG디스플레이 원문입니다.", category="displays"),
        DiscoveredArticle("etnews_hardware", "https://www.etnews.com/a", "https://www.etnews.com/a", "전자신문 반도체 장비 기사", now, now, body_original="전자신문 원문입니다.", category="semiconductors"),
    ])
    run_id = database.start_run("sk_hynix_newsroom")
    database.record_source_health(run_id, "sk_hynix_newsroom", duration_ms=10, success=True, references=1, accepted=1, rejected=0, new=1, existing=0, extraction_failures=0, timestamped=1)
    database.finish_run(run_id, "success", RunSummary(attempted=1, succeeded=1, discovered=1, accepted=1, new=1, timestamped=1))
    return database


def _server(monkeypatch, tmp_path):
    database = _seed(monkeypatch, tmp_path)
    server = serve(port=0)
    thread = Thread(target=server.serve_forever)
    thread.start()
    return database, server, thread


def test_newsroom_empty_state_and_isolated_path(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "field state"))
    server = serve(port=0)
    thread = Thread(target=server.serve_forever); thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
            page = response.read().decode("utf-8")
        assert "No leads yet" in page
        assert "Collected Korean technology leads" in page
        assert "field state" in load_settings(Path("config/config.example.yaml")).database_path.as_posix()
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_newsroom_korean_channels_filters_health_and_detail(monkeypatch, tmp_path):
    database, server, thread = _server(monkeypatch, tmp_path)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/?channel=PRODUCTION") as response:
            production = response.read().decode("utf-8")
        assert "SK하이닉스, 차세대 메모리 공개" in production
        assert "삼성전자, 새로운 기술 발표" not in production
        with urlopen(base + "/?source=samsung_newsroom_kr") as response:
            filtered = response.read().decode("utf-8")
        assert "삼성전자, 새로운 기술 발표" in filtered
        assert "Source Health" in filtered and "Run History" in filtered
        with database.connect() as con:
            article_id = con.execute("SELECT id FROM articles WHERE source_id='sk_hynix_newsroom'").fetchone()[0]
        with urlopen(base + f"/articles/{article_id}") as response:
            detail = response.read().decode("utf-8")
        assert "한국어 원문 증거와 긴 설명입니다." in detail
        assert "Original ↗" in detail
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_feedback_persists_without_mutating_article(monkeypatch, tmp_path):
    database, server, thread = _server(monkeypatch, tmp_path)
    try:
        with database.connect() as con:
            row = con.execute("SELECT id,title_original FROM articles WHERE source_id='sk_hynix_newsroom'").fetchone()
        payload = urlencode({"article_id": row["id"], "outcome": "USEFUL"}).encode()
        request = Request(f"http://127.0.0.1:{server.server_port}/feedback", data=payload, method="POST")
        with urlopen(request) as response:
            page = response.read().decode("utf-8")
        assert "USEFUL" in page
        with database.connect() as con:
            assert con.execute("SELECT title_original FROM articles WHERE id=?", (row["id"],)).fetchone()[0] == row["title_original"]
        assert database.feedback_history(row["id"])[0]["outcome"] == "USEFUL"
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_native_packaging_keeps_dashboard_visible_and_uses_windowed_bundle():
    assert "--windowed" in Path("native/macos/build.sh").read_text()
    assert "from korean_tech_wire.dashboard import serve" in Path("native/macos/launcher.py").read_text()
