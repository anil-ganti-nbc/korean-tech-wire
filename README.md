# Korean Tech Wire

An independent, Korean-language technology intelligence collector. It is intentionally a separate package, database, configuration, and runtime from every other Wire project.

## Current status

Stage 4 closed 2026-08-19. **PRODUCTION**: SK hynix Korea, The Elec, ETNews Hardware Sections. **EXPERIMENTAL**: Samsung Newsroom Korea, LG Display. There are no alert integrations.

SK hynix Korea's RSS endpoint is returning `403 Forbidden` from every Hetzner-origin request since 2026-08-10 (see `docs/stage4-editorial-yield.md`); it remains the production control by lifecycle but is not currently collecting. This is an open incident, not a lifecycle change.

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

See `docs/runbook.md` for operational use, `docs/source-research.md` for source decisions, `docs/hetzner-migration.md` for safe runtime-state migration, and `docs/stage4-editorial-yield.md` for the Stage 4 closeout record.
