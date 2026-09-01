"""Separate, on-disk QC/decision archive database.

Modeled on Chinese Tech Wire's LeadOutcome pattern (an append-style,
provenance-carrying record of what an editor decided about a lead) but
implemented as a *physically separate* SQLite file rather than another table
in the live collector database. Rationale:

  - The live database (korean_tech_wire.db) is fleet-governed: destructive
    changes to it are prohibited, and any schema migration to it requires a
    fresh verified backup first. Keeping the QC decision ledger in its own
    file (korean_tech_wire_qc.db, created fresh by this module) means normal
    QC operation never needs to touch or migrate the live DB's schema at
    all.
  - A decision is a durable editorial/audit record. Storing a full snapshot
    of the item (title, body, url, source, discovered/published timestamps)
    at decision time means the archive is self-contained -- it stays
    readable even if the source article is later purged or its source
    retired from config/sources.yaml.
  - UNIQUE(article_id) is the race guard: two concurrent QC submissions for
    the same article can both attempt an INSERT, but only one commits. The
    caller sees IntegrityError and reports 409/"already decided", so there
    is never a duplicate decision or a lost update.

"Active queue" filtering (removing a QC'd item from the default dashboard
view) is done by the caller consulting `decided_article_ids()` -- the live
DB's `articles` table and `record_status` column are never mutated by a QC
decision. This means an item's presence in the live DB is unaffected by QC;
only this archive's ledger says whether/how it was reviewed, which is also
exactly what makes a restart safe (SQLite-on-disk, no in-memory state) and
what makes "FIRST_SEEN is not the same as editorially novel" easy to honour:
this module records decisions, never novelty judgements.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .database import SchemaCompatibility, SchemaCompatibilityError

# KTW's own naming for the four terminal QC decisions, chosen to match the
# vocabulary Chinese Tech Wire's quick-tap lead feedback already uses
# (USEFUL / NOT_USEFUL / DUPLICATE / FALSE_POSITIVE) rather than inventing
# unrelated terms -- there is no e-commerce "out of stock" concept for a
# news lead, so DUPLICATE (a story that is no longer novel / already
# covered) is KTW's equivalent terminal decision for that slot.
QC_DECISIONS = ("USEFUL", "NOT_USEFUL", "FALSE_POSITIVE", "DUPLICATE")
QC_SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS qc_decisions (
    id INTEGER PRIMARY KEY,
    article_id INTEGER NOT NULL UNIQUE,
    source_id TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    title_original TEXT NOT NULL,
    body_original TEXT,
    category TEXT,
    published_at TEXT,
    discovered_at TEXT,
    first_seen_at TEXT,
    decision TEXT NOT NULL,
    note TEXT,
    decided_at TEXT NOT NULL,
    decided_by TEXT
);
CREATE INDEX IF NOT EXISTS qc_decisions_decided_at_idx ON qc_decisions(decided_at DESC);
CREATE INDEX IF NOT EXISTS qc_decisions_source_idx ON qc_decisions(source_id);
"""


def _iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


class AlreadyDecided(Exception):
    """Raised when an article already has a QC decision (race or re-submit)."""


