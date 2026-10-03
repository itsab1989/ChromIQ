"""The one window about verifications from an earlier profile (#182, UMM §6f).

Knut: 5964384250 Q1 (a rebuild archives the profile only; choosing
Verification afterwards offers to archive the old verification runs, or keep
them), Q2 (an ordinary chart is kept), 5965626117 (an ordinary chart opens
Create Chart too; "Keep" asks again after a restart), 5964076758 Q5 (no
sound). The window is answered here through `EarlierProfileOffer._exec`, the
one place it blocks.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings                                 # noqa: E402
from PyQt6.QtTest import QTest                                     # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget     # noqa: E402

from core.file_manager import FileManager, Project                 # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,           # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                              # noqa: E402
from ui import earlier_profile_offer as EPO                        # noqa: E402
from ui.measurement_target_bar import MeasurementTargetController  # noqa: E402

from tests.test_verification_profile_match import (                # noqa: E402
    HEADER_UTC, created_stamp, reference, vid, write_icc)
from workflow.verification_profile_match import profile_created    # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


class Env:
    """A project P with run1, a profile, and a recorder for every outcome."""

    def __init__(self, tmp_path, monkeypatch, answer="archive"):
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
        s.set("custom_output_path", str(tmp_path))
        self.fm = FileManager(s)
        self.project = Project.create(tmp_path / "P", "P")
        self.run = self.project.current_run()
        self.run.ensure_dir()
        self.run.verifications_dir.mkdir(parents=True, exist_ok=True)
        write_icc(self.run.profile_icc, HEADER_UTC)
        self.p = profile_created(self.run.profile_icc)
        self.fm.set_target_name("P")
        self.ctl = MeasurementTargetController(self.fm)
        self.parent = QWidget()
        self.busy = False
        self.opened: list = []
        self.lines: list = []
        self.asked: list = []
        self.answer = answer
        self.offer = EPO.EarlierProfileOffer(
            self.ctl, self.parent, busy=lambda: self.busy,
            open_create_chart=self.opened.append,
            log_line=self.lines.append)
        env = self

        def _exec(offer, box):
            env.asked.append(box.text())
            env.box = box
            wanted = box.defaultButton() if env.answer == "archive" \
                else box.escapeButton()
            wanted.click()
        monkeypatch.setattr(EPO.EarlierProfileOffer, "_exec", _exec)

    # the run's contents -----------------------------------------------------
    def date(self, when: datetime):
        v = self.run.verification(vid(when))
        v.ensure_dir()
        v.measurement_ti3.write_text("CTI3\nBEGIN_DATA\nEND_DATA\n",
                                     encoding="utf-8")
        (v.reports_dir).mkdir(exist_ok=True)
        (v.reports_dir / "report_x.json").write_text("{}", encoding="utf-8")
        return v

    def gamut_chart(self, created: datetime):
        self.run.verify_chart_ti2.write_text("CTI2\n", encoding="utf-8")
        reference(self.run.verifications_dir
                  / f"{self.run.verify_stem}-reference.ti3",
                  created_stamp(created))

    def ordinary_chart(self):
        self.run.verify_chart_ti2.write_text("CTI2\n", encoding="utf-8")

    # the user ----------------------------------------------------------------
    def choose_verification(self):
        self.ctl.set_profile_run("run1")
        self.ctl.set_run_type(RUN_TYPE_VERIFICATION)
        QTest.qWait(30)

    def choose_profiling(self):
        self.ctl.set_run_type(RUN_TYPE_PROFILING)
        QTest.qWait(30)


def _tree(root) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        h.update(str(p.relative_to(root)).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


@pytest.fixture
def env(qapp, tmp_path, monkeypatch):
    return Env(tmp_path, monkeypatch)


# ---------------------------------------------------------------------------
# the one trigger
# ---------------------------------------------------------------------------
def test_choosing_verification_asks(env):
    env.date(env.p - timedelta(days=1))
    env.ordinary_chart()
    env.choose_verification()
    assert len(env.asked) == 1


def test_profiling_never_asks(env):
    env.date(env.p - timedelta(days=1))
    env.ctl.set_profile_run("run1")
    QTest.qWait(30)
    assert env.asked == []


def test_selecting_a_date_never_asks(env, monkeypatch):
    """Start Measurement selects the date; the key leaves it out."""
    v = env.date(env.p - timedelta(days=1))
    env.ordinary_chart()
    env.answer = "keep"
    env.choose_verification()
    env.asked.clear()
    env.offer._kept.clear()          # so only the key can stop it
    env.ctl.set_verification_id(v.id)
    QTest.qWait(30)
    env.ctl.set_verification_id("")
    QTest.qWait(30)
    assert env.asked == []


def test_nothing_from_an_earlier_profile_asks_nothing(env):
    env.date(env.p + timedelta(days=1))
    env.ordinary_chart()
    env.choose_verification()
    assert env.asked == []


# ---------------------------------------------------------------------------
# waiting, and asking once
# ---------------------------------------------------------------------------
def test_never_while_measuring_or_building(env):
    env.date(env.p - timedelta(days=1))
    env.busy = True
    env.choose_verification()
    assert env.asked == []
    env.busy = False
    QTest.qWait(300)
    assert env.asked == [], "dropped, not held: the bar was locked"


def test_another_window_open_waits_and_asks_when_it_closes(env, monkeypatch):
    env.date(env.p - timedelta(days=1))
    state = {"modal": QWidget()}
    monkeypatch.setattr(EPO.QApplication, "activeModalWidget",
                        staticmethod(lambda: state["modal"]))
    env.choose_verification()
    QTest.qWait(EPO.WAIT_FOR_WINDOW_MS * 2)
    assert env.asked == [], "never on top of another window"
    state["modal"] = None
    QTest.qWait(EPO.WAIT_FOR_WINDOW_MS * 3)
    assert len(env.asked) == 1


def test_one_check_for_two_changes_in_one_go(env):
    """Load .ti2 changes the run type and the run together."""
    env.date(env.p - timedelta(days=1))
    env.ctl.set_run_type(RUN_TYPE_VERIFICATION)
    env.ctl.set_profile_run("run1")
    QTest.qWait(30)
    assert len(env.asked) == 1


# ---------------------------------------------------------------------------
# Keep
# ---------------------------------------------------------------------------
def test_keep_changes_nothing_on_disk(qapp, tmp_path, monkeypatch):
    env = Env(tmp_path, monkeypatch, answer="keep")
    env.date(env.p - timedelta(days=2))
    env.date(env.p - timedelta(days=1))
    env.gamut_chart(env.p - timedelta(days=3))
    before = _tree(env.run.dir)
    env.choose_verification()
    assert len(env.asked) == 1
    assert _tree(env.run.dir) == before
    assert env.opened == [] and env.lines == []


def test_keep_is_remembered_for_the_session_only(qapp, tmp_path, monkeypatch):
    env = Env(tmp_path, monkeypatch, answer="keep")
    env.date(env.p - timedelta(days=1))
    env.choose_verification()
    env.choose_profiling()
    env.choose_verification()
    assert len(env.asked) == 1, "asked once per session"
    # A restart is a new offer with an empty memory (5965626117).
    again = EPO.EarlierProfileOffer(
        env.ctl, env.parent, busy=lambda: False,
        open_create_chart=env.opened.append, log_line=env.lines.append)
    env.choose_profiling()
    env.choose_verification()
    assert len(env.asked) == 2
    del again


def test_a_rebuild_after_keep_asks_again(qapp, tmp_path, monkeypatch):
    env = Env(tmp_path, monkeypatch, answer="keep")
    env.date(env.p - timedelta(days=1))
    env.choose_verification()
    env.choose_profiling()
    write_icc(env.run.profile_icc, HEADER_UTC + timedelta(hours=5))
    env.choose_verification()
    assert len(env.asked) == 2


# ---------------------------------------------------------------------------
# Archive: text A, B and C
# ---------------------------------------------------------------------------
def _documents(env, dates):
    folder = env.run.verifications_dir / "reports"
    folder.mkdir(exist_ok=True)
    path = folder / "report_2026-10-01_10-00-00.json"
    path.write_text(json.dumps({"document": {"id": "d1", "measurements": [
        {"dir": str(env.run.verification(d).dir)} for d in dates]}}),
        encoding="utf-8")
    return path


def test_archive_a_moves_the_dates_and_their_reports_and_opens_gamut(env):
    a = env.date(env.p - timedelta(days=2))
    b = env.date(env.p - timedelta(days=1))
    later = env.date(env.p + timedelta(days=1))
    doc = _documents(env, [a.id, b.id])
    env.gamut_chart(env.p - timedelta(days=3))
    env.ctl.set_profile_run("run1")
    env.ctl.set_run_type(RUN_TYPE_VERIFICATION)
    env.ctl.set_verification_id(a.id)
    QTest.qWait(30)

    assert "earlier profile" in env.asked[0]
    olds = [d for d in env.run.verifications_old_dir.iterdir() if d.is_dir()]
    assert len(olds) == 1, "one timestamped folder for one answer"
    moved = sorted(p.name for p in olds[0].iterdir())
    assert moved == sorted([a.id, b.id, doc.name])
    assert (olds[0] / a.id / "reports" / "report_x.json").is_file()
    assert later.exists(), "a date of the current profile stays"
    # The chart moves at Generate Chart, as today, never from the window.
    assert env.run.verify_chart_ti2.exists()
    assert env.opened == [True], "Create Chart on FROM PROFILE GAMUT"
    assert env.ctl.target.verification_id == ""
    assert str(olds[0]) in env.lines[0]
    assert "have moved to this folder" in env.lines[0]


def test_archive_b_keeps_the_ordinary_chart_and_opens_create_chart(env):
    a = env.date(env.p - timedelta(days=1))
    env.ordinary_chart()
    env.choose_verification()
    assert "has moved to this folder" in env.lines[0]   # singular
    assert not a.exists()
    assert env.run.verify_chart_ti2.exists()
    assert env.opened == [False], ("Create Chart on the chart as it is "
                                   "(Knut 5965626117)")


def test_archive_c_moves_nothing_and_opens_gamut(env):
    env.gamut_chart(env.p - timedelta(days=3))
    before = _tree(env.run.dir)
    env.choose_verification()
    assert "verification chart in this run was made from an earlier" \
        in env.asked[0]
    assert _tree(env.run.dir) == before
    assert env.opened == [True] and env.lines == []


def test_after_archive_a_stale_chart_left_behind_is_asked_about_again(env):
    """Only Keep is remembered: no Generate, so text C the next time."""
    env.date(env.p - timedelta(days=1))
    env.gamut_chart(env.p - timedelta(days=3))
    env.choose_verification()
    env.choose_profiling()
    env.choose_verification()
    assert len(env.asked) == 2
    assert "verification chart in this run" in env.asked[1]


# ---------------------------------------------------------------------------
# the window itself
# ---------------------------------------------------------------------------
def test_the_window_buttons(env):
    from workflow import measurement_messages as M
    env.date(env.p - timedelta(days=2))
    env.date(env.p - timedelta(days=1))
    env.gamut_chart(env.p - timedelta(days=3))
    env.answer = "keep"
    env.choose_verification()
    box = env.box
    assert box.defaultButton().text() == M.M_EARLIER_ARCHIVE_NEW_CHART
    assert box.escapeButton().text() == M.M_EARLIER_KEEP
    assert box.icon() == QMessageBox.Icon.NoIcon
    assert env.p.strftime("%Y-%m-%d %H:%M") in box.informativeText()
    assert "The 2 dated verification measurements" in box.informativeText()


def test_no_sound():
    """Knut, 5964076758 Q5."""
    src = inspect.getsource(EPO)
    assert "sound" not in src.replace("No sound", "").replace(
        "no sound", "")


def test_the_main_window_builds_it_before_the_tabs_get_the_controller():
    """So its check is queued ahead of the Measure tab's arrival windows."""
    from ui.main_window import MainWindow
    src = inspect.getsource(MainWindow.__init__)
    assert src.index("EarlierProfileOffer(") < src.index(
        "set_target_controller(self._target_ctl)")


