"""A deliberate refusal is not the same failure as a broken source.

sk_hynix_newsroom accumulated 844 "source failures" while
news.skhynix.co.kr was up the entire time, serving valid RSS to every client
except the one IP the deployment host egresses from: an AWS ELB edge ACL
answers 403 for that address on every path, including the site root, for any
User-Agent. Reporting that as source_or_parser told the operator the
publisher's site or our parser was broken, and pointed any repair effort at
the wrong thing.

These tests pin the reclassification AND, more importantly, pin that it is
only a reclassification: nothing about failure visibility, streak breaking,
run outcome or retained evidence may soften.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from korean_tech_wire.discovery.runner import RunSummary
from korean_tech_wire.storage.database import Database, health_failure_classification


# -- classification -----------------------------------------------------------


def test_deliberate_refusals_are_classified_as_access_blocked():
    for note in (
        "Invalid RSS response: HTTP Error 403: Forbidden",
        "Invalid RSS response: HTTP Error 401: Unauthorized",
        "Invalid RSS response: HTTP Error 429: Too Many Requests",
    ):
        assert health_failure_classification(note) == "access_blocked", note


def test_the_real_sk_hynix_failure_string_classifies_as_access_blocked():
    """The exact message recorded 422 times in production."""
    assert (
        health_failure_classification("Invalid RSS response: HTTP Error 403: Forbidden")
        == "access_blocked"
    )


def test_genuine_source_and_parser_failures_are_still_source_or_parser():
    """The new class must not swallow real publisher/parser breakage."""
    for note in (
        "Invalid RSS response: HTTP Error 500: Internal Server Error",
        "Invalid RSS response: HTTP Error 404: Not Found",
        "unexpected zero references after populated baseline",
        "ValueError: could not parse published_at",
        "Invalid RSS response: not well-formed (invalid token)",
    ):
        assert health_failure_classification(note) == "source_or_parser", note


def test_environment_and_intentional_classes_are_unchanged():
    assert health_failure_classification("connection refused") == "environment"
    assert health_failure_classification("timed out") == "environment"
    assert health_failure_classification("WinError 10013") == "environment"
    assert health_failure_classification("KeyboardInterrupt") == "intentional_development"


def test_unknown_notes_still_default_to_source_or_parser():
    """Fail toward blaming ourselves/the source, never toward 'blocked'."""
    assert health_failure_classification(None) == "source_or_parser"
    assert health_failure_classification("") == "source_or_parser"
    assert health_failure_classification("something entirely new") == "source_or_parser"


# -- summary behaviour --------------------------------------------------------


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "ktw.db")
    db.migrate()
    return db


def _blocked_run(db: Database, source_id: str = "sk_hynix_newsroom") -> int:
    run_id = db.start_run(source_id)
    note = "Invalid RSS response: HTTP Error 403: Forbidden"
    db.record_error(run_id, source_id, "CollectorError", note)
    db.record_source_health(
        run_id, source_id, duration_ms=10, success=False, references=0,
        accepted=0, rejected=0, new=0, existing=0, extraction_failures=0,
        timestamped=0, note=note,
    )
    db.finish_run(run_id, "partial_failure", RunSummary(attempted=1, failed=1))
    return run_id


def _ok_run(db: Database, source_id: str = "sk_hynix_newsroom") -> int:
    run_id = db.start_run(source_id)
    db.record_source_health(
        run_id, source_id, duration_ms=10, success=True, references=5,
        accepted=5, rejected=0, new=5, existing=0, extraction_failures=0,
        timestamped=5,
    )
    db.finish_run(run_id, "success", RunSummary(attempted=1, succeeded=1))
    return run_id


def test_blocked_failures_are_counted_separately_from_source_failures(tmp_path):
    db = _db(tmp_path)
    for _ in range(3):
        _blocked_run(db)
    summary = next(s for s in db.health_summary() if s["source_id"] == "sk_hynix_newsroom")

    assert summary["access_blocked_failures"] >= 3
    # The whole point: these no longer masquerade as publisher/parser breakage.
    assert summary["source_failures"] == 0


def test_a_blocked_run_is_still_a_failed_run(tmp_path):
    """Reclassification must never become suppression."""
    db = _db(tmp_path)
    _blocked_run(db)
    summary = next(s for s in db.health_summary() if s["source_id"] == "sk_hynix_newsroom")

    assert summary["successes"] == 0
    assert summary["runs"] == 1
    assert summary["last_failure"] is not None
    assert summary["last_success"] is None


def test_a_blocked_run_still_breaks_a_consecutive_success_streak(tmp_path):
    """An access block is a real inability to collect, not a transient blip:
    unlike an `environment` failure it must break the streak, so it can never
    make a source look more qualified than it is."""
    db = _db(tmp_path)
    _ok_run(db)
    _ok_run(db)
    summary = next(s for s in db.health_summary() if s["source_id"] == "sk_hynix_newsroom")
    assert summary["consecutive_successes"] == 2

    _blocked_run(db)
    _ok_run(db)
    summary = next(s for s in db.health_summary() if s["source_id"] == "sk_hynix_newsroom")
    assert summary["consecutive_successes"] == 1, "the block must break the streak"


def test_the_verbatim_error_evidence_is_still_retained(tmp_path):
    """Historical evidence is never overwritten by classification."""
    import sqlite3

    db = _db(tmp_path)
    _blocked_run(db)
    with db.connect() as con:
        con.row_factory = sqlite3.Row
        rows = list(con.execute("SELECT error_type, message FROM run_errors"))
    assert len(rows) == 1
    assert rows[0]["error_type"] == "CollectorError"
    assert rows[0]["message"] == "Invalid RSS response: HTTP Error 403: Forbidden"


def test_a_blocked_source_never_reports_a_healthy_state(tmp_path):
    """No silent empty success: a source we cannot reach is not healthy."""
    db = _db(tmp_path)
    for _ in range(5):
        _blocked_run(db)
    summary = next(s for s in db.health_summary() if s["source_id"] == "sk_hynix_newsroom")

    assert summary["successes"] == 0
    assert summary["consecutive_successes"] == 0
    assert summary["access_blocked_failures"] >= 5
