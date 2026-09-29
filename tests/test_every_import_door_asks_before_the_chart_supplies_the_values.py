"""One door asked "Only you can confirm this is a measurement of this chart".
The other filed the same file without a word.

A measurement made in i1Profiler's measure tool on a chart it did not generate
carries the patch NAME and the colour and no device values at all. ChromIQ
pairs it with the chart by name and takes the device values from the chart.
What it cannot then do is check the pairing: that check compares device values,
and the file has none. `ui/tabs/tab_measure.py` therefore puts the question to
the person, and says why in its own comment: *"this is the one thing ChromIQ
genuinely cannot check … another chart laid out the same way would carry the
same names. Only the person who printed the sheet knows."*

The Build Profile / Check & Refine filing doors reach the identical act, through
`say_what_was_filed` -> `complete_from_chart`, and asked nothing.

Driven on screen, adversarial round four, 2026-09-12: an i1Profiler-shaped
export (SAMPLE_ID in reading order, SAMPLE_LOC, XYZ, no device column) of a
30-patch chart was handed to `file_into_project` on a project whose run held a
chart with those same 30 names. The only window that appeared was "Where should
the measurement go?". The copy landed in `runs/run2` carrying
``CHROMIQ_DEVICE_FROM_CHART "PairProbe.ti2"`` and the chart's RGB columns, and
nobody was ever asked whether the sheet had been printed from that chart.

The question is asked BEFORE the copy, at both doors, so its own last sentence
("Cancel changes nothing") is true: driven again after the fix, Cancel left the
project with `["run1"]` exactly as it found it and filed nothing.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMessageBox,   # noqa: E402
                             QWidget)

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from workflow import measurement_messages as M            # noqa: E402
from workflow.measurement_import import assess            # noqa: E402
from workflow.measurement_pairing import device_came_from_chart  # noqa: E402

STEPS, STRIPS = 6, 5
DESIGNED = STEPS * STRIPS
_FIELDS = "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def parent(qapp):
    """A real widget: the door reaches `parent.window()` for the run picker."""
    w = QWidget()
    yield w
    w.deleteLater()


def _locs() -> "list[str]":
    return [f"{chr(ord('A') + s)}{p + 1}"
            for s in range(STRIPS) for p in range(STEPS)]


def _write_chart(ti2: Path) -> None:
    slots = _locs()[3:] + _locs()[:3]
    rows = [f'{i + 1} "{slots[i]}" {i % 101}.0 {(i * 2) % 101}.0 '
            f'{(i * 3) % 101}.0 40.0 42.0 44.0' for i in range(DESIGNED)]
    ti2.write_text(
        'CTI2\n\nDESCRIPTOR "x"\nORIGINATOR "ChromIQ layout engine"\n'
        f'COLOR_REP "iRGB"\nSTEPS_IN_PASS "{STEPS}"\n\n'
        f"NUMBER_OF_FIELDS {len(_FIELDS.split())}\n"
        f"BEGIN_DATA_FORMAT\n{_FIELDS}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    d = [f"{i + 1} 0.0 0.0 0.0" for i in range(DESIGNED)]
    ti2.with_suffix(".ti1").write_text(
        'CTI1\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n'
        f"NUMBER_OF_SETS {DESIGNED}\nBEGIN_DATA\n" + "\n".join(d)
        + "\nEND_DATA\n", encoding="utf-8")


def _write_device_less_measurement(path: Path) -> Path:
    """i1Profiler's own shape: reading order, the printed name, XYZ, no ink."""
    reading = [f"{chr(ord('A') + s)}{p + 1}"
               for p in range(STEPS) for s in range(STRIPS)]
    f = "SAMPLE_ID SAMPLE_LOC XYZ_X XYZ_Y XYZ_Z"
    rows = [f'{i + 1} "{loc}" {30 + i % 40}.0 {31 + i % 40}.0 {32 + i % 40}.0'
            for i, loc in enumerate(reading)]
    path.write_text(
        'CTI3\n\nDESCRIPTOR "x"\nORIGINATOR "Argyll target"\n'
        'DEVICE_CLASS "OUTPUT"\n\n'
        f"NUMBER_OF_FIELDS {len(f.split())}\n"
        f"BEGIN_DATA_FORMAT\n{f}\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n" + "\n".join(rows)
        + "\nEND_DATA\n", encoding="utf-8")
    return path


@pytest.fixture
def staged(tmp_path):
    """A project whose run1 holds the chart, and the device-less file."""
    root = tmp_path / "out"
    root.mkdir()
    proj = Project.create(root / "PairProbe", "PairProbe")
    run = proj.current_run()
    run.ensure_dir()
    _write_chart(run.chart_ti2)
    src = _write_device_less_measurement(tmp_path / "export.ti3")
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s.set("custom_output_path", str(root))
    return proj, run, src, s


