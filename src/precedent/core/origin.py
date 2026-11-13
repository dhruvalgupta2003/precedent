"""Where a decision was loaded from, and what one load owns (ADR0021). Pure: no git, no database.

One org graph takes decisions from many repositories and many loads (ADR0012). A load owns the decision files under
the folder it loaded, in its own repository. It may take a decision id only from a file it owns, and a decision it
owns but didn't load (its file was deleted, renamed or moved) stops counting.
"""

import re
from collections.abc import Iterable
from typing import NamedTuple

from precedent.core.model import Origin

# scheme://, then user:secret@, then the host, an optional :port, then the path after "/" or (scp-like) ":".
REMOTE = re.compile(r"^(?:[a-z][a-z0-9+.-]*://)?(?:[^@/]*@)?(?P<host>[^/:@\s]+)(?::\d*)?[:/](?P<path>\S+)$", re.I)
ON_THIS_MACHINE = re.compile(r"^(?:[/.~]|file:|[a-z]:\\)", re.I)


class Reach(NamedTuple):
    """What one load owns: the decision files under `under` ("" for the whole repository) in repository `repo`."""

    repo: str
    under: str  # "" or a folder ending in "/"


def repo_name(url: str) -> str | None:
    """A remote as "host/owner/name": lower case, without scheme, port, ".git" or any credential (a token in the URL
    must never reach the graph). None for a remote that is a path on this machine, or not a remote at all."""
    url = url.strip()
    match = REMOTE.match(url) if url and not ON_THIS_MACHINE.match(url) else None
    if match is None:
        return None
    path = match["path"].strip("/").removesuffix(".git").strip("/").lower()
    if not path or any(c in path for c in "@:"):
        return None
    return f"{match['host'].lower()}/{path}"


def covers(reach: Reach, origin: Origin | None) -> bool:
    """The load owns this decision: its file is under the loaded folder, in the same repository."""
    return origin is not None and origin.repo == reach.repo and origin.path.startswith(reach.under)


def clashes(
    loading: Iterable[tuple[str, Origin]], loaded: Iterable[tuple[str, Origin | None]], reach: Reach
) -> list[str]:
    """Ids this load would take from a file it doesn't own: another repository, or a folder outside this load.

    A decision with no origin (loaded before origins were kept) can't be placed, so it becomes this load's.
    """
    now = dict(loading)
    found = []
    for decision, before in sorted(loaded, key=lambda entry: entry[0]):
        mine = now.get(decision)
        if mine is None or before is None or before == mine or covers(reach, before):
            continue
        found.append(
            f"{decision} is already loaded from {before.repo} ({before.path}), and this load reads it from"
            f" {mine.repo} ({mine.path})"
        )
    return found


def gone(loaded: Iterable[tuple[str, Origin | None]], kept: set[str], reach: Reach) -> list[str]:
    """Decisions this load owns but didn't load: their file was deleted, renamed or moved."""
    return sorted(decision for decision, origin in loaded if covers(reach, origin) and decision not in kept)
