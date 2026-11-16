"""The CI recipes in docs/ci.md, run the way a CI runner runs them, with stand-ins for git and precedent (#65).

Bugs this guards: an error exited 1, which the GitHub recipe allows as WARN, and a `git diff` that failed piped
nothing into the check, which read as "nothing changed". A recipe must pass only when the diff was really made,
the decisions loaded, and the verdict allows it, and the check must be given the real diff.
"""

import itertools
import re
import subprocess
from pathlib import Path

import pytest
import yaml

CI = (Path(__file__).parents[2] / "docs" / "ci.md").read_text()
DIFF = "+++ b/a.ts\n+import x from 'axios';\n"
# How GitHub runs a step's `run:` on Linux: `bash -e {0}` with no `shell:`, and with pipefail for `shell: bash`.
GITHUB_SHELL = {None: ["bash", "-e"], "bash": ["bash", "--noprofile", "--norc", "-eo", "pipefail"]}

GIT = """#!/bin/sh
if [ "$GIT_FAILS" = 1 ]; then echo "fatal: bad revision" >&2; exit 128; fi
printf '%s' "$DIFF"
"""
PRECEDENT = """#!/bin/sh
case "$1" in
  load) exit "$LOAD" ;;
  check)
    shift
    file=-
    while [ $# -gt 0 ]; do [ "$1" = --diff ] && file=$2; shift; done
    if [ "$file" = - ]; then cat > "$SEEN"; else cat "$file" > "$SEEN"; fi
    exit "$VERDICT" ;;
esac
exit 99
"""


def stand_ins(tmp: Path) -> Path:
    bin_ = tmp / "bin"
    bin_.mkdir()
    for name, text in [("git", GIT), ("precedent", PRECEDENT)]:
        (bin_ / name).write_text(text)
        (bin_ / name).chmod(0o755)
    return bin_


def code_block(language: str, text: str) -> str:
    found = re.search(rf"```{language}\n(.*?)```", text, re.S)
    assert found, f"no {language} block in docs/ci.md"
    return found.group(1)


def run(tmp: Path, shell: list[str], script: str, **given: str) -> tuple[bool, str | None]:
    """Run the recipe; return whether it passed and what the check was given (None if it never ran)."""
    (tmp / "step.sh").write_text(script)
    env = {"PATH": f"{stand_ins(tmp)}:/usr/bin:/bin", "BASE": "main", "RUNNER_TEMP": str(tmp), "DIFF": DIFF}
    env |= {"SEEN": str(tmp / "seen"), "LOAD": "0", "GIT_FAILS": "0", "VERDICT": "0"} | given
    step = subprocess.run([*shell, str(tmp / "step.sh")], cwd=tmp, env=env, check=False)  # noqa: S603 (our own recipe)
    passed = step.returncode == 0
    seen = tmp / "seen"
    return passed, seen.read_text() if seen.exists() else None


def github_step() -> dict:
    workflow = yaml.safe_load(code_block("yaml", CI))
    return next(s for s in workflow["jobs"]["precedent"]["steps"] if s.get("name") == "Stop on BLOCK, allow WARN")


GITHUB = list(itertools.product([False, True], [0, 1, 2, 3]))


@pytest.mark.parametrize(("git_fails", "verdict"), GITHUB, ids=[f"git-{'fails' if g else 'ok'}-{v}" for g, v in GITHUB])
def test_the_github_recipe_passes_only_on_a_real_diff_that_is_clear_or_warn(tmp_path, git_fails, verdict):
    step = github_step()

    passed, seen = run(
        tmp_path, GITHUB_SHELL[step.get("shell")], step["run"], GIT_FAILS=str(int(git_fails)), VERDICT=str(verdict)
    )

    assert passed == (not git_fails and verdict in (0, 1))
    if not git_fails:
        assert seen == DIFF  # the check was given the real change, not an empty one


def anywhere_else() -> str:
    """The commands in the "Anywhere else" recipe, without the install line."""
    section = CI.split("## Anywhere else", 1)[1]
    block = code_block("sh", section)
    return "".join(line + "\n" for line in block.splitlines() if not line.startswith("uv "))


ELSEWHERE = list(itertools.product([0, 3], [False, True], [0, 1, 2, 3]))


@pytest.mark.parametrize(
    ("load", "git_fails", "verdict"),
    ELSEWHERE,
    ids=[f"load-{x}-git-{'fails' if g else 'ok'}-{v}" for x, g, v in ELSEWHERE],
)
def test_the_plain_recipe_stops_on_any_failure_and_never_checks_after_a_failed_load(tmp_path, load, git_fails, verdict):
    given = {"LOAD": str(load), "GIT_FAILS": str(int(git_fails)), "VERDICT": str(verdict)}

    passed, seen = run(tmp_path, ["sh"], anywhere_else(), **given)

    assert passed == (load == 0 and not git_fails and verdict == 0)
    if load or git_fails:
        assert seen is None  # nothing was checked against an empty database or an empty change
    else:
        assert seen == DIFF
