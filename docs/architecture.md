# Current architecture

Korean Tech Wire is a standalone Python package rooted here. It does not import, configure, share a database with, or schedule alongside any other Wire.

## Implemented Stage 1 path

`collector -> discovered reference -> SQLite identity check -> fetch unseen article -> basic extraction -> SQLite`

Collectors emit `DiscoveredArticle`, preserving the Korean title exactly. Discovery is index-only; the runner fetches an article body only when its `(source_id, canonical_url)` is not already persisted. A collector error is caught per source, stored in `run_errors`, and turns the run into `partial_failure` without rolling back another source.

SQLite migrations are explicit in `storage/database.py`. The initial schema includes `schema_migrations`, `sources`, `articles`, `runs`, `run_errors`, and `fetch_attempts` is intentionally deferred until per-request observability is introduced. Articles retain source/canonical URLs, source article ID where present, normalised title, original body, publication/discovery/first-seen/last-seen times, hash, and raw metadata. Records are never deleted because they disappear from a source index.

Times are persisted as ISO-8601 UTC. Korean publication dates are interpreted as `Asia/Seoul` by source-specific parsing when supplied; UI conversion to IST is deferred.

## Boundaries deliberately left small

- `extraction` holds body extraction and is independent of discovery.
- `language.Translator` is a vendor-neutral protocol. Korean source text is never overwritten.
- `editorial` is reserved for filtering/scoring; collection does not alert or score.
- No story clustering, DART integration, entity aliases, English propagation checks, dashboards, webhooks, or Discord integration exist yet.

The current HTML text extraction is intentionally conservative and generic. Site-specific article extractors should be added only after fixture-backed validation.
