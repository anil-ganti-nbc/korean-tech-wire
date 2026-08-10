# Runbook

Run from this repository after installing the package:

```powershell
korean-tech-wire source list
korean-tech-wire run --source the_elec
korean-tech-wire run
korean-tech-wire articles latest --limit 10
korean-tech-wire status
```

`run` reports attempted/succeeded/failed sources and discovered/new/existing articles. A `partial failure` means at least one collector failed; inspect the terminal error and then `status`. Failures are recorded in SQLite and do not remove historical articles or prevent healthy collectors from persisting.

Codex's execution sandbox can block outbound HTTPS even when the normal Windows host can resolve and fetch the same public URL. A sandbox `WinError 10013` or curl connection failure before TLS is an environment failure, not automatically a source-health failure. Confirm with the same low-rate command from host PowerShell before changing a collector or source status.

Use only the checked-in experimental configuration while testing. Do not add credentials, webhook URLs, cookies, database files, or logs to Git. Be polite: retain the provided user agent, use the default timeout, and do not defeat access controls. For parser changes, add/update an offline fixture and run `pytest` before an experimental live smoke run.

There are deliberately no scheduled tasks or notifications in this bootstrap. Production enablement requires the validation checklist in `source-research.md`.
