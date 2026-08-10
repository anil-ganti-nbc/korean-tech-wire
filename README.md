# Korean Tech Wire

An independent, Korean-language technology intelligence collector. It is intentionally a separate package, database, configuration, and runtime from every other Wire project.

## Bootstrap status

Stage 1 uses three **EXPERIMENTAL** collectors: The Elec’s Korean HTML index, SK hynix Newsroom’s RSS feed, and Samsung Newsroom Korea’s HTML index. The production allowlist is empty and there are no alert integrations.

## Install and run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
korean-tech-wire source list
korean-tech-wire run
korean-tech-wire articles latest
korean-tech-wire status
pytest
```

`config/config.example.yaml` is safe to copy to the ignored `config/config.local.yaml` before changing runtime settings. The SQLite database defaults to `var/korean_tech_wire.db`.

See `docs/runbook.md` for operational use and `docs/source-research.md` for source decisions.
