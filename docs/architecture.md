# Current architecture

Korean Tech Wire is a standalone Python package rooted here. It does not import, configure, share a database with, or schedule alongside any other Wire.

## Implemented Stage 1 path

`collector -> discovered reference -> editorial classification -> SQLite identity check -> fetch unseen/enrichment-needed article -> extraction -> SQLite`

Collectors emit `DiscoveredArticle`, preserving the Korean title exactly. Discovery is index-only; the runner fetches an article body and source metadata only when its `(source_id, canonical_url)` is new or lacks required enrichment such as publication time. A collector error is caught per source, stored in `run_errors`, and turns the run into `partial_failure` without rolling back another source.

SQLite migrations are explicit in `storage/database.py`. The initial schema includes `schema_migrations`, `sources`, `articles`, `runs`, `run_errors`, and `fetch_attempts` is intentionally deferred until per-request observability is introduced. Articles retain source/canonical URLs, source article ID where present, normalised title, original body, publication/discovery/first-seen/last-seen times, hash, and raw metadata. Records are never deleted because they disappear from a source index.

Times are persisted as ISO-8601 UTC. Korean publication dates are interpreted as `Asia/Seoul` by source-specific parsing when supplied; UI conversion to IST is deferred.

## Boundaries deliberately left small

- `extraction` holds body extraction and is independent of discovery.
- `language.Translator` is a vendor-neutral protocol. Korean source text is never overwritten.
- `editorial` is reserved for filtering/scoring; collection does not alert or score.
- No story clustering, DART integration, entity aliases, English propagation checks, dashboards, webhooks, or Discord integration exist yet.

The current HTML text extraction is intentionally conservative and generic. `extraction.metadata` independently reads Open Graph `article:published_time` and JSON-LD `NewsArticle.datePublished`; it does not infer a publication time from discovery.

## HTML collector validation rules

Samsung discovery accepts only cards in the homepage's `li.article_lists` or `li.article_lists_color` containers. Those cards contain an article URL plus separate `article_title`, `article_category`, and `article_data` fields. Navigation, RSS, article-more controls, category/search links and media albums are outside those containers and cannot enter discovery. Exact timestamps come from the fetched detail page's `NewsArticle` JSON-LD.

Samsung timestamp audit (2026-08-10): 23 active records use authoritative `NewsArticle` timestamps. Thirteen atypical cards have no usable article time: one `미래동행` page has a blank `NewsArticle.datePublished` alongside a `VideoObject` date, one overseas-video page exposes only `VideoObject.datePublished`, and eleven overseas-news pages expose no detail-page publication marker. Video-object dates and index-only dates are deliberately not converted into article timestamps. This is a source limitation, not a parser fallback opportunity.

The Elec discovery polls only its public Semiconductors (`S1N2`), Displays (`S1N4`), Batteries (`S1N9`) and Finished Products (`S1N7`) section indexes, rather than the broad homepage. In live validation, those query URLs still exposed some broad-index material, so the separate editorial classifier applies a narrow hardware/manufacturing title vocabulary as a defensive second gate. It rejects obvious delivery, lifestyle, generic software and non-technology stories without being hidden inside HTML selectors. The Elec detail pages provide `article:published_time` and JSON-LD timestamps with a `+09:00` Korean offset.

## Ingestion-pattern rationale

Stage 1 intentionally validates reliable multi-source ingestion and source-specific extraction, not arbitrary protocol diversity. HTML discovery/extraction (with two independently structured publishers) and RSS/XML discovery together exercise the collector contract, run isolation, persistence, timestamps and deduplication. A third mechanism should be added only when a high-value API, sitemap, regulatory, or certification source warrants it; it is not a Stage 1 prerequisite.

The initial Samsung run pre-dated the structural rule. The explicit maintenance command marks all its old rows `legacy_unverified`, removes only URL-proven noise (`/medialibrary/`, RSS, and known index controls), and preserves ambiguous historical hubs rather than guessing. The equivalent The Elec maintenance command quarantines the broad-index history rather than deleting it. `articles latest` excludes unverified rows.
