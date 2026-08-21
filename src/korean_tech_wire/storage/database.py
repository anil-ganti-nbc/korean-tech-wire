from __future__ import annotations

import hashlib, json, sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from ..models import DiscoveredArticle
from ..models import Source
from ..scheduling import SourceDueState

MIGRATIONS = [(1, """
CREATE TABLE sources (id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE runs (id INTEGER PRIMARY KEY, source_id TEXT, started_at TEXT NOT NULL, finished_at TEXT, status TEXT, summary_json TEXT);
CREATE TABLE run_errors (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, source_id TEXT NOT NULL, error_type TEXT NOT NULL, message TEXT NOT NULL, occurred_at TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(id));
CREATE TABLE fetch_attempts (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, source_id TEXT NOT NULL, url TEXT NOT NULL, fetched_at TEXT NOT NULL, outcome TEXT NOT NULL, error_message TEXT, FOREIGN KEY(run_id) REFERENCES runs(id));
CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, source_article_id TEXT, source_url TEXT NOT NULL, canonical_url TEXT NOT NULL, title_original TEXT NOT NULL, title_normalized TEXT NOT NULL, body_original TEXT, author TEXT, category TEXT, published_at TEXT, discovered_at TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, content_hash TEXT NOT NULL, raw_metadata TEXT NOT NULL, translation_status TEXT NOT NULL DEFAULT 'untranslated', title_english TEXT, summary_english TEXT, UNIQUE(source_id, canonical_url));
CREATE INDEX articles_seen_idx ON articles(last_seen_at DESC);
CREATE INDEX articles_source_article_id_idx ON articles(source_id, source_article_id);
"""), (2, """
ALTER TABLE articles ADD COLUMN record_status TEXT NOT NULL DEFAULT 'valid';
CREATE INDEX articles_status_idx ON articles(record_status);
"""), (3, """
CREATE TABLE source_run_health (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, source_id TEXT NOT NULL, attempted_at TEXT NOT NULL, duration_ms INTEGER NOT NULL, success INTEGER NOT NULL, references_discovered INTEGER NOT NULL, accepted INTEGER NOT NULL, rejected INTEGER NOT NULL, new_articles INTEGER NOT NULL, existing_articles INTEGER NOT NULL, extraction_failures INTEGER NOT NULL, timestamped INTEGER NOT NULL, health_note TEXT, FOREIGN KEY(run_id) REFERENCES runs(id));
CREATE INDEX source_run_health_source_idx ON source_run_health(source_id, attempted_at DESC);
"""), (4, """
CREATE TABLE article_feedback (id INTEGER PRIMARY KEY, article_id INTEGER NOT NULL, outcome TEXT NOT NULL, note TEXT, created_at TEXT NOT NULL, FOREIGN KEY(article_id) REFERENCES articles(id));
CREATE INDEX article_feedback_article_idx ON article_feedback(article_id, created_at DESC);
""")]

def iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()

def health_failure_classification(note: str | None) -> str:
    """Classify retained historical failures without overwriting their evidence."""
    text = (note or "").casefold()
    if any(token in text for token in ("winerror 10013", "failed to connect", "network is unreachable", "connection refused", "timed out")):
        return "environment"
    if any(token in text for token in ("keyboardinterrupt", "intentionally aborted", "development run")):
        return "intentional_development"
    return "source_or_parser"

