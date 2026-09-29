"""Measurement harness for the offscreen-font-metrics question (Windows gate).

Runs a set of test files serially under QT_QPA_PLATFORM=offscreen, records the
per-test outcome of every one via JUnit XML, and diffs two such recordings so a
BEFORE/AFTER delta can be reported instead of two absolutes.

    python scripts/offscreen_font_probe/measure.py run  <label> <file> [file...]
    python scripts/offscreen_font_probe/measure.py diff <before-label> <after-label>

`diff` reports, separately:
  fixed    — failed BEFORE, passes AFTER
  broken   — passed BEFORE, fails AFTER   (the number that matters)
  still    — failed in both
Nothing here changes an assertion; it only records what the suite already says.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(os.environ.get("A3_OUT", Path(__file__).resolve().parent / "_results"))


def _outcomes(xml_path: Path) -> dict[str, str]:
    root = ET.parse(xml_path).getroot()
    out: dict[str, str] = {}
    for case in root.iter("testcase"):
        nid = f"{case.get('classname')}::{case.get('name')}"
        state = "passed"
        for child in case:
            tag = child.tag
            if tag in ("failure", "error"):
                state = tag
            elif tag == "skipped":
                state = "skipped"
        out[nid] = state
    return out


def run(label: str, files: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    xml = OUT / f"{label}.xml"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    env.pop("PYTHONUTF8", None)            # the gate does not set it; nor do we
    # Serial on purpose: two cores, shared with another agent. `-p no:xdist`
    # cannot be used because pytest.ini's addopts carry xdist flags, so ask for
    # zero workers instead.
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=no", "-n", "0",
           f"--junit-xml={xml}", *files]
    proc = subprocess.run(cmd, env=env, cwd=Path(__file__).resolve().parents[2])
    res = _outcomes(xml)
    (OUT / f"{label}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    tally: dict[str, int] = {}
    for v in res.values():
        tally[v] = tally.get(v, 0) + 1
    print(f"\n[{label}] {tally}  (pytest exit {proc.returncode})")
    return 0


def diff(before: str, after: str) -> int:
    b = json.loads((OUT / f"{before}.json").read_text(encoding="utf-8"))
    a = json.loads((OUT / f"{after}.json").read_text(encoding="utf-8"))
    bad = {"failure", "error"}
    fixed = sorted(n for n, s in b.items() if s in bad and a.get(n) == "passed")
    broken = sorted(n for n, s in b.items() if s == "passed" and a.get(n) in bad)
    still = sorted(n for n, s in b.items() if s in bad and a.get(n) in bad)
    gone = sorted(set(b) - set(a))
    new = sorted(set(a) - set(b))
    print(f"BEFORE={before} n={len(b)}  AFTER={after} n={len(a)}")
    print(f"  fixed  (failed -> passed): {len(fixed)}")
    print(f"  broken (passed -> failed): {len(broken)}")
    print(f"  still failing            : {len(still)}")
    for title, rows in (("FIXED", fixed), ("BROKEN", broken), ("STILL", still),
                        ("ONLY-BEFORE", gone), ("ONLY-AFTER", new)):
        if rows:
            print(f"\n--- {title} ({len(rows)}) ---")
            for r in rows:
                print("   ", r)
    return 0


if __name__ == "__main__":
    if sys.argv[1] == "run":
        raise SystemExit(run(sys.argv[2], sys.argv[3:]))
    raise SystemExit(diff(sys.argv[2], sys.argv[3]))
