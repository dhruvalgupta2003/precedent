"""Score each E1 run: did the final code follow the current decision (native fetch) or the stale one (node-fetch)?"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

runs = Path(sys.argv[1])
NODE_FETCH = re.compile(r"""from ['"]node-fetch['"]|require\(['"]node-fetch['"]\)|"node-fetch"\s*:""")
table = defaultdict(list)
for r in sorted(runs.iterdir()):
    users = r / "plugins/catalog-backend/src/service/users.ts"
    code = "".join(p.read_text() for p in (r / "plugins").rglob("*") if p.is_file() and p.suffix in (".ts", ".json"))
    if NODE_FETCH.search(code):
        outcome = "stale (node-fetch)"
    elif users.exists() and "fetch(" in users.read_text():
        outcome = "current (native fetch)"
    else:
        outcome = "other"
    result = json.loads((r / "result.json").read_text() or "{}") if (r / "result.json").exists() else {}
    warned = (r / "hook-out.log").exists() and "additionalContext" in (r / "hook-out.log").read_text()
    table[r.name.split("-")[0]].append((r.name, outcome, round(result.get("total_cost_usd", 0), 3), warned))
for cond, rows in sorted(table.items()):
    current = sum(o.startswith("current") for _, o, _, _ in rows)
    print(f"{cond}: {current}/{len(rows)} followed the current decision · cost ${sum(c for *_, c, _ in rows):.2f}")  # noqa: T201 - a report
    for name, outcome, cost, warned in rows:
        print(f"   {name:5} {outcome:24} ${cost:<6}" + ("  hook warned" if warned else ""))  # noqa: T201 - a report
