"""Review of 4.3.5 beta 8: guided refinement patch by patch, when the list
names a patch the chart does not have, and #211's check on a file that holds
one place twice.

THE LOOP. The engine answers a ``goto`` to a patch it does not have with
``{"event":"error","kind":"patch_not_found"}`` and a ``spot_ready`` for the
patch it is still on (measured with the real helper below). The guide asked
for the same patch again at that ``spot_ready``, and again, for ever: one
"Patch not found" after another, no reading possible. A refinement list from
a check of another file can name such a patch, so the tab leaves those out
(`TabMeasure._guided_patches`) and the manager drops one the engine refuses
(`MeasureManager._guided_patch_missing`).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import types
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "helpers"))
from test_211_guided_refinement_goes_patch_by_patch import (  # noqa: E402
    _guided, _patch_gotos, _read, _ready)
from test_211_a_measurement_that_does_not_fit_the_chart import (  # noqa: E402
    _chart, _write)

from workflow.measurement_pairing import resume_fit       # noqa: E402


def _not_found(loc):
    return {"event": "error", "kind": "patch_not_found", "detail": loc}


def test_a_patch_the_engine_cannot_reach_is_asked_for_once():
    m, r, feed, lines, done = _guided(["A2", "Q9", "D1"])
    feed(_ready("A1"), _ready("A2"), _read("A2"), _ready("A3"))
    assert _patch_gotos(r) == ["A2", "Q9"]
    # the engine cannot go there: an error, then the patch it is still on
    feed(_not_found("Q9"), _ready("A3"))
    assert _patch_gotos(r) == ["A2", "Q9", "D1"], \
        "the guide must move on, not ask for Q9 again"
    feed(_ready("D1"), _read("D1"))
    assert done == [True]


def test_the_last_patch_missing_still_ends_the_guide():
    m, r, feed, lines, done = _guided(["A2", "Q9"])
    feed(_ready("A1"), _ready("A2"), _read("A2"), _ready("A3"))
    feed(_not_found("Q9"), _ready("A3"), _ready("A3"))
    assert _patch_gotos(r).count("Q9") == 1
    assert done == [True]
    assert m._guided_state == "idle_done"


def test_a_not_found_for_another_patch_changes_nothing():
    m, r, feed, lines, done = _guided(["A2", "B3"])
    feed(_ready("A1"))
    feed(_not_found("ZZ1"))
    assert m._guided_strips == ["A2", "B3"]


def _tab_stub(tmp_path, listed, strips=()):
    from ui.tabs.tab_measure import TabMeasure
    ti2 = _chart(tmp_path)
    log_lines = []
    stub = types.SimpleNamespace(
        _refine_patch_list=list(listed), _strip_list=list(strips),
        _ti1_path=ti2, _chart_file_for=TabMeasure._chart_file_for,
        _strip_of=lambda loc: str(loc).rstrip("0123456789"),
        _log=types.SimpleNamespace(appendPlainText=log_lines.append))
    return TabMeasure._guided_patches, stub


def test_the_tab_visits_only_patches_the_chart_has(tmp_path):
    fn, stub = _tab_stub(tmp_path, ["A2", "Q9", "D1"], strips=["A", "D"])
    assert fn(stub) == ["A2", "D1"]


def test_the_tab_keeps_a_list_that_fits(tmp_path):
    fn, stub = _tab_stub(tmp_path, ["A2", "B3", "D1"])
    assert fn(stub) == ["A2", "B3", "D1"]


def test_the_engine_answers_a_jump_it_cannot_make_as_the_guard_expects(
        tmp_path):
    """The premise, with the real helper: an error, then the SAME patch."""
    from replay_tools import HELPER, ReplaySession, write_replay_script
    if not HELPER.exists():
        pytest.skip("chromiq-chartread helper not built")
    argyll = Path("/Applications/Argyll/bin")
    targen = shutil.which("targen") or str(argyll / "targen")
    printtarg = shutil.which("printtarg") or str(argyll / "printtarg")
    if not (Path(targen).exists() and Path(printtarg).exists()):
        pytest.skip("Argyll targen/printtarg not available")
    base = tmp_path / "chart"
    subprocess.run([targen, "-v0", "-d2", "-G", "-e4", "-B4", "-f30",
                    str(base)], check=True, capture_output=True, cwd=tmp_path,
                   timeout=120)
    subprocess.run([printtarg, "-v0", "-ii1", "-pA4", "-r", str(base)],
                   check=True, capture_output=True, cwd=tmp_path, timeout=120)
    replay = tmp_path / "replay.txt"
    write_replay_script(base.with_suffix(".ti2"), replay, noise=0.0)
    s = ReplaySession(base, replay, extra_args=["-p"])
    try:
        first = s.wait_event("spot_ready", timeout=30)
        idx = s.event_index()
        s.send(cmd="goto", patch="ZZ999")
        err = s.wait_event("error", after=idx, timeout=30)
        assert err["kind"] == "patch_not_found" and err["detail"] == "ZZ999"
        again = s.wait_event("spot_ready", after=idx, timeout=30)
        assert again["loc"] == first["loc"]
    finally:
        s.proc.kill()


# ---- #211: one place twice ----------------------------------------------------

def test_one_place_twice_with_the_same_patch_does_not_fit(tmp_path):
    """Both readers keep the FIRST row of a place and drop the rest, so a
    file that holds a place twice loses a reading on resume even when both
    rows name the same patch. Nothing else in the 211 tests reaches the
    "already holds it" branch: ids catch every other case first."""
    ti2 = _chart(tmp_path)
    text = ti2.read_text(encoding="utf-8").split("BEGIN_DATA\n", 1)[1]
    sid, loc = text.splitlines()[0].split()[:2]
    rows = [f"{sid} {loc} 1 1 1 20 21 22", f"{sid} {loc} 1 1 1 30 31 32"]
    fit = resume_fit(_write(tmp_path / "m.ti3", rows), ti2)
    assert not fit.fits and fit.wrong == 1 and fit.rows == 2
