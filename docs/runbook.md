# Runbook

Run from this repository after installing the package:

```powershell
korean-tech-wire source list
korean-tech-wire run --source the_elec
korean-tech-wire health
korean-tech-wire health --source etnews_hardware
korean-tech-wire soak --cycles 3 --interval-seconds 7200
korean-tech-wire run
korean-tech-wire articles latest --limit 10
korean-tech-wire status
```

`run` reports attempted/succeeded/failed sources and discovered/new/existing articles. A `partial failure` means at least one collector failed; inspect the terminal error and then `status`. Failures are recorded in SQLite and do not remove historical articles or prevent healthy collectors from persisting.

Codex's execution sandbox can block outbound HTTPS even when the normal Windows host can resolve and fetch the same public URL. A sandbox `WinError 10013` or curl connection failure before TLS is an environment failure, not automatically a source-health failure. Confirm with the same low-rate command from host PowerShell before changing a collector or source status.

Use only the checked-in experimental configuration while testing. Do not add credentials, webhook URLs, cookies, database files, or logs to Git. Be polite: retain the provided user agent, use the default timeout, and do not defeat access controls. For parser changes, add/update an offline fixture and run `pytest` before an experimental live smoke run.

There are deliberately no scheduled tasks or notifications in this bootstrap. Production enablement requires the validation checklist in `source-research.md`.

`health` reports persisted per-source run history, including lifecycle, success/failure classification, latest reference/acceptance/timestamp counts, unexpected-zero events and recent notes. It preserves early sandbox failures and classifies known connection restrictions as environment failures rather than publisher/parser failures.

`soak` is a portable foreground runner, not a scheduler. Each cycle invokes normal collectors against the configured database; stopping it cleanly leaves completed runs in SQLite, and rerunning it safely resumes the evidence history. Its default two-hour interval is intended for a real working-day/multi-day observation, not rapid artificial load.

After deploying the Samsung structural fix, run the one-time, conservative historical cleanup before checking latest articles:

```powershell
korean-tech-wire maintenance cleanup-samsung-legacy
```

It marks old Samsung rows unverified and deletes only rows whose URL itself proves they are media albums, RSS, or known index controls. It intentionally preserves ambiguous historical records instead of guessing that they are invalid.

If migrating data collected before The Elec’s source filter, quarantine rather than delete that broad-index history:

```powershell
korean-tech-wire maintenance quarantine-theelec-legacy
```
