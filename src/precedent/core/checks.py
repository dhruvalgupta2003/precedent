"""The checks format (docs/design/production-architecture.md §4). A check only ever warns; a promotion, a frozen
snapshot of a check that owners approved, is the only thing that can block."""

import re
from datetime import date
from typing import Annotated, Literal, Self

from pydantic import Field, Strict, StrictBool, field_validator, model_validator

from precedent.core.grounding import looks_like_code
from precedent.core.model import Frozen, Scope

ENGINES = ("package", "symbol", "path", "component", "feature_gate", "config", "version")
LATER = ("semgrep", "boundary", "conftest")  # designed, not built: refused, so a check that can't run never passes
ID = r"[a-z0-9][a-z0-9-]{0,63}"
TAG = "tag:"
MAX_GLOB = 256
Engine = Literal["package", "symbol", "path", "component", "feature_gate", "config", "version"]
Polarity = Literal["applies", "prefer", "avoid", "require"]


class Home(Frozen):
    """What a checks file may cover (§4.1): the whole organisation (no repo), or one folder of one repo ("" is the
    whole repo). One reach has exactly one value, however the file that names it was found."""

    repo: str | None = None
    path: str = ""


def contains(outer: Home, inner: Home) -> bool:
    return outer.repo is None or (outer.repo == inner.repo and under(inner.path, outer.path))


def under(path: str, folder: str) -> bool:
    return not folder or path == folder or path.startswith(f"{folder}/")


def glob_ok(pattern: str) -> bool:
    """One meaning only: relative, no `.`, `..` or empty segment, no backslash or NUL, at most 256 characters."""
    segments = pattern.split("/")
    plain = "\\" not in pattern and "\0" not in pattern
    return 0 < len(pattern) <= MAX_GLOB and plain and all(s not in ("", ".", "..") for s in segments)


def entry_ok(entry: str, home: Home) -> bool:
    """A `where` or `except` entry: a glob, or `tag:<name>`; in the org home also `<repo-glob>:<path-glob>`."""
    if entry.startswith(TAG):
        return re.fullmatch(ID, entry.removeprefix(TAG)) is not None
    repo, colon, path = entry.partition(":")
    if not colon:
        return glob_ok(entry)
    return home.repo is None and "/" not in repo and glob_ok(repo) and glob_ok(path)


def matches(pattern: str, path: str) -> bool:
    """`**` crosses folders (at the end: one or more, elsewhere: zero or more), `*` and `?` stay inside one. Segment
    by segment, so the time is linear in the path and no pattern can make it explode."""
    globs, parts = pattern.split("/"), path.split("/")
    reach = {0}  # how many path segments the globs so far can have consumed
    for i, glob in enumerate(globs):
        if glob == "**":
            least = min(reach) + (1 if i == len(globs) - 1 else 0)
            reach = set(range(least, len(parts) + 1))
        else:
            reach = {j + 1 for j in reach if j < len(parts) and _segment(glob, parts[j])}
        if not reach:
            return False
    return len(parts) in reach


def _segment(glob: str, text: str) -> bool:
    """`*` and `?` inside one name, greedy with one backtrack point: no regex, so no catastrophic backtracking."""
    g = t = 0
    star, mark = -1, 0
    while t < len(text):
        if g < len(glob) and glob[g] in ("?", text[t]):
            g, t = g + 1, t + 1
        elif g < len(glob) and glob[g] == "*":
            star, mark, g = g, t, g + 1
        elif star >= 0:
            g, mark = star + 1, mark + 1
            t = mark
        else:
            return False
    return all(c == "*" for c in glob[g:])


class Content(Frozen):
    """Everything about a check but its id and home: what a promotion freezes, compared field for field."""

    decision: str
    engine: Engine
    value: str
    range: str | None = None
    polarity: Polarity
    where: tuple[str, ...] = ("**",)
    except_: tuple[str, ...] = Field(default=(), alias="except")
    why: str | None = None
    quote: str | None = None

    @field_validator("engine", mode="before")
    @classmethod
    def _built(cls, engine: object) -> object:
        if engine in LATER:
            raise ValueError(f"the {engine} engine isn't available yet")
        return engine

    @field_validator("where", "except_", mode="before")
    @classmethod
    def _entries(cls, entries: object) -> tuple[str, ...]:
        """Sorted, without repeats, so two snapshots that mean the same thing are equal."""
        if not isinstance(entries, list | tuple) or not all(isinstance(e, str) for e in entries):
            raise ValueError("expected a list of paths")
        return tuple(sorted(set(entries)))

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if not self.where:
            raise ValueError("where can't be empty; leave it out to cover the whole home")
        if not (self.why or self.quote):
            raise ValueError("needs a why or quote: the reason, or the decision's own words")
        if (self.engine == "version") != (self.range is not None):
            raise ValueError("range is for version checks, and every version check needs one")
        kind = "package" if self.engine == "version" else self.engine
        if not looks_like_code(Scope(kind=kind, value=self.value)):
            raise ValueError(f"{self.value!r} doesn't look like a {kind}")
        return self

    def reaches(self, home: Home) -> None:
        """Every entry stays inside the home: no `..`, no leading `/`, and repo prefixes only in the org home."""
        for entry in (*self.where, *self.except_):
            if not entry_ok(entry, home):
                raise ValueError(f"{entry[:80]!r} isn't a path inside this home")


class Check(Content):
    id: str = Field(pattern=f"^{ID}$")
    home: Home

    @model_validator(mode="after")
    def _inside(self) -> Self:
        self.reaches(self.home)
        return self

    @property
    def content(self) -> Content:
        return Content.model_validate(self.model_dump(exclude={"id", "home"}, by_alias=True))


class Promotion(Frozen):
    """A frozen snapshot that blocks (§4.3). Its snapshot must equal the check at the PR's base (phase 3 policy)."""

    check: str = Field(pattern=f"^{ID}$")
    snapshot: Content
    scope: Literal["all", "new-code"] = "all"
    from_: Annotated[date, Strict()] | None = Field(default=None, alias="from")  # a UTC day, never a time
    critical: StrictBool = False
    home: Home

    @model_validator(mode="after")
    def _inside(self) -> Self:
        self.snapshot.reaches(self.home)
        return self