class Database:
    def __init__(self, path: Path, *, clock: Callable[[], datetime] | None = None):
        self.path = path
        self._clock = clock or (lambda: datetime.now(timezone.utc))
    def _iso(self, value: datetime | None = None) -> str:
        return iso(value or self._clock())
    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True); connection = sqlite3.connect(self.path); connection.row_factory = sqlite3.Row; return connection
    def migrate(self) -> None:
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            done = {row[0] for row in con.execute("SELECT version FROM schema_migrations")}
            for version, sql in MIGRATIONS:
                if version not in done:
                    con.executescript(sql); con.execute("INSERT INTO schema_migrations VALUES (?, ?)", (version, self._iso()))
    def start_run(self, source_id: str | None) -> int:
        with self.connect() as con:
            return con.execute("INSERT INTO runs(source_id, started_at) VALUES (?, ?)", (source_id, self._iso())).lastrowid
    def sync_sources(self, sources: Iterable[Source]) -> None:
        with self.connect() as con:
            for source in sources:
                con.execute("INSERT INTO sources(id,name,status,updated_at) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,status=excluded.status,updated_at=excluded.updated_at", (source.id, source.name, source.status, self._iso()))
    def record_fetch(self, run_id: int, source_id: str, url: str, outcome: str, error_message: str | None = None) -> None:
        with self.connect() as con: con.execute("INSERT INTO fetch_attempts(run_id,source_id,url,fetched_at,outcome,error_message) VALUES (?,?,?,?,?,?)", (run_id, source_id, url, self._iso(), outcome, error_message))
    def finish_run(self, run_id: int, status: str, summary: object) -> None:
        with self.connect() as con: con.execute("UPDATE runs SET finished_at=?, status=?, summary_json=? WHERE id=?", (self._iso(), status, json.dumps(asdict(summary)), run_id))
    def record_error(self, run_id: int, source_id: str, error_type: str, message: str) -> None:
        with self.connect() as con: con.execute("INSERT INTO run_errors(run_id,source_id,error_type,message,occurred_at) VALUES (?,?,?,?,?)", (run_id,source_id,error_type,message,self._iso()))
    def baseline_has_content(self, source_id: str) -> bool:
        with self.connect() as con:
            return con.execute("SELECT 1 FROM source_run_health WHERE source_id=? AND success=1 AND references_discovered>0 LIMIT 1", (source_id,)).fetchone() is not None
    def record_source_health(self, run_id: int, source_id: str, *, duration_ms: int, success: bool, references: int, accepted: int, rejected: int, new: int, existing: int, extraction_failures: int, timestamped: int, note: str | None = None) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO source_run_health(run_id,source_id,attempted_at,duration_ms,success,references_discovered,accepted,rejected,new_articles,existing_articles,extraction_failures,timestamped,health_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (run_id,source_id,self._iso(),duration_ms,int(success),references,accepted,rejected,new,existing,extraction_failures,timestamped,note))
    def health_summary(self, source_ids: Iterable[str] | None = None, recent_limit: int = 20) -> list[dict[str, object]]:
        requested = list(source_ids or [])
        with self.connect() as con:
            query = "SELECT * FROM source_run_health"
            params: list[object] = []
            if requested:
                query += " WHERE source_id IN (" + ",".join("?" for _ in requested) + ")"; params = requested
            query += " ORDER BY source_id, attempted_at DESC"
            rows = con.execute(query, params).fetchall()
            error_query = "SELECT source_id, occurred_at, message FROM run_errors"
            if requested:
                error_query += " WHERE source_id IN (" + ",".join("?" for _ in requested) + ")"
            errors = con.execute(error_query, params).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows: grouped.setdefault(row["source_id"], []).append(row)
        errors_by_source: dict[str, list[sqlite3.Row]] = {}
        for error in errors: errors_by_source.setdefault(error["source_id"], []).append(error)
        summaries = []
        for source_id in sorted(set(grouped) | set(errors_by_source)):
            history = grouped.get(source_id, [])
            historical_errors = errors_by_source.get(source_id, [])
            recent = history[:recent_limit]
            source_failures = sum(not row["success"] and health_failure_classification(row["health_note"]) == "source_or_parser" for row in history) + sum(health_failure_classification(row["message"]) == "source_or_parser" for row in historical_errors)
            environment_failures = sum(not row["success"] and health_failure_classification(row["health_note"]) == "environment" for row in history) + sum(health_failure_classification(row["message"]) == "environment" for row in historical_errors)
            intentional = sum(not row["success"] and health_failure_classification(row["health_note"]) == "intentional_development" for row in history)
            consecutive_successes = 0
            for row in history:
                if row["success"]: consecutive_successes += 1
                elif health_failure_classification(row["health_note"]) != "environment": break
            latest = history[0] if history else None
            last_success = next((row for row in history if row["success"]), None)
            last_failure = next((row for row in history if not row["success"]), None)
            historical_last_failure = max((row["occurred_at"] for row in historical_errors), default=None)
            summaries.append({
                "source_id": source_id, "runs": len(history), "recent_runs": len(recent), "successes": sum(row["success"] for row in history),
                "source_failures": source_failures, "environment_failures": environment_failures, "intentional_development_failures": intentional,
                "consecutive_successes": consecutive_successes, "last_success": last_success["attempted_at"] if last_success else None,
                "last_failure": max(last_failure["attempted_at"] if last_failure else "", historical_last_failure or "") or None, "latest_references": latest["references_discovered"] if latest else None,
                "latest_accepted": latest["accepted"] if latest else None, "latest_rejected": latest["rejected"] if latest else None,
                "latest_timestamped": latest["timestamped"] if latest else None, "latest_extraction_failures": latest["extraction_failures"] if latest else None,
                "unexpected_zero_events": sum("unexpected zero" in (row["health_note"] or "").casefold() for row in history),
                "recent_notes": [row["health_note"] for row in recent if row["health_note"]],
            })
        return summaries
    def source_due_state(self, source_id: str, *, history_limit: int = 200) -> SourceDueState:
        with self.connect() as con:
            rows = con.execute("SELECT attempted_at, success FROM source_run_health WHERE source_id=? ORDER BY attempted_at DESC LIMIT ?", (source_id, history_limit)).fetchall()
        if not rows:
            return SourceDueState(last_attempt_at=None, last_success_at=None, consecutive_failures=0)
        last_attempt_at = datetime.fromisoformat(rows[0]["attempted_at"])
        last_success_at = None
        consecutive_failures = 0
        for row in rows:
            if row["success"]:
                last_success_at = datetime.fromisoformat(row["attempted_at"])
                break
            consecutive_failures += 1
        return SourceDueState(last_attempt_at=last_attempt_at, last_success_at=last_success_at, consecutive_failures=consecutive_failures)

    def source_last_successes(self, source_ids: Iterable[str]) -> dict[str, datetime]:
        requested = list(source_ids)
        if not requested:
            return {}
        with self.connect() as con:
            rows = con.execute("SELECT source_id, MAX(attempted_at) AS attempted_at FROM source_run_health WHERE success=1 AND source_id IN (" + ",".join("?" for _ in requested) + ") GROUP BY source_id", requested).fetchall()
        return {row["source_id"]: datetime.fromisoformat(row["attempted_at"]) for row in rows}
    def backup_to(self, destination: Path) -> None:
        if destination.exists():
            raise ValueError(f"backup destination already exists: {destination}")
        with self.connect() as source:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("source database integrity check failed")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(destination) as target:
                source.backup(target)
        with sqlite3.connect(destination) as check:
            if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("backup database integrity check failed")
    def migration_checkpoint(self) -> dict[str, object]:
        with self.connect() as con:
            article_counts = {row["source_id"]: row["count"] for row in con.execute("SELECT source_id, COUNT(*) AS count FROM articles GROUP BY source_id")}
            table_counts = {table: con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("articles", "runs", "source_run_health", "fetch_attempts", "run_errors")}
            migrations = [row[0] for row in con.execute("SELECT version FROM schema_migrations ORDER BY version")]
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            journal_mode = con.execute("PRAGMA journal_mode").fetchone()[0]
            duplicates = con.execute("SELECT COUNT(*) - COUNT(DISTINCT source_id || char(0) || canonical_url) FROM articles").fetchone()[0]
        return {"integrity": integrity, "journal_mode": journal_mode, "migrations": migrations, "table_counts": table_counts, "article_counts": article_counts, "duplicate_canonical_identities": duplicates, "health": self.health_summary()}
    def persist_articles(self, articles: Iterable[DiscoveredArticle]) -> tuple[int, int]:
        new = existing = 0
        with self.connect() as con:
            for article in articles:
                now = self._iso(); normalized = " ".join(article.title_original.casefold().split()); content = article.body_original or article.title_original
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                values = (article.source_id, article.source_article_id, article.source_url, article.canonical_url, article.title_original, normalized, article.body_original, article.author, article.category, iso(article.published_at) if article.published_at else None, iso(article.discovered_at), now, now, digest, json.dumps(article.metadata, ensure_ascii=False))
                try:
                    con.execute("INSERT INTO articles(source_id,source_article_id,source_url,canonical_url,title_original,title_normalized,body_original,author,category,published_at,discovered_at,first_seen_at,last_seen_at,content_hash,raw_metadata) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values); new += 1
                except sqlite3.IntegrityError:
                    con.execute("UPDATE articles SET source_article_id=?, source_url=?, title_original=?, title_normalized=?, body_original=COALESCE(?, body_original), author=COALESCE(?, author), category=COALESCE(?, category), published_at=COALESCE(?, published_at), last_seen_at=?, content_hash=?, raw_metadata=?, record_status='valid' WHERE source_id=? AND canonical_url=?", (article.source_article_id, article.source_url, article.title_original, normalized, article.body_original, article.author, article.category, iso(article.published_at) if article.published_at else None, now, digest, json.dumps(article.metadata, ensure_ascii=False), article.source_id, article.canonical_url)); existing += 1
        return new, existing
    def needs_enrichment(self, source_id: str, canonical_url: str) -> bool:
        with self.connect() as con:
            row = con.execute("SELECT body_original, published_at, record_status FROM articles WHERE source_id=? AND canonical_url=?", (source_id, canonical_url)).fetchone()
            return bool(row and (row["record_status"] != "valid" or row["body_original"] is None or row["published_at"] is None))
    def stored_published_at(self, source_id: str, canonical_url: str) -> datetime | None:
        with self.connect() as con:
            row = con.execute("SELECT published_at FROM articles WHERE source_id=? AND canonical_url=?", (source_id, canonical_url)).fetchone()
        if not row or not row["published_at"]:
            return None
        return datetime.fromisoformat(row["published_at"])
    def quarantine_legacy_samsung_records(self) -> tuple[int, int]:
        """Safely retain ambiguous legacy rows while deleting only URL-proven non-articles."""
        with self.connect() as con:
            marked = con.execute("UPDATE articles SET record_status='legacy_unverified' WHERE source_id='samsung_newsroom_kr' AND record_status='valid'").rowcount
            deleted = con.execute("DELETE FROM articles WHERE source_id='samsung_newsroom_kr' AND record_status='legacy_unverified' AND (canonical_url LIKE '%/medialibrary/%' OR canonical_url LIKE '%/feed/rss' OR canonical_url IN ('https://news.samsung.com/kr/latest', 'https://news.samsung.com/kr/highlights'))").rowcount
        return marked, deleted
    def quarantine_legacy_theelec_records(self) -> int:
        with self.connect() as con:
            return con.execute("UPDATE articles SET record_status='legacy_unverified' WHERE source_id='the_elec' AND record_status='valid'").rowcount
    def has_article(self, source_id: str, canonical_url: str) -> bool:
        with self.connect() as con:
            return con.execute("SELECT 1 FROM articles WHERE source_id=? AND canonical_url=?", (source_id, canonical_url)).fetchone() is not None
    def latest_articles(self, limit: int = 20) -> list[sqlite3.Row]:
        with self.connect() as con: return con.execute("SELECT * FROM articles WHERE record_status='valid' ORDER BY COALESCE(published_at, discovered_at) DESC LIMIT ?", (limit,)).fetchall()
    def add_feedback(self, article_id: int, outcome: str, note: str | None = None) -> None:
        with self.connect() as con:
            con.execute("INSERT INTO article_feedback(article_id,outcome,note,created_at) VALUES (?,?,?,?)", (article_id, outcome, note, iso()))
    def feedback_history(self, article_id: int | None = None) -> list[sqlite3.Row]:
        with self.connect() as con:
            if article_id is None:
                return con.execute("SELECT f.*, a.title_original, a.source_id FROM article_feedback f JOIN articles a ON a.id=f.article_id ORDER BY f.created_at DESC").fetchall()
            return con.execute("SELECT * FROM article_feedback WHERE article_id=? ORDER BY created_at DESC", (article_id,)).fetchall()
    def status(self) -> dict[str, int]:
        with self.connect() as con:
            return {"articles": con.execute("SELECT COUNT(*) FROM articles").fetchone()[0], "runs": con.execute("SELECT COUNT(*) FROM runs").fetchone()[0], "errors": con.execute("SELECT COUNT(*) FROM run_errors").fetchone()[0]}
