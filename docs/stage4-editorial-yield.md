# Stage 4 editorial-yield log and closeout record

Use this small log only for genuinely new items observed during the Stage 4 soak. Record title, source, outcome (`HIT`, `INTERESTING`, `NOISE`) and a short reason. It is a review aid, not automated scoring.

## Baseline — 2026-08-10

No new items arrived during the initial Stage 4 baseline cycles. The records created during Stage 3 are not counted as Stage 4 soak discoveries. New items should be appended here only after a normal collector run persists them.

The initial baseline therefore establishes stability only, not a fresh-yield claim. Promotion evidence needs new-item observations across ordinary spaced soak cycles.

## Stage 4 closeout — 2026-08-19

Soak interval: **2026-08-10 (~05:53 UTC, first post-migration run) through 2026-08-18 (~18:33 UTC, most recent timer-triggered run)**, roughly 8.5 unattended days on the Hetzner systemd timer, migrated from the local Windows heartbeat with runtime state preserved byte-for-byte at handoff.

### Run/article counts at closeout

| Metric | At migration (2026-08-10) | At closeout (2026-08-19) |
| --- | --- | --- |
| Articles | 189 | 363 |
| Runs | 45 | 2,052 |
| Migrations applied | 1–3 | 1–3 (unchanged) |
| Duplicate canonical identities | 0 | 0 |
| SQLite integrity check | — | `ok` |

Per-source article counts at closeout: `etnews_hardware` 143, `the_elec` 129, `samsung_newsroom_kr` 66, `sk_hynix_newsroom` 20, `lg_display_newsroom` 5.

### Anomaly: SK hynix Korea production source down for the entire soak

SK hynix Korea's RSS endpoint (`https://news.skhynix.co.kr/feed/`) has returned `403 Forbidden` (via an AWS ELB in front of the origin) on essentially every attempt since **2026-08-10T09:16 UTC**, roughly two hours after the last successful run following migration. Manual `curl` from the Hetzner host with a browser-like user agent reproduces the same `403` — this is a standing access block against the Hetzner egress IP (or IP range), not a code defect or a rate-limit self-inflicted by this project's polling cadence at the per-source level. `korean-tech-wire health` shows 410 attempts, 9 successes (all before the block began), 0 consecutive successes, and 0 new articles since the block started. The 20 SK hynix articles in the database are unchanged since 2026-08-10. This is a real, unresolved production incident: the sole original production source has not collected a single new article for essentially the entire Stage 4 soak. It is not remediated as part of this closeout (see Unresolved issues below); the lifecycle stays `PRODUCTION` because the collector and identity model are not at fault, but this needs owner attention separately from Stage 4.

### Anomaly: `soak --if-due` due-gating defect

`run_soak`'s `if_due` check (`src/korean_tech_wire/soak.py`) only skips a cycle when **every** selected source has a recent (< `interval_seconds`) success recorded. Because SK hynix has not recorded a fresh success since 2026-08-10, that condition can never be satisfied, so the due-aware gate has been permanently "due" for the whole soak. The systemd timer fires every 30 minutes (`OnUnitActiveSec=30min`) and, because of this defect, every tick actually executes a full 5-source collection cycle instead of respecting the documented 2-hour cadence — confirmed directly against `source_run_health.attempted_at` gaps (median gap ≈1800s / 30 min, not 7200s / 2h) and systemd journal entries showing a `soak` cycle completing every ~30 minutes throughout 2026-08-18. This inflated run volume roughly 4x across all five sources for over a week (runs≈403–410 per source instead of the ~100 expected at a true 2-hour cadence). The healthy sources tolerated the extra load without new failures, but this is a genuine defect in the due-gating logic, not a feature of the design, and is flagged for a follow-up fix (make `if_due` evaluate per-source rather than requiring every selected source to have a fresh success) rather than corrected inside this closeout, per the instruction not to alter collector/filter or soak behavior beyond what a promotion decision strictly requires.

