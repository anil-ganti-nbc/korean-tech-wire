from dataclasses import dataclass, field


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

