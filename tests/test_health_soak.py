from datetime import datetime, timezone
from pathlib import Path

import pytest

from korean_tech_wire.collectors import COLLECTORS
from korean_tech_wire.collectors.base import Collector
from korean_tech_wire.config import Settings
from korean_tech_wire.discovery import run_collectors
from korean_tech_wire.models import DiscoveredArticle, Source
from korean_tech_wire.locking import LockUnavailable, RunLock
from korean_tech_wire.soak import run_soak
from korean_tech_wire.storage import Database, health_failure_classification


def test_health_summary_classifies_environment_failures_without_deleting_history(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    run_id = database.start_run("et")
    database.record_source_health(run_id, "et", duration_ms=1, success=False, references=0, accepted=0, rejected=0, new=0, existing=0, extraction_failures=0, timestamped=0, note="OSError: [WinError 10013] blocked")
    run_id = database.start_run("et")
    database.record_source_health(run_id, "et", duration_ms=1, success=True, references=5, accepted=4, rejected=1, new=0, existing=4, extraction_failures=0, timestamped=4)
    summary = database.health_summary(["et"])[0]
    assert health_failure_classification("[WinError 10013]") == "environment"
    assert summary["runs"] == 2 and summary["environment_failures"] == 1 and summary["source_failures"] == 0
    assert summary["consecutive_successes"] == 1


def test_health_summary_includes_pre_health_schema_run_errors_as_environment_evidence(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    run_id = database.start_run("et")
    database.record_error(run_id, "et", "URLError", "[WinError 10013] socket access blocked")
    summary = database.health_summary(["et"])[0]
    assert summary["environment_failures"] == 1 and summary["source_failures"] == 0


class _FakeCollector(Collector):
    def discover(self):
        now = datetime.now(timezone.utc)
        return [DiscoveredArticle(self.source.id, f"https://example.test/{self.source.id}", f"https://example.test/{self.source.id}", "테스트 기사", now, now, body_original="fixture body")]


def _source(source_id: str, status: str) -> Source:
    return Source(source_id, source_id, status, True, "fake", "https://example.test/")


def test_soak_resumes_through_normal_runner_and_only_sleeps_between_cycles(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    settings = Settings(tmp_path / "wire.db", 1, "test")
    COLLECTORS["fake"] = _FakeCollector
    pauses: list[float] = []
    summaries = run_soak([_source("a", "EXPERIMENTAL")], settings, database, cycles=2, interval_seconds=7, sleep=pauses.append)
    assert len(summaries) == 2 and pauses == [7]
    assert database.health_summary(["a"])[0]["runs"] == 2


def test_production_scope_excludes_experimental_and_expands_per_individual_promotion(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    settings = Settings(tmp_path / "wire.db", 1, "test")
    COLLECTORS["fake"] = _FakeCollector
    first = [_source("sk", "PRODUCTION"), _source("lg", "EXPERIMENTAL"), _source("et", "EXPERIMENTAL")]
    assert run_collectors(first, settings, database, production_only=True).attempted == 1
    promoted_lg = [_source("sk", "PRODUCTION"), _source("lg", "PRODUCTION"), _source("et", "EXPERIMENTAL")]
    assert run_collectors(promoted_lg, settings, database, production_only=True).attempted == 2
    promoted_all = [_source("sk", "PRODUCTION"), _source("lg", "PRODUCTION"), _source("et", "PRODUCTION")]
    assert run_collectors(promoted_all, settings, database, production_only=True).attempted == 3


def test_zero_new_run_reuses_persisted_timestamp_for_health_coverage(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    settings = Settings(tmp_path / "wire.db", 1, "test")
    COLLECTORS["fake"] = _FakeCollector
    source = _source("sk", "PRODUCTION")
    run_collectors([source], settings, database, production_only=True)
    second = run_collectors([source], settings, database, production_only=True)
    assert second.new == 0 and second.timestamped == 1


def test_soak_rejects_unknown_source_without_recording_a_fake_run(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    settings = Settings(tmp_path / "wire.db", 1, "test")
    with pytest.raises(ValueError, match="unknown source"):
        run_soak([_source("sk", "PRODUCTION")], settings, database, cycles=1, interval_seconds=0, source_ids=["missing"])
    assert database.status()["runs"] == 0


def test_due_aware_soak_skips_when_every_source_has_a_recent_success(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    settings = Settings(tmp_path / "wire.db", 1, "test")
    COLLECTORS["fake"] = _FakeCollector
    source = _source("sk", "PRODUCTION")
    run_collectors([source], settings, database)
    assert run_soak([source], settings, database, cycles=1, interval_seconds=7200, if_due=True) == []
    assert database.health_summary(["sk"])[0]["runs"] == 1


def test_sqlite_backup_and_run_lock_preserve_safe_handoff_boundaries(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    database.backup_to(tmp_path / "copy.db")
    assert (tmp_path / "copy.db").exists()
    checkpoint = database.migration_checkpoint()
    assert checkpoint["integrity"] == "ok" and checkpoint["duplicate_canonical_identities"] == 0
    first = RunLock(tmp_path / "wire.db.lock"); first.__enter__()
    try:
        with pytest.raises(LockUnavailable):
            RunLock(tmp_path / "wire.db.lock").__enter__()
    finally:
        first.__exit__(None, None, None)
    with RunLock(tmp_path / "wire.db.lock"):
        assert Path(tmp_path / "wire.db.lock").exists()
