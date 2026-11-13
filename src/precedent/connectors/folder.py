"""Any folder → what to load (ADR0014).

ADR-shaped notes load through the ADR connector, folder by folder. Other Markdown is searched, without AI, for
decisions that are clearly marked: a `Decision:` line, a `## Decision` section, or a "we decided" sentence. What it
finds quotes the document word for word and enters as proposed and unstructured: it may warn, never block (ADR0004).
"""

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from precedent.connectors import adr
from precedent.core.grounding import looks_like_code
from precedent.core.model import DecisionRecord, Scope, SourceRef

SKIP_DIRS = frozenset({"node_modules", "dist", "build", "site", "vendor", "target", "coverage", "venv", "__pycache__"})
# Instruction files tell agents what to do; a stale line there must never become a decision. Boilerplate isn't one.
NOT_DECISIONS = re.compile(
    r"(claude|agents|gemini|changelog|licen[cs]e|code_of_conduct|copilot-instructions)\.md", re.IGNORECASE
)
# A newline that doesn't start a blank line, a list item, a heading, a quote or a table row: the same paragraph.
WRAP = r"\n(?![ \t]*(?:\n|[-*+>#|]|\d+\.))"
MARKED = re.compile(
    rf"^[ \t>*-]*(?:\*\*|__)?Decision(?:\*\*|__)?[ \t]*:[ \t]*(?:\*\*|__)?[ \t]*(\S[^\n]*(?:{WRAP}[^\n]*)*)",
    re.IGNORECASE | re.MULTILINE,
)
# A "we decided" sentence, whole even when it wraps over lines, and never across a paragraph break.
DECIDED = re.compile(
    rf"(?:[^.!?\n]|{WRAP})*?\b(?:we|the team)\s+(?:have\s+|'ve\s+)?(?:decided|agreed)\b"
    rf"(?:[^\n]|{WRAP})*?(?:[.!?](?=\s|$)|(?=\n[ \t]*\n)|\Z)",
    re.IGNORECASE,
)
AVOID = re.compile(
    r"\b(?:do not|don't|never|no longer|stop)\s+(?:use|using|add|adding|import|importing)\s+`([^`]+)`"
    r"|\bavoid(?:ing)?\s+`([^`]+)`|\binstead of\s+`([^`]+)`",
    re.I,
)
USE = re.compile(r"\b(?:use|using|prefer|keep|switch to|move to|adopt)\s+(?:the\s+built-in\s+)?`([^`]+)`", re.I)
TITLE_CHARS = 80
MIN_WORDS = 2  # "use `luxon`" is a decision; ")" is not
WORD = re.compile(r"[A-Za-z]{2,}")


class Scan(NamedTuple):
    adr_folders: list[Path]
    docs: list[Path]  # Markdown outside ADR folders (an ADR folder's index or template isn't a decision)


def scan(root: Path) -> Scan:
    files = markdown_files(root)
    adr_folders = sorted({p.parent for p in files if adr.adr_id_of(p)})
    return Scan(adr_folders, [p for p in files if p.parent not in adr_folders])


def markdown_files(root: Path) -> list[Path]:
    """Every .md under root, skipping dependency, build and hidden folders, and instruction files.

    In a git repository, git decides what's ignored (.gitignore); elsewhere every folder is walked. Symbolic links to
    folders aren't followed, so loading never wanders outside the folder.
    """
    listed = _git_files(root)
    files = listed if listed is not None else [here / f for here, _, names in root.walk() for f in names]
    return sorted(p for p in files if _readable(p.relative_to(root)))


def _readable(rel: Path) -> bool:
    folders = rel.parts[:-1]
    skipped = any(part in SKIP_DIRS or part.startswith(".") for part in folders)
    return rel.suffix.lower() == ".md" and not skipped and not NOT_DECISIONS.fullmatch(rel.name)


class Repository(NamedTuple):
    """The git repository a folder is in, as git sees it (so a mistyped letter case or a symlinked path agree)."""

    top: Path
    remote: str  # the `origin` remote as written, "" without one
    prefix: str  # the folder inside the repository: "" or "docs/adr/"
    head: str | None  # the commit checked out; None before the first commit


def repository(root: Path) -> Repository | None:
    """The git repository a folder is in, or None outside one, when git refuses to run there, or when git's answer
    isn't this folder (a stray GIT_DIR or GIT_WORK_TREE would make git describe another one)."""
    top = _git(root, "rev-parse", "--show-toplevel")
    prefix = _git(root, "rev-parse", "--show-prefix")
    if top is None or prefix is None or not (Path(top) / prefix).samefile(root):  # case and links agree
        return None
    head = _git(root, "rev-parse", "--verify", "-q", "HEAD")
    return Repository(Path(top), _git(root, "remote", "get-url", "origin") or "", prefix, head)


def committed(repo: Repository) -> set[str] | None:
    """Paths under the folder in the checked-out commit (a file only on disk isn't committed yet). None when git
    can't list them: then nothing can be proven gone."""
    if repo.head is None:
        return set()
    listed = _git(repo.top, "ls-tree", "-r", "-z", "--name-only", repo.head, "--", repo.prefix or ".")
    return None if listed is None else set(listed.split("\0")) - {""}


def in_history(repo: Repository, commit: str) -> bool:
    """The commit is the checked-out one or one of its ancestors. False when git can't tell (a shallow clone)."""
    return repo.head is not None and _git(repo.top, "merge-base", "--is-ancestor", commit, repo.head) is not None


