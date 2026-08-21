from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

# The documented normal soak cadence (matches the `soak --interval-seconds` default and
# the systemd service's cadence); used where a display needs a cadence but isn't itself
# driving a live soak run with its own --interval-seconds.
DEFAULT_INTERVAL_SECONDS = 7200

# A source's first `TRANSIENT_FAILURE_THRESHOLD` consecutive failures retry at the
# normal cadence: a blip shouldn't change scheduling. Beyond that, the retry
# interval doubles per additional failure, capped at `BACKOFF_CEILING_MULTIPLIER`
# times the normal cadence, so a persistent block (like a host-level access block)
# degrades to a modest, bounded polling rate instead of retrying forever at full speed.
TRANSIENT_FAILURE_THRESHOLD = 2
BACKOFF_CEILING_MULTIPLIER = 12


@dataclass(frozen=True, slots=True)
class SourceDueState:
    """Facts derived from persisted run history for one source; no wall-clock reads."""

    last_attempt_at: datetime | None
    last_success_at: datetime | None
    consecutive_failures: int


def retry_interval_seconds(base_interval_seconds: int, consecutive_failures: int) -> int:
    """Seconds to wait after the most recent attempt before the next retry is due."""
    if consecutive_failures <= TRANSIENT_FAILURE_THRESHOLD:
        return base_interval_seconds
    multiplier = min(2 ** (consecutive_failures - TRANSIENT_FAILURE_THRESHOLD), BACKOFF_CEILING_MULTIPLIER)
    return base_interval_seconds * multiplier


def is_due(state: SourceDueState, base_interval_seconds: int, now: datetime) -> bool:
    """Whether a single source's own cadence has elapsed. A failure never resets it early."""
    if state.last_attempt_at is None:
        return True
    if state.consecutive_failures == 0:
        anchor = state.last_success_at or state.last_attempt_at
        return now >= _add_seconds(anchor, base_interval_seconds)
    interval = retry_interval_seconds(base_interval_seconds, state.consecutive_failures)
    return now >= _add_seconds(state.last_attempt_at, interval)


def describe(state: SourceDueState, base_interval_seconds: int) -> str:
    """Human-readable scheduling state for operator-facing health output."""
    if state.consecutive_failures == 0:
        return "normal"
    if state.consecutive_failures <= TRANSIENT_FAILURE_THRESHOLD:
        return f"transient_retry(failures={state.consecutive_failures})"
    interval = retry_interval_seconds(base_interval_seconds, state.consecutive_failures)
    at_ceiling = interval == base_interval_seconds * BACKOFF_CEILING_MULTIPLIER
    return f"backoff(failures={state.consecutive_failures}, retry_interval_s={interval}{', at_ceiling' if at_ceiling else ''})"


def due_sources(states: dict[str, SourceDueState], base_interval_seconds: int, now: datetime) -> list[str]:
    """Selected source ids (in the given order) whose own cadence has elapsed."""
    return [source_id for source_id, state in states.items() if is_due(state, base_interval_seconds, now)]


def _add_seconds(value: datetime, seconds: int) -> datetime:
    return value + timedelta(seconds=seconds)
