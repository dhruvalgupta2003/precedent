#!/bin/bash
# run.sh <condition> <index>: build a fresh fixture repo, run one headless Claude Code session, keep evidence.
# Conditions: A stale CLAUDE.md · B stale + one sentence · C stale + Precedent hook · D no CLAUDE.md
#             A2/B2/C2: the same, in a repo where the current decision exists only in Precedent's org graph.
# Needs: `claude` on PATH, FalkorDB running, and the backstage org ingested (see README.md).
set -u
E=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$E/../../.." && pwd); C=$1; I=$2
R="$ROOT/.cache/experiments/e1/$C-$I"
case $C in *2) BASE=base2 ;; *) BASE=base ;; esac
rm -rf "$R"; mkdir -p "$(dirname "$R")"; cp -R "$E/$BASE" "$R"
case $C in
  A|C|A2|C2) cp "$E/stale.md" "$R/CLAUDE.md" ;;
  B|B2)      cat "$E/stale.md" "$E/sentence.md" > "$R/CLAUDE.md" ;;
esac
if [ "$C" = C ] || [ "$C" = C2 ]; then
  (cd "$ROOT" && uv run --locked precedent hooks install --org backstage --project "$R" >/dev/null)
  python3 - "$R" <<'PY'
import json, pathlib, sys
p = pathlib.Path(sys.argv[1]) / ".claude" / "settings.local.json"
s = json.loads(p.read_text())
h = s["hooks"]["PreToolUse"][0]["hooks"][0]
h["command"] = f'tee -a {sys.argv[1]}/hook-in.log | {h["command"]} | tee -a {sys.argv[1]}/hook-out.log'
p.write_text(json.dumps(s, indent=2))
PY
fi
cd "$R" && claude -p "Add a fetchUsers() function to plugins/catalog-backend/src/service/users.ts that GETs https://example.com/api/users and returns the parsed JSON. Follow this repository's conventions." \
  --model sonnet --permission-mode acceptEdits --setting-sources project,local --strict-mcp-config \
  --allowedTools Read Write Edit MultiEdit Glob Grep --disallowedTools Bash WebFetch WebSearch Task Agent \
  --no-session-persistence --output-format json < /dev/null > "$R/result.json" 2> "$R/stderr.log"
echo "$C-$I done"
