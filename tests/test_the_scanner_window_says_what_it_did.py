"""Beta 8, B8-30 / B8-31 / B8-32 — one inert control and three silences.

All four were found by driving the real window (`beta 8/11-regression-sweep`,
checks J10, J18, J26 and J32) and all four are about the same thing: the window
showing something that is not so.

* **B8-30** "Correct perspective (slightly skewed scan)" was on screen, enabled
  and **ticked by default**, and could not reach any command this window runs.
  `scanin_args` appends ``-p`` only when ``corners is None`` and all four scanin
  call sites pass ``corners=self._scanin_corners(...)``. Measured ticked and
  unticked: identical argv, ``-F`` present, ``-p`` absent.
* **B8-31** Sample area, "Use fiducial marks" and "Save a diagnostic image"
  were kept by nothing — not "Save as Defaults", which wrote exactly one key
  and it was not this one, and so not across a window close either.
* **B8-32 / F-7** An averaging slot left empty is skipped, silently: the shot
  bar reads "Scan 1 / Scan 2" while the build runs one scanin, no averaging
  step, and ends "[OK] Scanner profile saved".
* **B8-32 / F-9** Changing "Target type" discards the loaded scan, its four
  corners and every other shot on the page, into a log that is cleared in the
  same block.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QCheckBox     # noqa: E402

from core.settings import DEFAULTS                      # noqa: E402
from ui.dialogs.scanin_dialog import ScannerProfileDialog  # noqa: E402
from workflow.scanin_runner import ScaninParams, scanin_args  # noqa: E402


class _FakeSettings:
    """DEFAULTS plus a real temp output root — the dialog provisions standard
    targets on open and must never write into the developer's own ~/ChromIQ."""

    def __init__(self, out_dir, **overrides):
        self._store = {**DEFAULTS, **overrides,
                       "custom_output_path": str(out_dir)}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def _out_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("agentM-scanner")


def _dialog(_app, out_dir, settings=None):
    return ScannerProfileDialog(object(), settings or _FakeSettings(out_dir))


# ---------------------------------------------------------------- B8-30 ----
def test_the_window_offers_no_control_that_cannot_act(_app, _out_dir):
    """Asked of the built window, not of the source: every checkbox in it, by
    the words a user reads."""
    dlg = _dialog(_app, _out_dir)
    try:
        labels = [cb.text() or "" for cb in dlg.findChildren(QCheckBox)]
        assert labels, "the window has no checkboxes at all — wrong question"
        offenders = [t for t in labels if "perspective" in t.lower()]
        assert not offenders, (
            f"a control that can never change a command line is still offered: "
            f"{offenders}")
        assert not hasattr(dlg, "_perspective")
    finally:
        dlg.deleteLater()


def test_no_help_text_in_this_window_still_explains_it(_app, _out_dir):
    """Removing a widget and leaving its paragraph behind is half a fix — and
    the paragraph was the untrue half: *"There's no downside to leaving it
    on"* described a switch that did nothing at all.

    Only the strings that reach a SCREEN are checked, parsed out of `tr()`
    calls rather than grepped, so the comment recording why the control was
    removed is not mistaken for the help text that described it.
    """
    import ast
    import textwrap

    src = textwrap.dedent(inspect.getsource(ScannerProfileDialog))
    shown = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "tr" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            shown.append(node.args[0].value)
    assert shown, "no translated literals found — wrong question"
    offenders = [t[:90] for t in shown if "perspective" in t.lower()]
    assert not offenders, (
        f"the window still shows text about a control it no longer has: "
        f"{offenders}")


def test_removing_it_changed_no_command_line(tmp_path):
    """The argv is identical either way, so the removal is provably neutral.

    This is the measurement the decision rests on: with corners given — which
    every one of this window's call sites does — the flag is suppressed, so
    ticking it and unticking it produced the same command. Removing the control
    removes a choice that had no consequence.
    """
    scan, cht, cie = (tmp_path / "s.tif", tmp_path / "c.cht", tmp_path / "r.cie")
    corners = [(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)]
    on = scanin_args(scan, cht, cie, corners=corners, perspective=True)
    off = scanin_args(scan, cht, cie, corners=corners, perspective=False)
    assert on == off, (on, off)
    assert "-p" not in on and "-F" in on
    # …and with no corners it is still a real flag, so nothing was broken in
    # the runner itself.
    assert "-p" in scanin_args(scan, cht, cie, corners=None, perspective=True)


def test_the_build_never_asks_for_the_perspective_search(_app, _out_dir):
    """`_execute` must not carry the argument at all any more."""
    src = inspect.getsource(ScannerProfileDialog._execute)
    src += inspect.getsource(ScannerProfileDialog._execute_printer)
    assert "perspective=" not in src, \
        "a call site still passes a perspective flag the window cannot set"


