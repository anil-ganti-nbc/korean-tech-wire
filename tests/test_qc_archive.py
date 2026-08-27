from __future__ import annotations

from pathlib import Path

import pytest

from korean_tech_wire.storage.qc_archive import QC_DECISIONS, AlreadyDecided, QCArchive


def _article(article_id: int = 1) -> dict:
    return {
        "id": article_id,
        "source_id": "sk_hynix_newsroom",
        "canonical_url": "https://news.skhynix.co.kr/a",
        "title_original": "SK하이닉스, 차세대 메모리 공개",
        "body_original": "한국어 원문",
        "category": "memory",
        "published_at": "2026-08-20T00:00:00+00:00",
        "discovered_at": "2026-08-20T00:00:00+00:00",
        "first_seen_at": "2026-08-20T00:00:00+00:00",
    }


def test_decide_archives_full_item_and_provenance(tmp_path: Path):
    archive = QCArchive(tmp_path / "qc_archive.db")
    archive.migrate()
    archive.decide(_article(), "USEFUL", note="looks solid", decided_by="owner")
    row = archive.decision_for(1)
    assert row is not None
    assert row["decision"] == "USEFUL"
    assert row["note"] == "looks solid"
    assert row["source_id"] == "sk_hynix_newsroom"
    assert row["title_original"] == "SK하이닉스, 차세대 메모리 공개"
    assert row["decided_at"]


def test_decide_rejects_unknown_decision(tmp_path: Path):
    archive = QCArchive(tmp_path / "qc_archive.db")
    archive.migrate()
    with pytest.raises(ValueError):
        archive.decide(_article(), "MAYBE")


def test_decide_is_idempotency_guarded_against_double_qc(tmp_path: Path):
    archive = QCArchive(tmp_path / "qc_archive.db")
    archive.migrate()
    archive.decide(_article(), "USEFUL")
    with pytest.raises(AlreadyDecided):
        archive.decide(_article(), "NOT_USEFUL")
    # The first decision wins; no duplicate row, no overwrite.
    row = archive.decision_for(1)
    assert row["decision"] == "USEFUL"
    with archive.connect() as con:
        assert con.execute("SELECT COUNT(*) FROM qc_decisions").fetchone()[0] == 1


def test_decided_article_ids_and_recent(tmp_path: Path):
    archive = QCArchive(tmp_path / "qc_archive.db")
    archive.migrate()
    archive.decide(_article(1), "USEFUL")
    archive.decide(_article(2), "DUPLICATE")
    assert archive.decided_article_ids() == {1, 2}
    recent = archive.recent(10)
    assert [row["article_id"] for row in recent] == [2, 1]
    assert archive.status()["total"] == 2


def test_archive_persists_across_reopen(tmp_path: Path):
    path = tmp_path / "qc_archive.db"
    first = QCArchive(path)
    first.migrate()
    first.decide(_article(), "FALSE_POSITIVE")
    # Simulate a restart: a brand new QCArchive instance over the same file
    # must see the previously recorded decision -- this is on-disk state,
    # not in-memory, so it survives a process restart.
    second = QCArchive(path)
    assert second.decision_for(1)["decision"] == "FALSE_POSITIVE"


def test_all_decisions_are_recognised_values():
    assert set(QC_DECISIONS) == {"USEFUL", "NOT_USEFUL", "FALSE_POSITIVE", "DUPLICATE"}
