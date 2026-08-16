"""Thin macOS launcher for the isolated Korean Tech Wire field test."""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

from korean_tech_wire.dashboard import serve


def wait_for_ready(port: int, timeout: float = 10.0) -> bool:
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
    state = Path(os.environ.setdefault("KOREAN_TECH_WIRE_DATA_DIR", str(Path.home() / "Library" / "Application Support" / "Korean Tech Wire"))).expanduser().resolve()
    state.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = serve(port=port)
    thread = threading.Thread(target=server.serve_forever, name="ktw-loopback", daemon=False)
    thread.start()
    def stop(_signum: int, _frame: object) -> None:
        server.shutdown()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    if wait_for_ready(port):
        subprocess.Popen(["open", f"http://127.0.0.1:{port}/"])
    thread.join()
    server.server_close()


if __name__ == "__main__":
    main()
