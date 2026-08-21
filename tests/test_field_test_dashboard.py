from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
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
    server = serve(port=0, mutation_authorizer=lambda _headers: True)
    thread = Thread(target=server.serve_forever)
    thread.start()
    return database, server, thread


def test_phase0_host_validation_rejects_wildcard_lan_and_invalid(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "security"))
    for host in ("0.0.0.0", "::", "192.168.1.20", "bad host", ""):
        try:
            serve(host=host, port=0)
        except ValueError:
            continue
        raise AssertionError(f"unsafe host accepted: {host}")


def test_phase0_unauthenticated_mutation_is_denied(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "read-only"))
    server = serve(port=0)
    thread = Thread(target=server.serve_forever); thread.start()
    try:
        request = Request(
            f"http://127.0.0.1:{server.server_port}/collect", data=b"source=", method="POST"
        )
        try:
            urlopen(request)
            raise AssertionError("unauthenticated mutation was accepted")
        except HTTPError as error:
            assert error.code == 403
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_newsroom_empty_state_and_isolated_path(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "field state"))
    server = serve(port=0, mutation_authorizer=lambda _headers: True)
    thread = Thread(target=server.serve_forever); thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
            page = response.read().decode("utf-8")
        assert "No local leads yet" in page
        assert "Phase 0 dashboard is read-only" in page
        assert "COLLECT NOW" not in page
        assert "Local database only" in page and "No external delivery" in page
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
        assert '/?source=samsung_newsroom_kr#health' in filtered
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
    launcher = Path("native/macos/launcher.py").read_text()
    assert '"DISCORD", "WEBHOOK", "DELIVERY", "OUTBOX"' in launcher


def test_collect_now_uses_core_reports_status_refuses_overlap_and_populates(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "interactive"))

    def fake_run(sources, settings, database, source_id=None, production_only=False, progress=None):
        selected = [source for source in sources if source.enabled and (not source_id or source.id == source_id)]
        now = datetime.now(timezone.utc)
        for source in selected:
            if progress: progress("started", source, {})
            time.sleep(0.04)
            database.persist_articles([DiscoveredArticle(source.id, f"https://fixture.invalid/{source.id}", f"https://fixture.invalid/{source.id}", f"Local lead {source.name}", now, now, body_original="Local fixture evidence", category="test")])
            if progress: progress("succeeded", source, {"discovered": 1, "accepted": 1, "new": 1, "existing": 0})
        return RunSummary(attempted=len(selected), succeeded=len(selected), discovered=len(selected), accepted=len(selected), new=len(selected))

    monkeypatch.setattr("korean_tech_wire.dashboard.run_collectors", fake_run)
    server = serve(port=0, mutation_authorizer=lambda _headers: True); thread = Thread(target=server.serve_forever); thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        first = Request(base + "/collect", data=b"source=", method="POST")
        with urlopen(first) as response:
            assert response.status == 202
        try:
            urlopen(Request(base + "/collect", data=b"source=", method="POST"))
            raise AssertionError("overlapping collection was accepted")
        except HTTPError as error:
            assert error.code == 409
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with urlopen(base + "/collection-status") as response:
                state = json.load(response)
            if not state["running"]:
                break
            time.sleep(0.03)
        assert state["status"] == "COMPLETED"
        assert state["summary"]["new"] == 5
        assert set(state["sources"]) == {"the_elec", "sk_hynix_newsroom", "samsung_newsroom_kr", "lg_display_newsroom", "etnews_hardware"}
        with urlopen(base + "/") as response:
            page = response.read().decode("utf-8")
        assert "Local lead SK hynix Newsroom Korea" in page
        assert "No local leads yet" not in page
    finally:
        server.shutdown(); thread.join(); server.server_close()
