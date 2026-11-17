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

from precedent.core.errors import LoadRunningError

LOCK_WAIT_S = 30.0  # a load with an AI can take minutes; a second one waits this long, then says why it stopped
POLL_S = 0.05


def read(path: Path) -> bytes | None:
    """The saved bytes, or None when nothing is saved."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def write(path: Path, raw: bytes) -> None:
    """A reader sees the old bundle or the new one, never half of one: write a temporary file, then rename it."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
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
def locked(path: Path) -> Generator[None]:
    """One load of an org at a time, so two loads never mix their writes."""
    import fcntl  # noqa: PLC0415 (POSIX only, see above)

    lock = path.with_suffix(".lock")
    lock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with lock.open("a") as file:
        deadline = time.monotonic() + LOCK_WAIT_S
        while True:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    message = f"another load of org {path.stem!r} is running: try again when it ends"
                    raise LoadRunningError(message) from None
                time.sleep(POLL_S)
        yield
