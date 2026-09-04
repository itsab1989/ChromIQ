#!/bin/zsh
# B8-22 — the scanner/camera window regression sweep, re-runnable before every beta.
#
#   ./run-sweep.sh                 # every check, against the working tree
#   ./run-sweep.sh J12 J24 J30     # only these
#   CHROMIQ_TREE=/path/to/other ./run-sweep.sh     # against another checkout
#
# It DRIVES THE REAL WINDOW on screen. It does not use the offscreen platform,
# because half of what it measures (paint, handles, pop-out, the diagnostic
# view) only exists on a real screen.
#
# Two things are pinned so a sweep can never touch the user's own work:
#   * CHROMIQ_SETTINGS_FILE — the preferences store is a throwaway .ini
#   * custom_output_path    — forced to /private/tmp/agentJ/ChromIQ inside the
#                             script, so "Try with a demo scan" and every build
#                             land there and never in ~/ChromIQ
# When it is over, check the VALUE, not a backup:
#   defaults read com.chromiq.ChromIQ custom_output_path
set -e
# THE TREE THIS SCRIPT IS PART OF, not a hard-coded path. Copy the repo to test
# a patch, run this from the copy, and a default of "/Users/Basti/develop/ChromIQ"
# silently drives the ORIGINAL — 34 checks pass, the patch is never exercised,
# and the run reports a clean bill of health for code it never loaded. That
# happened on 2026-09-04 and left an agent's no-regression bar unverified while
# looking verified. Deriving it from the script's own location makes a copied
# sweep test the copy, which is the only thing a copied sweep is for.
# `$0`, captured BEFORE any `cd`, and never `${BASH_SOURCE[0]}`: this script
# is `#!/bin/zsh` and BASH_SOURCE is a *bash* builtin, so under zsh it is
# EMPTY — `dirname ""` gives "." and _HERE silently became the caller's
# working directory. That is the third time this one line has been half
# fixed: first it hard-coded the tree, then it resolved after the `cd`,
# then it used a builtin the interpreter does not have. `$0` is the script
# path in both shells, and taking it here means no `cd` has happened yet.
_HERE=$(cd -- "$(dirname -- "$0")" && pwd)
REPO=${CHROMIQ_TREE:-$(cd -- "$_HERE/../.." && pwd)}
cd "$REPO"
# The venv may legitimately live only in the original checkout (a copied tree
# has no .venv), so falling back is right — but SAY which one, because a
# borrowed interpreter with the wrong tree on sys.path is the same fault in
# a different coat.
if [ -f "$REPO/.venv/bin/activate" ]; then
  source "$REPO/.venv/bin/activate"
else
  echo "note: $REPO has no .venv; borrowing the one in /Users/Basti/develop/ChromIQ" >&2
  source /Users/Basti/develop/ChromIQ/.venv/bin/activate
fi
echo "sweep is driving: $REPO" >&2
export CHROMIQ_SETTINGS_FILE=${CHROMIQ_SETTINGS_FILE:-/tmp/chromiq-sweep-$USER.ini}
export CHROMIQ_TREE="$REPO"
# `$_HERE`, not `dirname "$0"`: by this line we have already `cd "$REPO"`,
# so a relative `$0` (which is what `./run-sweep.sh` gives) resolves to the
# repo root and the script is not there. `_HERE` was made absolute at the
# top for exactly this reason and then not used here.
exec python "$_HERE/scanner_window_sweep.py" "$@"
