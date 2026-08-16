"""Non-secret provenance for local field-test surfaces."""
from __future__ import annotations

import os


def revision() -> str:
    value = os.environ.get("KOREAN_TECH_WIRE_SOURCE_REVISION", "").strip()
    return value[:12] if value else "local development build"
