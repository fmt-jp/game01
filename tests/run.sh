#!/usr/bin/env bash
# Serve the site and run the checks against it.
#
#   tests/run.sh            every check
#   tests/run.sh maze3d     only the checks whose name contains "maze3d"
#
# Each check prints its own results and exits non-zero if something failed.
set -u
cd "$(dirname "$0")/.."

# Whichever interpreter actually has playwright: the system python3 often does
# not, and a missing import looks like a broken check rather than a setup gap.
PY=""
for candidate in python3 python3.13 python3.12 python3.11; do
  command -v "$candidate" >/dev/null 2>&1 || continue
  if "$candidate" -c "import playwright" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  echo "no python with playwright found. pip install playwright" >&2
  exit 1
fi

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
  "$PY" "$check" || { echo "--- FAILED: $check"; failed=1; }
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
