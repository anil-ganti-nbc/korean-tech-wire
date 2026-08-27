"""Thin Windows launcher for the Korean Tech Wire dashboard.

Mirrors native/macos/launcher.py: starts the same in-repo
korean_tech_wire.dashboard.serve() used on macOS, swapping only the
platform-specific bits (browser-open mechanism, signal handling). Unlike the
macOS launcher, this one DOES install a mutation_authorizer: it generates a
fresh per-process bearer token and wires up dashboard.token_authorizer, which
turns on the dashboard's "Run collector now" / per-collector run buttons
(POST /collect) and the QC decision buttons (POST /qc: Useful / Not useful /
False positive / Duplicate). The token never leaves this machine -- it's
only ever compared against the Authorization header the dashboard's own
same-origin JS sends, embedded straight into the page it serves on
loopback. The free-text POST /feedback history endpoint is a separate,
non-terminal, append-only note -- it shares the same token gate but never
archives or removes an item from the active queue; only /qc does that.
"""
from __future__ import annotations

import json
import os
import secrets
import signal
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _default_repo_root() -> Path:
    """Repo root is normally two levels up from native/windows/launcher.py,
    and the desktop .cmd already does `cd /d %REPO%` before invoking this
    script -- but that `__file__`-based trick breaks once this script is
    frozen by PyInstaller: inside a onefile build, `__file__` resolves
    relative to the bootloader's temp extraction dir (sys._MEIPASS-adjacent),
    not the real checkout, so `parents[2]` lands on nonsense like
    `%LOCALAPPDATA%\\config\\config.local.yaml` instead of the repo's config.

    When frozen, resolve from `sys.executable` (the real .exe path) instead,
    and walk upward looking for this repo's tracked config/sources.yaml --
    that handles the exe being kept inside the repo (e.g. dist/Korean Tech
    Wire.exe). If no ancestor has it -- e.g. the exe was copied out to
    _Launchers, a sibling of the repo rather than a descendant -- fall back
    to this fleet's standard checkout location, matching the hardcoded
    `set "REPO=C:\\Users\\anil\\Clanks\\korean-tech-wire"` every sibling .cmd
    launcher already relies on.
    """
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().parent
        for _ in range(4):
            if (candidate / "config" / "sources.yaml").exists():
                return candidate
            parent = candidate.parent
            if parent == candidate:
                break
            candidate = parent
        return Path(r"C:\Users\anil\Clanks\korean-tech-wire")
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _default_repo_root()

# config.local.yaml's database_path is a plain relative path
# ("var/korean_tech_wire.db"), resolved against the process's cwd -- fine
# for the .cmd, which already does `cd /d %REPO%` before invoking this
# script, but a double-clicked standalone .exe (e.g. copied straight into
# _Launchers) inherits whatever cwd Explorer starts it with instead, and
# would silently create/read a stray var/ next to the exe rather than the
# repo's real database. Anchor cwd to REPO_ROOT unconditionally so this
# resolves the same way no matter how the process was started.
os.chdir(REPO_ROOT)

# Point the dashboard at the same local config the launcher's health check
# already validated, instead of letting it silently fall back to the
# tracked config/config.example.yaml. Only set a default if the caller
# (e.g. the .cmd) hasn't already provided one.
os.environ.setdefault("KOREAN_TECH_WIRE_CONFIG", str(REPO_ROOT / "config" / "config.local.yaml"))

# One token per process, so the "Run collector now" button works but nothing
# outside this dashboard's own served page can trigger a collection.
os.environ.setdefault("KOREAN_TECH_WIRE_DASHBOARD_AUTH_TOKEN", secrets.token_urlsafe(32))

from korean_tech_wire.dashboard import serve, token_authorizer


def wait_for_ready(server, timeout: float = 10.0) -> bool:
    import urllib.request

    port = server.server_address[1]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=0.5) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.1)
    return False


def main() -> None:
    # Mirrors native/macos/launcher.py: KTW has no Discord/webhook delivery
    # code paths at all today, but scrub any such env vars anyway so an
    # inherited/ambient credential can never silently activate one in a
    # future build. Belt-and-suspenders, not a functional dependency.
    for name in tuple(os.environ):
        if any(token in name.upper() for token in ("DISCORD", "WEBHOOK", "DELIVERY", "OUTBOX")):
            os.environ.pop(name, None)
    host = os.environ.get("KOREAN_TECH_WIRE_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.environ.get("KOREAN_TECH_WIRE_DASHBOARD_PORT", "0"))
    print(f"Config: {os.environ['KOREAN_TECH_WIRE_CONFIG']}")
    server = serve(host=host, port=port, mutation_authorizer=token_authorizer)
    actual_port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, name="ktw-loopback", daemon=False)
    thread.start()

    def stop(_signum: int, _frame: object) -> None:
        server.shutdown()

    signal.signal(signal.SIGINT, stop)
    try:
        signal.signal(signal.SIGBREAK, stop)  # Windows console close/Ctrl+Break
    except AttributeError:
        pass

    try:
        if wait_for_ready(server):
            print(f"Korean Tech Wire dashboard -> http://127.0.0.1:{actual_port}")
            print("Use the 'Run collector now' button on the dashboard to fetch new articles,")
            print("or run one separately: '_Launchers\\Korean Tech Wire - Run Collection.cmd'")
            print("(or from this repo: scripts\\run-collection.cmd)")
            if os.environ.get("KOREAN_TECH_WIRE_NO_BROWSER") != "1":
                webbrowser.open(f"http://127.0.0.1:{actual_port}/")
        else:
            print("Dashboard did not become ready in time.")
        thread.join()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
