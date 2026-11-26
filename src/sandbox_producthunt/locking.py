"""Single-run process lock for an InstaBox allocation."""
from __future__ import annotations

import fcntl
import os
import socket
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


class RunAlreadyActive(RuntimeError):
    pass


@contextmanager
def exclusive_run_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RunAlreadyActive("Another Product Hunt run already holds the sandbox lock") from None
        handle.seek(0)
        handle.truncate()
        handle.write(
            f"pid={os.getpid()} host={socket.gethostname()} started="
            f"{datetime.now(timezone.utc).isoformat()}\n"
        )
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
