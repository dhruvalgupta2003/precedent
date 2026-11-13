"""The Precedent facade every surface calls (ADR0009)."""

import os
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Literal, NamedTuple

from falkordb import Graph

from precedent.adapters.falkor import connect, ensure_schema, found_urls, retire_found, rules, save_decision
from precedent.connectors import adr, folder
from precedent.core.diff import Change, facts
from precedent.core.doctor import StaleLine, mentions, stale_lines
from precedent.core.errors import ExtractionError
from precedent.core.grounding import keep_grounded
from precedent.core.model import DecisionRecord, Scope
from precedent.core.preflight import Report, check

ScopeReader = Callable[[str], list[Scope]]


class IngestReport(NamedTuple):
    written: int = 0
    unchanged: int = 0
    scopes: int = 0  # AI-read scopes kept
    dropped: int = 0  # AI-read scopes whose quote isn't in the source or whose value isn't code
    failed: int = 0  # sources the AI could not read; their decisions are still saved
    found: int = 0  # decisions found in ordinary documents (ADR0014): proposed, may warn, never block


def ingest(graph: Graph, root: str, org: str, read_scopes: ScopeReader | None = None) -> IngestReport:
    """Load any folder (ADR0014): its ADRs wherever they are, and the decisions marked in its other documents.

    `org` may be "org/source" to keep this folder's decision ids apart from another's (ADR0012). With ADRs in more
    than one folder, each folder's ids are qualified by its path, so two ADR0001s don't collide.
    """
    ensure_schema(graph)
    counts: Counter[str] = Counter()
    org, _, source = org.partition("/")
    plan = folder.scan(Path(root))
    for adr_folder in plan.adr_folders:
        name = _source(source, adr_folder, Path(root)) if len(plan.adr_folders) > 1 else source or None
        for parsed in adr.records(str(adr_folder), org, name):
            record = _with_scopes(parsed, read_scopes, counts) if read_scopes else parsed
            counts["written" if save_decision(graph, record) else "unchanged"] += 1
    counts["found"] = _load_docs(graph, plan.docs, Path(root), f"{org}/{source}" if source else org)
    return IngestReport(**counts)


def _source(source: str, adr_folder: Path, root: Path) -> str:
    """'docs/adr' → 'docs-adr' (after any --source name), so ids from different folders stay apart."""
    where = adr.slug(adr_folder.relative_to(root).as_posix() if adr_folder != root else root.resolve().name)
    return f"{source}-{where}" if source else where


def _load_docs(graph: Graph, docs: list[Path], root: Path, prefix: str) -> int:
    """Save what the documents mark as decisions, and retire what they (or deleted documents) no longer say."""
    found = [record for doc in docs for record in folder.found_in(doc, root, prefix)]
    for record in found:
        save_decision(graph, record)
    under = "" if str(root) == "." else f"{root}/"
    gone = [u for u in found_urls(graph, f"{prefix}/") if _inside(u, under) and not Path(u).exists()]
    retire_found(graph, f"{prefix}/", [str(d) for d in docs] + gone, [r.id for r in found])
    return len(found)


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


def preflight(graph: Graph, changes: list[Change]) -> Report:
    """Check a change against every live decision in the org's graph (docs/spec.md §7)."""
    return check(facts(changes), rules(graph))


def default_scope_reader(kind: Literal["adr", "instructions"] = "adr") -> ScopeReader | None:
    """The configured extraction model (PRECEDENT_MODEL_EXTRACT), or None to work without AI."""
    model = os.environ.get("PRECEDENT_MODEL_EXTRACT")
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