# ---------------------------------------------------------------------------
# the Measure tab's arrival windows yield to any open window
# ---------------------------------------------------------------------------
def test_the_measure_tab_waits_for_an_open_window(qapp, tmp_path, monkeypatch):
    from core.argyll_runner import ArgyllRunner
    from ui.tabs import tab_measure as TM
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    tab = TM.TabMeasure(ArgyllRunner(s), s)
    calls: list = []
    monkeypatch.setattr(TM.TabMeasure, "_queue_verification_preflight",
                        lambda self: calls.append("preflight"))
    monkeypatch.setattr(TM.TabMeasure, "_queue_overlay_offer",
                        lambda self: calls.append("offer"))
    state = {"modal": QWidget()}
    monkeypatch.setattr(TM.QApplication, "activeModalWidget",
                        staticmethod(lambda: state["modal"]))
    assert tab._another_window_is_open("preflight")
    assert tab._another_window_is_open("offer")
    QTest.qWait(600)
    assert calls == [], "still open: nothing is asked"
    state["modal"] = None
    QTest.qWait(600)
    assert sorted(calls) == ["offer", "preflight"]


def test_both_arrival_windows_ask_the_question():
    from ui.tabs.tab_measure import TabMeasure
    for name in ("_show_verification_preflight_now",
                 "_offer_existing_overlay_now"):
        assert "_another_window_is_open(" in inspect.getsource(
            getattr(TabMeasure, name)), name


