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

# KTW's own naming for the four terminal QC decisions, chosen to match the
# vocabulary Chinese Tech Wire's quick-tap lead feedback already uses
# (USEFUL / NOT_USEFUL / DUPLICATE / FALSE_POSITIVE) rather than inventing
# unrelated terms -- there is no e-commerce "out of stock" concept for a
# news lead, so DUPLICATE (a story that is no longer novel / already
# covered) is KTW's equivalent terminal decision for that slot.
QC_DECISIONS = ("USEFUL", "NOT_USEFUL", "FALSE_POSITIVE", "DUPLICATE")

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

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def migrate(self) -> None:
        with self.connect() as con:
            con.executescript(_SCHEMA)

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
