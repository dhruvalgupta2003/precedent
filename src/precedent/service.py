"""The Precedent facade every surface calls (ADR0009)."""

import os
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

from falkordb import Graph

from precedent.adapters.falkor import (
    connect,
    ensure_schema,
    found_quotes,
    found_urls,
    retire_found,
    rules,
    save_decision,
)
from precedent.connectors import adr, folder
from precedent.core.authority import Standing, resolve
from precedent.core.diff import Change, facts
from precedent.core.doctor import StaleLine, mentions, stale_lines
from precedent.core.errors import ExtractionError
from precedent.core.grounding import grounded, keep_grounded
from precedent.core.model import DecisionRecord, Scope
from precedent.core.preflight import Report, check

if TYPE_CHECKING:
    from precedent.adapters.llm import Kind

ScopeReader = Callable[[str], list[Scope]]


class Readers(NamedTuple):
    """The AI readers for one load (ADR0014): one for ADRs, one for ordinary documents. None: no AI."""

    adrs: ScopeReader | None = None
    docs: ScopeReader | None = None


class _Docs(NamedTuple):
    """The ordinary documents of one load, the folder they were loaded from, and the id prefix for what's found."""

    paths: list[Path]
    root: Path
    prefix: str


class IngestReport(NamedTuple):
    written: int = 0
    unchanged: int = 0
    scopes: int = 0  # AI-read scopes kept
    dropped: int = 0  # AI-read scopes whose quote isn't in the source or whose value isn't code
    failed: int = 0  # sources the AI could not read; their decisions are still saved
    found: int = 0  # decisions found in ordinary documents (ADR0014): proposed, may warn, never block


def ingest(graph: Graph, root: str, org: str, ai: Readers = Readers()) -> IngestReport:  # noqa: B008 (immutable)
    """Load any folder (ADR0014): its ADRs wherever they are, and the decisions marked in its other documents.

    `org` may be "org/source" to keep this folder's decision ids apart from another's (ADR0012). With ADRs in more
    than one folder, each folder's ids are qualified by its path, so two ADR0001s don't collide.
    """
    counts: Counter[str] = Counter()
    org, _, source = org.partition("/")
    plan = folder.scan(Path(root))
    named = len(plan.adr_folders) > 1
    # Read and check every folder before writing anything: a team's decisions load all at once or not at all.
    found = [
        parsed
        for adr_folder in plan.adr_folders
        for parsed in adr.records(
            str(adr_folder), org, _source(source, adr_folder, Path(root)) if named else source or None
        )
    ]
    ensure_schema(graph)
    for parsed in found:
        record = _with_scopes(parsed, ai.adrs, counts) if ai.adrs else parsed
        counts["written" if save_decision(graph, record) else "unchanged"] += 1
    docs = _Docs(plan.docs, Path(root), f"{org}/{source}" if source else org)
    counts["found"] = _load_docs(graph, docs, ai.docs, counts)
    return IngestReport(**counts)


def _source(source: str, adr_folder: Path, root: Path) -> str:
    """'docs/adr' → 'docs-adr' (after any --source name), so ids from different folders stay apart."""
    where = adr.slug(adr_folder.relative_to(root).as_posix() if adr_folder != root else root.resolve().name)
    return f"{source}-{where}" if source else where


def _load_docs(graph: Graph, docs: _Docs, read: ScopeReader | None, counts: Counter[str]) -> int:
    """Save the decisions found in the documents, and retire those whose sentence (or document) is gone.

    A found decision stays while its quote is still in its document, whoever found it: a later load without an AI
    (a teammate, CI) must not silently undo what the AI found.
    """
    found = [record for doc in docs.paths for record in _found_in(doc, docs, read, counts)]
    for record in found:
        save_decision(graph, record)
    prefix, urls = f"{docs.prefix}/", [str(d) for d in docs.paths]
    still = [i for i, url, quote in found_quotes(graph, prefix, urls) if grounded(quote, folder.body(Path(url)))]
    under = "" if str(docs.root) == "." else f"{docs.root}/"
    gone = [u for u in found_urls(graph, prefix) if _inside(u, under) and not Path(u).exists()]
    retire_found(graph, prefix, urls + gone, [r.id for r in found] + still)
    return len(found)


def _found_in(doc: Path, docs: _Docs, read: ScopeReader | None, counts: Counter[str]) -> list[DecisionRecord]:
    """The marked decisions in a document and, with an AI, the decisions it states in plain prose (ADR0014)."""
    marked = folder.found_in(doc, docs.root, docs.prefix)
    if read is None:
        return marked
    text = folder.body(doc)
    try:
        scopes = read(text)
    except ExtractionError:
        counts["failed"] += 1
        return marked
    kept = keep_grounded(scopes, text)
    counts["scopes"] += len(kept)
    counts["dropped"] += len(scopes) - len(kept)
    return folder.merge(marked + folder.from_scopes(doc, docs.root, docs.prefix, kept))


def _inside(url: str, under: str) -> bool:
    """A document under the loaded folder. Loading "." covers the current folder, not ../ or absolute paths."""
    return url.startswith(under) if under else not url.startswith(("/", "../"))


