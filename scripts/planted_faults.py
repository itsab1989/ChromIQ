#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Test the tests: plant small faults in COPIES of the tree, one at a time, and see which a
chosen test selection catches.

A test that has never been seen to fail proves little. Before a safety review, plant the faults
a reviewer would fear (a check removed, a cap raised by one, a confirmation skipped) and make
sure a test goes red for each one. A fault no test catches gets a test.
(docs/adding_an_instrument.md, section 12b; the method is the reviews' "planted faults".)

    python scripts/planted_faults.py FAULTS.json --out NEW_FOLDER
    python scripts/planted_faults.py FAULTS.json --out NEW_FOLDER --only F2 F5
    python scripts/planted_faults.py --example        # print an example FAULTS.json

FAULTS.json:

    {"tests": ["tests/i1io_table/test_job_safety.py"],      # the default selection
     "pytest_args": ["-q", "-x"],                          # optional
     "faults": [
       {"id": "F1", "why": "the writer's hands-off guard removed",
        "file": "workflow/i1io/table/session_table.py",
        "old": "exact text, must occur exactly once", "new": "its replacement",
        "tests": ["tests/i1io_table/test_final_m1_hands_off_after_every_question.py"]}]}

What it does, and what it never does:

* it NEVER changes the tree you run it from, and never deletes anything. Every fault gets its
  own new folder ``NEW_FOLDER/<id>/`` holding a full copy of the tree (the files git tracks,
  as they are on disk now, or every file when the folder is not a git checkout), the planted
  file, the pytest output and pytest's temp folders. ``NEW_FOLDER`` must not exist yet;
* it first runs the selection on an UNPLANTED copy (``baseline``): if that is not green, a red
  result means nothing, and the run stops;
* a fault whose ``old`` text does not occur exactly once (or ``count`` times) is reported as
  NOT PLANTED and not run;
* "caught" means pytest itself exited 1 (tests failed). Exit 2 to 4 (an import broke, an
  internal error) is reported as ERROR: a fault that breaks importing proves little about the
  tests, so plant it where a test has to notice the behaviour;
* at the end it checks that every file named in FAULTS.json is unchanged in your tree.

Each copy is the size of the tree (a few hundred MB for ChromIQ), so the folder can grow large:
it says how large, and the folders are yours to delete when you have read the report.
Exit code: 0 when the baseline is green and every planted fault was caught, 1 otherwise.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

EXAMPLE = {
    "tests": ["tests/i1io_table/test_job_safety.py"],
    "pytest_args": ["-q", "-x", "-p", "no:randomly"],
    "faults": [
        {"id": "F1-cap-plus-one",
         "why": "the creep may take one step more than reviewed",
         "file": "workflow/i1io/table/geometry.py",
         "old": "CREEP_STEP = 50",
         "new": "CREEP_STEP = 51",
         "tests": ["tests/i1io_table/test_job_safety.py"]},
    ],
}

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist"}


def tracked_files(root: Path) -> "list[str]":
    """The files to copy: git's tracked files when *root* is a checkout, else every file."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True,
                             check=True, timeout=120).stdout
        files = [f for f in out.decode("utf-8", "surrogateescape").split("\0") if f]
        if files:
            return files
    except (OSError, subprocess.SubprocessError):
        pass
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            files.append(str(Path(dirpath, name).relative_to(root)))
    return sorted(files)


def copy_tree(root: Path, dest: Path, files) -> int:
    """Copy *files* (relative to *root*) into the NEW folder *dest*; returns the bytes copied."""
    dest.mkdir(parents=True, exist_ok=False)
    total = 0
    for rel in files:
        src = root / rel
        if not src.is_file() or src.is_symlink():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        total += src.stat().st_size
    return total


def plant(tree: Path, fault: dict) -> str:
    """Apply one fault inside the COPY *tree*; returns "" or why it could not be planted."""
    path = tree / fault["file"]
    if not path.is_file():
        return f"no file {fault['file']}"
    text = path.read_text(encoding="utf-8")
    want = int(fault.get("count", 1))
    found = text.count(fault["old"])
    if found != want:
        return f"'old' occurs {found} times in {fault['file']}, expected {want}"
    path.write_text(text.replace(fault["old"], fault["new"]), encoding="utf-8")
    return ""


def run_tests(tree: Path, here: Path, tests, pytest_args, python: str, timeout: float):
    (here / "tmp").mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env.update(TMPDIR=str(here / "tmp"), TEMP=str(here / "tmp"), TMP=str(here / "tmp"),
               QT_QPA_PLATFORM="offscreen", PYTHONDONTWRITEBYTECODE="1")
    cmd = [python, "-m", "pytest", *tests, *pytest_args, "-p", "no:cacheprovider",
           f"--basetemp={here / 'basetemp'}"]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=tree, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        rc, output = proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired as exc:
        rc = -1
        output = f"did not finish within {timeout:.0f} s\n{exc.stdout or ''}"
    (here / "pytest.txt").write_text(" ".join(cmd) + "\n\n" + output, encoding="utf-8")
    last = [ln for ln in output.strip().splitlines() if ln.strip()][-1:] or [""]
    return rc, last[0], time.monotonic() - t0


def verdict(rc: int) -> str:
    if rc == 0:
        return "SURVIVED"
    if rc == 1:
        return "caught"
    if rc == 5:
        return "ERROR (no tests collected)"
    if rc == -1:
        return "ERROR (timed out)"
    return f"ERROR (pytest exit {rc})"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "missing"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("faults", nargs="?", help="the FAULTS.json file")
    ap.add_argument("--out", help="a NEW folder for the copies and the report")
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent),
                    help="the tree to copy (default: this checkout); it is never changed")
    ap.add_argument("--python", default=sys.executable, help="the Python that runs pytest")
    ap.add_argument("--only", nargs="*", help="run only these fault ids")
    ap.add_argument("--timeout", type=float, default=1800.0, help="seconds per test run")
    ap.add_argument("--example", action="store_true", help="print an example FAULTS.json")
    a = ap.parse_args(argv)
    if a.example:
        print(json.dumps(EXAMPLE, indent=2))
        return 0
    if not a.faults or not a.out:
        ap.error("FAULTS.json and --out are needed (or --example)")
    spec = json.loads(Path(a.faults).read_text(encoding="utf-8"))
    root, out = Path(a.root).resolve(), Path(a.out).resolve()
    if out.exists():
        print(f"{out} exists already: give a NEW folder (nothing is ever overwritten)",
              file=sys.stderr)
        return 2
    if out == root or root in out.parents:
        print("the output folder must be outside the tree that is copied", file=sys.stderr)
        return 2
    faults = [f for f in spec["faults"] if not a.only or f["id"] in a.only]
    ids = [f["id"] for f in faults]
    if len(set(ids)) != len(ids) or "baseline" in ids:
        print("fault ids must be unique and not 'baseline'", file=sys.stderr)
        return 2
    named = sorted({f["file"] for f in faults})
    before = {rel: digest(root / rel) for rel in named}
    files = tracked_files(root)
    out.mkdir(parents=True)
    report = {"root": str(root), "started": time.strftime("%Y-%m-%d %H:%M:%S"), "runs": []}
    print(f"copying {len(files)} files per run into {out}/<id>/tree (nothing is deleted)")

    def one(fid, fault):
        here = out / fid
        tree = here / "tree"
        size = copy_tree(root, tree, files)
        why_not = plant(tree, fault) if fault else ""
        row = {"id": fid, "why": (fault or {}).get("why", "no fault: the selection must pass"),
               "copy": str(tree), "copy_mb": round(size / 1e6, 1)}
        if why_not:
            row.update(result="NOT PLANTED", detail=why_not, rc=None)
        else:
            tests = (fault or {}).get("tests") or spec.get("tests") or []
            rc, last, secs = run_tests(tree, here, tests, spec.get("pytest_args", ["-q"]),
                                       a.python, a.timeout)
            row.update(result="passed" if (fault is None and rc == 0) else verdict(rc),
                       rc=rc, detail=last, seconds=round(secs, 1), tests=tests)
        report["runs"].append(row)
        print(f"  {fid:<24} {row['result']:<22} {row.get('detail', '')}")
        return row

    base = one("baseline", None)
    ok = base.get("rc") == 0
    if not ok:
        print("the UNPLANTED copy is not green: fix that first; no fault was run")
    else:
        for f in faults:
            one(f["id"], f)
    after = {rel: digest(root / rel) for rel in named}
    report["tree_unchanged"] = before == after
    planted = [r for r in report["runs"] if r["id"] != "baseline"]
    caught = sum(1 for r in planted if r["result"] == "caught")
    report["summary"] = {"planted": sum(1 for r in planted if r["result"] != "NOT PLANTED"),
                         "caught": caught,
                         "survived": [r["id"] for r in planted if r["result"] == "SURVIVED"],
                         "not_planted": [r["id"] for r in planted if r["result"] == "NOT PLANTED"],
                         "errors": [r["id"] for r in planted if r["result"].startswith("ERROR")]}
    (out / "report.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    lines = ["| fault | why | result | pytest's last line |", "|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['why']} | {r['result']} | {r.get('detail', '')} |"
              for r in report["runs"]]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    s = report["summary"]
    total_mb = sum(r["copy_mb"] for r in report["runs"])
    print(f"caught {s['caught']} of {s['planted']} planted; survived: {s['survived'] or 'none'}; "
          f"not planted: {s['not_planted'] or 'none'}; errors: {s['errors'] or 'none'}")
    print(f"your tree unchanged: {report['tree_unchanged']}")
    print(f"report: {out / 'report.md'}; copies take about {total_mb:.0f} MB in {out} "
          "(delete the folder yourself once you have read the report)")
    good = ok and report["tree_unchanged"] and not s["survived"] and not s["not_planted"] \
        and not s["errors"]
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
