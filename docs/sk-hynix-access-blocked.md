# sk_hynix_newsroom — ACCESS_BLOCKED

Status as of 2026-09-04. This records why the Korean SK hynix source cannot
collect from the production host, why it is nevertheless still enabled, and
what would actually restore it.

## State

| | |
|---|---|
| Source | `sk_hynix_newsroom` |
| Lifecycle | **PRODUCTION** — unchanged, still enabled |
| Health | `access_blocked` |
| Last successful collection | 2026-08-10T07:16Z |
| Consecutive failures | 846 access-blocked, 0 source-or-parser |
| Probe cadence | once per day (backoff at ceiling, 86400 s) |

## What is actually wrong

Nothing is wrong with the source, the URL, the feed or the collector. The
deployment host's egress address is refused at the publisher's edge.

Measured 2026-09-04, same URL and same collector User-Agent:

| From | Result |
|---|---|
| Hetzner host `204.168.142.1` (Helsinki) | `403`, `server: awselb/2.0`, 118-byte body |
| An unblocked address | `200`, `server: Apache`, valid RSS, 10 items |

The 403 is produced by an AWS ALB in `ap-northeast-2`
(`skhynix-prd-alb-579844989.ap-northeast-2.elb.amazonaws.com`) *before* the
WordPress origin, which serves `Server: Apache` to permitted clients.

Ruled out by direct evidence rather than inference:

- **not a User-Agent block** — 403 with the collector UA, with a browser UA,
  and with no UA header at all
- **not URL or structure drift** — the configured URL is correct and serves
  valid RSS; even `https://news.skhynix.co.kr/` (the site root) 403s from the
  host
- **not a geo-block** — an unblocked probe from India, also outside Korea,
  succeeds
- **not retired** — the feed is live and publishing daily
- **not a collector bug** — the fetch never completes; the parser is never
  reached
- **not transient** — 422 consecutive 403s over 25 days, one error signature

The domain is IPv4-only (no AAAA), so there is no alternate address family
either. The site's own `robots.txt` says `User-agent: * / Allow: /` — its
stated crawling policy permits this collector. The refusal is an
infrastructure ACL, most plausibly datacenter-ASN reputation.

## Why it is still enabled

Deliberately. Now that the failure is classified `access_blocked` rather than
`source_or_parser`, leaving it on costs one request per day, the failure is
isolated per-source (`run()` never raises), it misleads nobody in the health
view, and it **recovers by itself** the moment the ACL is lifted. Disabling it
would buy nothing and would throw away that automatic recovery.

It must not be disabled, repointed, aliased, or merged with any other source.

## What would restore it

Only a change of egress. The collector is correct; the vantage point is
refused.

This fleet already operates that pattern: `garmin-relay-forwarder` runs on
this same Hetzner host with a NAS-side tunnel, built precisely because Garmin
blocks datacenter addresses. Routing `sk_hynix_newsroom` through an
established relay would be reuse of sanctioned infrastructure, not evasion —
particularly given the publisher's `Allow: /` robots policy.

**This source is eligible for that relay, but not yet.** The prerequisite is
that the Garmin relay finishes its own reliability qualification first. As of
smartwatch-clank canon that repair is recorded PARTIAL: the Hetzner side is
complete, the NAS tunnel client still needs `ServerAlive`/`ExitOnForwardFailure`
flags, and the Garmin qualification window has not started. Attaching a second
production source to a relay that has not yet proven it stays up would move
the outage rather than fix it.

Sequence, in order:

1. Complete the NAS tunnel client flags.
2. Let the Garmin relay qualification window run and pass.
3. Only then evaluate routing `sk_hynix_newsroom` through the relay, as its
   own reviewed change with its own evidence.

Do not build or extend the relay for this source before step 2 completes.

## Coverage in the meantime

`sk_hynix_newsroom_global` (English edition, `news.skhynix.com/en/feed/`) was
added 2026-09-04 as an **independent EXPERIMENTAL source** — its own identity,
its own baseline, no alias or migration, and no reuse of Korean stored
articles as novelty history. It is coverage of the same publisher, not a
replacement for the Korean edition, and it does not change this source's
status in any way.
