#!/usr/bin/env bash
# Run the release gate N times in a row on this checkout, and read pytest's OWN exit code.
#
# CLAUDE.md: a release needs THREE CONSECUTIVE green `--runslow` gates on the final,
# version-bumped tree, each "N passed" with no "failed", exit 0 read from pytest itself (never
# through a pipe), and no source edit in between. This script runs them and writes, per gate,
# the commit, whether the tree was clean, start and end, pytest's exit code, the count line and
# how many "node down" / "Fatal Python" lines the output holds. It stops at the first red gate.
#
#   scripts/run_release_gates.sh OUT_DIR [COUNT] [-- extra pytest arguments]
#   scripts/run_release_gates.sh /path/to/new/folder 3
#   scripts/run_release_gates.sh /path/to/new/folder 1 -- --runengine
#
# OUT_DIR must not exist yet; everything goes into it (gateN.txt, gateN_exit.txt, gates.md,
# and the test runs' temp folders under OUT_DIR/tmp). A lock file in OUT_DIR's parent folder
# refuses a second runner started there at the same time. CHROMIQ_GATE_WATCHDOG_S (seconds,
# default 0 = off) stops a gate that has written no output for that long and records it as
# exit=WATCHDOG. Run it from the repository root with the project's .venv. Nothing is deleted.
# Do not edit any file in this tree while it runs.
set -u
if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -lt 1 ]; then
  sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
fi
OUT="$1"; shift
COUNT="${1:-3}"; [ $# -gt 0 ] && shift
[ "${1:-}" = "--" ] && shift
EXTRA=("$@")
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"
if [ -e "$OUT" ]; then echo "$OUT exists already: give a NEW folder"; exit 2; fi
LOCK="$(dirname "$OUT")/.chromiq-gates.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "another gate runner holds $LOCK; wait for it (or remove the lock folder if it is stale)"
  exit 2
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
mkdir -p "$OUT/tmp"
WATCH="${CHROMIQ_GATE_WATCHDOG_S:-0}"
cd "$ROOT" || exit 2
for N in $(seq 1 "$COUNT"); do
  {
    echo "## gate $N"
    echo "HEAD $(git rev-parse HEAD)"
    echo "status: [$(git status --short | tr '\n' ' ')]"
    echo "start $(date)"
  } >> "$OUT/gates.md"
  TMPDIR="$OUT/tmp" QT_QPA_PLATFORM=offscreen "$PY" -m pytest --runslow -n auto -q \
    ${EXTRA[@]+"${EXTRA[@]}"} > "$OUT/gate$N.txt" 2>&1 &
  P=$!
  RC=""
  while kill -0 "$P" 2>/dev/null; do
    sleep 30
    if [ "$WATCH" -gt 0 ]; then
      AGE=$(( $(date +%s) - $(stat -f %m "$OUT/gate$N.txt" 2>/dev/null || stat -c %Y "$OUT/gate$N.txt") ))
      if [ "$AGE" -ge "$WATCH" ]; then
        echo "WATCHDOG $(date): no output for ${AGE}s" >> "$OUT/gate${N}_watchdog.txt"
        tail -60 "$OUT/gate$N.txt" >> "$OUT/gate${N}_watchdog.txt"
        kill -TERM "$P"; RC="WATCHDOG"
      fi
    fi
  done
  wait "$P"; PRC=$?
  [ -z "$RC" ] && RC="$PRC"
  echo "exit=$RC" > "$OUT/gate${N}_exit.txt"
  {
    echo "end $(date)"
    echo "exit=$RC"
    echo "count: $(tail -1 "$OUT/gate$N.txt")"
    echo "node down / fatal: $(grep -cE 'node down|Fatal Python' "$OUT/gate$N.txt")"
    echo
  } >> "$OUT/gates.md"
  if [ "$RC" != "0" ] || grep -qE "[0-9]+ failed" "$OUT/gate$N.txt"; then
    echo "gate $N is RED (exit=$RC): see $OUT/gate$N.txt"; echo "GATES STOPPED at $N" >> "$OUT/gates.md"
    exit 1
  fi
  echo "gate $N green: $(tail -1 "$OUT/gate$N.txt")"
done
echo "GATES DONE: $COUNT green" >> "$OUT/gates.md"
echo "$COUNT consecutive green gates; the record is $OUT/gates.md"
