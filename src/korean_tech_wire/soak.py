from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from time import sleep as default_sleep

from .config import Settings
from .discovery import RunSummary, run_collectors
from .models import Source
from .scheduling import due_sources
from .storage import Database


def default_now() -> datetime:
    return datetime.now(timezone.utc)


def run_soak(
    sources: Sequence[Source], settings: Settings, database: Database, *, cycles: int,
    interval_seconds: int, source_ids: Sequence[str] = (), if_due: bool = False, sleep: Callable[[float], None] = default_sleep,
    now: Callable[[], datetime] = default_now,
) -> list[RunSummary]:
    """Run normal collectors in resumable cycles; SQLite health history is the resume state.

    With if_due, each selected source's own persisted history decides whether *that*
    source runs this cycle -- a source stuck failing never keeps a healthy sibling from
    running, and never makes itself falsely due either (see scheduling.py for the backoff
    policy that keeps a persistently failing source from being retried at full frequency).
    """
    if cycles < 1:
        raise ValueError("cycles must be at least 1")
    if interval_seconds < 0:
        raise ValueError("interval_seconds cannot be negative")
    selected = list(source_ids) or [source.id for source in sources if source.enabled]
    known = {source.id for source in sources}
    unknown = set(selected) - known
    if unknown:
        raise ValueError(f"unknown source id(s): {', '.join(sorted(unknown))}")
    summaries: list[RunSummary] = []
    for cycle in range(cycles):
        if if_due:
            states = {source_id: database.source_due_state(source_id) for source_id in selected}
            due = due_sources(states, interval_seconds, now())
        else:
            due = selected
        for source_id in due:
            summaries.append(run_collectors(list(sources), settings, database, source_id=source_id))
        if cycle + 1 < cycles:
            sleep(interval_seconds)
    return summaries
