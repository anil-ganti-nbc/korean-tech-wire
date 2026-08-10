from __future__ import annotations

import os
from pathlib import Path


class LockUnavailable(RuntimeError):
    pass


class RunLock:
    """Small cross-platform advisory lock for a process-wide collector/soak run."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0); self.handle.write(b"0"); self.handle.flush()
        try:
            if os.name == "nt":
                import msvcrt
                self.handle.seek(0); msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.handle.close(); self.handle = None
            raise LockUnavailable(f"another Korean Tech Wire run holds {self.path}") from error
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if not self.handle:
            return
        if os.name == "nt":
            import msvcrt
            self.handle.seek(0); msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        self.handle.close(); self.handle = None
