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
import threading
import time
import webbrowser
from pathlib import Path

# Repo root is two levels up from native/windows/launcher.py. The desktop
# .cmd already does `cd /d %REPO%` before invoking this script, but we pin
# paths from our own file location too so this keeps working if it is ever
# launched with a different working directory.
REPO_ROOT = Path(__file__).resolve().parents[2]

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
