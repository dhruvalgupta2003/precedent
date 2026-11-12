#!/bin/bash
# Doctor on each stale repo, then 3 repos × 3 conditions × 3 runs = 27 sessions (~$1.60 with Sonnet).
E=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$E/../../.." && pwd)
for repo in http-service web-ui dates-lib; do
  D="$ROOT/.cache/experiments/e2-doctor/$repo"; rm -rf "$D"; mkdir -p "$D"; cp -R "$E/repos/$repo/." "$D"; cp "$E/stale/$repo.md" "$D/CLAUDE.md"
  echo "--- doctor: $repo"; (cd "$ROOT" && uv run --locked --env-file .env precedent doctor --org backstage --project "$D" | head -2)
done
for repo in http-service web-ui dates-lib; do
  (for c in A B C; do for i in 1 2 3; do "$E/run.sh" $repo $c $i; done; done) &
done
wait
python3 "$E/score.py" "$ROOT/.cache/experiments/e2"
