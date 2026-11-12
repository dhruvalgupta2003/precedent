"""Score E2: per repo and condition, how often the final code follows the org's current decision."""

import re
import sys
from collections import defaultdict
from pathlib import Path

# repo → (file the task asks for, what following the stale rule looks like)
CHECKS = {
    "http-service": ("src/users.ts", re.compile(r"""from ['"]node-fetch['"]|require\(['"]node-fetch|"node-fetch":""")),
    "web-ui": ("src/Badge.tsx", re.compile(r"\bReact\.FC\b|:\s*FC\s*<|\bFC\b.*from ['\"]react['\"]")),
    "dates-lib": ("src/dates.ts", re.compile(r"""from ['"]moment['"]|require\(['"]moment|"moment"\s*:""")),
}


def outcome(run: Path, repo: str) -> str:
    target, stale = CHECKS[repo]
    # Only the repo's own code: the agent's summary (result.json) mentions the stale rule when explaining it.
    files = [*(run / "src").rglob("*"), run / "package.json"]
    code = "".join(p.read_text() for p in files if p.is_file() and p.suffix in (".ts", ".tsx", ".json"))
    if stale.search(code):
        return "stale"
    return "current" if (run / target).exists() else "other"


def main() -> None:
    table: dict[tuple[str, str], list[str]] = defaultdict(list)
    for run in sorted(Path(sys.argv[1]).iterdir()):
        repo, condition, _ = run.name.rsplit("-", 2)
        table[repo, condition].append(outcome(run, repo))
    for (repo, condition), outcomes in sorted(table.items()):
        print(f"{repo:13} {condition}  {outcomes.count('current')}/{len(outcomes)} current  {outcomes}")  # noqa: T201
    for condition in "ABC":
        all_runs = [o for (_, c), os in table.items() if c == condition for o in os]
        print(f"all repos     {condition}  {all_runs.count('current')}/{len(all_runs)} current")  # noqa: T201


if __name__ == "__main__":
    main()