# Variables a git hook exports that point git at another repository or index than the folder's own.
GIT_LOCATION = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY", "GIT_PREFIX")


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """git on the folder itself: no inherited location variables, and any file name decoded without crashing."""
    env = {k: v for k, v in os.environ.items() if k not in GIT_LOCATION}
    return subprocess.run(  # noqa: S603 (fixed arguments, no shell)
        ["git", "-C", str(root), *args],  # noqa: S607
        capture_output=True,
        text=True,
        errors="surrogateescape",
        env=env,
        check=False,
    )


def _git(root: Path, *args: str) -> str | None:
    done = _run_git(root, *args)
    return done.stdout.strip("\n") if done.returncode == 0 else None


def _git_files(root: Path) -> list[Path] | None:
    """Files git shows (tracked, or new and not ignored) that still exist; None outside a git repository."""
    listed = _run_git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    if listed.returncode != 0:
        return None
    return [root / name for name in listed.stdout.split("\0") if name and (root / name).is_file()]


def found_in(doc: Path, root: Path, prefix: str) -> list[DecisionRecord]:
    """Clearly marked decisions in an ordinary document, each quoting it verbatim. `prefix` is "org" or "org/source".

    Without AI, a "we decided" sentence counts only if it names something checkable in backticks: prose without code
    is the AI finder's job.
    """
    name = _name(doc, root)
    found = []
    for quote, needs_code in _quotes(body(doc)):
        record = _record(quote, doc, f"{prefix}/{name}", prefix)
        if len(WORD.findall(quote)) >= MIN_WORDS and (record.scopes or not needs_code):
            found.append(record)
    return found


def from_scopes(doc: Path, root: Path, prefix: str, scopes: list[Scope]) -> list[DecisionRecord]:
    """Decisions an AI read in a document (ADR0014): one per quote, with the stances it states. The scopes must
    already be grounded in `body(doc)`; like every found decision, these are proposed and may only warn."""
    by_quote: dict[str, list[Scope]] = {}
    for scope in (s for s in scopes if s.polarity != "applies"):  # about something isn't a decision on it
        by_quote.setdefault(" ".join((scope.quote or "").split()), []).append(scope)
    records = (
        _record(quote, doc, f"{prefix}/{_name(doc, root)}", prefix).model_copy(update={"scopes": tuple(found)})
        for quote, found in by_quote.items()
        if len(WORD.findall(quote)) >= MIN_WORDS
    )
    return list(records)


def merge(records: list[DecisionRecord]) -> list[DecisionRecord]:
    """One decision per id: the rules and the AI finding the same sentence add their stances to one record."""
    merged: dict[str, DecisionRecord] = {}
    for record in records:
        first = merged.get(record.id, record)
        stances = {(s.kind, s.value, s.polarity): s for s in record.scopes + first.scopes}
        merged[record.id] = first.model_copy(update={"scopes": tuple(stances.values())})
    return list(merged.values())


def body(doc: Path) -> str:
    """The document's text without code blocks: an example inside a code block is not a decision."""
    return adr.FENCE.sub("", adr.text(doc))


def _name(doc: Path, root: Path) -> str:
    return adr.slug(doc.relative_to(root).with_suffix("").as_posix())


def _quotes(body: str) -> list[tuple[str, bool]]:
    """Marked decisions in document order, with whether each needs code to count. Marked lines win overlaps."""
    marked = [(m.start(1), m.end(1), False) for m in MARKED.finditer(body)]
    section = adr.DECISION_SECTION.search(body)
    if section and (first := section[1].strip().split("\n\n")[0]):
        start = body.index(first, section.start(1))
        marked.append((start, start + len(first), False))
    decided = [(*m.span(), True) for m in DECIDED.finditer(body)]
    kept: list[tuple[int, int, bool]] = []
    for start, end, needs_code in marked + decided:
        if not any(s < end and start < e for s, e, _ in kept):
            kept.append((start, end, needs_code))
    return [(body[s:e].strip(), needs_code) for s, e, needs_code in sorted(kept)]


def _record(quote: str, doc: Path, id_base: str, prefix: str) -> DecisionRecord:
    statement = " ".join(quote.split())
    return DecisionRecord(
        id=f"{id_base}-{hashlib.sha256(statement.encode()).hexdigest()[:6]}",
        org=prefix.partition("/")[0],
        title=statement[:TITLE_CHARS],
        statement=statement,
        status="proposed",
        tier="unstructured",
        confirmed=False,
        scopes=_scopes(quote),
        sources=(SourceRef(url=str(doc), kind="doc", quote=quote),),
    )


def _scopes(quote: str) -> tuple[Scope, ...]:
    """Code in backticks after "do not use" or "avoid" (avoid), or after "use" or "prefer" (prefer).

    Read from prose, so marked as extracted: it may warn, never block.
    """
    avoid = [(m.span(), next(g for g in m.groups() if g)) for m in AVOID.finditer(quote)]
    taken = [span for span, _ in avoid]
    use = [(m.span(), m[1]) for m in USE.finditer(quote) if not any(s <= m.start() < e for s, e in taken)]
    stances = [(v, "avoid") for _, v in avoid] + [(v, "prefer") for _, v in use]
    fields = ({"kind": _kind(v), "value": v, "polarity": p, "quote": quote, "extracted": True} for v, p in stances)
    scopes = (Scope.model_validate(f) for f in fields)
    return tuple(dict.fromkeys(s for s in scopes if looks_like_code(s)))


def _kind(value: str) -> str:
    if "/" in value and not value.startswith("@"):
        return "path"
    return "symbol" if "." in value or value[:1].isupper() else "package"
