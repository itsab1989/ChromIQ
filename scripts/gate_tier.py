#!/usr/bin/env python3
"""Which gate does this change need: the NORMAL one or the FULL one?

    python scripts/gate_tier.py              # against the last release tag
    python scripts/gate_tier.py --base v4.3.30
    python scripts/gate_tier.py --quiet      # only FULL or NORMAL
    python scripts/gate_tier.py --snapshot full-gate.xml   # re-make the
                                             # timing snapshot from a FULL gate
                                             # run with --junitxml=full-gate.xml

The heavy engine builds (tests/_engine_tier.py) run only with
``--runengine`` (Basti, 2026-11-11: the engine is beta and off by default, so
it must not put 25 minutes on every gate). So that the tier cannot simply be
forgotten, this looks at everything that differs from the last release tag,
committed or not, and says:

* FULL gate   ``pytest --runslow --runengine -n auto`` when anything under
  ``FULL_GATE_PATHS`` changed (the engine, its native helpers, the research
  benchmarks, the tier list itself) or any file of the heavy tier did;
* NORMAL gate ``pytest --runslow -n auto`` otherwise.

Exit status 0 either way; it is advice for the person or agent about to run
the gate, printed with the files that decided it. A release of the engine (the
switch turned on by default, or engine work in the change) needs the FULL gate.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import _engine_tier as tier  # noqa: E402

NORMAL = ("QT_QPA_PLATFORM=offscreen pytest --runslow -n auto -q "
          "> gate.txt 2>&1")
FULL = ("QT_QPA_PLATFORM=offscreen pytest --runslow --runengine -n auto -q "
        "> gate.txt 2>&1")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def last_release_tag() -> str:
    """The newest ``v<digits>...`` tag reachable from HEAD (research tags
    such as ``research-integration-12`` are not releases)."""
    return _git("describe", "--tags", "--abbrev=0", "--match",
                "v[0-9]*").strip()


def changed_files(base: str) -> list[str]:
    """Everything that differs from ``base``: commits since it, staged and
    unstaged edits, and new files git does not ignore."""
    out = set(_git("diff", "--name-only", base).split())
    out |= set(_git("ls-files", "--others", "--exclude-standard").split())
    return sorted(out)


def heavy_test_files() -> set[str]:
    files = {f"tests/{name}" for name in tier.HEAVY_FILES}
    files |= {t.split("::", 1)[0] for t in tier.HEAVY_TESTS}
    return files


def reasons_for_full(files: list[str]) -> list[str]:
    heavy = heavy_test_files()
    hits = []
    for f in files:
        if any(f == p or (p.endswith("/") and f.startswith(p))
               for p in tier.FULL_GATE_PATHS):
            hits.append(f)
        elif f in heavy:
            hits.append(f)
    return hits


SNAPSHOT = ROOT / "tests" / "data" / "gate_durations.json"
#: Below this a test is not written into the snapshot: it cannot matter to
#: either bound, and the file stays small enough to read in a diff.
SNAPSHOT_FLOOR = 2.0


def _nodeid(classname: str, name: str) -> str:
    """Rebuild a pytest node id from a junit ``classname`` + ``name``
    (``tests.test_x.TestY`` + ``test_z[p]`` -> ``tests/test_x.py::TestY::test_z[p]``)."""
    parts = classname.split(".")
    for cut in range(len(parts), 0, -1):
        rel = "/".join(parts[:cut]) + ".py"
        if (ROOT / rel).is_file():
            return "::".join([rel, *parts[cut:], name])
    raise ValueError(f"no test file for junit classname {classname!r}")


def make_snapshot(junit: Path, command: str, measured: str) -> dict:
    """Per-test setup + call + teardown seconds from a junit file (pytest's
    default ``junit_duration_report = total``)."""
    import xml.etree.ElementTree as ET

    tests: dict[str, float] = {}
    files: dict[str, float] = {}
    for case in ET.parse(junit).iter("testcase"):
        if case.find("skipped") is not None:
            continue
        secs = float(case.get("time") or 0.0)
        nodeid = _nodeid(case.get("classname", ""), case.get("name", ""))
        rel = nodeid.split("::", 1)[0]
        files[rel] = files.get(rel, 0.0) + secs
        if secs >= SNAPSHOT_FLOOR:
            tests[nodeid] = round(secs, 1)
    return {
        "what": "per-test setup+call+teardown seconds of one FULL gate run "
                "(tests/test_the_normal_gate_cannot_silently_grow.py); only "
                f"tests of {SNAPSHOT_FLOOR} s or more are kept; 'files' is "
                "every file's total over all its tests",
        "measured": measured,
        "command": command,
        "tests": dict(sorted(tests.items())),
        "files": {f: round(v, 1) for f, v in sorted(files.items())
                  if v >= SNAPSHOT_FLOOR},
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", help="compare with this ref instead of the "
                                   "last release tag")
    ap.add_argument("--quiet", action="store_true",
                    help="print only FULL or NORMAL")
    ap.add_argument("--snapshot", type=Path, metavar="JUNIT_XML",
                    help="write tests/data/gate_durations.json from the junit "
                         "file of a FULL gate run, then stop")
    ap.add_argument("--measured", default="",
                    help="with --snapshot: date and machine of the run")
    a = ap.parse_args(argv)
    if a.snapshot:
        snap = make_snapshot(a.snapshot, "pytest --runslow --runengine -n auto",
                             a.measured)
        SNAPSHOT.write_text(json.dumps(snap, indent=1) + "\n",
                            encoding="utf-8")
        print(f"wrote {SNAPSHOT.relative_to(ROOT)}: {len(snap['tests'])} tests")
        return 0
    base = a.base or last_release_tag()
    files = changed_files(base)
    hits = reasons_for_full(files)
    if a.quiet:
        print("FULL" if hits else "NORMAL")
        return 0
    print(f"compared with {base}: {len(files)} file(s) differ")
    if hits:
        print("\nThis change needs the FULL gate, because it touches the "
              "engine or its heavy tests:")
        for f in hits[:40]:
            print(f"    {f}")
        if len(hits) > 40:
            print(f"    ... and {len(hits) - 40} more")
        print(f"\n    {FULL}")
    else:
        print("\nNothing here touches the engine or its heavy tests: the "
              "NORMAL gate is enough.")
        print(f"\n    {NORMAL}")
        print("\n(The FULL gate adds --runengine. Run it anyway before a "
              "release that changes what the engine does.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