# ---------------------------------------------------------------------------
# the whole app: Archive on text A lands on Create Chart, FROM PROFILE GAMUT
# ---------------------------------------------------------------------------
def test_the_main_window_opens_create_chart_on_the_gamut_module(
        qapp, tmp_path, monkeypatch):
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    proj = Project.create(tmp_path / "projects" / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    run.verifications_dir.mkdir(parents=True)
    write_icc(run.profile_icc, HEADER_UTC)
    p = profile_created(run.profile_icc)
    v = run.verification(vid(p - timedelta(days=1)))
    v.ensure_dir()
    v.measurement_ti3.write_text("CTI3\nBEGIN_DATA\nEND_DATA\n",
                                 encoding="utf-8")
    run.verify_chart_ti2.write_text("CTI2\n", encoding="utf-8")
    reference(run.verifications_dir / f"{run.verify_stem}-reference.ti3",
              created_stamp(p - timedelta(days=2)))
    asked: list = []

    def _exec(offer, box):
        asked.append(box.text())
        box.defaultButton().click()
    monkeypatch.setattr(EPO.EarlierProfileOffer, "_exec", _exec)

    w = MainWindow(s)
    try:
        w._tabs.setCurrentWidget(w._tab_measure)
        w._file_mgr.set_target_name("P")
        w._target_ctl.set_profile_run("run1")
        w._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
        QTest.qWait(100)
        assert len(asked) == 1
        assert w._tabs.currentWidget() is w._tab_chart
        assert w._tab_chart._mode_name() == "gamut"
        assert not v.exists()
        assert run.verify_chart_ti2.exists(), "moved at Generate, not here"
        assert "have moved" in w._tab_chart._log.toPlainText() or \
            "has moved" in w._tab_chart._log.toPlainText()
    finally:
        w.close()
        w.deleteLater()


# ---------------------------------------------------------------------------
# review of the §6f build (2026-10-03)
# ---------------------------------------------------------------------------
def test_text_b_without_a_chart_says_nothing_about_a_chart(env):
    """Old dates and no verification chart at all: B's "the chart itself can
    still be used" and "the chart stays" would be untrue."""
    from workflow import measurement_messages as M
    env.date(env.p - timedelta(days=2))
    env.date(env.p - timedelta(days=1))
    env.answer = "keep"
    env.choose_verification()
    body = env.box.informativeText()
    title, expected = M.M_VERIFY_EARLIER_PROFILE_NO_CHART.render(
        n=2, date=vid(env.p - timedelta(days=2))[:10],
        profile_when=env.p.strftime("%Y-%m-%d %H:%M"))
    assert body == expected
    assert "chart" not in body.replace("Create Chart", "").lower()
    assert env.box.defaultButton().text() == M.M_EARLIER_ARCHIVE


def test_text_b_with_a_chart_still_names_it(env):
    env.date(env.p - timedelta(days=1))
    env.ordinary_chart()
    env.answer = "keep"
    env.choose_verification()
    assert "can still be used" in env.box.informativeText()


def test_the_settle_overlay_window_waits_for_an_open_window():
    """The third window a selection change can raise from the Measure tab
    (M-OVERLAY-NO-MEASUREMENT through a stored overlay tick) yields too."""
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._settle_after_selection_change)
    assert src.index('_another_window_is_open("settle")') < src.index(
        "self._on_overlay_toggled(True)")
    assert '"settle" in owed' in inspect.getsource(
        TabMeasure._after_other_window_closed)


