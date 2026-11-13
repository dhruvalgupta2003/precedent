"""Command line (docs/spec.md §9): parse input, call the service, print the result. No business logic."""

import argparse
import json
import os
import re
import subprocess
import sys
from functools import partial
from pathlib import Path

import redis
from falkordb import Graph

from precedent import service
from precedent.core.diff import changes
from precedent.core.errors import PrecedentError
from precedent.surfaces.explain import as_json, explain
from precedent.surfaces.hook import change_from_tool, describe, response

EXIT = {"CLEAR": 0, "WARN": 1, "BLOCK": 2}  # spec §9: CI-friendly
HOOK_TOOLS = "Edit|Write|MultiEdit"
GIT = partial(subprocess.run, capture_output=True, text=True, check=False)
CLAUDE_CODE_MODEL = "claude-code:haiku"  # fast and cheap; set PRECEDENT_MODEL_EXTRACT=claude-code:sonnet for more


def org_name(value: str) -> str:
    """The org becomes its own graph's name, so only lowercase letters, digits and '-' are allowed."""
    if not re.fullmatch(r"[a-z0-9-]+", value):
        raise argparse.ArgumentTypeError(f"{value!r}: use lowercase letters, digits and '-'")
    return value


def folder(value: str) -> str:
    if not Path(value).is_dir():
        raise argparse.ArgumentTypeError(f"{value!r} is not a folder")
    return value


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.run(args)
    except redis.ConnectionError as exc:
        print(_no_database(exc), file=sys.stderr)
        return 1
    except PrecedentError as exc:
        print(exc, file=sys.stderr)
        return 1


def run_ingest(args: argparse.Namespace) -> int:
    ai = service.Readers() if args.no_ai else service.readers(_model(args))
    prefix = f"{args.org}/{args.source}" if args.source else args.org
    report = service.ingest(_graph(args.org), args.folder, prefix, ai)
    total = report.written + report.unchanged
    news = f"{report.written} new or changed, {report.unchanged} already up to date"
    print(f"Loaded {total} decision{'' if total == 1 else 's'} into {args.org!r}: {news}.")
    if report.found:
        found = f"Found {report.found} more in other documents"
        print(f"{found}. They are proposed: they can warn, but not stop a change, until someone accepts them.")
    if ai.adrs or ai.docs:
        found, failed = _count(report.scopes, "thing"), _count(report.failed, "file")
        skipped = f"skipped {report.dropped} not quoted word for word or not naming code"
        print(f"The AI found {found} to look for; {skipped}; {failed} failed.")
    return 0


def run_check(args: argparse.Namespace) -> int:
    if args.hook:
        return _hook(args.org)
    found = service.with_files(changes(_change_text(args.diff)), _top() or Path.cwd())
    report = service.preflight(_graph(args.org), found)
    print(report.model_dump_json(indent=2) if args.format == "json" else describe(report))
    return EXIT[report.verdict]


def _change_text(diff: str | None) -> str:
    """A diff file, a piped diff, or (typed at a terminal with nothing piped in) this repo's uncommitted changes."""
    if diff == "-" or (diff is None and not sys.stdin.isatty()):
        return sys.stdin.read()
    return Path(diff).read_text() if diff else _working_changes()


def _working_changes() -> str:
    """`git diff HEAD`, plus new files git doesn't track yet as if every line were added. Paths are repo-relative."""
    top = _top()
    if not top:
        raise PrecedentError("Not inside a git repository. Give a change with --diff FILE, or pipe a diff in.")
    new = GIT(["git", "-C", top, "ls-files", "--others", "--exclude-standard", "-z"]).stdout.split("\0")
    added = (
        f"+++ b/{p}\n" + "".join(f"+{line}\n" for line in (top / p).read_text(errors="replace").splitlines())
        for p in new
        if p
    )
    return GIT(["git", "-C", top, "diff", "HEAD"]).stdout + "".join(added)


def _top() -> Path | None:
    """The git repository this runs in, if any."""
    top = GIT(["git", "rev-parse", "--show-toplevel"]).stdout.strip()
    return Path(top) if top else None


