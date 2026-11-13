"""The docs website must match the code. A new option or a version bump fails here until the docs say so.

Runs before every push (pre-push hook: `make docs-check`) and in CI.
"""

import argparse
import re
import tomllib
from collections.abc import Iterator
from pathlib import Path

import pytest

from precedent.surfaces.cli import _parser

ROOT = Path(__file__).parents[2]
COMMANDS_PAGE = ROOT / "docs" / "reference" / "commands.md"


def commands(parser: argparse.ArgumentParser, name: str = "precedent") -> Iterator[tuple[str, list[str]]]:
    """Every runnable command with its long options, e.g. ("precedent hooks install", ["--org", "--user"])."""
    subparsers = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    if not subparsers:
        yield name, [o for a in parser._actions for o in a.option_strings if o.startswith("--") and o != "--help"]
    for sub in subparsers:
        for child, child_parser in sub.choices.items():
            yield from commands(child_parser, f"{name} {child}")


@pytest.mark.parametrize(("command", "options"), list(commands(_parser())), ids=str)
def test_every_command_and_option_is_on_the_commands_page(command, options):
    page = COMMANDS_PAGE.read_text()

    assert f"`{command}" in page, f"{command} has no section in {COMMANDS_PAGE.name}"
    assert [o for o in options if f"`{o}" not in page] == []


def test_install_lines_pin_the_current_version():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    pages = [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]

    pins = {(p.name, pin) for p in pages for pin in re.findall(r"precedent@v([\d.]+)", p.read_text())}

    assert pins, "no install line pins a version"
    assert {pin for _, pin in pins} == {version}, sorted(pins)
