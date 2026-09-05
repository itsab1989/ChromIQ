"""Check & Refine must not judge a profile against data it was not built from.

A user's account of the guided-refinement loop (2026-09-05): *"Initially it said
my profile was excellent, ΔE < 0.4, but advised to re-run one strip. I did this,
checked the profile again, and … this time the delta-E number was higher … the
delta-E number was now higher than ever and it was suggested I print the strips
off and start again!"*

**Measured, on his own 924-patch chart, with the same re-reads both ways** —
the only difference being whether the profile was rebuilt in between:

    rebuilt        avg ΔE 0.770 → 0.753   peak 5.99 →  7.81   (improving)
    NOT rebuilt    avg ΔE 0.770 → 0.835   peak 5.99 → 10.23   (worsening)

Same readings, opposite verdicts. And nothing rebuilds: guided refinement
re-reads a strip with ``chartread -r``, which rewrites the run's ``.ti3`` in
place, while the window that follows only *opens* the Build Profile tab. The
session-restore path then re-arms Check & Refine with the new ``.ti3`` and the
old ``.icc`` (``ui/main_window.py``), and profcheck is asked a question whose
answer is read as a profile grade.

§6c of ``docs/design/unified_measurement_management.md`` is explicit about what
that tool compares — *"a profile against **the data it was built from**"* — so
the pairing is part of the specification, not a nicety.

It is settled rather than guessed: ``colprof`` embeds the whole ``.ti3`` in the
profile's ``targ`` tag, so the profile carries its own source data.
"""
from __future__ import annotations

import inspect
import os
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.profile_provenance import (CIE_EPSILON, Provenance,  # noqa: E402
                                         check, embedded_ti3)

ARGYLL = Path("/Applications/Argyll/bin")


