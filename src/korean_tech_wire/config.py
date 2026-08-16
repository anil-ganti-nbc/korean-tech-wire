from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import Source


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    request_timeout_seconds: int
    user_agent: str


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_settings(config_path: Path) -> Settings:
    data = _load_yaml(config_path)
    configured_database = Path(data.get("database_path", "var/korean_tech_wire.db"))
    # The native field-test launcher opts into a dedicated application-data
    # root. Existing CLI/server runs keep their configured (normally
    # CWD-relative) SQLite location unchanged when the override is absent.
    data_dir = os.environ.get("KOREAN_TECH_WIRE_DATA_DIR")
    if data_dir and configured_database == Path("var/korean_tech_wire.db"):
        root = Path(data_dir).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        configured_database = root / "korean_tech_wire.db"
    return Settings(
        database_path=configured_database,
        request_timeout_seconds=int(data.get("request_timeout_seconds", 20)),
        user_agent=str(data.get("user_agent", "KoreanTechWire/0.1")),
    )


def load_sources(path: Path) -> list[Source]:
    entries = _load_yaml(path).get("sources", {})
    if not isinstance(entries, dict):
        raise ValueError("sources must be a mapping")
    return [
        Source(
            id=source_id, name=item["name"], status=item["status"],
            enabled=bool(item.get("enabled", False)), collector=item["collector"],
            url=item["url"], timezone=item.get("timezone", "Asia/Seoul"),
            beats=tuple(item.get("beats", [])), options=dict(item.get("options", {})),
        )
        for source_id, item in entries.items()
    ]
