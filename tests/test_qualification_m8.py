from __future__ import annotations

from datetime import datetime, timezone

from korean_tech_wire.collectors.base import Collector
from korean_tech_wire.config import Settings
from korean_tech_wire.discovery import run_collectors
from korean_tech_wire.models import DiscoveredArticle, Source
from korean_tech_wire.qualification import (
    QualificationProvenance,
    event_rows,
    finish,
    gate,
    material_identity,
    prepare,
    reset_rows,
    terminal_rows,
)
from korean_tech_wire.storage import Database


def _context(database: Database, run_id: int, source: str, scope: str, material: str,
             provenance: QualificationProvenance | str = QualificationProvenance.SCHEDULED):
    return prepare(
        database, run_id=run_id, source_id=source, scope_key=scope,
        material=material_identity({"source": source, "material": material}),
        provenance=provenance,
    )


def test_material_change_resets_before_gate_and_preserves_prior_identity(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    try:
        first_run = database.start_run("source-a", "SCHEDULED")
        first = _context(database, first_run, "source-a", "production:source-a", "A")
        finish(database, first, "success")
        assert gate(database, "production:source-a")["eligible"]

        changed_run = database.start_run("source-a", "SCHEDULED")
        changed = _context(database, changed_run, "source-a", "production:source-a", "B")
        assert changed.epoch_id != first.epoch_id
        assert changed.gate_status == "NOT_QUALIFIED"
        assert not gate(database, "production:source-a")["eligible"]
        resets = reset_rows(database, "production:source-a")
        assert len(resets) == 1
        assert resets[0]["run_id"] == changed_run
        assert resets[0]["prior_material_identity"]
        assert resets[0]["new_material_identity"] != resets[0]["prior_material_identity"]

        finish(database, changed, "success")
        finish(database, changed, "success")
        assert len(terminal_rows(database, "production:source-a")) == 2
        assert [row["event_type"] for row in event_rows(database, "production:source-a")] == ["TERMINAL", "RESET", "TERMINAL"]
        assert gate(database, "production:source-a")["eligible"]
    finally:
        pass


def test_scopes_are_isolated_and_unknown_provenance_fails_closed(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    try:
        a_run = database.start_run("source-a", "SCHEDULED")
        a = _context(database, a_run, "source-a", "production:source-a", "A")
        finish(database, a, "success")
        b_run = database.start_run("source-b", "SCHEDULED")
        b = _context(database, b_run, "source-b", "production:source-b", "B")
        finish(database, b, "success")
        assert gate(database, "production:source-a")["eligible"]
        assert gate(database, "production:source-b")["eligible"]

        changed_run = database.start_run("source-a", "SCHEDULED")
        _context(database, changed_run, "source-a", "production:source-a", "A2")
        assert not gate(database, "production:source-a")["eligible"]
        assert gate(database, "production:source-b")["eligible"]

        unknown_run = database.start_run("source-c", "UNKNOWN")
        unknown = _context(database, unknown_run, "source-c", "production:source-c", "C", QualificationProvenance.UNKNOWN)
        finish(database, unknown, "success")
        assert not gate(database, "production:source-c")["eligible"]
        assert terminal_rows(database, "production:source-c")[0]["provenance"] == "UNKNOWN"
    finally:
        pass


def test_migration_is_additive_and_legacy_run_provenance_is_unknown(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    try:
        run_id = database.start_run("legacy-source")
        with database.connect() as con:
            row = con.execute("SELECT provenance FROM runs WHERE id=?", (run_id,)).fetchone()
            tables = {item["name"] for item in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            versions = [item[0] for item in con.execute("SELECT version FROM schema_migrations ORDER BY version")]
        assert row["provenance"] == "UNKNOWN"
        assert versions == [1, 2, 3, 4, 5]
        assert {"qualification_scopes", "qualification_epochs", "qualification_resets", "qualification_terminals"} <= tables
    finally:
        pass


class _FakeCollector(Collector):
    def discover(self):
        now = datetime.now(timezone.utc)
        return [DiscoveredArticle(self.source.id, "https://example.test/a", "https://example.test/a", "테스트 기사", now, now, body_original="fixture")]


def test_real_runner_supplies_structured_provenance_and_terminal_fact(tmp_path):
    database = Database(tmp_path / "wire.db"); database.migrate()
    settings = Settings(tmp_path / "wire.db", 1, "test")
    source = Source("source-a", "Source A", "PRODUCTION", True, "m8-fake", "https://example.test/")
    from korean_tech_wire.collectors import COLLECTORS
    COLLECTORS["m8-fake"] = _FakeCollector
    try:
        summary = run_collectors([source], settings, database, production_only=True, provenance=QualificationProvenance.SCHEDULED)
        assert summary.succeeded == 1
        with database.connect() as con:
            run = con.execute("SELECT provenance, qualification_scope, qualification_gate_status FROM runs WHERE id=1").fetchone()
        assert run["provenance"] == "SCHEDULED"
        assert run["qualification_scope"] == "production:source-a"
        assert run["qualification_gate_status"] == "NOT_QUALIFIED"
        assert terminal_rows(database, "production:source-a")[0]["provenance"] == "SCHEDULED"
    finally:
        pass
