# Stage 4.1 reliability repair — 2026-08-19

Stage 4 closeout (`379d3c2`) exposed two production defects instead of a clean baseline. This is the record of diagnosing and repairing both.

## Defect 1 — soak due-gating

### Root cause

`run_soak`'s `if_due` check treated the whole selected fleet as a single due/not-due unit: it skipped a cycle only when *every* selected source had a recent successful run. Because SK hynix Korea stopped succeeding entirely on 2026-08-10 (see below), that condition could never be satisfied again, so the fleet was permanently "due." The 30-minute systemd timer then ran a full 5-source collection cycle on every wake instead of the documented 2-hour cadence — confirmed during Stage 4 by measuring `source_run_health.attempted_at` gaps (median ≈1800s, not 7200s) and the systemd journal. Roughly 4x the intended request rate, sustained for over a week.

### Repair architecture

Due-ness is now evaluated **per source**, derived entirely from persisted `source_run_health` history — no new in-memory scheduler state, no schema change:

- `Database.source_due_state(source_id)` (`src/korean_tech_wire/storage/database.py`) reads the most recent rows for a source and returns `SourceDueState(last_attempt_at, last_success_at, consecutive_failures)` — `consecutive_failures` is the count of failed rows since the most recent success (or since the beginning of history, if none).
- `src/korean_tech_wire/scheduling.py` is a small, pure module with no I/O: `is_due(state, base_interval_seconds, now)` decides one source's due-ness, and `due_sources(states, base_interval_seconds, now)` filters a fleet down to the subset that's actually due. Everything takes `now` as an explicit parameter — nothing reads the wall clock internally — so it's directly unit-testable with fake time.
- `run_soak` (`src/korean_tech_wire/soak.py`) now computes `database.source_due_state(...)` per selected source, on each cycle, and only invokes `run_collectors` for the sources that come back due. A source that never succeeds can no longer hold every other source hostage, and a source's own failure history can no longer make it *falsely* due either.
- The systemd timer/service (`deploy/systemd/korean-tech-wire-soak.*`) are unchanged — the 30-minute wake mechanism stays; only what happens on each wake changed.

### Failure-backoff semantics

A source's first two consecutive failures ("transient") retry at the normal cadence — a blip shouldn't change scheduling. From the third consecutive failure onward, the retry interval doubles per additional failure, capped at 12x the normal cadence:

| Consecutive failures | Retry interval (at 2h base cadence) |
| --- | --- |
| 0 (healthy) / 1–2 (transient) | 2h (normal cadence) |
| 3 | 4h |
| 4 | 8h |
| 5 | 16h |
| 6+ | 24h (ceiling, stays here) |

A successful run resets `consecutive_failures` to 0 immediately, returning the source to normal cadence. Because the whole calculation is derived from `source_run_health` rows read fresh from SQLite on every due-check, a service restart (or the systemd timer simply waking up again) does not reset a persistently-failing source back into full-frequency hammering — its accumulated failure history is exactly what it was before the restart.

### Regression tests

`tests/test_scheduling.py` (15 new tests) covers: pure due/backoff-interval calculations; all-healthy-and-fresh → nothing fetched; one due / others fresh → only that source runs; a failing source doesn't disturb healthy siblings; a failing source doesn't make the fleet globally due (the direct Stage 4 regression case, simulating 10 scheduler wakeups); a failed attempt never counts as a successful cadence reset; persistent failure enters backoff; backoff survives a simulated process restart (a fresh `Database` object against the same SQLite file); successful recovery resets backoff; multiple independently-due sources run together; production/experimental scope selection is unaffected by the scheduling change. All use a deterministic, manually-advanced fake clock (`Database` now accepts an injectable `clock` callable so persisted timestamps and the due-calculation agree) — no test sleeps in real time.

Full suite: **41/41 passing** (26 original + 15 new).

## Defect 2 — SK hynix Korea HTTP 403

### Diagnosis

Compared from three vantage points:

