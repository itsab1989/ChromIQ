"""#211, Basti's suggestion (a): after a refinement the profile is the old one.

A refinement re-reads patches of a FINISHED measurement the run has built a
profile from. It replaces readings rather than adding them, so after Stop and
"Save and stop" ChromIQ said nothing at all (not even "N patches added"), and
the "Re-measurement Complete" window offered Build Profile without saying that
the profile Check & Refine judged is still the one built from the old
readings. M-REFINE-REBUILD says it: build the profile again, then Analyse
Profile Quality again, and judge only after both.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

_F = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"
LOCS = [f"{s}{p}" for s in "AB" for p in range(1, 5)]


def _write(path: Path, rows, kind) -> Path:
    path.write_text(
        f"{kind}\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n{_F}\n"
        f"END_DATA_FORMAT\n\nNUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n"
        + "\n".join(rows) + "\nEND_DATA\n", encoding="utf-8")
    return path


def _rows(locs, xyz="20 21 22"):
    return [f'{i} "{loc}" 1 1 1 {xyz}' for i, loc in enumerate(locs, 1)]


@pytest.fixture
def tab(tmp_path):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import Project
    from core.settings import AppSettings
    from ui.tabs.tab_measure import TabMeasure
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    t = TabMeasure(ArgyllRunner(s), s)
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    _write(run.chart_ti2, _rows(LOCS, "1 1 1"), "CTI2")
    run.chart_ti1.write_text("CTI1\n", encoding="utf-8")
    t._ti1_path = run.chart_ti1
    shown: list = []
    t._say_on_screen = lambda title, body: shown.append((title, body))
    yield t, run, shown
    t.deleteLater()


class _P:
    def __init__(self, resume):
        self.resume = resume


def test_a_refinement_is_a_resume_of_a_finished_measurement_with_a_profile(
        tab):
    t, run, _shown = tab
    _write(run.measurement_ti3, _rows(LOCS), "CTI3")
    assert t._starts_a_refinement(_P(True)) is False, "no profile yet"
    run.profile_icc.write_bytes(b"icc")
    assert t._starts_a_refinement(_P(True)) is True
    assert t._starts_a_refinement(_P(False)) is False, "a fresh read"
    _write(run.measurement_ti3, _rows(LOCS[:5]), "CTI3")
    assert t._starts_a_refinement(_P(True)) is False, \
        "filling in a partial measurement is not a refinement"


def _session(t, run, *, refinement=True, discarded=False, reread=True):
    from workflow.measurement_session import MeasurementSession
    _write(run.measurement_ti3, _rows(LOCS), "CTI3")
    g = MeasurementSession(run.measurement_ti3, run.chart_ti2)
    g.begin()
    if reread:
        # The engine writes the file again with one patch replaced.
        rows = _rows(LOCS)
        rows[2] = f'3 "{LOCS[2]}" 1 1 1 30 31 32'
        _write(run.measurement_ti3, rows, "CTI3")
        st = run.measurement_ti3.stat()
        os.utime(run.measurement_ti3, ns=(st.st_atime_ns,
                                          st.st_mtime_ns + 10_000_000))
    t._session_guard = g
    t._refinement_session = refinement
    t._discard_chosen = discarded
    t._finish_session_guard()


def test_save_and_stop_in_a_refinement_says_so_on_screen(tab):
    t, run, shown = tab
    t._all_done_shown = False
    _session(t, run)
    assert len(shown) == 1
    title, body = shown[0]
    assert title == "Your profile has not changed yet"
    assert "Build the profile again on the Build Profile tab" in body
    assert "“Analyse Profile Quality” on the Check & Refine tab" in body
    assert "Your profile has not changed yet" in t._log.toPlainText()


def test_not_twice_when_the_completion_window_already_said_it(tab):
    t, run, shown = tab
    t._all_done_shown = True
    _session(t, run)
    assert shown == []
    assert "Your profile has not changed yet" in t._log.toPlainText()


def test_not_after_discard_and_not_when_nothing_was_read(tab):
    t, run, shown = tab
    t._all_done_shown = False
    _session(t, run, discarded=True)
    _session(t, run, reread=False)
    _session(t, run, refinement=False)
    assert not [x for x in shown if x[0] == "Your profile has not changed yet"]


def test_the_re_measurement_complete_window_carries_it():
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._show_all_stripes_done)
    i = src.index('tr("Re-measurement Complete")')
    assert "self._refine_rebuild_texts()" in src[i:i + 1500]