def run_hooks_install(args: argparse.Namespace) -> int:
    """Add the PreToolUse hook to a project's personal settings, or with --user to every repo (ADR0012)."""
    claude = Path.home() / ".claude" if args.user else Path(args.project) / ".claude"
    path = claude / ("settings.json" if args.user else "settings.local.json")
    settings = json.loads(path.read_text()) if path.exists() else {}
    command = f"{Path(sys.argv[0]).resolve()} check --hook --org {args.org}"
    entries = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    if not any("check --hook" in h.get("command", "") for e in entries for h in e.get("hooks", [])):
        entries.append({"matcher": HOOK_TOOLS, "hooks": [{"type": "command", "command": command, "timeout": 10}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"Precedent hook installed in {path} for org {args.org!r}")
    return 0


def run_why(args: argparse.Namespace) -> int:
    """Which decision about something wins, and why (ADR0018). Ends with 1 when no decision is about it."""
    ranked = service.why(_graph(args.org), args.name)
    print(json.dumps(as_json(args.name, ranked), indent=2) if args.format == "json" else explain(args.name, ranked))
    return 0 if ranked else 1


def run_doctor(args: argparse.Namespace) -> int:
    """Instruction-file lines (CLAUDE.md, AGENTS.md, …) that contradict a live decision. Exit 1 if any (CI)."""
    reader = None if args.no_ai else service.default_scope_reader("instructions", _model(args))
    files, found = service.doctor(_graph(args.org), args.project, reader)
    for stale in found:
        print(f'{stale.message}\n    the file says: "{" ".join(stale.quote.split())}"')
        if stale.decision_quote:
            print(f'    {stale.decision} says: "{" ".join(stale.decision_quote.split())}"' + _at(stale.source))
    if not found:
        print(f"No stale lines in {len(files)} instruction file{'s' if len(files) != 1 else ''}.")
    return 1 if found else 0


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _model(args: argparse.Namespace) -> str | None:
    """`--with claude` reads with your own Claude Code (ADR0017); otherwise PRECEDENT_MODEL_EXTRACT, if set."""
    return CLAUDE_CODE_MODEL if args.with_ == "claude" else None


def _at(source: str | None) -> str:
    return f" ({source})" if source else ""


def _hook(org: str) -> int:
    """Claude Code PreToolUse. Fails open: Precedent's own errors never block the agent (H3)."""
    try:
        event = json.load(sys.stdin)
        change = change_from_tool(event)
        found = service.with_files([change], Path(event.get("cwd") or ".")) if change else []
        out = response(service.preflight(_graph(org), found)) if change else None
    except Exception as exc:
        print(f"Precedent hook skipped: {exc}", file=sys.stderr)
        return 0
    if out:
        print(json.dumps(out))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="precedent")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser(
        "load", aliases=["ingest"], help="load decisions from any folder: ADRs, and decisions marked in other Markdown"
    )
    ingest.add_argument("folder", type=folder)
    _org_option(ingest)
    _ai_options(ingest, "skip AI-read scopes (status and links only)")
    ingest.add_argument("--source", type=org_name, help="name this folder (e.g. platform) so ids don't collide")
    ingest.set_defaults(run=run_ingest)
    check = commands.add_parser("check", help="check a diff, or with --hook a Claude Code edit, against decisions")
    _org_option(check)
    check.add_argument(
        "--diff", help="a diff file, or - for stdin (default: what's piped in, else this repo's changes)"
    )
    check.add_argument("--format", choices=["text", "json"], default="text")
    check.add_argument("--hook", action="store_true", help="read a Claude Code PreToolUse event from stdin")
    check.set_defaults(run=run_check)
    _why_command(commands)
    doctor = commands.add_parser("doctor", help="find lines in CLAUDE.md/AGENTS.md that contradict live decisions")
    _org_option(doctor)
    doctor.add_argument("--project", default=".", help="the repository to check (default: here)")
    _ai_options(doctor, "only flag lines that mention what a decision avoids")
    doctor.set_defaults(run=run_doctor)
    hooks = commands.add_parser("hooks", help="manage the Claude Code hook").add_subparsers(
        dest="action", required=True
    )
    install = hooks.add_parser("install", help="add the PreToolUse hook to .claude/settings.local.json")
    _org_option(install)
    where = install.add_mutually_exclusive_group()
    where.add_argument("--project", default=".", help="the repository to install into (default: here)")
    where.add_argument("--user", action="store_true", help="guard every repo you open (~/.claude/settings.json)")
    install.set_defaults(run=run_hooks_install)
    return parser


def _why_command(commands: argparse._SubParsersAction) -> None:
    why = commands.add_parser("why", help="which decision about something wins, and why")
    why.add_argument("name", help="a package, code name or path, for example moment")
    _org_option(why)
    why.add_argument("--format", choices=["text", "json"], default="text")
    why.set_defaults(run=run_why)


def _ai_options(command: argparse.ArgumentParser, no_ai: str) -> None:
    which = command.add_mutually_exclusive_group()
    which.add_argument("--no-ai", action="store_true", help=no_ai)
    which.add_argument(
        "--with", dest="with_", choices=["claude"], help="read with your own Claude Code instead of a model key"
    )


def _org_option(command: argparse.ArgumentParser) -> None:
    """One team needs no --org: it defaults to $PRECEDENT_ORG, else 'team'."""
    default = os.environ.get("PRECEDENT_ORG", "team")
    command.add_argument(
        "--org", type=org_name, default=default, help=f"your team's set of decisions (default: {default})"
    )


def _no_database(exc: Exception) -> str:
    if url := os.environ.get("FALKORDB_URL"):
        return f"No FalkorDB at {url}: {exc}. Is the server running?"
    return (
        "No database. Install Precedent with its built-in one:\n"
        '  uv tool install --force "precedent[embedded] @ git+https://github.com/dhruvalgupta2003/precedent"\n'
        "or start a FalkorDB server: docker run -d -p 6380:6379 falkordb/falkordb:6.0.4"
    )


def _graph(org: str) -> Graph:
    return service.open_graph(org)
