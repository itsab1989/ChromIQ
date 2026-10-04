"""Shared paths and small helpers for the neighbour-check test campaign.

Knut, #182 5983470377 item 5 and 5983725218: test the neighbour check on many
charts (80 to more than 4000 patches) against simulated measurements with
every conceivable misread, printer, paper, ink and laser fault, and watch the
outlines turn red and yellow at the right time.

TEST-ONLY CODE. Nothing here is imported by the app. The neighbour check
itself (``workflow/neighbour_check.py``) lives on the branch
``fix/4.3.3-beta11-neighbours``; :func:`neighbour_module` copies that file
from origin into the campaign folder and imports it from there, for running
only. It is never written into product code on this branch.

Big outputs (charts, printer models, cases, results) live in the campaign
folder on the Desktop, never in the repository (CLAUDE.md, disk hygiene).
"""
from __future__ import annotations

import importlib.util
import math
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

#: The campaign's notes folder. Overridable for a test run.
CAMPAIGN = Path(os.environ.get(
    "CHROMIQ_NB_CAMPAIGN",
    str(Path.home() / "Desktop/ChromIQ-work/2026-10-04_beta11/campaign")))
CHARTS = CAMPAIGN / "fixtures" / "charts"
PRINTERS = CAMPAIGN / "fixtures" / "printers"
CASES = CAMPAIGN / "cases"
RESULTS = CAMPAIGN / "results"
RUNTIME = CAMPAIGN / "runtime"

#: The branch the neighbour check is built on.
NB_BRANCH = "origin/fix/4.3.3-beta11-neighbours"
NB_FILE = "workflow/neighbour_check.py"

#: ArgyllCMS's icmD50 (the engine's L*a*b* white).
D50 = (0.9642, 1.0, 0.8249)

#: Never let anything here find a real instrument (the task's hard rule).
os.environ["ARGYLL_EXCLUDE_SERIAL_SCAN"] = "/dev/cu.Bluetooth-Incoming-Port"


def argyll(tool: str) -> str:
    """An ArgyllCMS FILE tool (targen, printtarg, colprof, xicclu). Never a
    reader: chartread, spotread, dispread are refused here."""
    if tool in ("chartread", "spotread", "dispread", "dispcal", "illumread"):
        raise RuntimeError(f"{tool} would talk to an instrument: refused")
    for base in ("/Applications/Argyll/bin", "/opt/homebrew/bin", "/usr/local/bin"):
        p = Path(base) / tool
        if p.exists():
            return str(p)
    raise SystemExit(f"ArgyllCMS {tool} not found")


def run_tool(cmd, *, cwd=None, timeout=600, stdin_text=None) -> str:
    """Run a file tool with a timeout (CLAUDE.md: every Argyll call has one)."""
    r = subprocess.run(cmd, cwd=cwd, timeout=timeout, input=stdin_text,
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed ({r.returncode}): "
                           f"{(r.stderr or r.stdout)[-1500:]}")
    return r.stdout


def neighbour_module(ref: str = NB_BRANCH):
    """The neighbour check as origin's branch has it, imported from a copy in
    the campaign's runtime folder (never from, and never into, product code).

    Returns ``(module, commit)``. Set ``CHROMIQ_NB_MODULE`` to a file to use
    that copy instead (for example a local worktree of the branch)."""
    override = os.environ.get("CHROMIQ_NB_MODULE")
    if override:
        path, commit = Path(override), "local:" + override
    else:
        commit = subprocess.run(["git", "rev-parse", ref], cwd=REPO,
                                capture_output=True, text=True,
                                check=True).stdout.strip()
        src = subprocess.run(["git", "show", f"{commit}:{NB_FILE}"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
        RUNTIME.mkdir(parents=True, exist_ok=True)
        path = RUNTIME / f"neighbour_check_{commit[:10]}.py"
        if not path.exists() or path.read_text() != src:
            path.write_text(src)
    spec = importlib.util.spec_from_file_location("nb_campaign_neighbour_check",
                                                  path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, commit


def xyz_to_lab(xyz100) -> tuple:
    """L*a*b* as the engine computes it: XYZ 0..100 against icmD50."""
    def f(t: float) -> float:
        return t ** (1.0 / 3.0) if t > 216.0 / 24389.0 else (
            (24389.0 / 27.0 * t + 16.0) / 116.0)
    fx, fy, fz = (f(max(0.0, float(v)) / 100.0 / w) for v, w in zip(xyz100[:3], D50))
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


def lab_to_xyz(lab) -> tuple:
    """The inverse of :func:`xyz_to_lab` (XYZ 0..100)."""
    L, a, b = (float(v) for v in lab[:3])
    fy = (L + 16.0) / 116.0
    fx = fy + a / 500.0
    fz = fy - b / 200.0

    def finv(t: float) -> float:
        return t ** 3 if t > 6.0 / 29.0 else 3 * (6.0 / 29.0) ** 2 * (t - 4.0 / 29.0)
    return tuple(100.0 * w * finv(t) for t, w in zip((fx, fy, fz), D50))


def de76(a, b) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a[:3], b[:3])))


def strip_of(loc: str) -> str:
    """The strip label of a ChromIQ/Argyll location: "A12" -> "A", "AB3" -> "AB"."""
    return "".join(c for c in str(loc) if c.isalpha()).upper()


def patch_no(loc: str) -> int:
    return int("".join(c for c in str(loc) if c.isdigit()) or 0)


def strip_key(label: str):
    """Reading order of strip labels: A..Z, then AA, AB.. (length first)."""
    return (len(label), label)
