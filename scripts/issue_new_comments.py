#!/usr/bin/env python3
"""Say what is new on a GitHub issue since the last time this was asked.

Written for the #182 loop: every round ends by checking whether Knut has posted
or EDITED anything, so a round never starts from a stale reading of what he
wants. He edits his posts, so `updated_at` counts as new, not only `created_at`.

The watermark is one JSON file per issue under `.claude/`, holding the last
`updated_at` seen and the ids that carried it. It is deliberately not in git:
it is this machine's reading position, not a project fact.

Usage::

    python scripts/issue_new_comments.py 182            # what is new
    python scripts/issue_new_comments.py 182 --mark     # ...and mark it read
    python scripts/issue_new_comments.py 182 --author soul-traveller
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.proc_text import run_text          # noqa: E402

STATE_DIR = ROOT / ".claude" / "issue-watermarks"


def _gh(path: str) -> list:
    # UTF-8, named. GitHub serves JSON as UTF-8 and Knut writes Norwegian in
    # it; `text=True` alone would let the platform choose the codec, which is
    # US-ASCII under a POSIX locale. See `core/proc_text.py`.
    out = run_text(["gh", "api", path, "--paginate"],
                   capture_output=True, timeout=120)
    if out.returncode != 0:
        print(out.stderr.strip(), file=sys.stderr)
        raise SystemExit(2)
    # --paginate concatenates JSON arrays; gh emits them one after another.
    text = out.stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        rows: list = []
        dec = json.JSONDecoder()
        i = 0
        while i < len(text):
            val, j = dec.raw_decode(text, i)
            rows.extend(val)
            i = j
            while i < len(text) and text[i] in " \n\r\t":
                i += 1
        return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("issue", type=int)
    ap.add_argument("--author", default="", help="only this login")
    ap.add_argument("--mark", action="store_true",
                    help="record what was shown as read")
    ap.add_argument("--repo", default="{owner}/{repo}")
    a = ap.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path = STATE_DIR / f"issue-{a.issue}.json"
    state = {}
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    since = state.get("updated_at", "")

    rows = _gh(f"repos/{a.repo}/issues/{a.issue}/comments?per_page=100")
    if a.author:
        rows = [r for r in rows if r["user"]["login"] == a.author]
    fresh = [r for r in rows if r["updated_at"] > since]

    if not fresh:
        print(f"issue #{a.issue}: nothing new since {since or 'ever'}"
              f"{' from ' + a.author if a.author else ''}")
        return 0

    print(f"issue #{a.issue}: {len(fresh)} new or edited comment(s) since "
          f"{since or 'ever'}\n")
    for r in fresh:
        edited = " (EDITED)" if r["updated_at"] != r["created_at"] else ""
        print(f"=== {r['id']}  {r['user']['login']}  {r['updated_at']}{edited}")
        print(r["body"].rstrip())
        print()

    if a.mark:
        newest = max(r["updated_at"] for r in fresh)
        state_path.write_text(json.dumps(
            {"updated_at": newest,
             "ids": [r["id"] for r in fresh if r["updated_at"] == newest]},
            indent=1), encoding="utf-8")
        print(f"(marked read up to {newest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