### Per-source summary

**SK hynix Korea (PRODUCTION, unchanged)** — 410 runs, 9 successes, 0 consecutive successes, last success 2026-08-10T07:16 UTC, last (and ongoing) failure `HTTP 403: Forbidden`. 20 articles, unchanged since migration. Identity model (URL/GUID) was never in question — the source is simply inaccessible from Hetzner. **Not currently a healthy production control**; it is a production source in name only until the access block is resolved.

**ETNews Hardware Sections** — 406 runs, 403 successes (99.3%), 4 source failures (2× SSL EOF, 1× read timeout — isolated, not persistent), 100 consecutive successes at closeout. Latest run: 51 discovered / 44 accepted / 7 rejected, 0 extraction failures. 143 new articles accumulated, 0 null publication timestamps. The low-value-term filter (`editorial/filtering.py`) is active and rejecting a meaningful fraction (≈12% overall: 2,461 rejected of 20,652 discovered across the soak) — notices, recruitment, civic/political items. Sampled accepted output is substantive semiconductor/display/manufacturing reporting (TSMC/Samsung/SK yield-lab investment, LG's first LDI equipment order, Hanmi Semiconductor factory land purchase, MLCC lead-time squeeze from AI server demand), with only occasional soft leakage (a job-fair notice, an internal-policy item). **Editorial yield: mostly HIT/INTERESTING, low noise.**

**The Elec** — 403 runs, 403 successes (100%), 0 source failures, 1 environment blip, 403 consecutive successes. Latest run: 35 discovered / 18 accepted / 17 rejected. 129 new articles, 0 null timestamps among valid (non-legacy) records — the 34 null-timestamp rows are all pre-hardening `legacy_unverified` rows excluded from `articles latest`, not a live parser regression. The hardware/manufacturing signal-term filter rejects roughly half of discovered references, consistent with the documented broad-index leakage. Sampled output (LS Electric/Bloom Energy supply deal, ITM Semiconductor's non-Apple revenue growth, Microchip's radiation-hardened space atomic clock, NXP's Malaysia back-end expansion, materials suppliers' earnings) is genuinely distinct from ETNews — different companies, more financial/supply-chain-transaction detail — supporting the "independent corroboration is valuable" framing rather than redundant overlap. **Editorial yield: strong HIT rate, good complement to ETNews.**

**LG Display** — 408 runs, 387 successes (94.9%), 36 source failures ("remote end closed connection" ×18) plus 6 environment failures (timeouts), largely clustered mid-soak and resolved: 47 consecutive successes at closeout, last failure 2026-08-17. Article count has not moved past the original 5 discovered on 2026-08-10/12 — zero new articles for the remaining ~7 days of the soak despite continued successful polling. Per the task's own guidance this is not penalized as a defect (it is a naturally low-volume corporate newsroom), but it also means there is effectively no fresh Stage 4 editorial evidence to weigh, and the connection-reset pattern needs a few more clean cycles before its access reliability can be called settled. **No new editorial-yield evidence this soak; access needs to keep proving out.**

**Samsung Newsroom Korea** — 403 runs, 403 successes (100%), 0 source failures ever — the most structurally stable collector in the fleet. But **0 items rejected across all 403 successful runs (19,344 accepted of 19,344 discovered)** — confirmed in `src/korean_tech_wire/editorial/filtering.py`: `classify()` has explicit low-value-term branches for `the_elec`, `lg_display_newsroom`, and `etnews_hardware`, but no branch at all for `samsung_newsroom_kr`, so every discovered card falls through to the default `accepted`. 66 articles accumulated; the sampled recent output is dominated by marketing/CSR/lifestyle material (a Galaxy Z Fold8 skydiving stunt in Dubai, a Barcelona fashion-show collaboration, a football sponsorship campaign, an art-store exhibit, a Spider-Man movie tie-in campaign) with only occasional items of real technology-journalism value (a Samsung Research wearable-AI health foundation-model paper; a new production line in India tied to AI-datacenter cooling). The known timestamp-template limitation (marketing/overseas pages lacking `NewsArticle.datePublished`) persists proportionally (14 of 66 valid rows). **Editorial yield: mostly NOISE by volume; the collector is reliable but has no relevance filter.**

### Promotion decisions

- **ETNews Hardware Sections — PROMOTE.** Near-perfect run reliability (99.3%), an active and effective relevance filter, complete timestamp coverage, and a sustained week of substantive semiconductor/display/manufacturing hits. Meets the promotion policy's bar for stable, sufficiently useful, unattended collection.
- **The Elec — PROMOTE.** Perfect run reliability across 403 runs, an active filter doing real work, and a full week of distinct, high-value reporting that corroborates rather than duplicates ETNews. Meets the same bar.
- **LG Display — CONTINUE EXPERIMENTAL.** Real (if since-resolved) access instability mid-soak, and zero new articles for most of the soak period leave no fresh Stage 4 editorial evidence to promote on. Its underlying value was never in question (Stage 3's four accepted items were all strong hits); it simply needs a few more clean, non-empty cycles before the "sufficient time, runs, or layout confidence" bar in the promotion policy is met.
- **Samsung Newsroom Korea — REWORK.** The collector itself is the most reliable in the fleet, but it has no editorial filter at all — a confirmed code gap, not a slow-burn quality issue — and the accumulated evidence shows that gap actually matters: most of what it currently persists is PR/marketing/lifestyle noise. It should not be evaluated for promotion again until a Samsung-specific low-value-term filter (mirroring the existing `LGDISPLAY_LOW_VALUE_TERMS` / `ETNEWS_LOW_VALUE_TERMS` pattern in `editorial/filtering.py`) is added and given its own soak. This is a substantive correction, not a promotion-blocking nuance, so it is documented here rather than fixed inside this closeout.

### Final production scope (verified live, twice, 2026-08-18)

`korean-tech-wire run --production` scope is exactly `the_elec`, `sk_hynix_newsroom`, `etnews_hardware` — no experimental source leaked into production scope. Two consecutive live production runs were idempotent (0 new articles both times, since these three sources had just been polled by the ordinary soak cycle). SK hynix failed both runs with the same `403 Forbidden`, isolated from the other two sources, which both succeeded — confirming failure isolation holds under the new scope. Post-promotion `state checkpoint`: SQLite integrity `ok`, 0 duplicate canonical identities, article counts unchanged by the validation runs. Offline test suite: 26/26 passing both before and after the lifecycle change.

### Unresolved issues carried forward (not fixed in this closeout)

1. ~~**SK hynix Korea `403 Forbidden` from the Hetzner egress IP**~~ — **Diagnosed and given an explicit backoff/suspension mechanism in Stage 4.1** (`docs/stage4.1-reliability-repair.md`): confirmed HOST-BLOCKED (an AWS ALB-level block scoped to this one subdomain, reproducible on every endpoint including `robots.txt`, unrelated to User-Agent). No legitimate alternate endpoint exists on the same domain, so no transport change was made; lifecycle stays PRODUCTION. The source is not actually recovered — it still cannot collect from Hetzner — but it no longer retries at full frequency forever.
2. ~~**`soak --if-due` due-gating defect**~~ — **Fixed in Stage 4.1**: due-ness is now evaluated per source from persisted history, with a failure-backoff policy, instead of requiring every selected source to have a fresh success. See `docs/stage4.1-reliability-repair.md`.
3. **Samsung Newsroom Korea has no editorial filter** — confirmed code gap (see REWORK decision above); needs a dedicated low-value-term filter before re-evaluation. Not touched in Stage 4.1.
4. **LG Display's mid-soak connection-reset pattern** — self-resolved (47 consecutive successes at closeout) but worth a few more cycles of confirmation before treating access as fully settled. Not touched in Stage 4.1.