@pytest.mark.parametrize("chart, module", [
    ("ordinary", "manual"),
    ("gamut-current", "gamut"),
])
def test_text_b_opens_the_kept_chart_in_its_own_module(
        qapp, tmp_path, monkeypatch, chart, module):
    """Knut 5965626117: Create Chart opens on the kept chart "so that the user
    can confirm if this is the chart he wants to use, and then move to
    printing". An ordinary chart is shown in Manual, not under FROM PROFILE
    GAMUT (whose Generate would replace it); a gamut chart from the current
    profile stays on its module."""
    from ui.main_window import MainWindow

    s = AppSettings()
    s.set("custom_output_path", str(tmp_path / "projects"))
    s.set("session_project", "")
    s.set("restore_last_session", False)
    proj = Project.create(tmp_path / "projects" / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    run.verifications_dir.mkdir(parents=True)
    write_icc(run.profile_icc, HEADER_UTC)
    p = profile_created(run.profile_icc)
    v = run.verification(vid(p - timedelta(days=1)))
    v.ensure_dir()
    v.measurement_ti3.write_text("CTI3\nBEGIN_DATA\nEND_DATA\n",
                                 encoding="utf-8")
    run.verify_chart_ti2.write_text("CTI2\n", encoding="utf-8")
    if chart == "gamut-current":
        reference(run.verifications_dir / f"{run.verify_stem}-reference.ti3",
                  created_stamp(p + timedelta(hours=1)))
    asked: list = []

    def _exec(offer, box):
        asked.append(box.text())
        box.defaultButton().click()
    monkeypatch.setattr(EPO.EarlierProfileOffer, "_exec", _exec)

    w = MainWindow(s)
    try:
        w._tabs.setCurrentWidget(w._tab_measure)
        w._file_mgr.set_target_name("P")
        w._target_ctl.set_profile_run("run1")
        w._target_ctl.set_run_type(RUN_TYPE_VERIFICATION)
        QTest.qWait(150)
        for _ in range(40):          # the module switch is one tick later
            if w._tab_chart._mode_name() == module:
                break
            QTest.qWait(50)
        assert len(asked) == 1
        assert w._tabs.currentWidget() is w._tab_chart
        assert w._tab_chart._mode_name() == module
        assert not getattr(w._tab_chart, "_user_chose_module", False), \
            "not a choice by hand: the 2026-08-10 default is left alone"
        assert run.verify_chart_ti2.exists()
        assert not v.exists()
    finally:
        w.close()
        w.deleteLater()


def test_the_measure_tab_waits_while_the_earlier_profile_check_is_pending(
        qapp, tmp_path, monkeypatch):
    """Ours is asked FIRST (Archive changes what the offer would say). Being
    connected first was not enough: a zero-delay QTimer.singleShot is a posted
    call, delivered before the offer's QTimer, and on screen the existing-
    measurement offer opened ahead of it 3 times in 3."""
    from core.argyll_runner import ArgyllRunner
    from ui.tabs import tab_measure as TM

    class Pending:
        busy = True

        def pending(self):
            return self.busy

    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    host = QWidget()
    host._earlier_profile_offer = Pending()
    tab = TM.TabMeasure(ArgyllRunner(s), s)
    tab.setParent(host)
    calls: list = []
    monkeypatch.setattr(TM.TabMeasure, "_queue_overlay_offer",
                        lambda self: calls.append("offer"))
    monkeypatch.setattr(TM.QApplication, "activeModalWidget",
                        staticmethod(lambda: None))
    assert tab._another_window_is_open("offer")
    QTest.qWait(600)
    assert calls == []
    host._earlier_profile_offer.busy = False
    QTest.qWait(600)
    assert calls == ["offer"]


def test_pending_covers_queued_and_waiting(env, monkeypatch):
    env.date(env.p - timedelta(days=1))
    assert not env.offer.pending()
    env.offer._queue()
    assert env.offer.pending()
    QTest.qWait(30)
    assert not env.offer.pending()
