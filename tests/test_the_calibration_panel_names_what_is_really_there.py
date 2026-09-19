"""Three sentences in the calibration flow described an app that no longer
exists, and each of them sent a user somewhere.

Adversary round 26, R26-F2 and R26-F3, driven on screen:

* **Apply Calibration could not find the project's calibration.** Its autofill
  looked for ``cal/calibration.cal``. The name is ``cal/<project>-cal.cal``
  (`Calibration.stem`), which is also what `printcal` writes, and the literal
  "calibration.cal" occurred exactly once in the whole tree: on that line. So
  the field filled itself in one situation only, the session that made the
  calibration, from printcal's own finish handler. Every later session was
  blank, in the ordinary case of coming back to a project the next day.
* **The success window sent the user to a checkbox #137 removed.** "untick
  *Create chart for calibration* in the **Calibration Chart** box" - a group
  `TabChart.set_calibration_mode` hides unconditionally, as its own docstring
  says.
* **The output field promised a filename nothing writes.**
  ``cal_<name>.icc``, where the app writes `Run.calibrated_icc`.

The first two are pinned against the CLASSES THAT OWN THE ANSWER rather than
against a second copy of the string: `Calibration.cal_path` for the file, and
`Run.calibrated_icc` for the name. A guard that spells the expected name a
second time agrees with whatever the code was doing the day it was written.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtCore import QSettings  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

from core.argyll_runner import ArgyllRunner  # noqa: E402
from core.file_manager import Calibration, Run  # noqa: E402
from core.settings import AppSettings  # noqa: E402
from ui.tabs.tab_profile import TabProfile  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _tab(tmp_path):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    return TabProfile(ArgyllRunner(s), s)


def test_apply_calibration_finds_the_project_s_own_calibration(qapp, tmp_path):
    """The door is the Apply Calibration page, not the autofill helper.

    **THE MEASUREMENT IS DELIBERATELY NOT NAMED AFTER THE CALIBRATION.** The
    first version of this guard wrote `cal/<stem>.ti3` beside
    `cal/<stem>.cal`, and it passed with the broken code put back, because the
    fix's own fallback - the measurement's stem with `.cal` - answered it. A
    fixture too tidy to contain the fault agrees with the code. Here only
    `Calibration.cal_path` can find the file.
    """
    proj = tmp_path / "Demo-Paper"
    cal = Calibration(proj)
    cal.dir.mkdir(parents=True)
    ti3 = cal.dir / "measured-on-tuesday.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    cal.cal_path.write_text("CAL\n", encoding="utf-8")
    assert ti3.with_suffix(".cal") != cal.cal_path

    tab = _tab(tmp_path)
    tab._cal_ti3_path = ti3
    tab._switch_cal_mode(2)          # the button a person presses

    assert tab._ac_cal_edit.text() == str(cal.cal_path), (
        "the calibration on disk was not found: R26-F2")


def test_a_calibration_measured_under_another_name_is_still_found(qapp, tmp_path):
    """printcal names its output after the measurement it read, so a `.cal`
    that does not follow `Calibration.stem` is a real case, not a hypothetical:
    that is the fallback, and it needs its own guard or nothing measures it."""
    proj = tmp_path / "Demo-Paper"
    cal = Calibration(proj)
    cal.dir.mkdir(parents=True)
    ti3 = cal.dir / "measured-on-tuesday.ti3"
    ti3.write_text("CTI3\n", encoding="utf-8")
    beside = ti3.with_suffix(".cal")
    beside.write_text("CAL\n", encoding="utf-8")
    assert not cal.cal_path.exists()

    tab = _tab(tmp_path)
    tab._cal_ti3_path = ti3
    tab._switch_cal_mode(2)

    assert tab._ac_cal_edit.text() == str(beside)


def test_the_output_placeholder_names_the_file_the_app_writes(qapp, tmp_path):
    tab = _tab(tmp_path)
    tab._ac_update_out_placeholder("")
    blank = tab._ac_out_edit.placeholderText()
    tab._ac_update_out_placeholder(str(tmp_path / "some-profile.icc"))
    chosen = tab._ac_out_edit.placeholderText()

    written = Run.for_dir(tmp_path).calibrated_icc.name      # "calibrated.icc"
    for text in (blank, chosen):
        assert written in text, f"the field promises something else: {text!r}"
        assert "cal_" not in text, (
            "the cal_ prefix went with #127 and the app does not write it")


def test_the_success_window_does_not_send_anyone_to_a_retired_checkbox(
        qapp, tmp_path, monkeypatch):
    """The window is built and read without being shown: `exec` would block."""
    tab = _tab(tmp_path)
    seen = {}

    from PyQt6.QtWidgets import QDialog

    def _capture(self):
        seen["texts"] = [l.text() for l in self.findChildren(QLabel)]
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", _capture)
    tab._show_printcal_result_dialog(tmp_path / "Demo-Paper-cal.cal")

    whole = " ".join(seen.get("texts", []))
    assert whole, "the window said nothing"
    assert "Create chart for calibration" not in whole, (
        "the window still names the checkbox #137 retired: R26-F3a")
    assert "Calibration Chart" not in whole
    assert "Run type" in whole, (
        "and it must say what to do instead, on the control that replaced it")
