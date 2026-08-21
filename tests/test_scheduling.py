from datetime import datetime, timedelta, timezone

import pytest

from korean_tech_wire.collectors import COLLECTORS
from korean_tech_wire.collectors.base import Collector, CollectorError
from korean_tech_wire.config import Settings
from korean_tech_wire.models import DiscoveredArticle, Source
from korean_tech_wire.scheduling import (
    BACKOFF_CEILING_MULTIPLIER,
    SourceDueState,
    TRANSIENT_FAILURE_THRESHOLD,
    is_due,
    retry_interval_seconds,
)
from korean_tech_wire.soak import run_soak
from korean_tech_wire.storage import Database

EPOCH = datetime(2026, 8, 10, 0, 0, 0, tzinfo=timezone.utc)
BASE_INTERVAL = 7200  # 2 hours


class _Clock:
    """Deterministic, manually-advanced clock -- tests never sleep in real time.

    Shared between the Database (so persisted `attempted_at` values follow it) and
    run_soak's due-calculation, so both sides of the scheduling decision agree on "now".
    """

    def __init__(self, start: datetime):
        self.current = start

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


class _FakeCollector(Collector):
    def discover(self):
        now = datetime.now(timezone.utc)
        return [DiscoveredArticle(self.source.id, f"https://example.test/{self.source.id}", f"https://example.test/{self.source.id}", "테스트 기사", now, now, body_original="fixture body")]


class _FailingCollector(Collector):
    def discover(self):
        raise CollectorError("simulated persistent failure")


def _make_source(source_id: str, *, fails: bool, status: str = "PRODUCTION") -> Source:
    key = f"fake_{'fail' if fails else 'ok'}_{source_id}_{id(fails)}"
    COLLECTORS[key] = _FailingCollector if fails else _FakeCollector
    return Source(source_id, source_id, status, True, key, "https://example.test/")


@pytest.fixture()
def settings(tmp_path):
    return Settings(tmp_path / "wire.db", 1, "test")


def _db(tmp_path, clock: _Clock) -> Database:
    database = Database(tmp_path / "wire.db", clock=clock)
    database.migrate()
    return database


# --- pure scheduling-function unit tests -----------------------------------------


def test_never_attempted_source_is_immediately_due():
    state = SourceDueState(last_attempt_at=None, last_success_at=None, consecutive_failures=0)
    assert is_due(state, BASE_INTERVAL, EPOCH) is True


def test_recent_success_is_not_due_before_cadence_elapses():
    state = SourceDueState(last_attempt_at=EPOCH, last_success_at=EPOCH, consecutive_failures=0)
    assert is_due(state, BASE_INTERVAL, EPOCH + timedelta(minutes=30)) is False
    assert is_due(state, BASE_INTERVAL, EPOCH + timedelta(hours=2)) is True


def test_first_failures_retry_at_normal_cadence_transient():
    for n in range(1, TRANSIENT_FAILURE_THRESHOLD + 1):
        assert retry_interval_seconds(BASE_INTERVAL, n) == BASE_INTERVAL


def test_persistent_failures_back_off_up_to_a_ceiling():
    intervals = [retry_interval_seconds(BASE_INTERVAL, n) for n in range(TRANSIENT_FAILURE_THRESHOLD, TRANSIENT_FAILURE_THRESHOLD + 8)]
    assert intervals == sorted(intervals)  # never decreases
    assert max(intervals) == BASE_INTERVAL * BACKOFF_CEILING_MULTIPLIER
    assert intervals[-1] == intervals[-2]  # reached and stayed at the ceiling


def test_failed_attempt_does_not_count_as_successful_cadence_reset():
    within_threshold = SourceDueState(last_attempt_at=EPOCH, last_success_at=None, consecutive_failures=TRANSIENT_FAILURE_THRESHOLD)
    assert is_due(within_threshold, BASE_INTERVAL, EPOCH + timedelta(hours=2)) is True  # still transient, normal cadence
    heavy_state = SourceDueState(last_attempt_at=EPOCH, last_success_at=None, consecutive_failures=TRANSIENT_FAILURE_THRESHOLD + 1)
    assert is_due(heavy_state, BASE_INTERVAL, EPOCH + timedelta(hours=2)) is False  # backed off past normal cadence


# --- integration tests through run_soak / Database --------------------------------


