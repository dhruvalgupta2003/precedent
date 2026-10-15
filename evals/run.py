"""Run the golden eval suites and enforce their gates (ADR0006, docs/spec.md §11b).

Usage: uv run --locked python evals/run.py [suite ...] [--strict]

A scorer turns one case into (passed, got). Until the feature a suite tests exists, its scorer
raises NotImplementedError (or the import fails) and the case is PENDING, not failed.
Gates apply to the cases that ran; --strict also fails on anything still pending (release gate).
"""

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

HERE = Path(__file__).parent
RESULTS = HERE.parent / ".cache" / "evals"

Case = dict[str, Any]
Scorer = Callable[[Case], tuple[bool, Any]]
Status = Literal["pass", "fail", "pending"]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    status: Status
    expected: Any = None
    got: Any = None


def load(suite: str) -> Iterator[Case]:
    for line in (HERE / f"{suite}.jsonl").read_text().splitlines():
        if line.strip():
            yield json.loads(line)


def run_case(scorer: Scorer, case: Case) -> CaseResult:
    try:
        passed, got = scorer(case)
    except (NotImplementedError, ImportError):
        return CaseResult(case["id"], "pending", case["expected"])
    return CaseResult(case["id"], "pass" if passed else "fail", case["expected"], got)


# ---------- scorers: filled in as each feature lands ----------


def _not_built(case: Case) -> tuple[bool, Any]:
    raise NotImplementedError


SCORERS: dict[str, Scorer] = {
    "preflight": _not_built,
    "why": _not_built,
    "extraction": _not_built,
    "safety": _not_built,
    "session_capture": _not_built,
}

# Minimum pass rate per suite over the cases that ran (spec §11b; finer metrics join their scorers).
MIN_PASS = {"preflight": 0.9, "why": 0.95, "extraction": 0.85, "safety": 1.0, "session_capture": 0.8}


def false_blocks(results: list[CaseResult]) -> int:
    """A BLOCK on a case that expected anything else: the one error Precedent must never make."""
    return sum(1 for r in results if r.got == "BLOCK" and r.expected.get("verdict") != "BLOCK")


def gate(suite: str, results: list[CaseResult]) -> tuple[str, str]:
    ran = [r for r in results if r.status != "pending"]
    if not ran:
        return "PENDING", f"0/{len(results)} implemented"
    rate = sum(r.status == "pass" for r in ran) / len(ran)
    problems = [f"pass rate {rate:.0%} < {MIN_PASS[suite]:.0%}"] if rate < MIN_PASS[suite] else []
    if suite == "preflight" and (fb := false_blocks(ran)):
        problems.append(f"{fb} false BLOCK")
    summary = f"{len(ran)}/{len(results)} ran, pass {rate:.0%}"
    return ("FAIL", f"{summary} · {'; '.join(problems)}") if problems else ("PASS", summary)


def commit() -> str:
    """Short SHA of HEAD, so every saved result says which code produced it."""
    git = shutil.which("git")  # absolute path: never run whatever "git" is first on PATH
    if git is None:
        return "unknown"
    out = subprocess.run([git, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=False)  # noqa: S603 - fixed arguments
    return out.stdout.strip() or "unknown"


def save(suite: str, results: list[CaseResult]) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {"suite": suite, "commit": commit(), "cases": [asdict(r) for r in results]}
    (RESULTS / f"{suite}.json").write_text(json.dumps(payload, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("suites", nargs="*", choices=list(SCORERS), metavar="suite", help="default: all")
    parser.add_argument("--strict", action="store_true", help="treat pending cases as failures")
    args = parser.parse_args(argv)
    failed = False
    for suite in args.suites or list(SCORERS):
        results = [run_case(SCORERS[suite], case) for case in load(suite)]
        save(suite, results)
        verdict, detail = gate(suite, results)
        failed |= verdict == "FAIL" or (args.strict and verdict == "PENDING")
        print(f"{suite:16} {verdict:8} {detail}")  # noqa: T201 - a CLI report
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
