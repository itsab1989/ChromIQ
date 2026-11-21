"""4.3.54, the review's S5 (the root of issue 217's case): ONE decision governs both "is the
run's measurement built on" (no replace window, no move to old/) and "is -r sent".

Before, the window and the move followed the box ("Refine / resume existing measurement (-r)"
shown and ticked, or the refine box ticked) while -r followed `_resume_has_anything_to_resume`
(the file can be resumed). Where the two disagreed, the read replaced the file without a word
(only the session guard's copy remained) and the helper saw the old file (issue 217's "mixed").
Pinned for every combination: the box shown or hidden, ticked or not, the file complete (one
pass or dual), partial, header-only or mismatched with the chart: the parameters' -r, the
question before START and the archive agree."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TI2 = ("CTI2\n\nDESCRIPTOR \"chart\"\nTARGET_INSTRUMENT \"X-Rite i1Pro 2\"\n\n"
       "NUMBER_OF_FIELDS 5\nBEGIN_DATA_FORMAT\nSAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B\n"
       "END_DATA_FORMAT\n\nNUMBER_OF_SETS 2\nBEGIN_DATA\n1 A1 100 100 100\n2 A2 0 0 0\n"
       "END_DATA\n")


def _ti3(rows, dual=False):
    head = ["CTI3", "", 'TARGET_INSTRUMENT "X-Rite i1Pro 2"']
    if dual:
        head += ['CHROMIQ_DUAL_SCAN "i1pro2"', 'CHROMIQ_DUAL_SCALE "1.1560"',
                 'CHROMIQ_DUAL_SCALE_SOURCE "standard"', 'CHROMIQ_DUAL_WHITE "instrument"']
    body = [f"{i + 1} A{i + 1} 50 50 50 40.0 42.0 44.0" for i in range(rows)]
    return "\n".join(head + ["", "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
                             "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
                             "END_DATA_FORMAT", "", f"NUMBER_OF_SETS {rows}", "BEGIN_DATA"]
                     + body + ["END_DATA", ""])


FILES = {"complete one pass": _ti3(2), "complete dual": _ti3(2, dual=True),
         "partial": _ti3(1), "header only": _ti3(0), "mismatched": _ti3(3)}


@pytest.fixture
def tab(qapp, tmp_path):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import Project
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "out"))
    proj = Project.create(tmp_path / "out" / "Demo", "Demo")
    run = proj.current_run()
    run.dir.mkdir(parents=True, exist_ok=True)
    ti2 = run.dir / f"{run.stem}.ti2"
    ti2.write_text(TI2, encoding="utf-8")
    t = TabMeasure(ArgyllRunner(s), s)
    t._ti1_path = ti2
    yield t, ti2.with_suffix(".ti3"), run
    t.close()


@pytest.mark.parametrize("module", ["guided", "manual"])
@pytest.mark.parametrize("shown", [True, False])
@pytest.mark.parametrize("ticked", [True, False])
@pytest.mark.parametrize("kind", sorted(FILES))
def test_the_window_the_move_and_minus_r_follow_one_decision(tab, module, shown, ticked, kind):
    t, ti3, run = tab
    ti3.write_text(FILES[kind], encoding="utf-8")
    t._stack.setCurrentIndex(0 if module == "guided" else 1)
    cb = t._resume_cb if module == "guided" else t._m_resume_cb
    cb.setHidden(not shown)
    cb.setChecked(ticked)
    params = t._collect_guided() if module == "guided" else t._collect_manual()
    builds = t._read_builds_on_existing()
    assert bool(params.resume) == builds, (module, shown, ticked, kind)
    from workflow.measurement_state import can_resume
    resumable = can_resume(ti3, ti3.with_suffix(".ti2"))
    assert builds == (shown and ticked and resumable)
    # and the move: built on = the file stays; replaced = it goes to old/ BEFORE the helper
    t._archive_measurement_before_replacing()
    assert ti3.is_file() == builds
    if not builds:
        assert list(run.dir.glob("old/**/*.ti3"))
