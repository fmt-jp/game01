#!/usr/bin/env bash
# Serve the site and run the checks against it.
#
#   tests/run.sh            every check
#   tests/run.sh maze3d     only the checks whose name contains "maze3d"
#
# Each check prints its own results and exits non-zero if something failed.
set -u
cd "$(dirname "$0")/.."

PORT=8390
python3 -m http.server "$PORT" >/dev/null 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT

for _ in $(seq 20); do
  curl -sf -o /dev/null "http://localhost:$PORT/index.html" && break
  sleep 0.25
done

filter="${1:-}"
failed=0
for check in tests/test_*.py; do
  [ -n "$filter" ] && case "$check" in *"$filter"*) ;; *) continue ;; esac
  echo
  echo "=== $check ==="
  python3 "$check" || { echo "--- FAILED: $check"; failed=1; }
done

echo
if [ "$failed" = 0 ]; then
  echo "no check exited with a failure."
  echo "Note: only some checks decide for themselves — the rest print findings"
  echo "for a person to read and always exit 0. See tests/README.md."
else
  echo "some checks failed"
fi
exit "$failed"
