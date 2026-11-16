"""Places and homes (docs/design/production-architecture.md §4.1). A file's home comes from the folder it sits in,
never from a field, so nobody widens a check's reach by editing it. A place's parent follows from its repo and path,
so the tree can't have a cycle."""

import re

from pydantic import Field, field_validator

from precedent.core.checks import ID, Home, contains, glob_ok, under
from precedent.core.errors import KnowledgeError
from precedent.core.model import Frozen

CHECKS_FOLDER = "precedent"
CENTRAL_FOLDER = "homes"
ORG = "org"
CENTRAL_DEPTH = 3  # homes/<place>/<file>
REPO = r"^[A-Za-z0-9_.-]{1,100}$"
TEAM = r"^@[A-Za-z0-9-]+/[A-Za-z0-9_-][A-Za-z0-9._-]*$"  # an owner is a team, never one person


class Place(Frozen):
    name: str = Field(pattern=f"^{ID}$")
    repo: str = Field(pattern=REPO)
    path: str = ""  # its folder in the repo; "" is the whole repo
    owner: str = Field(pattern=TEAM)
    tags: tuple[str, ...] = ()

    @field_validator("repo")
    @classmethod
    def _repo(cls, repo: str) -> str:
        if repo in (".", ".."):
            raise ValueError("expected a repository name")
        return repo

    @field_validator("path", mode="before")
    @classmethod
    def _folder(cls, path: object) -> object:
        if not isinstance(path, str):
            return path
        path = path.strip("/")
        if path and (not glob_ok(path) or any(c in path for c in "*?[")):
            raise ValueError("expected a plain folder inside the repo")
        return path

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, tags: object) -> object:
        if not isinstance(tags, list | tuple) or not all(isinstance(t, str) and re.fullmatch(ID, t) for t in tags):
            raise ValueError("expected a list of tag names (lowercase letters, digits and '-')")
        return tuple(tags)

    @property
    def home(self) -> Home:
        return Home(repo=self.repo, path=self.path)


class Places(Frozen):
    places: tuple[Place, ...] = ()

    def get(self, name: str) -> Place | None:
        return next((p for p in self.places if p.name == name), None)

    def parent(self, name: str) -> Place | None:
        """The nearest place above, in the same repo; None when only the org is above."""
        place = self.get(name)
        if place is None or not place.path:
            return None
        repo, path = place.repo, place.path
        above = [p for p in self.places if p.repo == repo and p is not place and under(path, p.path)]
        return max(above, key=lambda p: len(p.path)) if above else None

    def tagged(self, tag: str, within: Home) -> set[tuple[str, str]]:
        """(repo, folder) of every place with this tag inside the home. An unknown tag, or one with no place inside
        the home, is an error: a check that can never match must not load as if it would."""
        tagged = [p for p in self.places if tag in p.tags]
        if not tagged:
            raise KnowledgeError(f"no place has the tag {tag!r} (places.yaml)")
        inside = {(p.repo, p.path) for p in tagged if contains(within, p.home)}
        if not inside:
            raise KnowledgeError(f"no place tagged {tag!r} is inside this home")
        return inside


def home_of(repo: str, file: str, places: Places, central: str | None) -> Home:
    """The home of a checks or promotions file, from its repo and repo-relative path. (Exceptions files come with
    phase 4.)"""
    parts = file.split("/")
    if central is not None and repo == central:
        return _central_home(parts, places)
    if parts[-2:-1] != [CHECKS_FOLDER]:
        raise KnowledgeError(f"{file[:120]}: checks live in a '{CHECKS_FOLDER}' folder")
    folder = "/".join(parts[:-2])
    if folder and not any(p.repo == repo and p.path == folder for p in places.places):
        raise KnowledgeError(f"{file[:120]}: map the folder {folder!r} to a place in places.yaml first")
    return Home(repo=repo, path=folder)


def _central_home(parts: list[str], places: Places) -> Home:
    shown = "/".join(parts)[:120]
    if len(parts) != CENTRAL_DEPTH or parts[0] != CENTRAL_FOLDER:
        raise KnowledgeError(
            f"{shown}: files go directly in {CENTRAL_FOLDER}/<place>/, not under {'/'.join(parts[:2])}"
        )
    if parts[1] == ORG:
        return Home()
    place = places.get(parts[1])
    if place is None:
        raise KnowledgeError(f"{shown}: no place {parts[1]!r} in places.yaml")
    return place.home
