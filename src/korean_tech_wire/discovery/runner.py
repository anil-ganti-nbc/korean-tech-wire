from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from time import perf_counter
from urllib.request import Request, urlopen

from ..collectors import COLLECTORS, CollectorError
from ..config import Settings
from ..extraction import extract_text
from ..extraction import extract_metadata
from ..editorial import classify
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
    attempted: int = 0; succeeded: int = 0; failed: int = 0; discovered: int = 0; accepted: int = 0; rejected: int = 0; new: int = 0; existing: int = 0; timestamped: int = 0; extraction_failed: int = 0
    errors: list[str] = field(default_factory=list)


def run_collectors(sources: list[Source], settings: Settings, database: Database, source_id: str | None = None, production_only: bool = False) -> RunSummary:
    database.sync_sources(sources)
    run_id = database.start_run(source_id)
    summary = RunSummary()
    for source in sources:
        if not source.enabled or (source_id and source.id != source_id) or (production_only and source.status != "PRODUCTION"): continue
        summary.attempted += 1
        started = perf_counter(); references = accepted_count = rejected_count = new = existing = timestamped = extraction_failures = 0
        try:
            collector = COLLECTORS[source.collector](source, HttpFetcher(settings))
            articles = collector.discover(); references = len(articles); summary.discovered += references
            if references == 0 and database.baseline_has_content(source.id):
                raise CollectorError("unexpected zero references after populated baseline")
            database.record_fetch(run_id, source.id, source.url, "success")
            # Reject known low-value index cards before fetching a detail page.
            candidates = []
            for article in articles:
                decision = classify(source, article)
                if decision.accepted: candidates.append(article)
                else: summary.rejected += 1; rejected_count += 1
            # Discovery remains cheap: fetch bodies only for unseen viable candidates.
            hydrated = []
            for article in candidates:
                if (database.has_article(article.source_id, article.canonical_url)
                    and not database.needs_enrichment(article.source_id, article.canonical_url)) or article.body_original:
                    hydrated.append(replace(article, published_at=database.stored_published_at(article.source_id, article.canonical_url) or article.published_at)); continue
                try:
                    html = HttpFetcher(settings).get(article.source_url)
                    database.record_fetch(run_id, source.id, article.source_url, "success")
                    details = extract_metadata(html)
                    hydrated.append(replace(article, body_original=extract_text(html), published_at=details.published_at or article.published_at))
                except OSError as error:
                    summary.extraction_failed += 1; extraction_failures += 1
                    database.record_fetch(run_id, source.id, article.source_url, "failure", str(error))
                    hydrated.append(article)
            accepted = hydrated
            accepted_count = len(accepted); summary.accepted += accepted_count
            timestamped = sum(article.published_at is not None for article in accepted); summary.timestamped += timestamped
            new, existing = database.persist_articles(accepted); summary.new += new; summary.existing += existing; summary.succeeded += 1
            database.record_source_health(run_id, source.id, duration_ms=int((perf_counter()-started)*1000), success=True, references=references, accepted=accepted_count, rejected=rejected_count, new=new, existing=existing, extraction_failures=extraction_failures, timestamped=timestamped)
        except (CollectorError, OSError, KeyError, ValueError) as error:
            summary.failed += 1; message = f"{source.id}: {type(error).__name__}: {error}"; summary.errors.append(message)
            database.record_error(run_id, source.id, type(error).__name__, str(error))
            database.record_fetch(run_id, source.id, source.url, "failure", str(error))
            database.record_source_health(run_id, source.id, duration_ms=int((perf_counter()-started)*1000), success=False, references=references, accepted=accepted_count, rejected=rejected_count, new=new, existing=existing, extraction_failures=extraction_failures, timestamped=timestamped, note=str(error))
    database.finish_run(run_id, "success" if not summary.failed else "partial_failure", summary)
    return summary