def test_the_file_really_is_the_case_the_question_exists_for(staged):
    """The fixture has to reach `device_from_chart`, or the tests below pass
    because nothing was asked of anything."""
    _proj, run, src, _s = staged
    v = assess(src, run.chart_ti2)
    assert v.ok and v.device_from_chart, (v.ok, v.reason, v.device_from_chart)
    assert v.n_measured == DESIGNED


def _answer(monkeypatch, clicks: list, say_yes: bool):
    """Answer every QMessageBox, recording each one's title."""
    real_exec = QMessageBox.exec

    def fake_exec(self):
        clicks.append(self.text() or self.windowTitle())
        want = (QMessageBox.ButtonRole.AcceptRole if say_yes
                else QMessageBox.ButtonRole.RejectRole)
        for b in self.buttons():
            if self.buttonRole(b) == want:
                self.setResult(0)
                self._clicked = b
                return 0
        return 0

    # QMessageBox.clickedButton() only answers after a real click, so the
    # doors are driven through the button itself.
    def fake_exec_click(self):
        clicks.append(self.text() or self.windowTitle())
        want = (QMessageBox.ButtonRole.AcceptRole if say_yes
                else QMessageBox.ButtonRole.RejectRole)
        for b in self.buttons():
            if self.buttonRole(b) == want:
                b.click()
                return 0
        return real_exec(self)

    monkeypatch.setattr(QMessageBox, "exec", fake_exec_click)
    return clicks


def _asked_it(clicks) -> bool:
    title, _body = M.M_IMPORT_DEVICE_FROM_CHART.render(count=2, chart="x.ti2")
    return any(title in c for c in clicks)


def test_the_filing_door_asks_before_the_chart_supplies_the_values(
        parent, staged, monkeypatch):
    """MUTATION: delete the `only_you_can_confirm_the_chart` call from
    `file_into_project` and this goes red. Watched, 2026-09-12."""
    proj, run, src, s = staged
    from ui import measurement_filing as mf
    clicks: list = []
    _answer(monkeypatch, clicks, say_yes=True)
    filed: list = []
    mf.file_into_project(parent, "PairProbe", src, _fm(s), None,
                         on_filed=filed.append)
    assert _asked_it(clicks), (
        "the filing door took the chart's device values without asking: "
        + repr(clicks))
    assert filed, "the import did not happen after the person said yes"
    assert device_came_from_chart(Path(filed[0])) == run.chart_ti2.name


def test_cancel_really_changes_nothing(parent, staged, monkeypatch):
    """The question's own last sentence. It is asked before the copy, so a run
    must not be left behind either.

    MUTATION: move the call below `shutil.copy2` and this goes red on the run
    list."""
    proj, run, src, s = staged
    from ui import measurement_filing as mf
    before = sorted(p.name for p in proj.runs_root.iterdir() if p.is_dir())
    clicks: list = []
    _answer(monkeypatch, clicks, say_yes=False)
    filed: list = []
    mf.file_into_project(parent, "PairProbe", src, _fm(s), None,
                         on_filed=filed.append)
    assert _asked_it(clicks), repr(clicks)
    assert not filed, "Cancel filed the measurement anyway"
    after = sorted(p.name for p in proj.runs_root.iterdir() if p.is_dir())
    assert after == before, f"Cancel left a run behind: {before} -> {after}"
    assert not run.measurement_ti3.is_file()


def test_a_measurement_that_has_device_values_is_not_interrogated(
        parent, tmp_path, monkeypatch):
    """The question is only for the case ChromIQ cannot check. A file that
    carries its own device values is checked against the chart, so asking
    would be asking the person to do work the app has already done."""
    from ui import measurement_filing as mf
    v = type("V", (), {"ok": True, "device_from_chart": False,
                       "n_measured": 30})()
    clicks: list = []
    _answer(monkeypatch, clicks, say_yes=False)
    assert mf.only_you_can_confirm_the_chart(parent, v, Path("x.ti2")) is True
    assert clicks == [], "a checked measurement was interrogated"


def test_both_filing_doors_carry_the_guard():
    """THE SOURCE. The two doors are 200 lines apart and one of them has
    always been the one that forgot; a test that drove only the first would
    pass with the second unguarded."""
    import inspect

    from ui import measurement_filing as mf
    for fn in (mf.file_into_project, mf.make_new_project_and_file):
        src = inspect.getsource(fn)
        assert "only_you_can_confirm_the_chart" in src, (
            f"{fn.__name__} files a device-less measurement without asking")


def _fm(settings):
    """A FileManager already OPEN on the project.

    `open_the_project` short-circuits when the manager is already there, which
    is the state the on-screen drive reached through the real Create Chart tab;
    without it the door answers NO_MACHINERY and never reaches the question.
    """
    from core.file_manager import FileManager
    fm = FileManager(settings)
    fm.set_target_name("PairProbe")
    return fm