def test_all_healthy_and_recently_run_nothing_fetched(tmp_path, settings):
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    a, b = _make_source("a", fails=False), _make_source("b", fails=False)
    run_soak([a, b], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, now=clock)
    clock.advance(60)  # 1 minute later, well inside the 2h cadence
    summaries = run_soak([a, b], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
    assert summaries == []
    assert database.health_summary(["a"])[0]["runs"] == 1
    assert database.health_summary(["b"])[0]["runs"] == 1


def test_one_source_due_others_fresh_only_that_source_runs(tmp_path, settings):
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    a, b = _make_source("a", fails=False), _make_source("b", fails=False)
    run_soak([a], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, now=clock)  # a's baseline at t=0
    clock.advance(3600)
    run_soak([b], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, now=clock)  # b's baseline at t=1h
    clock.advance(3700)  # t=2h1m40s: a is 2h1m40s since success (due); b is 1h1m40s since success (not due)
    summaries = run_soak([a, b], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
    assert len(summaries) == 1
    assert database.health_summary(["a"])[0]["runs"] == 2
    assert database.health_summary(["b"])[0]["runs"] == 1


def test_one_source_failing_does_not_disturb_healthy_siblings(tmp_path, settings):
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    healthy, failing = _make_source("healthy", fails=False), _make_source("failing", fails=True)
    run_soak([healthy, failing], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, now=clock)
    assert database.health_summary(["failing"])[0]["successes"] == 0
    clock.advance(60)  # both attempted moments ago; neither is due yet
    summaries = run_soak([healthy, failing], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
    assert summaries == []
    assert database.health_summary(["healthy"])[0]["runs"] == 1
    assert database.health_summary(["failing"])[0]["runs"] == 1


def test_one_failing_source_does_not_make_the_fleet_globally_due(tmp_path, settings):
    """Regression test for the Stage 4 defect: a source that never succeeds must not
    keep forcing every other selected source to be considered due."""
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    healthy, failing = _make_source("healthy", fails=False), _make_source("failing", fails=True)
    run_soak([healthy, failing], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, now=clock)
    for _ in range(10):  # simulate many 30-minute scheduler wakeups
        clock.advance(1800)
        run_soak([healthy, failing], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
    # healthy's own 2h cadence bounds its run count over 10*30min=5h; it must not
    # have run every 30 minutes the way the Stage 4 defect made the whole fleet do.
    assert database.health_summary(["healthy"])[0]["runs"] <= 4


def test_failed_attempt_does_not_count_as_successful_collection_end_to_end(tmp_path, settings):
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    failing = _make_source("f", fails=True)
    run_soak([failing], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, now=clock)
    summary = database.health_summary(["f"])[0]
    assert summary["successes"] == 0
    assert summary["last_success"] is None


def test_persistent_failure_enters_backoff(tmp_path, settings):
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    failing = _make_source("f", fails=True)
    for _ in range(TRANSIENT_FAILURE_THRESHOLD + 3):
        run_soak([failing], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
        clock.advance(BASE_INTERVAL + 1)  # always past the *normal* cadence
    state = database.source_due_state("f")
    assert state.consecutive_failures > TRANSIENT_FAILURE_THRESHOLD
    # now that it's backed off, a bare normal-cadence wait is no longer enough
    assert is_due(state, BASE_INTERVAL, state.last_attempt_at + timedelta(seconds=BASE_INTERVAL + 1)) is False


def test_backoff_survives_process_restart_via_persisted_history(tmp_path, settings):
    db_path = tmp_path / "wire.db"
    clock = _Clock(EPOCH)
    first_process_db = Database(db_path, clock=clock)
    first_process_db.migrate()
    failing = _make_source("f", fails=True)
    for _ in range(TRANSIENT_FAILURE_THRESHOLD + 2):
        run_soak([failing], settings, first_process_db, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
        clock.advance(BASE_INTERVAL + 1)
    expected_failures = first_process_db.source_due_state("f").consecutive_failures
    # simulate a service restart: a brand new Database object, no in-memory scheduler state
    second_process_db = Database(db_path, clock=clock)
    restarted_state = second_process_db.source_due_state("f")
    assert restarted_state.consecutive_failures == expected_failures
    assert restarted_state.consecutive_failures > TRANSIENT_FAILURE_THRESHOLD
    # a bare normal-cadence wait since the last real attempt is not enough to be due again
    just_past_normal_cadence = restarted_state.last_attempt_at + timedelta(seconds=BASE_INTERVAL + 1)
    assert is_due(restarted_state, BASE_INTERVAL, just_past_normal_cadence) is False  # not hammering right after "restart"


def test_successful_recovery_resets_backoff(tmp_path, settings):
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    source_id = "f"
    fail_key, ok_key = "fake_fail_recover", "fake_ok_recover"
    COLLECTORS[fail_key] = _FailingCollector
    COLLECTORS[ok_key] = _FakeCollector
    failing_source = Source(source_id, source_id, "PRODUCTION", True, fail_key, "https://example.test/")
    for _ in range(TRANSIENT_FAILURE_THRESHOLD + 2):
        run_soak([failing_source], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
        clock.advance(BASE_INTERVAL + 1)
    assert database.source_due_state(source_id).consecutive_failures > 0
    recovered_source = Source(source_id, source_id, "PRODUCTION", True, ok_key, "https://example.test/")
    run_soak([recovered_source], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
    state = database.source_due_state(source_id)
    assert state.consecutive_failures == 0
    assert state.last_success_at == clock.current
    clock.advance(60)
    assert is_due(database.source_due_state(source_id), BASE_INTERVAL, clock.current) is False  # back to normal cadence


def test_multiple_independently_due_sources_run_together(tmp_path, settings):
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    a, b, c = _make_source("a", fails=False), _make_source("b", fails=False), _make_source("c", fails=False)
    run_soak([a, b, c], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, now=clock)
    clock.advance(BASE_INTERVAL + 1)  # all three independently due again
    summaries = run_soak([a, b, c], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, if_due=True, now=clock)
    assert len(summaries) == 3
    for source_id in ("a", "b", "c"):
        assert database.health_summary([source_id])[0]["runs"] == 2


def test_production_scope_semantics_unaffected_by_due_gating(tmp_path, settings):
    clock = _Clock(EPOCH)
    database = _db(tmp_path, clock)
    prod = _make_source("prod", fails=False, status="PRODUCTION")
    exp = _make_source("exp", fails=False, status="EXPERIMENTAL")
    # a due-aware soak explicitly scoped to production ids only ignores the experimental source entirely
    summaries = run_soak([prod, exp], settings, database, cycles=1, interval_seconds=BASE_INTERVAL, source_ids=[prod.id], if_due=True, now=clock)
    assert len(summaries) == 1
    assert database.status()["runs"] == 1  # exp never attempted