class QCArchive:
    """A separate, append-only ledger of editorial QC decisions."""

    def __init__(self, path: Path):
        self.path = path

    def _connect_unchecked(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def inspect_compatibility(self) -> SchemaCompatibility:
        """Read the archive contract without creating or changing its file."""
        if not self.path.exists():
            return SchemaCompatibility("FRESH", QC_SCHEMA_VERSION, (), "QC archive does not exist")
        try:
            uri = self.path.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True) as con:
                integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
                if integrity != "ok":
                    return SchemaCompatibility("CORRUPT", QC_SCHEMA_VERSION, (), f"QC archive integrity check failed: {integrity}")
                rows = con.execute("SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
                tables = {name for kind, name in rows if kind == "table"}
                indexes = {name for kind, name in rows if kind == "index"}
                if not tables:
                    return SchemaCompatibility("FRESH", QC_SCHEMA_VERSION, (), "QC archive is empty")
                if "qc_schema_migrations" not in tables:
                    return SchemaCompatibility("UNKNOWN", QC_SCHEMA_VERSION, (), "non-empty QC archive has no version marker")
                marker_columns = {row[1] for row in con.execute("PRAGMA table_info(qc_schema_migrations)")}
                if not {"version", "applied_at"}.issubset(marker_columns):
                    return SchemaCompatibility("CORRUPT", QC_SCHEMA_VERSION, (), "QC archive marker shape is invalid")
                versions = tuple(row[0] for row in con.execute("SELECT version FROM qc_schema_migrations ORDER BY version"))
                if any(not isinstance(version, int) or version <= 0 for version in versions):
                    return SchemaCompatibility("CORRUPT", QC_SCHEMA_VERSION, (), "QC archive marker contains an invalid version")
                if any(version > QC_SCHEMA_VERSION for version in versions):
                    return SchemaCompatibility("INCOMPATIBLE_NEWER", QC_SCHEMA_VERSION, versions, "QC archive is newer than this KTW binary")
                required_tables = {"qc_decisions", "qc_schema_migrations"}
                required_indexes = {"qc_decisions_decided_at_idx", "qc_decisions_source_idx"}
                if versions == (QC_SCHEMA_VERSION,) and required_tables.issubset(tables) and required_indexes.issubset(indexes):
                    return SchemaCompatibility("COMPATIBLE", QC_SCHEMA_VERSION, versions, "exact QC archive contract is present")
                if versions in {(), (QC_SCHEMA_VERSION,)}:
                    return SchemaCompatibility("PARTIAL", QC_SCHEMA_VERSION, versions, "QC archive marker and structure disagree")
                return SchemaCompatibility("CORRUPT", QC_SCHEMA_VERSION, versions, "QC archive marker is not a valid numbered contract")
        except sqlite3.Error as error:
            return SchemaCompatibility("CORRUPT", QC_SCHEMA_VERSION, (), f"QC archive inspection failed: {error}")

    def require_compatible(self) -> SchemaCompatibility:
        status = self.inspect_compatibility()
        if not status.ready:
            raise SchemaCompatibilityError(f"KTW QC archive compatibility gate refused normal work: {status.state}: {status.reason}")
        return status

    def connect(self) -> sqlite3.Connection:
        self.require_compatible()
        return self._connect_unchecked()

    def migrate(self) -> None:
        """Canonical bootstrap for a genuinely empty QC archive only."""
        before = self.inspect_compatibility()
        if before.ready:
            return
        if before.state != "FRESH":
            raise SchemaCompatibilityError(
                f"KTW QC archive migration refused {before.state} state: {before.reason}"
            )
        with self._connect_unchecked() as con:
            con.execute("CREATE TABLE IF NOT EXISTS qc_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            con.executescript(_SCHEMA)
            con.execute("INSERT INTO qc_schema_migrations(version, applied_at) VALUES (?, ?)", (QC_SCHEMA_VERSION, _iso()))
        self.require_compatible()

    def decided_article_ids(self) -> set[int]:
        with self.connect() as con:
            return {row[0] for row in con.execute("SELECT article_id FROM qc_decisions")}

    def decision_for(self, article_id: int) -> sqlite3.Row | None:
        with self.connect() as con:
            return con.execute("SELECT * FROM qc_decisions WHERE article_id=?", (article_id,)).fetchone()

    def decide(self, article: sqlite3.Row | dict, decision: str, *, note: str | None = None, decided_by: str = "owner") -> None:
        """Transactionally archive one article's full snapshot + provenance and
        record the decision. Raises AlreadyDecided if this article_id already
        has a row (unique-constraint race guard -- never a silent duplicate)."""
        if decision not in QC_DECISIONS:
            raise ValueError(f"unknown QC decision: {decision!r}")
        article = dict(article)
        try:
            with self.connect() as con:
                con.execute(
                    "INSERT INTO qc_decisions(article_id,source_id,canonical_url,title_original,body_original,category,published_at,discovered_at,first_seen_at,decision,note,decided_at,decided_by)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        article["id"], article["source_id"], article["canonical_url"], article["title_original"],
                        article.get("body_original"), article.get("category"), article.get("published_at"),
                        article.get("discovered_at"), article.get("first_seen_at"), decision, note, _iso(), decided_by,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise AlreadyDecided(f"article {article['id']} already has a QC decision") from error

    def recent(self, limit: int = 50) -> list[sqlite3.Row]:
        with self.connect() as con:
            return con.execute("SELECT * FROM qc_decisions ORDER BY decided_at DESC LIMIT ?", (limit,)).fetchall()

    def status(self) -> dict[str, int]:
        with self.connect() as con:
            total = con.execute("SELECT COUNT(*) FROM qc_decisions").fetchone()[0]
            by_decision = {row["decision"]: row["n"] for row in con.execute("SELECT decision, COUNT(*) AS n FROM qc_decisions GROUP BY decision")}
        return {"total": total, **by_decision}
