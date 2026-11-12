"""Command line (docs/spec.md §9): parse input, call the service, print the result. No business logic."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import redis
from falkordb import FalkorDB, Graph

from precedent import service
from precedent.core.diff import changes
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


def run_ingest(args: argparse.Namespace) -> int:
    reader = None if args.no_ai else service.default_scope_reader()
    report = service.ingest(_graph(args.org), args.folder, args.org, reader)
    print(f"{args.org}: {report.written} written, {report.unchanged} unchanged")
    if reader:
        dropped = f"dropped {report.dropped} (quote not in the source, or not code)"
        print(f"AI read {report.scopes} scopes; {dropped}; {report.failed} failed")
    return 0


def run_check(args: argparse.Namespace) -> int:
    if args.hook:
        return _hook(args.org)
    text = sys.stdin.read() if args.diff == "-" else Path(args.diff).read_text()
    report = service.preflight(_graph(args.org), changes(text))
    print(report.model_dump_json(indent=2) if args.format == "json" else describe(report))
    return EXIT[report.verdict]


def run_hooks_install(args: argparse.Namespace) -> int:
    """Add the PreToolUse hook to the project's personal, git-ignored Claude Code settings (spec §9)."""
    path = Path(args.project) / ".claude" / "settings.local.json"
    settings = json.loads(path.read_text()) if path.exists() else {}
    command = f"{Path(sys.argv[0]).resolve()} check --hook --org {args.org}"
    entries = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
    if not any("check --hook" in h.get("command", "") for e in entries for h in e.get("hooks", [])):
        entries.append({"matcher": HOOK_TOOLS, "hooks": [{"type": "command", "command": command, "timeout": 10}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"Precedent hook installed in {path} for org {args.org!r}")
    return 0


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
    ingest = commands.add_parser("ingest", help="read a folder of ADRs into the org's graph")
    ingest.add_argument("folder", type=folder)
    ingest.add_argument("--org", type=org_name, required=True)
    ingest.add_argument("--no-ai", action="store_true", help="skip AI-read scopes (status and links only)")
    ingest.set_defaults(run=run_ingest)
    check = commands.add_parser("check", help="check a diff, or with --hook a Claude Code edit, against decisions")
    check.add_argument("--org", type=org_name, required=True)
    check.add_argument("--diff", default="-", help="unified diff file, or - for stdin (default)")
    check.add_argument("--format", choices=["text", "json"], default="text")
    check.add_argument("--hook", action="store_true", help="read a Claude Code PreToolUse event from stdin")
    check.set_defaults(run=run_check)
    hooks = commands.add_parser("hooks", help="manage the Claude Code hook").add_subparsers(
        dest="action", required=True
    )
    install = hooks.add_parser("install", help="add the PreToolUse hook to .claude/settings.local.json")
    install.add_argument("--org", type=org_name, required=True)
    install.add_argument("--project", default=".", help="the repository to install into (default: here)")
    install.set_defaults(run=run_hooks_install)
    return parser


def _url() -> str:
    return os.environ.get("FALKORDB_URL", "redis://localhost:6380")


def _graph(org: str) -> Graph:
    return FalkorDB.from_url(_url()).select_graph(org)
