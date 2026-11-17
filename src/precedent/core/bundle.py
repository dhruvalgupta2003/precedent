"""The bundle: everything a check reads, in one file (docs/design/production-architecture.md §4.5, ADR0025).

A load saves it; `check`, the hook, `why`, `doctor` and `status` read it. Its rules are in one fixed order, and it
carries the hash of what a verdict reads, so the same decisions give the same bundle on every machine (I6) and a
damaged file is never read.
"""

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime
from typing import Literal

from pydantic import ValidationError

from precedent.core.authority import Rule
from precedent.core.errors import BundleError
from precedent.core.model import Frozen

FORMAT = 1


class Stamp(Frozen):
    """When a saved bundle was built, and by which Precedent. Outside the hash: the same decisions are the same
    bundle. The version matters because the rules are saved already ranked: a fix to the ranking must not wait for
    the next load."""

    built_at: datetime
    version: str


class Bundle(Frozen):
    format: Literal[1]
    org: str
    loaded: bool  # the org has decisions, even if none of them checks anything (#66)
    rules: tuple[Rule, ...]
    hash: str  # of the org, `loaded` and the rules: everything a verdict reads
    stamp: Stamp | None = None  # None: built for one check, never saved


def build(org: str, rules: Iterable[Rule], *, loaded: bool, stamp: Stamp | None = None) -> Bundle:
    """The rules in one fixed order, whatever order the database returned them in."""
    ordered = tuple(sorted(rules, key=lambda rule: _canonical(rule.model_dump(mode="json"))))
    return Bundle(format=FORMAT, org=org, loaded=loaded, rules=ordered, hash=_digest(org, loaded, ordered), stamp=stamp)


def dump(bundle: Bundle) -> bytes:
    return _canonical(bundle.model_dump(mode="json"))


def parse(raw: bytes) -> Bundle:
    """The saved bundle, or a BundleError when it isn't one this version wrote, or was changed since."""
    try:
        bundle = Bundle.model_validate_json(raw)
    except ValidationError as exc:
        raise BundleError("isn't a bundle this version of Precedent can read") from exc
    if bundle.hash != _digest(bundle.org, bundle.loaded, bundle.rules):
        raise BundleError("is damaged: its rules don't match its hash")
    return bundle


def _digest(org: str, loaded: bool, rules: tuple[Rule, ...]) -> str:
    content = {"org": org, "loaded": loaded, "rules": [r.model_dump(mode="json") for r in rules]}
    return hashlib.sha256(_canonical(content)).hexdigest()


def _canonical(value: object) -> bytes:
    """Sorted keys, no spaces, ASCII only: the same bytes whatever the machine."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