# ---------------------------------------------------------------- B8-31 ----
def test_the_read_options_are_written_by_save_as_defaults(_app, _out_dir):
    st = _FakeSettings(_out_dir)
    dlg = _dialog(_app, _out_dir, st)
    try:
        dlg._sample_area.setValue(35)
        dlg._use_fiducials_cb.blockSignals(True)
        dlg._use_fiducials_cb.setChecked(True)
        dlg._use_fiducials_cb.blockSignals(False)
        dlg._diag.setChecked(True)
        dlg._save_defaults_clicked()
        assert st.get(ScannerProfileDialog._READ_KEY) == {
            "sample_area": 35, "fiducials": True, "diagnostic": True}
    finally:
        dlg.deleteLater()


def test_a_reopened_window_has_them_back(_app, _out_dir):
    """The half of B8-31 Knut lives with: he has "Use fiducial marks" ticked in
    both of his beta.7 screenshots and had to tick it again every session."""
    st = _FakeSettings(_out_dir)
    first = _dialog(_app, _out_dir, st)
    try:
        first._sample_area.setValue(35)
        first._use_fiducials_cb.blockSignals(True)
        first._use_fiducials_cb.setChecked(True)
        first._use_fiducials_cb.blockSignals(False)
        first._diag.setChecked(True)
        first._save_defaults_clicked()
    finally:
        first.deleteLater()
    second = _dialog(_app, _out_dir, st)
    try:
        assert second._sample_area.value() == 35
        assert second._use_fiducials_cb.isChecked()
        assert second._diag.isChecked()
    finally:
        second.deleteLater()


def test_a_window_nobody_ever_saved_from_opens_exactly_as_it_used_to(
        _app, _out_dir):
    """No settings migration is needed, and this is why: the stored default IS
    the value the widgets were built with, so a user who never presses the
    button sees no change at all (`project_settings_default_migration`)."""
    st = _FakeSettings(_out_dir)
    assert not st.get(ScannerProfileDialog._READ_KEY)
    dlg = _dialog(_app, _out_dir, st)
    try:
        assert dlg._sample_area.value() == 60
        assert not dlg._use_fiducials_cb.isChecked()
        assert not dlg._diag.isChecked()
        assert dlg._current_read_vals() == ScannerProfileDialog._READ_DEFAULTS
    finally:
        dlg.deleteLater()


def test_restore_defaults_puts_the_read_options_back_too(_app, _out_dir):
    """The two buttons have to be each other's inverse, or "Restore defaults"
    restores some of them."""
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._sample_area.setValue(80)
        dlg._diag.setChecked(True)
        dlg._restore_defaults_clicked()
        assert dlg._sample_area.value() == 60
        assert not dlg._diag.isChecked()
        assert not dlg._use_fiducials_cb.isChecked()
    finally:
        dlg.deleteLater()


def test_the_saved_marquee_area_reaches_the_marquee(_app, _out_dir):
    """A restored number that the preview does not follow would be #119 again —
    the drawn sample boxes a size smaller than everything scanin reads."""
    st = _FakeSettings(_out_dir)
    st.set(ScannerProfileDialog._READ_KEY,
           {"sample_area": 40, "fiducials": False, "diagnostic": False})
    dlg = _dialog(_app, _out_dir, st)
    try:
        assert abs(dlg._marquee._sample_frac - 0.40) < 1e-9
    finally:
        dlg.deleteLater()


def test_the_restored_fiducials_setting_reaches_the_picture(_app, _out_dir):
    """The checkbox and the grid must agree.

    `_apply_read_vals` sets the box with its signal BLOCKED — it has to, or
    `_on_fiducial_toggled` refuses it before a target exists — and blocking the
    signal also blocks the one line that slot exists to run. Pushed explicitly,
    or "Restore defaults" unticks the box while the crosses stay drawn.
    """
    st = _FakeSettings(_out_dir)
    st.set(ScannerProfileDialog._READ_KEY,
           {"sample_area": 60, "fiducials": True, "diagnostic": False})
    dlg = _dialog(_app, _out_dir, st)
    try:
        assert dlg._use_fiducials_cb.isChecked()
        assert dlg._marquee._show_fiducials is True
        dlg._restore_defaults_clicked()
        assert not dlg._use_fiducials_cb.isChecked()
        assert dlg._marquee._show_fiducials is False, (
            "the box was unticked and the crosses stayed on the grid")
    finally:
        dlg.deleteLater()


def test_the_save_button_still_says_what_it_saves(_app, _out_dir):
    """Its tooltip opened "Store everything you've set here" while excluding
    exactly the options a repeat user changes every session. It now names
    them."""
    dlg = _dialog(_app, _out_dir)
    try:
        tip = dlg._save_defaults_btn.toolTip()
        assert "sample area" in tip.lower()
        assert "reading option" in tip.lower()
    finally:
        dlg.deleteLater()


