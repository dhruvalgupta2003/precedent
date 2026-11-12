"""Command line (docs/spec.md §9): parse input, call the service, print the result. No business logic."""

import argparse
import os
import re
import sys
from pathlib import Path

import redis
from falkordb import FalkorDB

from precedent import service


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
    parser = argparse.ArgumentParser(prog="precedent")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="read a folder of ADRs into the org's graph")
    ingest.add_argument("folder", type=folder)
    ingest.add_argument("--org", type=org_name, required=True)
    ingest.add_argument("--no-ai", action="store_true", help="skip AI-read scopes (status and links only)")
    args = parser.parse_args(argv)

    url = os.environ.get("FALKORDB_URL", "redis://localhost:6380")
    try:
        reader = None if args.no_ai else service.default_scope_reader()
        report = service.ingest(FalkorDB.from_url(url).select_graph(args.org), args.folder, args.org, reader)
    except redis.ConnectionError as exc:
        print(f"No FalkorDB at {url}: {exc}. Start it with `docker compose up -d`.", file=sys.stderr)
        return 1
    print(f"{args.org}: {report.written} written, {report.unchanged} unchanged")
    if reader:
        print(f"AI read {report.scopes} scopes; dropped {report.dropped} without a real quote; {report.failed} failed")
    return 0
