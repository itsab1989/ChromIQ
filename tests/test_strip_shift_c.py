"""4.3.50: the strip shift test in C (chromiq_shift.c) is its Python twin.

Builds ``strip_shift_test`` (CMake target, EXCLUDE_FROM_ALL: chromiq_shift.c
alone, no instrument, no USB), feeds it every strip of
``tests/data/strip_shift_regression.json`` plus strips moved on purpose, and
compares every figure with ``workflow/strip_shift.py``. Then the decisions on
the real cases are asserted on the C numbers themselves.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from workflow import strip_shift as S

ROOT = Path(__file__).resolve().parents[1]
HELPER_SRC = ROOT / "native" / "chartread_helper"
DATA = Path(__file__).parent / "data" / "strip_shift_regression.json"
PAPER_READ = (86.5, 89.7, 74.0)


def _moved(read, k, end):
    r = list(read) if end == 0 else list(read)[::-1]
    k = min(k, len(r))
    out = [PAPER_READ] + r[:k - 1] + r[k:]
    return out if end == 0 else out[::-1]


def _cases():
    strips = json.loads(DATA.read_text(encoding="utf-8"))["strips"]
    cases = [(st["read"], st["exp"], st["paper"], st["label"], -1.0) for st in strips]
    for st in strips[157:257]:     # moved copies of 100 correct strips (the random part)
        for k, end in ((3, 0), (2, 1), (999, 0), (999, 1), (1, 0), (1, 1)):
            cases.append((_moved(st["read"], k, end), st["exp"], st["paper"], "moved", -1.0))
    # the guards: a strip read in place of another (its own row's expected
    # colours as the "other" best fit), and the same moved strip with an
    # other row that fits it worse than the shift
    for a, b in zip(strips[157:207], strips[208:258]):
        if len(a["read"]) == len(b["read"]):
            own = S.other_rows_best(a["read"], [a["exp"]])
            cases.append((a["read"], b["exp"], b["paper"], "wrong", own))
            cases.append((_moved(a["read"], 3, 0), a["exp"], a["paper"], "moved",
                          S.other_rows_best(_moved(a["read"], 3, 0), [b["exp"]])))
    cases.append((strips[10]["read"][:3], strips[10]["exp"][:3], strips[10]["paper"], "short", -1.0))
    return cases


@pytest.fixture(scope="module")
def c_results(tmp_path_factory):
    if sys.platform == "win32":
        pytest.skip("the C unit tests are built on macOS and Linux")
    cmake = shutil.which("cmake")
    if cmake is None:
        pytest.skip("cmake not available: the helper is not built here")
    build = tmp_path_factory.mktemp("strip_shift_test") / "build"
    subprocess.run([cmake, "-S", str(HELPER_SRC), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"],
                   check=True, capture_output=True, timeout=600)
    r = subprocess.run([cmake, "--build", str(build), "--target", "strip_shift_test"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    exe = next(p for p in build.rglob("strip_shift_test*")
               if p.is_file() and os.access(p, os.X_OK) and p.name in ("strip_shift_test", "strip_shift_test.exe"))
    cases = _cases()
    lines = []
    for read, exp, paper, _, other in cases:
        lines.append(f"STRIP {len(read)} %.17g" % other)
        lines.append("%.17g %.17g %.17g" % tuple(paper))
        for a, b in zip(read, exp):
            lines.append("%.17g %.17g %.17g %.17g %.17g %.17g" % (*a, *b))
    r = subprocess.run([str(exe)], input="\n".join(lines) + "\n", capture_output=True, text=True,
                       encoding="utf-8", timeout=300)
    assert r.returncode == 0 and r.stdout.rstrip().endswith("ALL DONE"), r.stdout[-2000:] + r.stderr[-2000:]
    res = [ln.split() for ln in r.stdout.splitlines() if ln.startswith("RESULT ")]
    assert len(res) == len(cases)
    return cases, res


def test_every_figure_of_the_c_file_is_the_twins(c_results):
    cases, res = c_results
    for (read, exp, paper, _, other), t in zip(cases, res):
        py = S.shift_test(read, exp, paper, other)
        assert int(t[2]) == int(py.flagged)
        if py.flagged:
            assert int(t[3]) == py.end and int(t[4]) == py.k
        got = [float(v) for v in t[5:-1]]
        want = [py.score, py.s[0][0], py.s[0][1], py.s[1][0], py.s[1][1],
                py.d[0][0], py.d[0][1], py.d[1][0], py.d[1][1], py.m, py.chroma, py.pd, py.werror, py.fit, py.other]
        assert got == pytest.approx(want, abs=1e-9)
        assert int(t[-1]) == int(py.guarded)


def test_the_c_file_decides_the_real_cases(c_results):
    cases, res = c_results
    flagged = {i for i, t in enumerate(res) if t[2] == "1"}
    labels = [c[3] for c in cases]
    assert 0 in flagged                                          # case 2, the kept misread
    assert float(res[0][5]) == pytest.approx(49.0, abs=0.5)
    assert not [i for i in flagged if labels[i] == "honest"]     # no correct strip
    assert labels[-1] == "short" and len(res) - 1 not in flagged
    moved = [i for i, lb in enumerate(labels) if lb == "moved"]
    assert sum(i in flagged for i in moved) >= 0.80 * len(moved)
    wrong = [i for i, lb in enumerate(labels) if lb == "wrong"]
    assert wrong and not [i for i in wrong if i in flagged]      # a wrong strip is not a shift
