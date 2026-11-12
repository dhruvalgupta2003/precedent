#!/bin/bash
# run.sh <repo> <A|B|C> <index>: fresh copy of a fixture repo, one headless Claude Code session, evidence kept.
# A stale CLAUDE.md · B stale + one sentence · C stale + Precedent hook. Decisions live only in the org graph.
set -u
E=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$E/../../.." && pwd); REPO=$1; C=$2; I=$3
R="$ROOT/.cache/experiments/e2/$REPO-$C-$I"
rm -rf "$R"; mkdir -p "$(dirname "$R")"; cp -R "$E/repos/$REPO" "$R"
case $C in
  A|C) cp "$E/stale/$REPO.md" "$R/CLAUDE.md" ;;
  B)   cat "$E/stale/$REPO.md" "$E/sentence.md" > "$R/CLAUDE.md" ;;
esac
if [ "$C" = C ]; then
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
TASK=$(awk -F'\t' -v r="$REPO" '$1 == r {print $2}' "$E/tasks.tsv")
cd "$R" && claude -p "$TASK" \
  --model sonnet --permission-mode acceptEdits --setting-sources project,local --strict-mcp-config \
  --allowedTools Read Write Edit MultiEdit Glob Grep --disallowedTools Bash WebFetch WebSearch Task Agent \
  --no-session-persistence --output-format json < /dev/null > "$R/result.json" 2> "$R/stderr.log"
echo "$REPO-$C-$I done"
