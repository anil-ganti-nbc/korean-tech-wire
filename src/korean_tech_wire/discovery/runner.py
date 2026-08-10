from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from ..collectors import COLLECTORS, CollectorError
from ..config import Settings
from ..extraction import extract_text
from ..models import Source
from ..storage import Database


class HttpFetcher:
    def __init__(self, settings: Settings): self.settings = settings
    def get(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": self.settings.user_agent, "Accept-Language": "ko-KR,ko;q=0.9"})
        with urlopen(request, timeout=self.settings.request_timeout_seconds) as response:
            return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")


@dataclass(slots=True)
class RunSummary:
    attempted: int = 0; succeeded: int = 0; failed: int = 0; discovered: int = 0; new: int = 0; existing: int = 0
    errors: list[str] = field(default_factory=list)


def run_collectors(sources: list[Source], settings: Settings, database: Database, source_id: str | None = None) -> RunSummary:
    database.sync_sources(sources)
    run_id = database.start_run(source_id)
    summary = RunSummary()
    for source in sources:
        if not source.enabled or (source_id and source.id != source_id): continue
        summary.attempted += 1
        try:
            collector = COLLECTORS[source.collector](source, HttpFetcher(settings))
            articles = collector.discover(); summary.discovered += len(articles)
            database.record_fetch(run_id, source.id, source.url, "success")
            # Discovery remains cheap: fetch bodies only for candidates not yet known.
            hydrated = []
            for article in articles:
                if database.has_article(article.source_id, article.canonical_url) or article.body_original:
                    hydrated.append(article); continue
                html = HttpFetcher(settings).get(article.source_url)
                database.record_fetch(run_id, source.id, article.source_url, "success")
                hydrated.append(replace(article, body_original=extract_text(html)))
            new, existing = database.persist_articles(hydrated); summary.new += new; summary.existing += existing; summary.succeeded += 1
        except (CollectorError, OSError, KeyError, ValueError) as error:
            summary.failed += 1; message = f"{source.id}: {type(error).__name__}: {error}"; summary.errors.append(message)
            database.record_error(run_id, source.id, type(error).__name__, str(error))
            database.record_fetch(run_id, source.id, source.url, "failure", str(error))
    database.finish_run(run_id, "success" if not summary.failed else "partial_failure", summary)
    return summary
