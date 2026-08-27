# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).parents[1]

# Unlike watch-clank, this dashboard is plain stdlib http.server (no
# FastAPI/uvicorn, no Jinja templates, no alembic migrations -- Database
# storage does its own inline-SQL migrate()). The only on-disk assets
# dashboard.py falls back to are config/config.example.yaml and
# config/sources.yaml (see korean_tech_wire.dashboard ROOT/SOURCES). The
# per-machine config/config.local.yaml is gitignored user data, supplied
# at runtime via KOREAN_TECH_WIRE_CONFIG (as the desktop .cmd launcher
# already does) -- it is never bundled into the frozen app.
a = Analysis(
    [str(root / "native" / "windows" / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(root / "config" / "config.example.yaml"), "config"),
        (str(root / "config" / "sources.yaml"), "config"),
    ],
    hiddenimports=[],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Korean Tech Wire",
    console=False,
)
