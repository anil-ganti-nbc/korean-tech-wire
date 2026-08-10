# GitHub and Hetzner migration

This procedure preserves Stage 4 evidence. It does not reset the soak, alter source lifecycles, or run collectors merely to prove deployment.

## Runtime-state classification

| Item | Classification | Notes |
| --- | --- | --- |
| `var/korean_tech_wire.db` | MUST MIGRATE | The authoritative articles, runs, health and identity history. |
| timestamped SQLite backup made with `state backup` | MUST MIGRATE | Transfer this verified snapshot, then install it as the live database. |
| `var/*.lock` | SAFE TO RECREATE | Advisory process lock; never copy it. |
| `.venv/`, `.pytest_cache/`, `__pycache__/`, `var/*.log` | SAFE TO RECREATE | Host-local generated state. |
| `.env`, `config/config.local.yaml`, API keys, credentials | MUST NOT MIGRATE through Git | Transfer only through the destination's secret-management path when actually needed. |

## Pre-transfer checkpoint on Windows

1. Let the current Stage 4 heartbeat finish or confirm it is idle. Do not start a fresh source cycle before the persisted two-hour cadence says it is due.
2. Pause/disable the old-host heartbeat only at the handoff point, before any Hetzner scheduler is enabled. There must be one executor.
3. From the repository root, create a uniquely named backup outside the repository. The command obtains the same run lock used by `run` and `soak`, checks source integrity, uses SQLite's online backup API, then checks the copy:

   ```powershell
   $stamp = Get-Date -Format yyyyMMddTHHmmssZ
   $backup = Join-Path $env:USERPROFILE "korean-tech-wire-$stamp.db"
   $env:PYTHONPATH = "src"
   python -m korean_tech_wire.cli state backup --destination $backup
   ```

4. Record an exact JSON checkpoint before transfer; compare the same command on Hetzner after installing the backup. The current `state backup` and `state checkpoint` never run collectors:

   ```powershell
   python -m korean_tech_wire.cli state checkpoint
   ```
5. Transfer the backup through an authenticated encrypted channel. Do not copy a live database file with a blind filesystem copy.

## GitHub

Create a private repository and push the existing `main` history; do not initialise a second repository or squash commits. The checked-in `.gitignore` excludes live databases, backups, locks, credentials, local configuration, virtual environments, logs and caches. When GitHub CLI authentication is available:

```bash
gh auth login
gh repo create korean-tech-wire --private --source . --remote origin --push
```

Use an organisation-qualified name if required by the intended owner. Review `git status --ignored` before pushing.

## Hetzner installation and non-fetching validation

The example deployment directory is `/opt/korean-tech-wire`; it is a deployment choice, not an application constant.

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin korean-tech-wire
sudo git clone <private-repository-url> /opt/korean-tech-wire
sudo chown -R korean-tech-wire:korean-tech-wire /opt/korean-tech-wire
sudo -u korean-tech-wire python3 -m venv /opt/korean-tech-wire/.venv
sudo -u korean-tech-wire /opt/korean-tech-wire/.venv/bin/pip install -e '/opt/korean-tech-wire[dev]'
sudo install -d -o korean-tech-wire -g korean-tech-wire /opt/korean-tech-wire/var
sudo install -o korean-tech-wire -g korean-tech-wire -m 0600 <transferred-backup> /opt/korean-tech-wire/var/korean_tech_wire.db
```

Before a cycle is due, validate without fetching sources:

```bash
cd /opt/korean-tech-wire
sudo -u korean-tech-wire .venv/bin/python -m pytest -q
sudo -u korean-tech-wire .venv/bin/python -m korean_tech_wire.cli health
sudo -u korean-tech-wire .venv/bin/python -m korean_tech_wire.cli state checkpoint
sudo -u korean-tech-wire .venv/bin/python -m korean_tech_wire.cli source list
sudo -u korean-tech-wire .venv/bin/python -m korean_tech_wire.cli soak --cycles 1 --interval-seconds 7200 --if-due
sqlite3 var/korean_tech_wire.db 'PRAGMA integrity_check;'
```

The final command above must return `ok`, and `health` must show historical runs. If it does not, stop: a newly-created empty database is not a migration success.

## Single scheduler ownership

The current ChatGPT heartbeat is local-host-only and must be paused before the Linux timer is enabled. Install the templates in `deploy/systemd/`, create `/etc/korean-tech-wire.env` with non-secret runtime settings only if needed, then:

```bash
sudo cp deploy/systemd/korean-tech-wire-soak.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now korean-tech-wire-soak.timer
systemctl list-timers korean-tech-wire-soak.timer
```

The timer only wakes the existing due-aware soak command every 30 minutes. `--if-due` consults persisted successful health rows for every enabled source, so changing the server timezone or moving hosts does not reset the two-hour cadence. `RunLock` prevents overlapping `run`, `soak`, and SQLite-backup processes on both Linux and Windows.

## First due Linux cycle

When the persisted cadence is actually due, run nothing manually first. Let the timer execute one all-source `soak --if-due` cycle, then inspect `health`, SQLite integrity, per-source counts, and duplicate canonical identities. New records must be genuinely new; a bulk of known articles becoming new is a migration red flag requiring an immediate stop and database/configuration investigation. Verify `run --production` separately at an appropriate time: its scope must remain only `sk_hynix_newsroom`.
