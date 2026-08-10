from __future__ import annotations

import hashlib, json, sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ..models import DiscoveredArticle
from ..models import Source

MIGRATIONS = [(1, """
CREATE TABLE sources (id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE runs (id INTEGER PRIMARY KEY, source_id TEXT, started_at TEXT NOT NULL, finished_at TEXT, status TEXT, summary_json TEXT);
CREATE TABLE run_errors (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, source_id TEXT NOT NULL, error_type TEXT NOT NULL, message TEXT NOT NULL, occurred_at TEXT NOT NULL, FOREIGN KEY(run_id) REFERENCES runs(id));
CREATE TABLE fetch_attempts (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, source_id TEXT NOT NULL, url TEXT NOT NULL, fetched_at TEXT NOT NULL, outcome TEXT NOT NULL, error_message TEXT, FOREIGN KEY(run_id) REFERENCES runs(id));
CREATE TABLE articles (id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, source_article_id TEXT, source_url TEXT NOT NULL, canonical_url TEXT NOT NULL, title_original TEXT NOT NULL, title_normalized TEXT NOT NULL, body_original TEXT, author TEXT, category TEXT, published_at TEXT, discovered_at TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, content_hash TEXT NOT NULL, raw_metadata TEXT NOT NULL, translation_status TEXT NOT NULL DEFAULT 'untranslated', title_english TEXT, summary_english TEXT, UNIQUE(source_id, canonical_url));
CREATE INDEX articles_seen_idx ON articles(last_seen_at DESC);
CREATE INDEX articles_source_article_id_idx ON articles(source_id, source_article_id);
""")]

def iso(value: datetime | None = None) -> str:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()

class Database:
    def __init__(self, path: Path): self.path = path
    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True); connection = sqlite3.connect(self.path); connection.row_factory = sqlite3.Row; return connection
    def migrate(self) -> None:
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            done = {row[0] for row in con.execute("SELECT version FROM schema_migrations")}
            for version, sql in MIGRATIONS:
                if version not in done:
                    con.executescript(sql); con.execute("INSERT INTO schema_migrations VALUES (?, ?)", (version, iso()))
    def start_run(self, source_id: str | None) -> int:
        with self.connect() as con:
            return con.execute("INSERT INTO runs(source_id, started_at) VALUES (?, ?)", (source_id, iso())).lastrowid
    def sync_sources(self, sources: Iterable[Source]) -> None:
        with self.connect() as con:
            for source in sources:
                con.execute("INSERT INTO sources(id,name,status,updated_at) VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,status=excluded.status,updated_at=excluded.updated_at", (source.id, source.name, source.status, iso()))
    def record_fetch(self, run_id: int, source_id: str, url: str, outcome: str, error_message: str | None = None) -> None:
        with self.connect() as con: con.execute("INSERT INTO fetch_attempts(run_id,source_id,url,fetched_at,outcome,error_message) VALUES (?,?,?,?,?,?)", (run_id, source_id, url, iso(), outcome, error_message))
    def finish_run(self, run_id: int, status: str, summary: object) -> None:
        with self.connect() as con: con.execute("UPDATE runs SET finished_at=?, status=?, summary_json=? WHERE id=?", (iso(), status, json.dumps(asdict(summary)), run_id))
    def record_error(self, run_id: int, source_id: str, error_type: str, message: str) -> None:
        with self.connect() as con: con.execute("INSERT INTO run_errors(run_id,source_id,error_type,message,occurred_at) VALUES (?,?,?,?,?)", (run_id,source_id,error_type,message,iso()))
    def persist_articles(self, articles: Iterable[DiscoveredArticle]) -> tuple[int, int]:
        new = existing = 0
        with self.connect() as con:
            for article in articles:
                now = iso(); normalized = " ".join(article.title_original.casefold().split()); content = article.body_original or article.title_original
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                values = (article.source_id, article.source_article_id, article.source_url, article.canonical_url, article.title_original, normalized, article.body_original, article.author, article.category, iso(article.published_at) if article.published_at else None, iso(article.discovered_at), now, now, digest, json.dumps(article.metadata, ensure_ascii=False))
                try:
                    con.execute("INSERT INTO articles(source_id,source_article_id,source_url,canonical_url,title_original,title_normalized,body_original,author,category,published_at,discovered_at,first_seen_at,last_seen_at,content_hash,raw_metadata) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values); new += 1
                except sqlite3.IntegrityError:
                    con.execute("UPDATE articles SET last_seen_at=?, content_hash=?, raw_metadata=? WHERE source_id=? AND canonical_url=?", (now, digest, json.dumps(article.metadata, ensure_ascii=False), article.source_id, article.canonical_url)); existing += 1
        return new, existing
    def has_article(self, source_id: str, canonical_url: str) -> bool:
        with self.connect() as con:
            return con.execute("SELECT 1 FROM articles WHERE source_id=? AND canonical_url=?", (source_id, canonical_url)).fetchone() is not None
    def latest_articles(self, limit: int = 20) -> list[sqlite3.Row]:
        with self.connect() as con: return con.execute("SELECT * FROM articles ORDER BY COALESCE(published_at, discovered_at) DESC LIMIT ?", (limit,)).fetchall()
    def status(self) -> dict[str, int]:
        with self.connect() as con:
            return {"articles": con.execute("SELECT COUNT(*) FROM articles").fetchone()[0], "runs": con.execute("SELECT COUNT(*) FROM runs").fetchone()[0], "errors": con.execute("SELECT COUNT(*) FROM run_errors").fetchone()[0]}
