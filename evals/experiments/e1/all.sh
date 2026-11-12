#!/bin/bash
# Every condition, 5 runs each (D: 3), conditions in parallel. About 38 sessions, ~$2 with Sonnet.
E=$(cd "$(dirname "$0")" && pwd)
for c in A B C A2 B2 C2; do (for i in 1 2 3 4 5; do "$E/run.sh" $c $i; done) & done
(for i in 1 2 3; do "$E/run.sh" D $i; done) &
wait
python3 "$E/score.py" "$(cd "$E/../../.." && pwd)/.cache/experiments/e1"
