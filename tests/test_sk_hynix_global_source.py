"""sk_hynix_newsroom_global is a NEW source, not a rescue of the Korean one.

news.skhynix.co.kr answers 403 to the deployment host's egress at its AWS
load balancer, so the Korean source cannot collect from production. SK hynix
also publishes an English edition on a separate first-party host that IS
reachable. That edition is registered here as an independent source.

The whole risk of adding it is that it quietly becomes an alias for the
blocked Korean source -- inheriting its history, its identity space, or its
production standing. These tests pin that it does not, and that a first
sighting is never mistaken for novelty.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from korean_tech_wire.config import load_sources
from korean_tech_wire.discovery.runner import RunSummary
from korean_tech_wire.models import DiscoveredArticle
from korean_tech_wire.storage import Database

GLOBAL_ID = "sk_hynix_newsroom_global"
KOREAN_ID = "sk_hynix_newsroom"


def _sources():
    return {s.id: s for s in load_sources(Path("config/sources.yaml"))}


# -- registration -------------------------------------------------------------


def test_the_global_source_is_registered_as_its_own_identity():
    sources = _sources()
    assert GLOBAL_ID in sources
    assert sources[GLOBAL_ID].id != KOREAN_ID


def test_it_points_at_the_first_party_english_feed():
    src = _sources()[GLOBAL_ID]
    assert src.url == "https://news.skhynix.com/en/feed/"
    # First-party SK hynix host, not an aggregator or a mirror.
    assert src.url.startswith("https://news.skhynix.com/")
    assert src.collector == "rss"


def test_it_is_experimental_and_therefore_out_of_production_runs():
    """It must earn promotion on its own evidence, like any new source."""
    assert _sources()[GLOBAL_ID].status == "EXPERIMENTAL"


def test_the_blocked_korean_source_is_left_exactly_as_it_was():
    """This mission must not modify, disable or repoint the Korean source."""
    korean = _sources()[KOREAN_ID]
    assert korean.status == "PRODUCTION"
    assert korean.enabled is True
    assert korean.url == "https://news.skhynix.co.kr/feed/"


def test_the_two_editions_are_distinct_sources_on_distinct_hosts():
    sources = _sources()
    assert sources[GLOBAL_ID].url != sources[KOREAN_ID].url
    assert "skhynix.co.kr" not in sources[GLOBAL_ID].url
    assert "skhynix.com" not in sources[KOREAN_ID].url


# -- identity separation ------------------------------------------------------


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "ktw.db")
    db.migrate()
    return db


def _article(source_id: str, url: str, title: str) -> DiscoveredArticle:
    now = datetime.now(timezone.utc)
    return DiscoveredArticle(source_id, url, url, title, now, now, body_original=title)


def test_the_global_source_cannot_inherit_korean_articles_as_history(tmp_path):
    """The exact failure this design must prevent: the new source treating the
    blocked source's stored articles as its own already-seen set."""
    db = _db(tmp_path)
    db.persist_articles([
        _article(KOREAN_ID, "https://news.skhynix.co.kr/a/", "한국어 기사"),
    ])

    # Nothing the Korean source stored is visible to the global source.
    assert db.has_article(KOREAN_ID, "https://news.skhynix.co.kr/a/") is True
    assert db.has_article(GLOBAL_ID, "https://news.skhynix.co.kr/a/") is False


def test_the_same_url_under_two_source_ids_is_two_distinct_records(tmp_path):
    """Identity is (source_id, canonical_url). Even an identical URL does not
    collide across sources, so no alias can form by accident."""
    db = _db(tmp_path)
    url = "https://news.skhynix.com/en/story/"
    new, existing = db.persist_articles([
        _article(KOREAN_ID, url, "story"),
        _article(GLOBAL_ID, url, "story"),
    ])
    assert (new, existing) == (2, 0)


def test_repeat_persist_is_idempotent_within_the_global_source(tmp_path):
    db = _db(tmp_path)
    items = [
        _article(GLOBAL_ID, "https://news.skhynix.com/en/one/", "One"),
        _article(GLOBAL_ID, "https://news.skhynix.com/en/two/", "Two"),
    ]
    assert db.persist_articles(items) == (2, 0)
    # Immediate resight: everything already seen, nothing new.
    assert db.persist_articles(items) == (0, 2)


# -- FIRST_SEEN != NOVELTY ----------------------------------------------------


def test_a_fresh_source_has_no_baseline_until_it_records_one(tmp_path):
    """baseline_has_content is source-scoped, so the Korean source's populated
    baseline never makes the global source look already-established."""
    db = _db(tmp_path)
    run_id = db.start_run(KOREAN_ID)
    db.record_source_health(run_id, KOREAN_ID, duration_ms=1, success=True,
                            references=10, accepted=10, rejected=0, new=10,
                            existing=0, extraction_failures=0, timestamped=10)
    db.finish_run(run_id, "success", RunSummary(attempted=1, succeeded=1))

    assert db.baseline_has_content(KOREAN_ID) is True
    assert db.baseline_has_content(GLOBAL_ID) is False


