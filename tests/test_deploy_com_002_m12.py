"""M12 regressions for KTW's numbered-SQLite compatibility barriers."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import pytest

from korean_tech_wire import dashboard
from korean_tech_wire.cli import context
from korean_tech_wire.config import Settings
from korean_tech_wire.models import Source
from korean_tech_wire.soak import run_soak
from korean_tech_wire.storage import Database, QCArchive, SCHEMA_VERSION, SchemaCompatibilityError
from korean_tech_wire.storage.database import MIGRATIONS


def _prefix_database(path: Path, through: int) -> Database:
    """Build a valid old numbered state without calling the M12 migrator."""
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        for version, sql in MIGRATIONS[:through]:
            con.executescript(sql)
            con.execute("INSERT INTO schema_migrations VALUES (?, ?)", (version, "2026-09-02T00:00:00+00:00"))
    return Database(path)


def _config(path: Path, database_path: Path) -> Path:
    path.write_text(
        f"database_path: {database_path.as_posix()}\nrequest_timeout_seconds: 1\nuser_agent: test\n",
        encoding="utf-8",
    )
    return path


def test_fresh_bootstrap_is_explicit_and_inspection_does_not_create_state(tmp_path: Path):
    path = tmp_path / "fresh.db"
    database = Database(path)
    before = database.inspect_compatibility()
    assert before.state == "FRESH" and not path.exists()
    database.migrate()
    assert database.inspect_compatibility().state == "COMPATIBLE"
    assert database.inspect_compatibility().expected_version == SCHEMA_VERSION == 5
    assert database.status()["runs"] == 0


def test_old_valid_prefix_requires_canonical_migration_before_normal_work(tmp_path: Path):
    database = _prefix_database(tmp_path / "old.db", 4)
    assert database.inspect_compatibility().state == "MIGRATION_REQUIRED"
    with pytest.raises(SchemaCompatibilityError, match="MIGRATION_REQUIRED"):
        database.status()
    database.migrate()
    assert database.inspect_compatibility().state == "COMPATIBLE"
    assert database.migration_checkpoint()["migrations"] == [1, 2, 3, 4, 5]


def test_newer_missing_corrupt_and_partial_main_state_all_fail_closed(tmp_path: Path):
    newer = Database(tmp_path / "newer.db"); newer.migrate()
    with sqlite3.connect(newer.path) as con:
        con.execute("INSERT INTO schema_migrations VALUES (6, 'future')")
    assert newer.inspect_compatibility().state == "INCOMPATIBLE_NEWER"
    with pytest.raises(SchemaCompatibilityError, match="INCOMPATIBLE_NEWER"):
        newer.start_run("source")

    missing = tmp_path / "missing-marker.db"
    with sqlite3.connect(missing) as con:
        con.execute("CREATE TABLE unknown_existing_state (id INTEGER PRIMARY KEY)")
    missing_database = Database(missing)
    before = missing.read_bytes()
    assert missing_database.inspect_compatibility().state == "UNKNOWN"
    assert missing.read_bytes() == before
    with pytest.raises(SchemaCompatibilityError, match="UNKNOWN"):
        missing_database.migrate()

    corrupt = tmp_path / "corrupt-marker.db"
    with sqlite3.connect(corrupt) as con:
        con.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        con.execute("INSERT INTO schema_migrations VALUES ('bad', 'now')")
    assert Database(corrupt).inspect_compatibility().state == "CORRUPT"

    partial = Database(tmp_path / "partial.db"); partial.migrate()
    with sqlite3.connect(partial.path) as con:
        con.execute("DROP TABLE qualification_terminals")
    assert partial.inspect_compatibility().state == "PARTIAL"
    with pytest.raises(SchemaCompatibilityError, match="PARTIAL"):
        partial.status()


def test_failed_migration_never_marks_database_compatible(tmp_path: Path, monkeypatch):
    import korean_tech_wire.storage.database as database_module

    database = _prefix_database(tmp_path / "failed.db", 4)
    broken = [*MIGRATIONS[:4], (5, "CREATE TABLE interrupted_migration (id INTEGER); SELECT no_such_column;")]
    monkeypatch.setattr(database_module, "MIGRATIONS", broken)
    with pytest.raises(sqlite3.Error):
        database.migrate()
    assert database.inspect_compatibility().state != "COMPATIBLE"
    with pytest.raises(SchemaCompatibilityError):
        database.status()


def test_qc_archive_has_its_own_fresh_marker_and_refuses_unknown_or_newer_state(tmp_path: Path):
    archive = QCArchive(tmp_path / "qc.db")
    assert archive.inspect_compatibility().state == "FRESH"
    archive.migrate()
    assert archive.inspect_compatibility().state == "COMPATIBLE"

    unknown = tmp_path / "unknown-qc.db"
    with sqlite3.connect(unknown) as con:
        con.execute("CREATE TABLE qc_decisions (id INTEGER PRIMARY KEY)")
    unknown_archive = QCArchive(unknown)
    assert unknown_archive.inspect_compatibility().state == "UNKNOWN"
    with pytest.raises(SchemaCompatibilityError, match="UNKNOWN"):
        unknown_archive.migrate()

    newer = QCArchive(tmp_path / "newer-qc.db"); newer.migrate()
    with sqlite3.connect(newer.path) as con:
        con.execute("INSERT INTO qc_schema_migrations VALUES (2, 'future')")
    assert newer.inspect_compatibility().state == "INCOMPATIBLE_NEWER"
    with pytest.raises(SchemaCompatibilityError, match="INCOMPATIBLE_NEWER"):
        newer.status()


def test_cli_scheduler_dashboard_and_direct_database_paths_cross_the_barrier(tmp_path: Path, monkeypatch):
    newer = Database(tmp_path / "entrypoint.db"); newer.migrate()
    with sqlite3.connect(newer.path) as con:
        con.execute("INSERT INTO schema_migrations VALUES (6, 'future')")

    config = _config(tmp_path / "config.yaml", newer.path)
    args = argparse.Namespace(config=str(config), sources="config/sources.yaml")
    with pytest.raises(SchemaCompatibilityError, match="INCOMPATIBLE_NEWER"):
        context(args)

    source = Source("source", "source", "PRODUCTION", True, "missing", "https://example.test/")
    with pytest.raises(SchemaCompatibilityError, match="INCOMPATIBLE_NEWER"):
        run_soak([source], Settings(newer.path, 1, "test"), newer, cycles=1, interval_seconds=0)
    with pytest.raises(SchemaCompatibilityError, match="INCOMPATIBLE_NEWER"):
        newer.sync_sources([source])

    monkeypatch.setattr(dashboard, "CONFIG", config)
    with pytest.raises(SchemaCompatibilityError, match="INCOMPATIBLE_NEWER"):
        dashboard.serve(port=0)


def test_current_version_and_existing_qualification_startup_contract_remain_intact(tmp_path: Path):
    database = Database(tmp_path / "current.db")
    database.migrate()
    source = Source("source", "source", "PRODUCTION", False, "unused", "https://example.test/")
    database.sync_sources([source])
    assert database.inspect_compatibility().ready is True
    # Qualification preparation uses Database.connect(), so this proves the
    # M8 path still has a compatible startup boundary rather than a bypass.
    from korean_tech_wire.qualification import QualificationProvenance, prepare

    run_id = database.start_run(source.id, QualificationProvenance.MANUAL)
    preparation = prepare(database, run_id=run_id, source_id=source.id, scope_key="production:source", material="m12-current", provenance=QualificationProvenance.MANUAL)
    assert preparation.epoch_id > 0