# ------------------------------------------------------- B8-32 / F-7 -------
def test_an_empty_averaging_slot_is_named_before_the_read(_app, _out_dir):
    """Two slots, one file: the build reads one scan and must say so.

    Driven through the real method that the build calls, with the shot list in
    exactly the state "＋ Add another scan to average" leaves it in.
    """
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._shots[0] = [{"path": Path("/tmp/one.tif"), "corners": None},
                         {"path": None, "corners": None}]
        dlg._log.clear()
        dlg._say_about_empty_shot_slots([0])
        said = dlg._log.toPlainText()
        assert "empty scan slot" in said.lower(), said
        assert "2 scan slots" in said, said
        assert "1 of them" in said, said
    finally:
        dlg.deleteLater()


def test_a_page_whose_slots_are_all_filled_says_nothing(_app, _out_dir):
    """A notice that fires when nothing happened teaches people to skip it."""
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._shots[0] = [{"path": Path("/tmp/one.tif"), "corners": None},
                         {"path": Path("/tmp/two.tif"), "corners": None}]
        dlg._log.clear()
        dlg._say_about_empty_shot_slots([0])
        assert dlg._log.toPlainText() == ""
    finally:
        dlg.deleteLater()


def test_the_page_is_named_only_when_there_is_more_than_one(_app, _out_dir):
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._shots[0] = [{"path": Path("/tmp/a.tif"), "corners": None},
                         {"path": None, "corners": None}]
        dlg._shots[1] = [{"path": Path("/tmp/b.tif"), "corners": None}]
        dlg._log.clear()
        dlg._say_about_empty_shot_slots([0, 1])
        assert "Page 1" in dlg._log.toPlainText()
        dlg._log.clear()
        dlg._say_about_empty_shot_slots([0])
        assert "Page 1" not in dlg._log.toPlainText()
    finally:
        dlg.deleteLater()


def test_the_shot_box_says_which_slot_has_no_file(_app, _out_dir):
    """"Scan 1 / Scan 2" reads as two scans. Only the slot's own entry can say
    otherwise before the build starts."""
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._shots[dlg._page] = [{"path": Path("/tmp/a.tif"), "corners": None},
                                 {"path": None, "corners": None}]
        dlg._refresh_shot_bar()
        entries = [dlg._shot_combo.itemText(i)
                   for i in range(dlg._shot_combo.count())]
        assert entries[0] == "Scan 1"
        assert "no file" in entries[1], entries
    finally:
        dlg.deleteLater()


def test_the_build_asks_before_it_reads_anything(_app, _out_dir):
    """Said at the TOP of the build, not buried under scanin's output."""
    src = inspect.getsource(ScannerProfileDialog._execute)
    assert "_say_about_empty_shot_slots" in src
    assert src.index("_say_about_empty_shot_slots") < src.index("self._jobs = []")


# ------------------------------------------------------- B8-32 / F-9 -------
def test_changing_the_target_type_says_the_scan_was_dropped(_app, _out_dir):
    """The discard is right; the silence was not."""
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._std_chts = [Path("/tmp/first.cht")]
        dlg._shots[0] = [{"path": Path("/tmp/a.tif"), "corners": [(0, 0)] * 4}]
        dlg._log.clear()
        dlg._set_std_targets([Path("/tmp/second.cht")])
        said = dlg._log.toPlainText()
        assert "the loaded scan was cleared" in said.lower(), said
        assert "Nothing on disk was touched" in said, said
        assert not any(s["path"] for s in dlg._page_shots(0)), \
            "the premise failed: the scan was not actually dropped"
    finally:
        dlg.deleteLater()


def test_a_target_change_with_nothing_loaded_stays_quiet(_app, _out_dir):
    """A notice about a scan the user never picked would be its own small lie."""
    dlg = _dialog(_app, _out_dir)
    try:
        dlg._std_chts = [Path("/tmp/first.cht")]
        dlg._shots.clear()
        dlg._log.clear()
        dlg._set_std_targets([Path("/tmp/second.cht")])
        assert "cleared" not in dlg._log.toPlainText().lower()
    finally:
        dlg.deleteLater()


# ------------------------------------------------------- the words ---------
def test_both_new_sentences_come_from_the_catalogue():
    """§M: a window may not write prose of its own."""
    from workflow import measurement_messages as M
    for mid in ("M-SCAN-SHOT-EMPTY", "M-SCAN-TARGET-CHANGED"):
        assert mid in M.CATALOGUE, mid
        assert not M.CATALOGUE[mid].approved, \
            f"{mid} is marked approved and nobody has approved it"
    src = inspect.getsource(ScannerProfileDialog._say_about_empty_shot_slots)
    assert "measurement_messages" in src
    assert "M_SCAN_SHOT_EMPTY" in src
    src = inspect.getsource(ScannerProfileDialog._set_std_targets)
    assert "M_SCAN_TARGET_CHANGED" in src
