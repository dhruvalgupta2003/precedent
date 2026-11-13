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
from falkordb import FalkorDB, Graph

from precedent import service
from precedent.core.diff import changes
from precedent.core.errors import PrecedentError
from precedent.surfaces.hook import change_from_tool, describe, response

EXIT = {"CLEAR": 0, "WARN": 1, "BLOCK": 2}  # spec §9: CI-friendly
HOOK_TOOLS = "Edit|Write|MultiEdit"


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
        print(f"No FalkorDB at {_url()}: {exc}. Start it with `docker compose up -d`.", file=sys.stderr)
        return 1
    except PrecedentError as exc:
        print(exc, file=sys.stderr)
        return 1


def run_ingest(args: argparse.Namespace) -> int:
    reader = None if args.no_ai else service.default_scope_reader()
    prefix = f"{args.org}/{args.source}" if args.source else args.org
    report = service.ingest(_graph(args.org), args.folder, prefix, reader)
    total = report.written + report.unchanged
    news = f"{report.written} new or changed, {report.unchanged} already up to date"
    print(f"Loaded {total} decision{'' if total == 1 else 's'} into {args.org!r}: {news}.")
    if report.found:
        found = f"Found {report.found} more in other documents"
        print(f"{found}. They are proposed: they can warn, but not stop a change, until someone accepts them.")
    if reader:
        skipped = f"skipped {report.dropped} it couldn't quote word for word"
        print(f"The AI found {report.scopes} things to look for; {skipped}; {report.failed} files failed.")
    return 0


def run_check(args: argparse.Namespace) -> int:
    if args.hook:
        return _hook(args.org)
    report = service.preflight(_graph(args.org), changes(_change_text(args.diff)))
    print(report.model_dump_json(indent=2) if args.format == "json" else describe(report))
    return EXIT[report.verdict]


def _change_text(diff: str | None) -> str:
    """A diff file, a piped diff, or (typed at a terminal with nothing piped in) this repo's uncommitted changes."""
    if diff == "-" or (diff is None and not sys.stdin.isatty()):
        return sys.stdin.read()
    return Path(diff).read_text() if diff else _working_changes()


def _working_changes() -> str:
    """`git diff HEAD`, plus new files git doesn't track yet as if every line were added. Paths are repo-relative."""
    git = partial(subprocess.run, capture_output=True, text=True, check=False)
    top = git(["git", "rev-parse", "--show-toplevel"]).stdout.strip()
    if not top:
        raise PrecedentError("Not inside a git repository. Give a change with --diff FILE, or pipe a diff in.")
    new = git(["git", "-C", top, "ls-files", "--others", "--exclude-standard", "-z"]).stdout.split("\0")
    added = (
        f"+++ b/{p}\n" + "".join(f"+{line}\n" for line in (Path(top) / p).read_text(errors="replace").splitlines())
        for p in new
        if p
    )
    return git(["git", "-C", top, "diff", "HEAD"]).stdout + "".join(added)


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


def run_doctor(args: argparse.Namespace) -> int:
    """Instruction-file lines (CLAUDE.md, AGENTS.md, …) that contradict a live decision. Exit 1 if any (CI)."""
    reader = None if args.no_ai else service.default_scope_reader("instructions")
    files, found = service.doctor(_graph(args.org), args.project, reader)
    for stale in found:
        print(f'{stale.message}\n    the file says: "{" ".join(stale.quote.split())}"')
        if stale.decision_quote:
            print(f'    {stale.decision} says: "{" ".join(stale.decision_quote.split())}"' + _at(stale.source))
    if not found:
        print(f"No stale lines in {len(files)} instruction file{'s' if len(files) != 1 else ''}.")
    return 1 if found else 0


def _at(source: str | None) -> str:
    return f" ({source})" if source else ""


def _hook(org: str) -> int:
    """Claude Code PreToolUse. Fails open: Precedent's own errors never block the agent (H3)."""
    try:
        change = change_from_tool(json.load(sys.stdin))
        out = response(service.preflight(_graph(org), [change])) if change else None
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
    ingest.add_argument("--no-ai", action="store_true", help="skip AI-read scopes (status and links only)")
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
    doctor = commands.add_parser("doctor", help="find lines in CLAUDE.md/AGENTS.md that contradict live decisions")
    _org_option(doctor)
    doctor.add_argument("--project", default=".", help="the repository to check (default: here)")
    doctor.add_argument("--no-ai", action="store_true", help="only flag lines that mention what a decision avoids")
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


def _org_option(command: argparse.ArgumentParser) -> None:
    """One team needs no --org: it defaults to $PRECEDENT_ORG, else 'team'."""
    default = os.environ.get("PRECEDENT_ORG", "team")
    command.add_argument(
        "--org", type=org_name, default=default, help=f"your team's set of decisions (default: {default})"
    )


def _url() -> str:
    return os.environ.get("FALKORDB_URL", "redis://localhost:6380")


def _graph(org: str) -> Graph:
    return FalkorDB.from_url(_url()).select_graph(org)
