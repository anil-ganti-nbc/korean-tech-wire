from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Protocol

from ..models import DiscoveredArticle, Source


class Fetcher(Protocol):
    def get(self, url: str) -> str: ...


class CollectorError(RuntimeError):
    pass


class Collector(ABC):
    def __init__(self, source: Source, fetcher: Fetcher):
        self.source, self.fetcher = source, fetcher

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    @abstractmethod
    def discover(self) -> list[DiscoveredArticle]: ...