def open_graph(org: str) -> Graph:
    """The org's graph: on the server at FALKORDB_URL, else in the built-in database (ADR0015)."""
    return connect(os.environ.get("FALKORDB_URL"), database_path()).select_graph(org)


def database_path() -> Path:
    """Where the built-in database keeps its file: $PRECEDENT_DB, else the user's data folder."""
    if path := os.environ.get("PRECEDENT_DB"):
        return Path(path)
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "precedent" / "precedent.db"


def with_files(changes: list[Change], root: Path) -> list[Change]:
    """Each change with its file as it is on disk, so pre-flight knows the names the file already imports (ADR0016).
    Only files inside `root` are read: a diff's paths come from outside and could point anywhere."""
    return [change._replace(context=_lines(root, change.path)) for change in changes]


MAX_FILE_BYTES = 1_000_000  # bigger files are generated or minified, and the hook runs on every edit


def _lines(root: Path, path: str) -> tuple[str, ...]:
    """The file's lines, or none if it is outside `root`, missing, too big, or can't be opened. Then the change is
    checked as if the file were new: a path the system rejects (a null byte, a name too long) must not crash the
    check, because a crash exits 1 like a WARN and would hide a BLOCK elsewhere in the diff."""
    try:
        file = (root / path).resolve()
        inside = file.is_relative_to(root.resolve()) and file.is_file()
        if not inside or file.stat().st_size > MAX_FILE_BYTES:
            return ()
        return tuple(file.read_text(errors="replace").splitlines())
    except (OSError, ValueError):
        return ()


ORDER = {"wins": 0, "disputed": 0, "outranked": 1, "replaced": 2, "retired": 3}


def why(graph: Graph, name: str) -> dict[tuple[str, str], list[Standing]]:
    """Every decision about `name` (a package, a symbol, a path…), the one that wins first, each with its reason."""
    ranked = resolve(r for r in rules(graph) if r.scope.value.lower() == name.lower())
    return {
        thing: sorted(standings, key=lambda s: (ORDER[s.outcome], s.rule.decision))
        for thing, standings in ranked.items()
    }


def preflight(graph: Graph, changes: list[Change]) -> Report:
    """Check a change against every live decision in the org's graph (docs/spec.md §7)."""
    return check(facts(changes), rules(graph))


def readers(model: str | None = None) -> Readers:
    """The AI readers for a load: the given model, else PRECEDENT_MODEL_EXTRACT; none without a model."""
    return Readers(default_scope_reader("adr", model), default_scope_reader("docs", model))


def default_scope_reader(kind: "Kind" = "adr", model: str | None = None) -> ScopeReader | None:
    """The given extraction model, else the configured one (PRECEDENT_MODEL_EXTRACT), else None to work without AI."""
    model = model or os.environ.get("PRECEDENT_MODEL_EXTRACT")
    if not model:
        return None
    # Imported here: the AI library takes ~0.35 s to load, and the hook, which never uses it, runs on every edit.
    from precedent.adapters.llm import scope_reader  # noqa: PLC0415

    return scope_reader(model, cache_dir=extract_cache_dir(), kind=kind)


def extract_cache_dir() -> Path:
    """The user's cache folder, never the repo being checked."""
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "precedent" / "extract"


# Where coding agents read their instructions; nested CLAUDE.md/AGENTS.md count too.
INSTRUCTION_FILES = (
    "CLAUDE.md",
    "AGENTS.md",
    ".cursorrules",
    ".github/copilot-instructions.md",
    ".cursor/rules/*.md*",
    "**/CLAUDE.md",
    "**/AGENTS.md",
)


def doctor(graph: Graph, project: str, read_stances: ScopeReader | None = None) -> tuple[list[Path], list[StaleLine]]:
    """Instruction-file lines in a project that contradict a live decision (scenario R1)."""
    root = Path(project)
    files = sorted({p for pattern in INSTRUCTION_FILES for p in root.glob(pattern) if _instruction_file(p, root)})
    live = rules(graph)
    found: list[StaleLine] = []
    for path in files:
        text, name = path.read_text(errors="replace"), str(path.relative_to(root))
        try:
            stances = keep_grounded(read_stances(text), text) if read_stances else None
        except ExtractionError:
            stances = None
        found += stale_lines(name, text, stances, live) if stances is not None else mentions(name, text, live)
    return files, found


def _instruction_file(path: Path, root: Path) -> bool:
    return path.is_file() and not {"node_modules", ".git"} & set(path.relative_to(root).parts)


def _with_scopes(record: DecisionRecord, read_scopes: ScopeReader, counts: Counter[str]) -> DecisionRecord:
    text = adr.text(Path(record.sources[0].url))
    try:
        found = read_scopes(text)
    except ExtractionError:
        counts["failed"] += 1
        return record
    kept = keep_grounded(found, text)
    counts["scopes"] += len(kept)
    counts["dropped"] += len(found) - len(kept)
    declared = {(s.kind, s.value, s.polarity) for s in record.scopes}  # reviewed knowledge wins (ADR0013)
    extra = tuple(s for s in kept if (s.kind, s.value, s.polarity) not in declared)
    return record.model_copy(update={"scopes": record.scopes + extra})
