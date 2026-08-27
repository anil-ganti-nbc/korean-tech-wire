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


def test_qc_decision_archives_removes_from_queue_and_blocks_double_qc(monkeypatch, tmp_path):
    database, server, thread = _server(monkeypatch, tmp_path)
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with database.connect() as con:
            row = con.execute("SELECT id, title_original FROM articles WHERE source_id='sk_hynix_newsroom'").fetchone()
        with urlopen(base + "/") as response:
            before = response.read().decode("utf-8")
        assert row["title_original"] in before

        payload = urlencode({"article_id": row["id"], "decision": "USEFUL"}).encode()
        request = Request(base + "/qc", data=payload, method="POST")
        with urlopen(request) as response:
            assert response.status == 200

        # Removed from the active queue immediately -- it may still surface
        # once, read-only, in the "Recently QCed" ledger section, but no
        # longer as a clickable active headline.
        with urlopen(base + "/") as response:
            after = response.read().decode("utf-8")
        assert f'<a class=headline href="/articles/{row["id"]}">' not in after
        assert "Recently QCed" in after
        assert after.count(row["title_original"]) == 1

        # The article row itself is untouched (no destructive mutation of the
        # live DB); the decision lives only in the separate QC archive.
        with database.connect() as con:
            assert con.execute("SELECT title_original FROM articles WHERE id=?", (row["id"],)).fetchone()[0] == row["title_original"]

        # A second QC decision on the same article is refused, not duplicated.
        again = Request(base + "/qc", data=urlencode({"article_id": row["id"], "decision": "NOT_USEFUL"}).encode(), method="POST")
        try:
            urlopen(again)
            raise AssertionError("double QC decision was accepted")
        except HTTPError as error:
            assert error.code == 409

        with urlopen(base + f"/articles/{row['id']}") as response:
            detail = response.read().decode("utf-8")
        assert "QC decision recorded" in detail
        assert "USEFUL" in detail
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_qc_decision_requires_authenticated_mutation_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "qc-read-only"))
    server = serve(port=0)
    thread = Thread(target=server.serve_forever); thread.start()
    try:
        request = Request(f"http://127.0.0.1:{server.server_port}/qc", data=urlencode({"article_id": 1, "decision": "USEFUL"}).encode(), method="POST")
        try:
            urlopen(request)
            raise AssertionError("unauthenticated QC decision was accepted")
        except HTTPError as error:
            assert error.code == 403
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_qc_archive_survives_restart(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "qc-restart"))
    database = _seed(monkeypatch, tmp_path)
    server = serve(port=0, mutation_authorizer=lambda _headers: True)
    thread = Thread(target=server.serve_forever); thread.start()
    try:
        with database.connect() as con:
            article_id = con.execute("SELECT id FROM articles WHERE source_id='sk_hynix_newsroom'").fetchone()[0]
        payload = urlencode({"article_id": article_id, "decision": "DUPLICATE"}).encode()
        urlopen(Request(f"http://127.0.0.1:{server.server_port}/qc", data=payload, method="POST"))
    finally:
        server.shutdown(); thread.join(); server.server_close()

    # Fresh server process/object over the same on-disk data directory: the
    # QC decision must still be there (on disk, not in memory) and the item
    # must still be excluded from the active queue.
    server2 = serve(port=0, mutation_authorizer=lambda _headers: True)
    thread2 = Thread(target=server2.serve_forever); thread2.start()
    try:
        with urlopen(f"http://127.0.0.1:{server2.server_port}/") as response:
            page = response.read().decode("utf-8")
        assert "Recently QCed" in page
        with urlopen(f"http://127.0.0.1:{server2.server_port}/articles/{article_id}") as response:
            detail = response.read().decode("utf-8")
        assert "QC decision recorded" in detail
        assert "DUPLICATE" in detail
    finally:
        server2.shutdown(); thread2.join(); server2.server_close()


def test_run_all_collectors_never_includes_experimental_sources(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "production-only"))
    calls = []

    def fake_run(sources, settings, database, source_id=None, production_only=False, progress=None):
        calls.append({"source_id": source_id, "production_only": production_only})
        from korean_tech_wire.discovery.runner import RunSummary
        return RunSummary(attempted=0, succeeded=0, discovered=0, accepted=0, new=0)

    monkeypatch.setattr("korean_tech_wire.dashboard.run_collectors", fake_run)
    server = serve(port=0, mutation_authorizer=lambda _headers: True)
    thread = Thread(target=server.serve_forever); thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        # Run all collectors (no explicit source): must be production_only.
        urlopen(Request(base + "/collect", data=b"source=", method="POST"))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not calls:
            time.sleep(0.02)
        assert calls[-1] == {"source_id": None, "production_only": True}
        while True:
            with urlopen(base + "/collection-status") as response:
                if not json.load(response)["running"]:
                    break
            time.sleep(0.02)

        # Explicitly targeting one collector (including an EXPERIMENTAL one)
        # is the only way an EXPERIMENTAL source gets to run, and it must not
        # be filtered out by production_only.
        urlopen(Request(base + "/collect", data=b"source=zdnet_korea_semi_display", method="POST"))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and len(calls) < 2:
            time.sleep(0.02)
        assert calls[-1] == {"source_id": "zdnet_korea_semi_display", "production_only": False}
    finally:
        server.shutdown(); thread.join(); server.server_close()


def test_experimental_sources_hidden_from_run_controls_unless_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("KOREAN_TECH_WIRE_DATA_DIR", str(tmp_path / "exp-hidden"))
    server = serve(port=0, mutation_authorizer=lambda _headers: True)
    thread = Thread(target=server.serve_forever); thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/") as response:
            page = response.read().decode("utf-8")
        assert "hidden (enable in config)" in page
        assert 'data-source="zdnet_korea_semi_display"' not in page
        assert 'data-source="sk_hynix_newsroom"' in page
    finally:
        server.shutdown(); thread.join(); server.server_close()


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
        # Registry size is expected to grow as sources are added; derive the
        # count from the live registry instead of hardcoding it.
        from korean_tech_wire import dashboard as _dashboard
        expected_sources = set(_dashboard._source_map().keys())
        assert state["summary"]["new"] == len(expected_sources)
        assert set(state["sources"]) == expected_sources
        with urlopen(base + "/") as response:
            page = response.read().decode("utf-8")
        assert "Local lead SK hynix Newsroom Korea" in page
        assert "No local leads yet" not in page
    finally:
        server.shutdown(); thread.join(); server.server_close()
