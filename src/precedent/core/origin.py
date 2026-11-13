"""Where a decision was loaded from, and what one load owns (ADR0021). Pure: no git, no database.

One org graph takes decisions from many repositories and many loads (ADR0012). A load owns the decision files under
the folder it loaded, in its own repository. It may take a decision id only from a file it owns. It retires a
decision only when this checkout proves the decision's file is gone; anything it can't prove keeps counting, as it
did before origins were kept, so a skipped folder or an older branch can never lift a block.
"""

import re
from collections.abc import Iterable
from typing import NamedTuple

from precedent.core.model import Origin

# scheme://, then user:secret@, then the host, an optional :port, then the path after "/" or (scp-like) ":", then
# an optional ?query or #fragment, which is dropped (a query string can carry a token too).
REMOTE = re.compile(
    r"^(?:[a-z][a-z0-9+.-]*://)?(?:[^@/]*@)?(?P<host>[^/:@\s?#]+)(?::\d*)?[:/](?P<path>[^\s?#]+)(?:[?#]\S*)?$", re.I
)
ON_THIS_MACHINE = re.compile(r"^(?:[/.~]|file:|[a-z]:[\\/])", re.I)  # a path, or a Windows drive either way


class Earlier(NamedTuple):
    """A decision already in the graph: where its file was, and the commit it was loaded at with its file committed."""

    decision: str
    origin: Origin | None
    commit: str | None


class Proof(NamedTuple):
    """What this checkout can show about decisions it owns but didn't load."""

    read: frozenset[str]  # paths this load read (a file can come back under a new id)
    missing: frozenset[str]  # owned paths with no file in this checkout
    history: frozenset[str]  # recorded commits that are in this checkout's history


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
    return "/".join(_azure(match["host"].lower(), path))


def _azure(host: str, path: str) -> tuple[str, str]:
    """Azure DevOps writes one repository two ways: ssh.dev.azure.com, path v3/org/project/repo, over ssh, and
    dev.azure.com, path org/project/_git/repo, over https. Both become dev.azure.com, org/project/repo."""
    if host == "ssh.dev.azure.com" and path.startswith("v3/"):
        host, path = "dev.azure.com", path.removeprefix("v3/")
    if host == "dev.azure.com":
        path = path.replace("/_git/", "/", 1)
    return host, path


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
            f"{decision} is already loaded from {_shown(before.repo)} ({_shown(before.path)}), and this load reads it"
            f" from {_shown(mine.repo)} ({_shown(mine.path)})"
        )
    return found


def retired(earlier: Iterable[Earlier], kept: set[str], reach: Reach, proof: Proof) -> list[str]:
    """Decisions this load owns and didn't load, that this checkout proves are gone: it read their file again under
    another id, or their file is missing here and the commit they were loaded at is in this checkout's history.

    A folder the load skipped, an older branch, a shallow clone or a file never committed proves nothing, so those
    decisions keep counting.
    """
    gone = []
    for decision, origin, commit in earlier:
        if origin is None or decision in kept or not covers(reach, origin):
            continue
        if origin.path in proof.read or (origin.path in proof.missing and commit in proof.history):
            gone.append(decision)
    return sorted(gone)


def _shown(text: str) -> str:
    """Hidden or control characters spelled out, so a crafted folder name can't drive the terminal."""
    return text if text.isprintable() else repr(text)
