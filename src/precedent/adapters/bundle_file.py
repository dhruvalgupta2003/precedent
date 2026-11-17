"""The bundle saved on this computer (ADR0025): written whole or not at all, by one load at a time.

Only used with the built-in database, which runs on Linux and macOS; `fcntl` is imported where it is used so the
module still imports on Windows.
"""

import os
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from precedent.core.errors import BundleError

LOCK_WAIT_S = 30.0  # a load with an AI can take minutes; a second one waits this long, then says why it stopped
POLL_S = 0.05


def read(path: Path) -> bytes | None:
    """The saved bytes, or None when nothing was saved yet."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def write(path: Path, raw: bytes) -> None:
    """A reader sees the old bundle or the new one, never half of one: write a temporary file, then rename it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")  # 0600, whatever the umask
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(raw)
            file.flush()
            os.fsync(file.fileno())
        Path(temp).replace(path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


@contextmanager
def locked(path: Path, wait: float | None = None) -> Generator[int]:
    """One load of an org at a time. Yields the last bundle number used: it sits in the lock file, so it outlives a
    damaged bundle."""
    import fcntl  # noqa: PLC0415 (POSIX only, see above)

    lock = path.with_suffix(".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as file:
        deadline = time.monotonic() + (LOCK_WAIT_S if wait is None else wait)
        while True:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise BundleError(f"another load of org {path.stem!r} is running: try again when it ends") from None
                time.sleep(POLL_S)
        file.seek(0)
        yield _number(file.read())


def record(path: Path, sequence: int) -> None:
    """Note the number before the bundle that carries it is written, so a crash between the two never reuses it."""
    path.with_suffix(".lock").write_text(str(sequence))


def _number(text: str) -> int:
    return int(text) if text.strip().isdigit() else 0
