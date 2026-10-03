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

It never deletes anything. Every row says what is safe to remove by hand, and
only the rows that are safe to remove count toward ``--check``.
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


def _rows() -> list[tuple]:
    """``(label, items, bytes, hint, deletable, paths)``. Only DELETABLE rows count
    toward ``--check``: evidence, transcripts and the running session's own
    scratch are reported but must never be what a failing check reaches for
    (challenge G, 2026-10-02)."""
    tmp = Path(tempfile.gettempdir())
    rows = []

    def add(label, paths, hint, deletable):
        paths = [p for p in paths if p.exists()]
        n, b = _sum(paths)
        rows.append((label, n, b, hint, deletable, paths))

    add("$TMPDIR chromiq-* folders",
        [p for p in tmp.glob("chromiq[-_]*") if p.name != "chromiq-demo-projects-cache"],
        "the next pytest run sweeps those older than an hour", True)
    add("$TMPDIR pytest trees", list(tmp.glob("pytest-of-*")),
        "a failed run keeps its tree as evidence; safe to delete once read", True)
    add("/private/tmp chromiq*", list(Path("/private/tmp").glob("chromiq*")),
        "driver sandboxes (CHROMIQ_SETTINGS_FILE etc.); safe after the run", True)
    add("core dumps (/cores)", list(Path("/cores").glob("core.*")),
        "kern.coredump writes one per crashed process, often gigabytes each; "
        "delete them once the crash is understood; any app can write one, "
        "so this is Basti's to delete, never automatic", False)
    import time as _time
    week_ago = _time.time() - 7 * 86400
    dist = [p for p in (REPO / "dist").glob("*")] if (REPO / "dist").is_dir() else []
    add("repo build/", [REPO / "build"],
        "PyInstaller's intermediate cache; may be Basti's own build", False)
    add("repo dist/ items older than 7 days",
        [p for p in dist if p.lstat().st_mtime < week_ago],
        "built apps and demo bundles of earlier releases; may be Basti's own, "
        "so delete by hand", False)
    add("repo dist/ items of the last 7 days",
        [p for p in dist if p.lstat().st_mtime >= week_ago],
        "the current release's build; goes after a week", False)
    add("repo worktrees (.claude/worktrees)", [REPO / ".claude" / "worktrees"],
        "git worktree remove <path>, only once its branch is merged", False)
    add("demo-project cache", [tmp / "chromiq-demo-projects-cache"],
        "kept on purpose: rebuilding it costs about two minutes per gate", False)
    add("Claude scratch (/private/tmp/claude-*)",
        list(Path("/private/tmp").glob("claude-*")),
        "includes the RUNNING session's scratch; only finished sessions' "
        "folders may go, and only by hand", False)
    add("Claude transcripts (~/.claude/projects)", [HOME / ".claude" / "projects"],
        "session history; Basti decides", False)
    add("Desktop session reports (~/Desktop/ChromIQ-work)",
        [HOME / "Desktop" / "ChromIQ-work"],
        "evidence for Basti; never deleted by an agent", False)
    add("ChromIQ log folder", [HOME / "Library" / "Logs" / "ChromIQ"],
        "rotating log, bounded by the app", False)
    return rows


def _snapshots() -> list[str]:
    try:
        out = subprocess.run(["tmutil", "listlocalsnapshots", "/"],
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [l.strip() for l in out.splitlines() if "com.apple" in l]


BASELINE = REPO / ".claude" / "disk_baseline.json"


def container_free() -> int:
    """Free bytes of the APFS container (what macOS can still hand out),
    the number that matters across volumes. Falls back to the home volume."""
    try:
        out = subprocess.run(["diskutil", "apfs", "list"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace",
                             timeout=30).stdout
        for line in out.splitlines():
            if "Capacity Not Allocated" in line:
                return int(line.split(":")[1].split("B")[0].strip())
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return shutil.disk_usage(str(HOME)).free


def save_baseline() -> dict:
    import json
    import time
    data = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "free": container_free(),
            "rows": {r[0]: r[2] for r in _rows()}}
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


def since_baseline() -> "str | None":
    """What changed since the session's baseline, in plain words, or None."""
    import json
    try:
        base = json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    used = base["free"] - container_free()
    rows = {r[0]: r[2] for r in _rows()}
    grew = sorted(((rows.get(k, 0) - v, k) for k, v in base["rows"].items()),
                  reverse=True)
    lines = [f"since {base['at']}: {used / 1e9:+.2f} GB used on the disk"]
    lines += [f"  {d / 1e9:+.2f} GB  {k}" for d, k in grew if abs(d) > 0.05e9]
    return "\n".join(lines)


def _min_free_bytes(total: int) -> float:
    """100 GB, or a tenth of a smaller disk, so a 256 GB Mac is not in
    permanent alarm."""
    return min(MIN_FREE_GB * 1e9, total * 0.10)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help=f"exit 1 if free space is below {MIN_FREE_GB} GB (or a "
                         f"tenth of a smaller disk) or the DELETABLE leftovers "
                         f"exceed {MAX_HELD_GB} GB")
    ap.add_argument("--save-baseline", action="store_true",
                    help="remember the disk state now (the session-start hook)")
    ap.add_argument("--since-baseline", action="store_true",
                    help="say what changed since the saved baseline")
    args = ap.parse_args()
    if args.save_baseline:
        d = save_baseline()
        print(f"disk baseline saved: {d['free'] / 1e9:.1f} GB free")
        return 0
    if args.since_baseline:
        print(since_baseline() or "no baseline saved")
        return 0

    rows = _rows()
    deletable = sum(r[2] for r in rows if r[4])
    kept = sum(r[2] for r in rows if not r[4])
    usage = shutil.disk_usage(str(HOME))
    snaps = _snapshots() if sys.platform == "darwin" else []

    width = max(len(r[0]) + (0 if r[4] else 7) for r in rows)
    for label, n, b, hint, d, _paths in rows:
        tag = "" if d else " (kept)"
        print(f"{label + tag:<{width}}  {b / 1e9:8.2f} GB  ({n} item{'s' if n != 1 else ''})")
        if b > 0.5e9:
            print(f"{'':<{width}}    -> {hint}")
    print(f"{'DELETABLE leftovers':<{width}}  {deletable / 1e9:8.2f} GB")
    print(f"{'kept on purpose':<{width}}  {kept / 1e9:8.2f} GB")
    print(f"{'free on the home volume':<{width}}  {usage.free / 1e9:8.2f} GB")
    if snaps:
        print(f"APFS local snapshots: {len(snaps)}. Deleted files stay on disk "
              "until macOS lets these expire. They are Time Machine's: purging "
              "them (`tmutil thinlocalsnapshots / 999999999999 4`) is Basti's "
              "decision, never an agent's.")

    if args.check and (usage.free < _min_free_bytes(usage.total)
                       or deletable > MAX_HELD_GB * 1e9):
        print("DISK CHECK FAILED: remove the DELETABLE leftovers above before "
              "the next gate run. Rows marked (kept) are not yours to delete.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
