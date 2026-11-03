"""FD-9 (Beta) review round 2: M1 to M4.

S1 and S2 (an FD-9 project opened with the Beta off) are proved on the real
window in `test_fd9_off_stale_project.py` and, rule by rule, in
`test_fd9_off_changes_nothing.py`.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests._fd9_beta import fd9_beta_on, fd9_windows  # noqa: F401
from tests.test_fd9_beta_option import fd9_chart, tab  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent


# ---- M1: Guided gives the Pages value back --------------------------------
@pytest.fixture
def chart_tab(qapp, tmp_path, qtbot):
    from PyQt6.QtCore import QSettings
    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.settings import AppSettings
    from ui.tabs.tab_chart import TabChart
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "isolated.ini"),
                      QSettings.Format.IniFormat)
    s.set("custom_output_path", str(tmp_path / "projects"))
    t = TabChart(ArgyllRunner(s), FileManager(s), s)
    qtbot.addWidget(t)
    return t


def test_leaving_the_fd9_in_guided_gives_back_the_pages_it_replaced(
        chart_tab):
    t = chart_tab
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("i1"))
    t._pages_spin.setValue(3)
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("FD9"))
    assert t._pages_spin.maximum() == 1 and t._pages_spin.value() == 1
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("CM"))
    assert t._pages_spin.maximum() == 20
    assert t._pages_spin.value() == 3, (
        "leaving the FD-9 kept its one page instead of the 3 it replaced")
    # Once given back it is not given back again over a later choice.
    t._pages_spin.setValue(5)
    t._instr_combo.setCurrentIndex(t._instr_combo.findData("i1"))
    assert t._pages_spin.value() == 5


# ---- M2: the exception's TYPE decides, through the wrapper ----------------
def _wrapped(cause):
    from workflow.fd9.independent import CaptureFailed
    return CaptureFailed("/tmp/s", "Capture failed; evidence preserved: "
                         + str(cause), cause=cause)


@pytest.mark.parametrize("cause,kind", [
    # A device fault whose words nobody listed: the type says network.
    (ConnectionResetError(0, "the device went away"), "connection"),
    (TimeoutError("no answer in 30 s"), "connection"),
    # And an OSError that is not the network stays out of that window.
    (FileNotFoundError(2, "No such file or directory", "scan.pgm"), "failed"),
    (RuntimeError("Sensor model version is not supported"), "firmware"),
])
def test_a_wrapped_capture_failure_is_judged_by_its_cause(cause, kind):
    from ui.fd9_measurement import fd9_exception_kind
    assert fd9_exception_kind(_wrapped(cause)) == kind


@pytest.mark.parametrize("words", [
    "Capture failed; evidence preserved: [WinError 10061] No connection could "
    "be made because the target machine actively refused it",
    "Capture failed; evidence preserved: [WinError 10060] A connection "
    "attempt failed because the connected party did not properly respond "
    "after a period of time",
])
def test_windows_words_for_a_refused_connection_are_a_connection_problem(
        words):
    from ui.fd9_measurement import fd9_error_kind, fd9_exception_kind
    assert fd9_error_kind(words) == "connection"
    assert fd9_exception_kind(RuntimeError(words)) == "connection"


def test_capture_layout_keeps_the_exception_that_ended_it(tmp_path,
                                                          monkeypatch):
    """The glue's own wrapper (`workflow.fd9.independent.capture_layout`)
    carries the cause, and `_measure_chart` passes it on when it re-raises."""
    import workflow.fd9.independent as ind
    from workflow.fd9.independent import CaptureFailed
    src = Path(ind.__file__).read_text(encoding="utf-8")
    assert "cause=failure" in src
    m = (ROOT / "workflow/fd9/measurement.py").read_text(encoding="utf-8")
    assert "cause=acquisition_cause" in m
    assert '"acquisition_exception": acquisition_cause' in m
    e = CaptureFailed(tmp_path, "x", cause=ConnectionRefusedError(61, "r"))
    assert isinstance(e.cause, ConnectionRefusedError)
    assert e.__cause__ is e.cause


def test_a_partial_result_names_its_window_by_the_exceptions_type(
        tab, fd9_chart, fd9_windows, monkeypatch, tmp_path):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._fd9_job = SimpleNamespace(stop_event=threading.Event())
    monkeypatch.setattr(tab, "_fd9_end_prompt", lambda *a: None)
    result = {"chart": str(fd9_chart), "staged": str(tmp_path / "s.ti3"),
              "session": str(tmp_path), "new_readings": 3, "patches": 3,
              "acquisition_error": "Capture failed; evidence preserved: "
                                   "the device went away",
              "acquisition_exception": ConnectionResetError(0, "gone")}
    tab._fd9_result(result)
    assert [w[0] for w in fd9_windows] == ["M-FD9-NO-CONNECTION"]


# ---- M3: the verification snapshot before the replace question ------------
def test_fd9_start_takes_the_snapshot_before_the_replace_question(
        tab, fd9_chart, monkeypatch):
    tab.set_ti1_path(fd9_chart.with_suffix(".ti1"))
    tab._settings.set("fd9_host", "10.0.0.9")
    for name in ("_blocked_by_new_run", "_blocked_by_missing_chart_file"):
        monkeypatch.setattr(tab, name, lambda: False)
    monkeypatch.setattr(tab, "_blocked_by_a_misfitting_measurement",
                        lambda params=None: False)
    monkeypatch.setattr(tab, "_verification_guard", lambda: None)
    order = []

    def snap():
        order.append("snapshot")
        return True

    def ask():
        order.append("replace question")
        return False                     # the user keeps what they have

    monkeypatch.setattr(tab, "_snapshot_verification_chart", snap)
    monkeypatch.setattr(tab, "_confirm_replacing_measurement", ask)
    tab._start_fd9_measurement()
    assert order == ["snapshot", "replace question"], (
        "the FD-9 asks in a different order from every other instrument")
    assert not tab._fd9_live


def test_every_instrument_takes_the_snapshot_before_the_replace_question():
    """The rule M3 aligns the FD-9 to, read from `TabMeasure._on_start`."""
    import inspect
    from ui.tabs.tab_measure import TabMeasure
    src = inspect.getsource(TabMeasure._on_start)
    assert (src.index("self._snapshot_verification_chart()")
            < src.index("self._confirm_replacing_measurement()"))


# ---- M4: the FD-9 driver's licence, where a built app keeps it -------------
def test_the_licence_list_names_the_fd9_driver_licence_of_a_built_app(
        tmp_path, monkeypatch):
    import ui.licences as lic
    frozen = tmp_path / "bundle"
    (frozen / "licenses/fd9-independent").mkdir(parents=True)
    (frozen / "licenses/fd9-independent/LICENSE").write_text("GPL", encoding="utf-8")
    (frozen / "LICENSE").write_text("GPL", encoding="utf-8")
    monkeypatch.setattr(lic, "resource_path", lambda rel: frozen / rel)
    got = [lic.licence_file_label(p) for p in lic.bundled_licence_files()]
    assert "licenses/fd9-independent/LICENSE" in got


def test_the_licence_list_names_it_in_the_source_tree_too():
    import ui.licences as lic
    got = [lic.licence_file_label(p) for p in lic.bundled_licence_files()]
    assert "vendor/fd9-independent/LICENSE" in got


def test_the_licence_page_lists_and_reveals_each_licence_file(qapp,
                                                              monkeypatch,
                                                              tmp_path):
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QLabel, QPushButton
    import ui.licences as lic
    from core.settings import AppSettings
    from ui.dialogs.settings_dialog import SettingsDialog
    revealed = []
    monkeypatch.setattr(lic, "reveal_file",
                        lambda path, *a: revealed.append(Path(path)))
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "a.ini"), QSettings.Format.IniFormat)
    dlg = SettingsDialog(s)
    try:
        page = dlg._build_licences_tab()
        labels = [w.text() for w in page.findChildren(QLabel)]
        assert "vendor/fd9-independent/LICENSE" in labels
        buttons = [b for b in page.findChildren(QPushButton)
                   if b.objectName() == "licence_reveal"]
        assert len(buttons) == len(lic.bundled_licence_files())
        fd9 = next(b for b in buttons
                   if b.toolTip().endswith("fd9-independent/LICENSE"))
        fd9.click()
        assert revealed and revealed[-1].as_posix().endswith(
            "vendor/fd9-independent/LICENSE")
    finally:
        dlg.deleteLater()


def test_the_notices_name_where_a_built_app_keeps_the_fd9_licence():
    text = (ROOT / "THIRD-PARTY-NOTICES.md").read_text(encoding="utf-8")
    i = text.index("## Independent FD-9 source")
    section = text[i:text.index("\n## ", i + 5)]
    assert "`licenses/fd9-independent/LICENSE`" in section
    assert "`vendor/fd9-independent/LICENSE`" in section
    for spec in ("ChromIQ.spec", "ChromIQWin.spec", "ChromIQLinux.spec"):
        assert ("('vendor/fd9-independent/LICENSE', "
                "'licenses/fd9-independent')") in (ROOT / spec).read_text(
                    encoding="utf-8"), spec