def test_first_run_is_a_baseline_and_the_resight_produces_no_novelty(tmp_path):
    """FIRST SEEN IS NOT NOVELTY. Run one persists a baseline; an immediate
    second pass over the same feed contents must add nothing."""
    db = _db(tmp_path)
    feed = [
        _article(GLOBAL_ID, f"https://news.skhynix.com/en/item-{i}/", f"Item {i}")
        for i in range(10)
    ]

    first_new, first_existing = db.persist_articles(feed)
    assert (first_new, first_existing) == (10, 0), "baseline establishment"

    second_new, second_existing = db.persist_articles(feed)
    assert second_new == 0, "an immediate resight must produce zero novelty"
    assert second_existing == 10


# -- language / editorial separation ------------------------------------------


def test_english_titles_are_stored_as_published(tmp_path):
    """title_original means 'as the publisher wrote it'. The English edition
    stores English; nothing transliterates or translates it on the way in."""
    db = _db(tmp_path)
    title = "[AI Ecosystem] The real bottleneck: Data, not compute"
    db.persist_articles([_article(GLOBAL_ID, "https://news.skhynix.com/en/x/", title)])
    with db.connect() as con:
        stored = con.execute(
            "SELECT title_original, translation_status FROM articles WHERE source_id=?",
            (GLOBAL_ID,),
        ).fetchone()
    assert stored[0] == title
    assert stored[1] == "untranslated"


def test_real_stories_are_not_subject_to_a_topic_filter():
    """Its only rule is the contentless-sibling one below. A first-party
    corporate newsroom is otherwise accepted wholesale, exactly as the Korean
    SK hynix source is -- deliberate parity, not an omission. No keyword or
    beat filter is applied to either edition."""
    from korean_tech_wire.editorial.filtering import classify

    sources = _sources()
    art = _article(GLOBAL_ID, "https://news.skhynix.com/en/x/", "Anything at all")
    assert classify(sources[GLOBAL_ID], art).accepted is True

    art_kr = _article(KOREAN_ID, "https://news.skhynix.co.kr/x/", "Anything at all")
    assert classify(sources[KOREAN_ID], art_kr).accepted is True


def test_ktw_has_no_delivery_mechanism_so_this_source_notifies_nothing():
    """'Zero notifications' is structural here, not a setting that could drift:
    the package contains no delivery path at all."""
    import pathlib

    src = pathlib.Path("src/korean_tech_wire")
    offenders = []
    for path in src.rglob("*.py"):
        text = path.read_text(encoding="utf-8").casefold()
        if any(t in text for t in ("discord", "webhook", "slack")):
            offenders.append(path.name)
    assert not offenders, f"unexpected delivery path: {offenders}"


# -- contentless duplicate rejection ------------------------------------------


def _rss_article(url: str, title: str, body):
    now = datetime.now(timezone.utc)
    return DiscoveredArticle(GLOBAL_ID, url, url, title, now, now, body_original=body)


def test_contentless_sibling_posts_are_rejected():
    """SK hynix emits sibling posts carrying the parent's title, their own post
    id and URL, and neither content:encoded nor description. On 2026-09-04 that
    was 8 of 10 feed items; accepting them reports ten new stories on a day two
    broke."""
    from korean_tech_wire.editorial.filtering import classify

    src = _sources()[GLOBAL_ID]
    for body in (None, "", "   ", "\n\t "):
        art = _rss_article(
            "https://news.skhynix.com/en/ai-ecosystem-series-ep2-3/",
            "[AI Ecosystem] The real bottleneck: Data, not compute",
            body,
        )
        decision = classify(src, art)
        assert decision.accepted is False
        assert decision.reason == "contentless_duplicate_post"


def test_the_real_article_with_a_body_is_accepted():
    from korean_tech_wire.editorial.filtering import classify

    src = _sources()[GLOBAL_ID]
    art = _rss_article(
        "https://news.skhynix.com/en/ai-ecosystem-series-ep2/",
        "[AI Ecosystem] The real bottleneck: Data, not compute",
        "<p>" + ("real article body " * 200) + "</p>",
    )
    assert classify(src, art).accepted is True


def test_the_rule_is_scoped_to_the_global_source_only():
    """The blocked Korean source must not gain a new filter from this mission."""
    from korean_tech_wire.editorial.filtering import classify

    sources = _sources()
    korean = DiscoveredArticle(
        KOREAN_ID, "https://news.skhynix.co.kr/x/", "https://news.skhynix.co.kr/x/",
        "제목", datetime.now(timezone.utc), datetime.now(timezone.utc),
        body_original=None,
    )
    # Same empty body, different source: still accepted, behaviour unchanged.
    assert classify(sources[KOREAN_ID], korean).accepted is True


def test_rejection_is_visible_as_a_rejection_not_a_silent_drop():
    """A rejected item must be counted and reasoned, never vanish: the run
    surfaces discovered vs accepted so the gap is inspectable."""
    from korean_tech_wire.editorial.filtering import classify

    src = _sources()[GLOBAL_ID]
    decision = classify(src, _rss_article("https://news.skhynix.com/en/e-1/", "T", None))
    assert decision.accepted is False
    assert decision.reason, "a rejection must carry a reason"