# --------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def built(tmp_path_factory, demo_projects_root):
    """A real colprof build: (icc, ti3) that genuinely belong together."""
    src = demo_projects_root / "Demo-Legacy-v2" / "runs" / "run1"
    ti3_src = src / "Demo-Legacy-v2.ti3"
    if not ti3_src.exists():
        pytest.skip("demo measurement not available")
    colprof = shutil.which("colprof") or str(ARGYLL / "colprof")
    if not Path(colprof).exists():
        pytest.skip("ArgyllCMS colprof not available")

    work = tmp_path_factory.mktemp("provenance")
    ti3 = work / "chart.ti3"
    shutil.copy2(ti3_src, ti3)
    # Budgeted for a saturated gate, not an idle machine (CLAUDE.md).
    proc = subprocess.run([colprof, "-v0", "-al", "-qm", "-D", "prov", "chart"],
                          cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    icc = work / "chart.icc"
    if not icc.exists():
        pytest.skip(f"colprof produced no profile: {proc.stdout}\n{proc.stderr}")
    return icc, ti3


# --------------------------------------------------------------- the tag
def test_a_profile_carries_the_measurement_it_was_built_from(built):
    icc, ti3 = built
    tag = embedded_ti3(icc)
    assert tag is not None, (
        "colprof's 'targ' tag was not found — the whole check rests on the "
        "profile carrying its own source data")
    assert "BEGIN_DATA" in tag and "NUMBER_OF_SETS" in tag, tag[:200]


def test_a_profile_and_its_own_measurement_pair(built):
    icc, ti3 = built
    result = check(icc, ti3)
    assert result.verdict is Provenance.BUILT_FROM_THIS, result
    assert result.differing == 0
    assert result.total > 0, "nothing was compared, so nothing was proved"


# ------------------------------------------------- the fault it exists for
def test_one_changed_reading_is_enough_to_say_so(built, tmp_path):
    """A re-read of a single strip is exactly this: a few rows, new values."""
    icc, ti3 = built
    text = ti3.read_text(encoding="latin-1")
    lines = text.splitlines()
    start = lines.index("BEGIN_DATA") if "BEGIN_DATA" in lines else \
        next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    # move ONE patch's CIE values, the way a second reading of it would
    changed = 0
    for i in range(start + 1, len(lines)):
        parts = lines[i].split()
        if len(parts) < 6 or lines[i].strip() == "END_DATA":
            continue
        parts[-1] = f"{float(parts[-1]) + 1.0:.6f}"
        lines[i] = " ".join(parts)
        changed = 1
        break
    assert changed == 1, "the fixture had no data row to move — test is vacuous"

    moved = tmp_path / "moved.ti3"
    moved.write_text("\n".join(lines) + "\n", encoding="latin-1")
    assert moved.read_text(encoding="latin-1") != text, "the mutation did not land"

    result = check(icc, moved)
    assert result.verdict is Provenance.NOT_BUILT_FROM_THIS, (
        "a measurement that has moved since the profile was built is reported "
        "as the profile's own source data — the ΔE figures below it would be "
        "read as a profile grade and are not one")
    assert result.changed == 1, result


def test_the_epsilon_does_not_swallow_a_real_re_read(built, tmp_path):
    """Guard the guard: a change smaller than a rounding is NOT a re-read."""
    icc, ti3 = built
    lines = ti3.read_text(encoding="latin-1").splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    for i in range(start + 1, len(lines)):
        parts = lines[i].split()
        if len(parts) < 6 or lines[i].strip() == "END_DATA":
            continue
        parts[-1] = f"{float(parts[-1]) + CIE_EPSILON / 10:.9f}"
        lines[i] = " ".join(parts)
        break
    tiny = tmp_path / "tiny.ti3"
    tiny.write_text("\n".join(lines) + "\n", encoding="latin-1")
    assert check(icc, tiny).verdict is Provenance.BUILT_FROM_THIS, (
        "a reformat is being reported as a different measurement")


# ------------------------------------------------- what must NOT be flagged
def test_a_merged_refinement_build_is_not_called_stale(tmp_path, demo_projects_root):
    """`merged.icc` is built from MORE than the chart Check & Refine holds.

    `average -m` concatenates the fresh chart and the pre-conditioning
    measurement, and both charts number their locations from "A1" — so the
    merged file holds two different readings under one key. Matching on the
    last one seen calls every patch of the fresh measurement changed: measured
    on a real merge, 240 of 240, for a profile built from exactly that data.
    """
    src = demo_projects_root / "Demo-Full-RGB" / "runs" / "run2"
    fresh, pre = src / "Demo-Full-RGB.ti3", src / "preconditioning.ti3"
    if not (fresh.exists() and pre.exists()):
        pytest.skip("demo refinement run not available")
    average = shutil.which("average") or str(ARGYLL / "average")
    colprof = shutil.which("colprof") or str(ARGYLL / "colprof")
    if not (Path(average).exists() and Path(colprof).exists()):
        pytest.skip("ArgyllCMS not available")

    work = tmp_path
    shutil.copy2(fresh, work / "chart.ti3")
    shutil.copy2(pre, work / "pre.ti3")
    subprocess.run([average, "-m", "chart.ti3", "pre.ti3", "merged.ti3"],
                   cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=True)
    assert (work / "merged.ti3").exists()
    subprocess.run([colprof, "-v0", "-al", "-qm", "-D", "m", "merged"],
                   cwd=work, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    merged_icc = work / "merged.icc"
    if not merged_icc.exists():
        pytest.skip("colprof produced no merged profile")

    result = check(merged_icc, work / "chart.ti3")
    assert result.verdict is Provenance.BUILT_FROM_THIS, (
        "a refinement build is reported as stale — every merged run would "
        "carry a warning it has not earned")


def test_a_profile_without_the_tag_says_nothing(tmp_path, built):
    """`colprof -n` embeds no data. Silence is the only honest answer."""
    icc, ti3 = built
    blanked = tmp_path / "no-tag.icc"
    data = bytearray(icc.read_bytes())
    assert data.count(b"targ") >= 1, "fixture has no tag to remove — test vacuous"
    blanked.write_bytes(data.replace(b"targ", b"xxxx"))
    assert embedded_ti3(blanked) is None, "the mutation did not land"
    result = check(blanked, ti3)
    assert result.verdict is Provenance.UNKNOWN, result
    assert not result.stale
    assert result.reason, "an UNKNOWN with no reason cannot be diagnosed"


def test_it_never_raises_on_rubbish(tmp_path):
    junk = tmp_path / "junk.icc"
    junk.write_bytes(b"not an icc profile at all")
    ti3 = tmp_path / "junk.ti3"
    ti3.write_text("nothing here", encoding="utf-8")
    assert check(junk, ti3).verdict is Provenance.UNKNOWN
    assert check(tmp_path / "absent.icc", tmp_path / "absent.ti3").verdict \
        is Provenance.UNKNOWN


# ------------------------------------------------------------ the wiring
def test_the_check_tab_asks_before_it_runs():
    """The detection is worthless if the tab never calls it."""
    from ui.tabs.tab_check_refine import TabCheckRefine
    run_src = inspect.getsource(TabCheckRefine._on_run)
    assert "_note_profile_provenance" in run_src, (
        "Check & Refine runs profcheck without asking whether the profile was "
        "built from the measurement it is judging")
    note_src = inspect.getsource(TabCheckRefine._note_profile_provenance)
    assert "profile_provenance" in note_src
    assert "except Exception" in note_src, (
        "a note about the profile must never be able to block a check")
