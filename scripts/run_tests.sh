#!/usr/bin/env bash
# Run the ChromIQ test suite robustly.
#
# Why this exists: the tests embed QWebEngineView (gamut viewer, patch cube,
# soft-proof). When a run is killed mid-flight (Ctrl-C, or back-to-back
# kill-and-rerun cycles), it can orphan a `QtWebEngineProcess` helper. A fresh
# pytest then wedges at startup waiting on that orphan — the "tests hang for
# minutes" symptom.
#
# Hardening (so a wedge can never hang indefinitely again):
#   1. A mkdir lock serialises runs, so two invocations can't race-kill each
#      other's pytest and orphan a WebEngine helper between them.
#   2. We *wait* for orphaned pytest/QtWebEngineProcess to actually exit
#      (polling), instead of a fixed sleep that may be too short.
#   3. A watchdog hard-kills the run after HARD_TIMEOUT seconds (default 240)
#      and clears WebEngine orphans — macOS has no coreutils `timeout`.
#   4. pytest.ini's faulthandler_timeout still dumps a traceback for a genuine
#      in-test hang.
#
# Usage:  ./scripts/run_tests.sh [pytest args]      e.g. -k softproof
#         HARD_TIMEOUT=600 ./scripts/run_tests.sh    (override the watchdog)
set -u
cd "$(dirname "$0")/.."

# 240 s suits the targeted runs this script is for (`-k something`). IT IS NOT
# ENOUGH FOR THE GATE: `--runslow` takes ~3 min at -n auto and ~19 min serial,
# and this script passes no -n of its own, so a gate run through it would be
# `kill -9`'d partway and reported as a HANG rather than a timeout. Run the
# gate directly (see CLAUDE.md), or set HARD_TIMEOUT and -n yourself.
HARD_TIMEOUT="${HARD_TIMEOUT:-240}"
LOCK="${TMPDIR:-/tmp}/chromiq_pytest.lock"

# --- 1. serialise: only one run at a time --------------------------------
for _ in $(seq 1 120); do
    mkdir "$LOCK" 2>/dev/null && break
    echo "run_tests.sh: another run is active, waiting…" >&2
    sleep 1
done
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

# --- 2. clear orphans and WAIT until they're really gone -----------------
pkill -9 -f "bin/pytest"         2>/dev/null || true
pkill -9 -f "QtWebEngineProcess" 2>/dev/null || true
for _ in $(seq 1 30); do
    if ! pgrep -f "QtWebEngineProcess" >/dev/null 2>&1 \
       && ! pgrep -f "bin/pytest" >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

# shellcheck disable=SC1091
source .venv/bin/activate

# --- 3. run under a self-terminating watchdog ----------------------------
env QT_QPA_PLATFORM=offscreen pytest -p no:cacheprovider "$@" &
pytest_pid=$!

(
    sleep "$HARD_TIMEOUT"
    if kill -0 "$pytest_pid" 2>/dev/null; then
        echo "run_tests.sh: HARD_TIMEOUT ${HARD_TIMEOUT}s hit — killing pytest." >&2
        kill -9 "$pytest_pid" 2>/dev/null || true
        pkill -9 -f "QtWebEngineProcess" 2>/dev/null || true
    fi
) &
watchdog_pid=$!

wait "$pytest_pid"; rc=$?
kill "$watchdog_pid" 2>/dev/null || true
wait "$watchdog_pid" 2>/dev/null || true
exit "$rc"