| Check | Local (residential, Mac) | Hetzner |
| --- | --- | --- |
| `GET /feed/` (no UA) | 200 | 403 |
| `GET /feed/` (KoreanTechWire/0.1 UA) | 200 | 403 |
| `GET /feed/` (browser UA) | 200 | 403 |
| `GET /` (homepage) | 200 | 403 |
| `GET /robots.txt` | 200, permissive `Allow: /` | 403 |
| `GET /sitemap.xml` | 200 | 403 |
| `GET /wp-json/` | — | 403 |
| Response server header | `Apache` (origin) | `awselb/2.0` (load balancer) |

Every endpoint under `news.skhynix.co.kr` returns identical `403 Forbidden` from Hetzner regardless of User-Agent, including `robots.txt` — a request no ordinary bot-mitigation product blocks. The response comes from the AWS Application Load Balancer itself (`server: awselb/2.0`), not the origin Apache server, meaning the block happens before the request reaches the application. This rules out a User-Agent check, a rate-limiting response to our own traffic pattern (robots.txt was never previously polled and is still blocked), and an endpoint-specific issue. It is consistent with an IP-reputation or datacenter-ASN block at the ALB/WAF layer, scoped to this one subdomain's infrastructure — `news.skhynix.com` (the English newsroom, CloudFront-fronted) and `www.skhynix.com` (main corporate site) both return normal `200`/`302` from the same Hetzner host, so it is not a company-wide block.

The Stage 4 due-gating defect (above) very likely made this worse — SK hynix was hit roughly 4x more often than the documented cadence for over a week — but the failure began within ~2 hours of the very first post-migration run, before that amplification had time to accumulate, so the block itself was not caused by the request-volume bug. It may have been triggered by something else about the Hetzner IP/ASN and then sustained regardless of request volume.

### Classification: **HOST-BLOCKED**

The source works normally from a non-datacenter IP; it does not work from Hetzner. Since the block operates below the URL path (identical 403 on `robots.txt`, `sitemap.xml`, the RSS feed, and the homepage), there is no legitimate alternate first-party endpoint on this domain that would escape it — this is not ENDPOINT-BLOCKED. No proxy rotation, CAPTCHA bypass, or residential proxying was attempted or is planned; this appears to be a deliberate infrastructure-level block and circumventing it is out of scope.

### Recovery decision

Not recovered in this repair. SK hynix Korea's `sources.yaml` entry, URL, and `PRODUCTION` lifecycle are unchanged — the source itself is not at fault, and demoting a company newsroom because of a datacenter IP block would misrepresent the actual defect. Instead, the Defect 1 backoff mechanism now doubles as the "explicit health/suspension mechanism" this situation calls for: a persistently failing source degrades automatically from a 2-hour retry cadence to a 24-hour ceiling, and `korean-tech-wire health` now prints each source's live scheduling state (e.g. `schedule=backoff(failures=9, retry_interval_s=86400, at_ceiling)`) so this is visible to an operator without database queries. No historical SK hynix data was touched or deleted (20 articles, 410+ historical run rows all preserved).

If SK hynix needs to actually collect again, the legitimate next step is out of scope for this repair: contacting SK hynix/AWS about the Hetzner IP range, or re-hosting the collector from a non-datacenter egress path. Neither was attempted here.

## Production source registry after this repair

Unchanged from the Stage 4 closeout: `the_elec` (PRODUCTION), `etnews_hardware` (PRODUCTION), `sk_hynix_newsroom` (PRODUCTION, HOST-BLOCKED from Hetzner, now backing off instead of hammering). `lg_display_newsroom` and `samsung_newsroom_kr` remain EXPERIMENTAL, untouched by this repair. The Elec and ETNews promotions are not revisited — the 403/406 and 403/403 soak run counts from Stage 4 remain valid evidence even though the request rate that produced them was unintentionally aggressive; that excess rate is documented as an incident here and in `docs/stage4-editorial-yield.md`, not repeated intentionally, and not treated as grounds to revert.

Samsung Newsroom Korea's missing editorial filter (0 of 19,344+ discovered references ever rejected — confirmed by reading `editorial/filtering.py`, which has no branch for `samsung_newsroom_kr`) is not touched in this repair; it remains the documented reason Samsung stays EXPERIMENTAL pending a REWORK task.
