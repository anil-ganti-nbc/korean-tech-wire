# Korean Tech Wire

An independent, Korean-language technology intelligence collector. It is intentionally a separate package, database, configuration, and runtime from every other Wire project.

## Current status

SK hynix Korea is the sole **PRODUCTION** source. The Elec, Samsung Newsroom Korea, LG Display, and ETNews hardware sections are **EXPERIMENTAL**. There are no alert integrations.

## Install and run

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
korean-tech-wire source list
korean-tech-wire health
korean-tech-wire soak --cycles 1 --interval-seconds 7200 --if-due
korean-tech-wire articles latest
pytest
```

`config/config.example.yaml` is safe to copy to the ignored `config/config.local.yaml` before changing runtime settings. The SQLite database defaults to `var/korean_tech_wire.db`.

See `docs/runbook.md` for operational use, `docs/source-research.md` for source decisions, and `docs/hetzner-migration.md` for safe runtime-state migration.
