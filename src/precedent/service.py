"""The Precedent facade every surface calls (ADR0009)."""

import os
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Literal, NamedTuple

from falkordb import Graph

from precedent.adapters.falkor import ensure_schema, rules, save_decision
from precedent.adapters.llm import scope_reader
from precedent.connectors import adr
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


def ingest(graph: Graph, folder: str, org: str, read_scopes: ScopeReader | None = None) -> IngestReport:
    """Save every ADR in the folder into the org's graph, with AI-read scopes when a reader is given."""
    ensure_schema(graph)
    counts: Counter[str] = Counter()
    for parsed in adr.records(folder, org):
        record = _with_scopes(parsed, read_scopes, counts) if read_scopes else parsed
        counts["written" if save_decision(graph, record) else "unchanged"] += 1
    return IngestReport(**counts)


def preflight(graph: Graph, changes: list[Change]) -> Report:
    """Check a change against every live decision in the org's graph (docs/spec.md §7)."""
    return check(facts(changes), rules(graph))


def default_scope_reader(kind: Literal["adr", "instructions"] = "adr") -> ScopeReader | None:
    """The configured extraction model (PRECEDENT_MODEL_EXTRACT), or None to work without AI."""
    model = os.environ.get("PRECEDENT_MODEL_EXTRACT")
    return scope_reader(model, cache_dir=Path(".cache/precedent/extract"), kind=kind) if model else None


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
    return record.model_copy(update={"scopes": tuple(kept)})
