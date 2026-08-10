from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Source:
    id: str
    name: str
    status: str
    enabled: bool
    collector: str
    url: str
    timezone: str = "Asia/Seoul"
    beats: tuple[str, ...] = field(default_factory=tuple)
    options: dict[str, Any] = field(default_factory=dict)
