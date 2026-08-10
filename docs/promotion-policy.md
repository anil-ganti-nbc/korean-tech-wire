# Source promotion policy

Promotion is an explicit, reversible per-source configuration change from `EXPERIMENTAL` to `PRODUCTION`. It is not a reward for a small number of successful smoke runs.

## Evidence to review

Review the source's SQLite health history through `korean-tech-wire health --source <id>` over a representative observation period. Consider consecutive host-successful runs, reference-count behaviour appropriate to the source, timestamp coverage, canonical stability, repeat-run idempotence, extraction failures, unexpected-zero events, and whether errors are isolated from other sources. The health view classifies retained failure notes as `environment`, `intentional_development`, or `source_or_parser`; early sandbox connection blocks remain evidence, but do not count as publisher/parser failures.

Editorial evidence is source-specific. Review new items in the lightweight yield log as HIT, INTERESTING, or NOISE. A high-volume filtered publication needs sustained leakage review; a low-volume corporate newsroom needs stable access and useful material, not constant publication. Do not use one global percentage threshold.

## Decision outcomes

- **PROMOTE** — stable and sufficiently useful for unattended collection. Change only that source's lifecycle, run the full tests, then run production twice and verify scope/idempotence.
- **CONTINUE EXPERIMENTAL** — useful but not yet enough time, runs, or layout confidence.
- **DEFER** — technically healthy but editorial value is too low for routine production collection.
- **REWORK** — source/filter behavior requires substantive correction.

An unexpected drop from an established nonzero discovery baseline to zero is a source-health failure. Zero new articles is normal. Historical articles are preserved on all failures.
