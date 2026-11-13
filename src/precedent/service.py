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
    note_commit,
    origins,
    retire_found,
    retire_gone,
    rules,
    save_decision,
)
from precedent.connectors import adr, folder
from precedent.core.authority import Standing, resolve
from precedent.core.diff import Change, facts
from precedent.core.doctor import StaleLine, mentions, stale_lines
from precedent.core.errors import ExtractionError, KnowledgeError
from precedent.core.grounding import grounded, keep_grounded
from precedent.core.model import DecisionRecord, Origin, Scope
from precedent.core.origin import Earlier, Proof, Reach, clashes, covers, repo_name, retired, taken_without_origin
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
    retired: int = 0  # decisions whose file this checkout proves is gone (ADR0021)


def ingest(graph: Graph, root: str, org: str, ai: Readers = Readers()) -> IngestReport:  # noqa: B008 (immutable)
    """Load any folder (ADR0014): its ADRs wherever they are, and the decisions marked in its other documents.

    `org` may be "org/source" to keep this folder's decision ids apart from another's (ADR0012). With ADRs in more
    than one folder, each folder's ids are qualified by its path, so two ADR0001s don't collide.
    """
    counts: Counter[str] = Counter()
    org, _, source = org.partition("/")
    plan = folder.scan(Path(root))
    where = _where(Path(root))
    decisions = [_with_origin(d, where, Path(root)) for d in _read_all(plan.adr_folders, Path(root), org, source)]
    ensure_schema(graph)
    earlier = _claim(graph, decisions, where)
    # The AI reads before the first write too, so nothing is written until everything has been read and checked.
    decisions = [_with_scopes(d, ai.adrs, counts) if ai.adrs else d for d in decisions]
    for record in decisions:
        counts["written" if save_decision(graph, record) else "unchanged"] += 1
    counts["retired"] = _retire(graph, decisions, earlier, where)
    docs = _Docs(plan.docs, Path(root), f"{org}/{source}" if source else org)
    counts["found"] = _load_docs(graph, docs, ai.docs, counts)
    return IngestReport(**counts)


def _read_all(adr_folders: list[Path], root: Path, org: str, source: str) -> list[DecisionRecord]:
    """Every folder's decisions, read and checked before anything is written (ADR0020): two files that would be the
    same decision stop the load, whether they sit in one folder or in folders whose names read the same."""
    name = {f: _source(source, f, root) if len(adr_folders) > 1 else source or None for f in adr_folders}
    decisions = [record for f in adr_folders for record in adr.records(str(f), org, name[f], root)]
    adr.one_file_per_id((d.id, Path(os.path.relpath(d.sources[0].url, root)).as_posix()) for d in decisions)
    return decisions


class Where(NamedTuple):
    """The repository a load runs in, and what of it the load owns (ADR0021)."""

    repo: folder.Repository
    reach: Reach


def _where(root: Path) -> Where | None:
    """None outside a git repository with a name: then decisions keep no origin, and nothing is refused or retired.

    The name is the `origin` remote (so a laptop and CI agree), else PRECEDENT_REPO for a repository without one.
    """
    repo = folder.repository(root)
    if repo is None:
        return None
    name = repo_name(repo.remote) or _named(os.environ.get("PRECEDENT_REPO"))
    return Where(repo, Reach(name, repo.prefix)) if name else None


def _named(value: str | None) -> str | None:
    """PRECEDENT_REPO as a repository name, normalised like a remote so a token in it is never kept."""
    if not value:
        return None
    if name := repo_name(value):
        return name
    raise KnowledgeError("PRECEDENT_REPO doesn't name a repository: use host/owner/name, like github.com/acme/web")


def _with_origin(record: DecisionRecord, where: Where | None, root: Path) -> DecisionRecord:
    """The file's path inside the repository: git's path to the loaded folder plus the file's path inside it, never
    a resolved path, so a symlinked file is known by the link's own place."""
    if where is None:
        return record
    path = where.reach.under + Path(os.path.relpath(record.sources[0].url, root)).as_posix()
    return record.model_copy(update={"origin": Origin(repo=where.reach.repo, path=path)})


def _claim(graph: Graph, decisions: list[DecisionRecord], where: Where | None) -> list[Earlier]:
    """The decisions this load may touch, after refusing to take an id from a file it doesn't own. A load from
    outside a git repository with a name owns nothing, so it may never take an id a repository owns."""
    ids = [d.id for d in decisions]
    earlier = origins(graph, ids, where.reach.repo if where else "")
    loaded = [(e.decision, e.origin) for e in earlier]
    if where is None:
        found = taken_without_origin(ids, loaded)
    else:
        found = clashes([(d.id, d.origin) for d in decisions if d.origin], loaded, where.reach)
    if found:
        raise KnowledgeError(
            "; ".join(found) + ". To keep both, load this folder with --source NAME (for example its repository's"
            " name), or load the folder that holds both if they are in one repository"
        )
    return earlier if where else []


def _retire(graph: Graph, decisions: list[DecisionRecord], earlier: list[Earlier], where: Where | None) -> int:
    """Note the commit each committed decision file is in, then retire what this checkout proves is gone: a file
    that is neither in the checked-out commit nor on disk, last seen at a commit in this checkout's history."""
    committed = folder.committed(where.repo) if where else None
    if where is None or committed is None:
        return 0
    if where.repo.head:
        note_commit(graph, [d.id for d in decisions if d.origin and d.origin.path in committed], where.repo.head)
    owned = [e for e in earlier if e.origin and covers(where.reach, e.origin)]
    missing = [e for e in owned if e.origin and _gone_from(e.origin.path, committed, where.repo.top)]
    asked = {c for e in missing for c in (e.commit, e.last) if c}
    proof = Proof(
        read=frozenset(d.origin.path for d in decisions if d.origin),
        missing=frozenset(e.origin.path for e in missing if e.origin),
        history=frozenset(c for c in asked if folder.in_history(where.repo, c)),
    )
    gone = retired(earlier, {d.id for d in decisions}, where.reach, proof)
    retire_gone(graph, gone)
    return len(gone)


def _gone_from(path: str, committed: set[str], top: Path) -> bool:
    """Not in the checked-out commit and not on disk: a sparse checkout or a skipped folder doesn't count."""
    return path not in committed and not (top / path).exists()


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
    """An instruction file of this project: a symbolic link that leads outside it is never read or quoted."""
    return adr.inside(path, root) and not {"node_modules", ".git"} & set(path.relative_to(root).parts)


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
