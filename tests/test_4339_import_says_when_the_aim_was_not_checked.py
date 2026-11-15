"""4.3.39 integration, addition (i): an i1Profiler "Measure Chart"
measurement of an i1iO chart filed on a chart too small or too uniform for
the import's checks to prove the aim (the chart could not tell and the person
answered Import; or the chart has at most two strips, §I.17 point 9) says so
after filing, in the log and in the "done" window, with what the person can
do to be sure (M-IMPORT-I1IO-AIM-UNCHECKED). A chart that can tell says
nothing more: nothing is presented as checked when it was not, and nothing
as unchecked when it was.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

from tests import i1p_forward as F  # noqa: E402
from tests.test_import_measurement_module import (_capture_refusals,  # noqa: E402
                                                  _silence_done_dialog, _tab,
                                                  _verify_env)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def beta_on():
    from workflow.i1io import support
    before = support._latched
    support.set_enabled_for_this_process(True)
    yield
    support._latched = before


def _verdict(**kw):
    from workflow.i1io.measure_chart import McVerdict
    return McVerdict(True, **kw)


def test_which_filed_measurements_count_as_unchecked():
    from workflow.i1io.measure_chart import AIM_FEW_STRIPS, \
        aim_unchecked_why
    from workflow.i1io.measure_chart import McVerdict
    big = SimpleNamespace(rows=22, columns=24)
    two = SimpleNamespace(rows=AIM_FEW_STRIPS, columns=24)
    assert aim_unchecked_why(_verdict(grid=big)) == ""
    assert aim_unchecked_why(_verdict(grid=two)) == "few-strips"
    assert aim_unchecked_why(_verdict(grid=big, ask_why="similar")) \
        == "similar"
    assert aim_unchecked_why(McVerdict(False, grid=two)) == ""


@pytest.mark.parametrize("why", ["few-strips", "similar", "neighbours",
                                 "few-patches", "short-strips",
                                 "no-colours", "cannot-tell"])
@pytest.mark.parametrize("labelled", [True, False])
def test_the_text_is_complete_for_every_reason(why, labelled):
    from workflow import measurement_messages as M
    title, body = M.i1io_aim_unchecked_text(
        why, {"p1": "A1", "p2": "B1", "p3": "B24", "labelled": labelled})
    assert "{" not in title + body
    assert "aim" in title
    # both ways to be sure are named
    assert "measure the sheet again" in body and "by eye" in body
    if labelled:
        assert "A1" in body and "B24" in body


def _verification_with(tmp_path, rgbs, **kw):
    s, fm, ctl, run = _verify_env(tmp_path)
    src = F.build_chart(tmp_path / "built", rgbs, **kw)
    dst = run.verify_chart_ti2
    stem = dst.name[:-4]
    shutil.copy2(src, dst)
    shutil.copy2(Path(str(src)[:-4] + ".i1io.json"),
                 dst.parent / (stem + ".i1io.json"))
    return s, fm, ctl, run, F.load_sheet(dst)


def _import(tmp_path, monkeypatch, rgbs, **kw):
    s, fm, ctl, run, sh = _verification_with(tmp_path, rgbs, **kw)
    tab = _tab(s, fm, ctl)
    done = _silence_done_dialog(tab, monkeypatch)
    refused = _capture_refusals(tab, monkeypatch)
    asked = []
    monkeypatch.setattr(tab, "_ask_import_question",
                        lambda msg, *a, **k: asked.append(msg.id) or True)
    try:
        tab._switch_mode("import")
        tab._import_path = F.measure(sh, tmp_path / "scan.cmxf")
        tab._on_import_measurement()
        log = tab._log.toPlainText()
        note = getattr(tab, "_i1io_aim_note", None)
    finally:
        tab.deleteLater()
    assert not refused, refused
    assert len(done) == 1, log[-800:]
    return sh, log, note, asked


def test_a_two_strip_chart_says_the_aim_was_not_checked(
        tmp_path, qapp, beta_on, monkeypatch):
    rng = np.random.default_rng(3)
    rgbs = [tuple(rng.uniform(0, 100, 3)) for _ in range(40)]
    sh, log, note, asked = _import(tmp_path, monkeypatch, rgbs, seed=3)
    assert sh.rows == 2
    assert not asked                     # the colours agreed: no question
    assert "ChromIQ could not check the aim on this chart" in log
    assert "too few strips" in log
    assert note and "too few strips" in note[1]


def test_a_ramp_chart_says_it_after_the_question(
        tmp_path, qapp, beta_on, monkeypatch):
    ramps = []
    for ch in "RGBK":
        for i in range(24):
            v = 100 * i / 23
            ramps.append({"R": (v, 0, 0), "G": (0, v, 0), "B": (0, 0, v),
                          "K": (v, v, v)}[ch])
    _sh, log, note, asked = _import(tmp_path, monkeypatch, ramps,
                                    randomize=False)
    assert asked == ["M-IMPORT-I1IO-CANNOT-CHECK"]
    assert "ChromIQ could not check the aim on this chart" in log
    assert note is not None


def test_a_chart_that_can_tell_says_nothing_more(
        tmp_path, qapp, beta_on, monkeypatch):
    rng = np.random.default_rng(6)
    rgbs = [tuple(rng.uniform(0, 100, 3)) for _ in range(96)]
    sh, log, note, asked = _import(tmp_path, monkeypatch, rgbs, seed=7)
    assert sh.rows > 2 and not asked
    assert "could not check the aim" not in log
    assert note is None


def test_the_done_windows_carry_the_note_once(qapp):
    from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout
    from ui.tabs.tab_measure import TabMeasure
    holder = SimpleNamespace(_i1io_aim_note=("Title", "Body"))
    dlg = QDialog()
    lay = QVBoxLayout(dlg)
    TabMeasure._add_i1io_aim_note(holder, dlg, lay)
    labels = [w.text() for w in dlg.findChildren(QLabel)]
    assert labels == ["⚠ Title\n\nBody"]
    assert holder._i1io_aim_note is None
    TabMeasure._add_i1io_aim_note(holder, dlg, lay)     # said once
    assert len(dlg.findChildren(QLabel)) == 1
    dlg.deleteLater()


def test_both_done_windows_ask_for_it():
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    for name in ("_show_import_done", "_show_import_done_profiling"):
        assert "_add_i1io_aim_note" in inspect.getsource(
            getattr(TabMeasure, name)), name
