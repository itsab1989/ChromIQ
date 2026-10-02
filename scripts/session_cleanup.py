#!/usr/bin/env python3
"""Remove what ChromIQ work left on the disk, and say what it freed.

Basti, 2026-10-02: *"make it a rule that is respected in new sessions that you
make sure to leave no unneccessary files on my hard drive ... when i asked you
to clean up after a session you never managed to free up all the space you
filled and so the drive slowly but steadily filled"*.

Runs from the SessionEnd hook (.claude/settings.local.json), so it happens
even when nobody remembers. Dry run by default; ``--yes`` deletes.

What it removes, and only that:
* every row ``scripts/disk_report.py`` marks DELETABLE (ChromIQ temp folders,
  pytest trees, driver sandboxes, core dumps, build/ and dist/), skipping
  anything changed in the last hour, which may belong to a session or a gate
  that is still running;
* git worktrees under .claude/worktrees whose branch is merged into the
  current branch or master and that have no uncommitted changes;
* the ENDING session's own scratch folder (/private/tmp/claude-*/<project>/
  <session id>), when the hook passes the session id.

What it never touches: the Desktop evidence, transcripts, the demo-project
cache, other sessions' scratch, Time Machine snapshots, anything of the
user's. Those are reported, never deleted.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import disk_report  # noqa: E402

#: While a test run, a driver or ChromIQ itself is running, anything changed
#: more recently than this may still be in use. With nothing running, the
#: ending session's own fresh leftovers go too (they are most of them).
QUIET_FOR_S = 3600

#: Processes that mean "something may still be writing there".
_BUSY_PATTERNS = ("pytest", "main.py", "chromiq-chartread", "chromiq-gammap",
                  "drive_", "capture_screens", "onscreen")


def something_running() -> list[str]:
    import os
    me = {os.getpid(), os.getppid()}
    out = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True,
                         text=True, encoding="utf-8", errors="replace").stdout
    busy = []
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        if not pid.isdigit() or int(pid) in me or "session_cleanup" in cmd:
            continue
        if "python" in cmd.lower() and any(b in cmd for b in _BUSY_PATTERNS):
            busy.append(cmd[:120])
        elif "ChromIQ.app/Contents/MacOS/" in cmd:
            busy.append(cmd[:120])           # the installed app, in use
        elif any(h in cmd for h in ("chromiq-chartread", "chromiq-gammap")):
            busy.append(cmd[:120])           # the engine, which is not Python
    return busy


def _newest_mtime(path: Path) -> float:
    newest = 0.0
    try:
        newest = path.lstat().st_mtime
        if path.is_dir() and not path.is_symlink():
            for p in path.rglob("*"):
                try:
                    newest = max(newest, p.lstat().st_mtime)
                except OSError:
                    pass
    except OSError:
        pass
    return newest


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=60)


def _is_cache(rel: str) -> bool:
    rel = rel.strip().strip('"')
    return any(part in ("__pycache__", ".pytest_cache") for part in Path(rel).parts) \
        or rel.endswith((".pyc", ".pyo"))


def merged_worktrees() -> list[tuple[Path, str]]:
    """(path, branch) of clean worktrees under .claude/worktrees whose branch
    is already contained in the current branch or in master."""
    out = []
    listing = _git("worktree", "list", "--porcelain").stdout.split("\n\n")
    targets = [t for t in ("HEAD", "master") if _git("rev-parse", "--verify", t).returncode == 0]
    for block in listing:
        lines = block.splitlines()
        fields = dict(l.split(" ", 1) for l in lines if " " in l)
        path = Path(fields.get("worktree", ""))
        branch = fields.get("branch", "").removeprefix("refs/heads/")
        if ".claude/worktrees" not in str(path) or not branch:
            continue
        if any(l == "locked" or l.startswith("locked ") for l in lines):
            continue                     # someone holds it (review K_review_beta1)
        if time.time() - _newest_mtime(path) < QUIET_FOR_S:
            continue                     # touched within the hour: may be in use
        status = subprocess.run(["git", "-C", str(path), "status", "--porcelain",
                                 "--ignored"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60)
        if status.returncode != 0:
            continue
        # `git worktree remove` takes IGNORED files with it, and plain
        # `--porcelain` does not list them: only caches may be lost that way.
        leftovers = [l for l in status.stdout.splitlines() if l.strip()
                     and not _is_cache(l[3:])]
        if leftovers:
            continue                     # uncommitted or ignored work: never
        if any(_git("merge-base", "--is-ancestor", branch, t).returncode == 0 for t in targets):
            out.append((path, branch))
    return out


def own_scratch(session_id: str) -> list[Path]:
    if not session_id or "/" in session_id or session_id in (".", ".."):
        return []
    return [p for p in Path("/private/tmp").glob(f"claude-*/*/{session_id}") if p.is_dir()]


def plan(session_id: str = "") -> list[tuple[str, Path, int]]:
    """``(why, path, bytes)`` for everything that would be removed."""
    now = time.time()
    quiet = QUIET_FOR_S if something_running() else 0
    items = []
    for label, _n, _b, _hint, deletable, paths in disk_report._rows():
        if not deletable:
            continue
        for p in paths:
            if quiet and now - _newest_mtime(p) < quiet:
                continue
            if is_ours(p):
                items.append((label, p, disk_report._size(p)))
    for path, branch in merged_worktrees():
        items.append((f"merged worktree ({branch})", path, disk_report._size(path)))
    for p in own_scratch(session_id):
        items.append(("this session's scratch", p, disk_report._size(p)))
    return items


def allowed_roots() -> list[tuple[Path, str]]:
    """The ONLY places anything may be deleted from, each with the name
    prefix it must carry. Basti, 2026-10-02: *"just make sure that does never
    delete any personal data - only what you added in a session that is
    considered not needed"*. A path that is not inside one of these, under a
    name of ours, is refused even if a bug ever put it on the list."""
    import tempfile
    tmp = Path(tempfile.gettempdir()).resolve()
    return [
        (tmp, "chromiq-"), (tmp, "chromiq_"), (tmp, "pytest-of-"),
        (Path("/private/tmp").resolve(), "chromiq"),
        ((REPO / ".claude" / "worktrees").resolve(), "agent-"),
    ]


def is_ours(path: Path, why: str = "") -> bool:
    """True only for something our tooling created, under a name of ours."""
    try:
        p = path.resolve()
    except OSError:
        return False
    if p.name == "chromiq-demo-projects-cache":
        return False                     # kept on purpose, rebuilt costs minutes
    if why == "this session's scratch":
        parts = p.parts                  # /private/tmp/claude-*/<project>/<session>
        return (len(parts) == 6 and parts[1:3] == ("private", "tmp")
                and parts[3].startswith("claude-"))
    return any(p.parent == root and p.name.startswith(prefix)
               for root, prefix in allowed_roots())


def remove(path: Path, why: str) -> bool:
    if not is_ours(path, why):
        print(f"REFUSED (not ours): {path}", file=sys.stderr)
        return False
    if why.startswith("merged worktree"):
        branch = why[len("merged worktree ("):-1]
        ok = _git("worktree", "remove", str(path)).returncode == 0
        if ok:
            _git("branch", "-d", branch)
        return ok
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        try:
            path.unlink()
        except OSError:
            pass
    return not path.exists()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yes", action="store_true", help="really delete (default: dry run)")
    ap.add_argument("--quiet", action="store_true",
                    help="print one JSON line for a Claude Code hook instead of a table")
    ap.add_argument("--session-id", default="", help="the ending session's id")
    args = ap.parse_args(argv)

    session_id = args.session_id
    if not session_id and not sys.stdin.isatty():
        try:                             # a hook passes its input on stdin
            session_id = json.loads(sys.stdin.read() or "{}").get("session_id", "")
        except ValueError:
            session_id = ""

    if args.yes:
        _git("worktree", "prune")        # records of worktrees already gone
    items = plan(session_id)
    freed = 0
    failed = []
    for why, path, size in items:
        if not args.quiet:
            print(f"{'remove' if args.yes else 'would remove'} {size / 1e9:7.2f} GB  {why}: {path}")
        if args.yes:
            if remove(path, why):
                freed += size
            else:
                failed.append(str(path))
    total = sum(s for _w, _p, s in items)
    summary = (f"ChromIQ cleanup: {'freed' if args.yes else 'would free'} "
               f"{(freed if args.yes else total) / 1e9:.2f} GB in {len(items)} item"
               f"{'s' if len(items) != 1 else ''}")
    if failed:
        summary += f"; {len(failed)} could not be removed"
    since = disk_report.since_baseline()
    if since:
        summary += f". Disk {since}"
    if args.quiet:
        print(json.dumps({"systemMessage": summary}))
    else:
        print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
