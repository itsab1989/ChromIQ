#!/usr/bin/env python3
"""How much disk space ChromIQ development is holding, and where. Read-only.

Basti, 2026-10-01: the disk kept filling up while ChromIQ was worked on and
could not be freed completely, which ended in a fresh install of macOS. The
suite already cleans up after itself (`tests/conftest.py`: the stale-temp
sweep at session start and the green run's tree at the end), so this looks
at everything AROUND the suite as well: on-screen drivers, agents' scratch
folders, builds, worktrees, transcripts, and the APFS local snapshots that
keep deleted files on disk until macOS purges them.

    python scripts/disk_report.py            # the table
    python scripts/disk_report.py --check    # exit 1 past the limits below

It never deletes anything. Every row says what is safe to remove by hand.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOME = Path.home()

#: --check fails past either limit.
MIN_FREE_GB = 100
MAX_HELD_GB = 25


def _size(path: Path) -> int:
    total = 0
    try:
        if path.is_file() or path.is_symlink():
            return path.lstat().st_size
        for root, _dirs, files in os.walk(path, onerror=lambda e: None):
            for f in files:
                try:
                    total += os.lstat(os.path.join(root, f)).st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


def _sum(paths) -> tuple[int, int]:
    paths = [p for p in paths if p.exists()]
    return len(paths), sum(_size(p) for p in paths)


def _rows() -> list[tuple[str, int, int, str]]:
    tmp = Path(tempfile.gettempdir())
    rows = []

    def add(label, paths, hint):
        n, b = _sum(paths)
        rows.append((label, n, b, hint))

    add("$TMPDIR chromiq-* folders", list(tmp.glob("chromiq[-_]*")),
        "the next pytest run sweeps those older than an hour; the demo cache "
        "(chromiq-demo-projects-cache) is kept on purpose")
    add("$TMPDIR pytest trees", list(tmp.glob("pytest-of-*")),
        "a failed run keeps its tree as evidence; safe to delete once read")
    add("/private/tmp chromiq*", list(Path("/private/tmp").glob("chromiq*")),
        "driver sandboxes (CHROMIQ_SETTINGS_FILE etc.); safe after the run")
    add("Claude scratch (/private/tmp/claude-*)",
        list(Path("/private/tmp").glob("claude-*")),
        "agents' scratchpads and transcripts of finished sessions")
    add("Claude transcripts (~/.claude/projects)",
        [HOME / ".claude" / "projects"],
        "old session .jsonl files; screenshots make them large")
    add("repo worktrees (.claude/worktrees)",
        [REPO / ".claude" / "worktrees"],
        "git worktree remove <path> once merged")
    add("repo build/ and dist/", [REPO / "build", REPO / "dist"],
        "PyInstaller output and old demo-project bundles")
    add("Desktop session reports (~/Desktop/ChromIQ-work)",
        [HOME / "Desktop" / "ChromIQ-work"],
        "evidence for Basti; archive or delete old sessions by hand")
    add("ChromIQ log folder", [HOME / "Library" / "Logs" / "ChromIQ"],
        "rotating log, bounded by the app")
    return rows


def _snapshots() -> list[str]:
    try:
        out = subprocess.run(["tmutil", "listlocalsnapshots", "/"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [l.strip() for l in out.splitlines() if "com.apple" in l]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help=f"exit 1 if free space < {MIN_FREE_GB} GB or "
                         f"ChromIQ work holds > {MAX_HELD_GB} GB")
    args = ap.parse_args()

    rows = _rows()
    held = sum(b for _l, _n, b, _h in rows)
    free = shutil.disk_usage(str(HOME)).free
    snaps = _snapshots() if sys.platform == "darwin" else []

    width = max(len(r[0]) for r in rows)
    for label, n, b, hint in rows:
        print(f"{label:<{width}}  {b / 1e9:8.2f} GB  ({n} item{'s' if n != 1 else ''})")
        if b > 0.5e9:
            print(f"{'':<{width}}    -> {hint}")
    print(f"{'TOTAL held by ChromIQ work':<{width}}  {held / 1e9:8.2f} GB")
    print(f"{'free on the home volume':<{width}}  {free / 1e9:8.2f} GB")
    if snaps:
        print(f"APFS local snapshots: {len(snaps)}. Deleted files stay on disk "
              "until these expire; `tmutil thinlocalsnapshots / 999999999999 4` "
              "asks macOS to purge them.")

    if args.check and (free < MIN_FREE_GB * 1e9 or held > MAX_HELD_GB * 1e9):
        print("DISK CHECK FAILED: clean up before the next gate run.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
