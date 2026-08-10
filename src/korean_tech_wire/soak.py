from __future__ import annotations

from collections.abc import Callable, Sequence
from time import sleep as default_sleep

from .config import Settings
from .discovery import RunSummary, run_collectors
from .models import Source
from .storage import Database


def run_soak(
    sources: Sequence[Source], settings: Settings, database: Database, *, cycles: int,
    interval_seconds: int, source_ids: Sequence[str] = (), sleep: Callable[[float], None] = default_sleep,
) -> list[RunSummary]:
    """Run normal collectors in resumable cycles; SQLite health history is the resume state."""
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
        for source_id in selected:
            summaries.append(run_collectors(list(sources), settings, database, source_id=source_id))
        if cycle + 1 < cycles:
            sleep(interval_seconds)
    return summaries
