"""The Report limits window (#182): shape A, editable where Knut ruled it,
read-only ISO columns, per-run column memory, per-column restore, the buffered
Preferences door and the write-as-edited report door, and the "This run" column.

Offscreen: enabled/values/round-trips are reliable there; visibility and
geometry are proven on screen by the driver, not here.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import (QApplication, QLabel,       # noqa: E402
                             QPushButton)

from core.file_manager import Project                     # noqa: E402
from core.settings import AppSettings                     # noqa: E402
from ui.widgets import NoScrollDoubleSpinBox              # noqa: E402
from workflow import run_compliance as rc                 # noqa: E402
from workflow.compliance_sets import Limit, factory_limits  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _settings(tmp_path) -> AppSettings:
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def _dlg(qapp, tmp_path, **kw):
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    s = kw.pop("settings", None) or _settings(tmp_path)
    return s, ThresholdsDialog(s, None, **kw)


def _cell(dlg, col, row_id):
    return dlg._cells[(col, row_id)]


def test_editable_and_read_only_columns_follow_the_rulings(qapp, tmp_path):
    s, dlg = _dlg(qapp, tmp_path)
    try:
        # ChromIQ's three sets and the two Custom sets have spin boxes …
        for col in ("chromiq_default", "chromiq_tight", "chromiq_quick",
                    "custom_iso_12647_7", "custom_iso_12647_8"):
            assert isinstance(_cell(dlg, col, "all_de00_avg"), NoScrollDoubleSpinBox), col
        # … the ISO columns are labels (read-only), reading ? until S-2
        for col in ("iso_12647_7", "iso_12647_8"):
            w = _cell(dlg, col, "all_de00_avg")
            assert isinstance(w, QLabel) and w.text() == "?", col
        # a row a set defines no limit for reads – ; an unmeasurable row ✕ / –
        assert _cell(dlg, "iso_12647_7", "best95_de00_avg").text() == "–"
        assert _cell(dlg, "iso_12647_7", "substrate_gloss_class").text() == "✕"
        assert _cell(dlg, "chromiq_default", "substrate_gloss_class").text() == "–"
        # a should-limit shows its brackets on the spin box
        sb = _cell(dlg, "chromiq_default", "grey_balance_neutral_ramp_avg")
        assert sb.prefix() == "(" and sb.suffix() == ")" and sb.value() == 1.5
        # no "This run" column without a run
        assert not any(c == "__run__" for c, _r in dlg._cells)
    finally:
        dlg.deleteLater()


def test_the_report_door_writes_overrides_as_they_are_edited(qapp, tmp_path):
    s, dlg = _dlg(qapp, tmp_path)
    try:
        sb = _cell(dlg, "chromiq_default", "all_de00_avg")
        sb.setValue(2.7)
        assert s.get_compliance_overrides() == {"chromiq_default": {"all_de00_avg": 2.7}}
        # back to the factory number removes the override instead of storing it
        sb.setValue(2.0)
        assert s.get_compliance_overrides() == {}
        # 0 means "no limit" (CH-21) and shows –
        sb.setValue(0.0)
        assert sb.text() == "–"
        assert s.get_compliance_overrides() == {"chromiq_default": {"all_de00_avg": None}}
        assert dlg.value_of("chromiq_default", "all_de00_avg").kind == "none"
    finally:
        dlg.deleteLater()


def test_the_preferences_door_edits_a_buffer_not_the_settings(qapp, tmp_path):
    """CH-19: from Preferences, edits are kept when Save is pressed and dropped
    with Cancel, so the window must not write the settings itself."""
    buf = {"overrides": {}, "default_set": "chromiq_default"}
    s, dlg = _dlg(qapp, tmp_path, buffer=buf)
    try:
        _cell(dlg, "chromiq_tight", "all_de00_max").setValue(1.2)
        assert buf["overrides"] == {"chromiq_tight": {"all_de00_max": 1.2}}
        assert s.get_compliance_overrides() == {}                 # untouched
        dlg._default_radios["chromiq_quick"].setChecked(True)
        assert buf["default_set"] == "chromiq_quick"
        assert s.get("compliance_default_set") == "chromiq_default"
    finally:
        dlg.deleteLater()


def test_restore_this_column_touches_that_column_only(qapp, tmp_path):
    s = _settings(tmp_path)
    s.set_compliance_overrides({"chromiq_default": {"all_de00_avg": 2.9},
                                "chromiq_tight": {"all_de00_avg": 0.7}})
    s, dlg = _dlg(qapp, tmp_path, settings=s)
    try:
        assert _cell(dlg, "chromiq_default", "all_de00_avg").value() == 2.9
        btn = next(w for w in dlg._column_widgets["chromiq_default"]
                   if w.__class__.__name__ == "QPushButton")
        btn.click()
        assert _cell(dlg, "chromiq_default", "all_de00_avg").value() == 2.0
        assert s.get_compliance_overrides() == {"chromiq_tight": {"all_de00_avg": 0.7}}
    finally:
        dlg.deleteLater()


def test_column_visibility_is_stored_per_run_or_in_preferences(qapp, tmp_path):
    # Preferences door: the settings key
    s, dlg = _dlg(qapp, tmp_path)
    try:
        dlg._column_checks["iso_12647_7"].setChecked(False)
        shown = json.loads(s.get("compliance_columns_shown"))
        assert "iso_12647_7" not in shown and "chromiq_default" in shown
        assert not _cell(dlg, "iso_12647_7", "all_de00_avg").isVisibleTo(dlg)
    finally:
        dlg.deleteLater()
    # report door: the run's meta.json, and Preferences untouched (CH-18)
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    s2 = _settings(tmp_path / "two")
    s2, dlg2 = _dlg(qapp, tmp_path / "two", settings=s2, run=run,
                    run_editable=True)
    try:
        dlg2._column_checks["chromiq_quick"].setChecked(False)
        assert "chromiq_quick" not in run.load_meta().compliance_columns
        assert "chromiq_default" in run.load_meta().compliance_columns
        assert s2.get("compliance_columns_shown") == ""
    finally:
        dlg2.deleteLater()
    # …and a window opened READ-ONLY on that run writes nothing, which is what
    # `run_editable` means everywhere else in this class. This case used to be
    # the one above, opened without `run_editable`, so it asserted that a
    # window saying "Show limits…" on a LOCKED run may still change what that
    # run stores. `done()` has always refused to; this slot did not, and a
    # challenge round drove it.
    before = list(run.load_meta().compliance_columns or [])
    s4, dlg4 = _dlg(qapp, tmp_path / "four", run=run)
    try:
        assert not dlg4._run_editable, "the premise failed"
        dlg4._column_checks["chromiq_tight"].setChecked(False)
        assert list(run.load_meta().compliance_columns or []) == before, (
            "a read-only limits window changed what the run stores")
        assert not _cell(dlg4, "chromiq_tight", "all_de00_avg").isVisibleTo(dlg4), (
            "the column did not even hide, so the click did nothing at all")
    finally:
        dlg4.deleteLater()
    # …and it is read back next time
    s3, dlg3 = _dlg(qapp, tmp_path / "three", run=run)
    try:
        assert not dlg3._column_checks["chromiq_quick"].isChecked()
        assert dlg3._column_checks["chromiq_default"].isChecked()
    finally:
        dlg3.deleteLater()


def test_this_run_column_is_locked_until_unlocked_and_written_once_on_close(qapp, tmp_path):
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    rc.bind_run(run, "chromiq_default", {})
    # locked: labels, and a note saying how to unlock
    s, dlg = _dlg(qapp, tmp_path, run=run, run_editable=False)
    try:
        w = _cell(dlg, "__run__", "all_de00_avg")
        from PyQt6.QtCore import QLocale
        # read-only cells use the spin boxes' locale (2,00 on a German machine)
        assert isinstance(w, QLabel) and w.text() == QLocale.system().toString(2.0, "f", 2)
        notes = [x.text() for x in dlg._column_widgets["__run__"] if isinstance(x, QLabel)]
        assert any("Unlock" in t for t in notes)
        dlg.accept()
        assert dlg.run_limits_changed is False
    finally:
        dlg.deleteLater()
    # unlocked: spin boxes; the copy is written ONCE, on close (CH-29)
    s, dlg = _dlg(qapp, tmp_path / "b", run=run, run_editable=True)
    try:
        sb = _cell(dlg, "__run__", "all_de00_avg")
        assert isinstance(sb, NoScrollDoubleSpinBox)
        sb.setValue(2.6)
        assert run.load_meta().compliance_thresholds["all_de00_avg"] == 2.0   # not yet
        dlg.accept()
        assert dlg.run_limits_changed is True
        assert run.load_meta().compliance_thresholds["all_de00_avg"] == 2.6
        assert rc.run_limits(run, {}).edited
    finally:
        dlg.deleteLater()
    # Restore this column on "This run" copies the set back
    s, dlg = _dlg(qapp, tmp_path / "c", run=run, run_editable=True)
    try:
        btn = next(w for w in dlg._column_widgets["__run__"]
                   if w.__class__.__name__ == "QPushButton")
        btn.click()
        assert _cell(dlg, "__run__", "all_de00_avg").value() == 2.0
        dlg.accept()
        assert run.load_meta().compliance_thresholds["all_de00_avg"] == 2.0
    finally:
        dlg.deleteLater()


def test_no_lambda_or_partial_is_connected_to_a_child_signal():
    """The segfault rule (CLAUDE.md): a closure capturing self on a child
    widget's signal. Every connect in this window names a bound method."""
    import inspect
    import re
    from ui.dialogs import thresholds_dialog as td
    src = inspect.getsource(td)
    for m in re.finditer(r"\.connect\(([^)]*)\)", src):
        arg = m.group(1)
        assert "lambda" not in arg and "partial" not in arg, arg


def test_a_default_radio_exists_only_for_selectable_sets(qapp, tmp_path):
    s, dlg = _dlg(qapp, tmp_path)
    try:
        assert set(dlg._default_radios) == {"chromiq_default", "chromiq_tight",
                                            "chromiq_quick"}
        assert dlg._default_radios["chromiq_default"].isChecked()
        assert factory_limits("iso_12647_7")["all_de00_avg"] == Limit.unknown()
    finally:
        dlg.deleteLater()


def test_this_run_recommendation_survives_a_trip_through_zero(qapp, tmp_path):
    """F4: turning a bracketed cell to 0 and back must keep it a recommendation."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    rc.bind_run(run, "chromiq_default", {})
    s, dlg = _dlg(qapp, tmp_path, run=run, run_editable=True)
    try:
        sb = _cell(dlg, "__run__", "grey_balance_neutral_ramp_avg")
        sb.setValue(0.0)
        sb.setValue(2.0)
        assert dlg._run_limits["grey_balance_neutral_ramp_avg"] == Limit.should(2.0)
        dlg.accept()
        assert run.load_meta().compliance_thresholds["grey_balance_neutral_ramp_avg"] == [2.0, "should"]
    finally:
        dlg.deleteLater()


def test_column_choice_from_preferences_waits_in_the_buffer(qapp, tmp_path):
    """F12: from Preferences, Cancel must drop a hidden column like any edit."""
    buf = {"overrides": {}, "default_set": "chromiq_default"}
    s, dlg = _dlg(qapp, tmp_path, buffer=buf)
    try:
        dlg._column_checks["iso_12647_7"].setChecked(False)
        assert "iso_12647_7" not in json.loads(buf["columns"])
        assert s.get("compliance_columns_shown") == ""
    finally:
        dlg.deleteLater()
    # …and a buffer with a choice is what the window opens on next time
    s2, dlg2 = _dlg(qapp, tmp_path / "b", buffer=buf)
    try:
        assert not dlg2._column_checks["iso_12647_7"].isChecked()
    finally:
        dlg2.deleteLater()


def test_hiding_a_column_leaves_the_rest_against_the_row_labels(qapp, tmp_path):
    """Knut, 4.2.1 beta 3: unticking columns pushed the ones still shown to the
    right edge, and a window then dragged narrower kept a horizontal scroll bar
    for space nothing painted in.

    Both came from the same two lines: all the horizontal stretch sat on the
    row-label column, and the scrolled body's minimum width was pinned once at
    build time with every column visible.

    The body is given its width here instead of the window, because offscreen
    the dialog is clamped to a 640 px screen and every column would be scrolled
    out of sight, which proves nothing either way.
    """
    s, dlg = _dlg(qapp, tmp_path)
    try:
        body = dlg._scroll.widget()
        cell = _cell(dlg, "chromiq_default", "all_de00_avg")
        wide = body.minimumWidth()
        assert wide > 0

        def x_of_first_value_column(width):
            body.setGeometry(0, 0, width, body.sizeHint().height())
            dlg._grid.activate()
            return cell.mapTo(body, cell.rect().topLeft()).x()

        # a body 200 px wider than the table needs must not move the columns
        assert x_of_first_value_column(wide) == x_of_first_value_column(wide + 200)
        x_before = x_of_first_value_column(wide + 200)

        for sid in ("chromiq_quick", "iso_12647_7", "iso_12647_8",
                    "custom_iso_12647_8"):
            dlg._column_checks[sid].setChecked(False)
        qapp.processEvents()
        # the first value column has not moved: it stays beside the row labels
        assert x_of_first_value_column(wide + 200) == x_before
        # and the body asks for only the width the columns still shown need,
        # so the scroll bar goes when the window is made narrower
        assert body.minimumWidth() < wide
        assert body.minimumWidth() == dlg._grid.sizeHint().width()
    finally:
        dlg.deleteLater()


def _column_x(dlg, width):
    """The x of every table column in each of the two grids, laid out at the
    same width. `cellRect` is the layout's own answer, not a guess from a
    style sheet."""
    from PyQt6.QtCore import QSize
    out = []
    for g in (dlg._head_grid, dlg._grid):
        holder = g.parentWidget()
        holder.resize(QSize(width, max(g.sizeHint().height(), 1)))
        g.activate()
        out.append([g.cellRect(0, ci).x()
                    for ci in range(2 + len(dlg._column_ids()))])
    return out


def test_the_frozen_head_stays_over_its_own_columns(qapp, tmp_path):
    """Knut, 4.2.1 beta 3: the heading row must stay put while the rows scroll.

    It lives in its own widget now, so nothing makes its columns agree with the
    rows' by itself. They are pinned to one geometry (`_sync_columns`), and a
    head that drifted would put every heading over the wrong column, which is
    worse than the scrolling it fixes.
    """
    s, dlg = _dlg(qapp, tmp_path)
    try:
        width0 = dlg._grid.sizeHint().width()
        x0 = _column_x(dlg, width0)[0]
        for width in (width0, width0 + 300):
            head, body = _column_x(dlg, width)
            assert head == body, f"columns drifted at width {width}"
        # …and they still agree when columns are hidden, which is where the
        # grid's own spacing used to charge the body for a column the head did
        # not pay for (42 px on four hidden columns, measured on screen)
        for sid in ("chromiq_quick", "iso_12647_7", "iso_12647_8",
                    "custom_iso_12647_8"):
            dlg._column_checks[sid].setChecked(False)
        qapp.processEvents()
        head, body = _column_x(dlg, dlg._grid.sizeHint().width())
        assert head == body, "columns drifted after hiding four columns"
        # …and ticking them back gives the table it started with: the gap is
        # folded into each column's pinned width, so it must be measured
        # unpinned or every tick would widen the table by another 14 px
        for sid in ("chromiq_quick", "iso_12647_7", "iso_12647_8",
                    "custom_iso_12647_8"):
            dlg._column_checks[sid].setChecked(True)
        qapp.processEvents()
        assert _column_x(dlg, width0) == [x0, x0]
    finally:
        dlg.deleteLater()


def test_the_head_follows_the_body_sideways_and_not_up_and_down(qapp, tmp_path):
    """Frozen vertically, slaved horizontally: the head is outside the scroll
    area, so the rows scroll under it, and it is moved by the body's own
    horizontal scroll bar so a heading never leaves its column."""
    s, dlg = _dlg(qapp, tmp_path)
    try:
        # the heading is NOT inside the scrolled body; its cell is
        hdr = dlg._column_widgets["chromiq_default"][0]
        cell = _cell(dlg, "chromiq_default", "all_de00_avg")
        body = dlg._scroll.widget()
        assert not dlg._head.isAncestorOf(cell)
        assert dlg._head.isAncestorOf(hdr)
        assert body.isAncestorOf(cell)
        assert not body.isAncestorOf(hdr)
        # sideways, it follows
        dlg._scroll.horizontalScrollBar().setValue(0)
        assert dlg._head.x() == 0
        dlg._scroll.horizontalScrollBar().setRange(0, 400)
        dlg._scroll.horizontalScrollBar().setValue(137)
        qapp.processEvents()
        assert dlg._head.x() == -137
    finally:
        dlg.deleteLater()


def test_typing_a_number_and_typing_it_back_is_not_an_edit(qapp, tmp_path):
    """`_run_dirty` was set on every `valueChanged`, so a visit that typed a
    number and typed the original straight back closed as an edit.

    Round 9 drove what that cost: the report window asked to recalculate a whole
    history, archived every date into `reports/old` for a change of nothing, and
    on an unbound run bound it permanently, with no control anywhere that undoes
    a binding.

    This has to drive the REAL dialog. A fake that sets `run_limits_changed`
    itself cannot test the rule that decides it, which is how the first version
    of this test proved nothing.

    MUTATION: drop the `_run_column_really_moved()` call from `done()` and this
    goes red.
    """
    from workflow.compliance_sets import Limit

    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    rc.bind_run(run, "chromiq_default", {})

    s, dlg = _dlg(qapp, tmp_path, run=run, run_editable=True)
    try:
        before = dict(dlg._run_limits)
        assert before, "the run column is empty, so this proves nothing"
        row = "all_de00_avg"
        original = before[row]
        assert original.number is not None

        # typed away…
        dlg._run_limits[row] = Limit.value(0.5)
        dlg._run_dirty = True
        # …and typed straight back
        dlg._run_limits[row] = original

        assert not dlg._run_column_really_moved(), (
            "a column that ends where it started is reported as edited")

        dlg.done(0)
        assert not dlg.run_limits_changed, (
            "a net-zero visit closed as an edit, so the report window would "
            "recalculate a history for a change of nothing")
    finally:
        dlg.deleteLater()


def test_a_real_edit_is_still_an_edit(qapp, tmp_path):
    """THE NEGATIVE HALF, and the one that would break silently.

    MUTATION: make `_run_column_really_moved` return False and this goes red.
    """
    from workflow.compliance_sets import Limit

    proj = Project.create(tmp_path / "Q", "Q")
    run = proj.current_run()
    run.ensure_dir()
    rc.bind_run(run, "chromiq_default", {})

    s, dlg = _dlg(qapp, tmp_path, run=run, run_editable=True)
    try:
        dlg._run_limits["all_de00_avg"] = Limit.value(0.25)
        dlg._run_dirty = True
        assert dlg._run_column_really_moved()
        dlg.done(0)
        assert dlg.run_limits_changed, "a real edit was not reported"
        got = rc.run_limits(run, {}).limits.get("all_de00_avg")
        assert got is not None and abs(got.number - 0.25) < 1e-9
    finally:
        dlg.deleteLater()


def test_a_showing_window_writes_nothing_at_all(qapp, tmp_path):
    """R17-7: "READ-ONLY FOR THE RUN" LET IT WRITE APP-WIDE, AND THE HARM IS
    SOMEWHERE ELSE.

    The reasoning for leaving those writable was that a bound run's limits come
    from its own stored copy, so nothing app-wide can reach it. True of that
    run, and it does not reach the harm: a challenge round moved "Default for
    new runs" from a "Show limits…" window with no question and no undo, and a
    DIFFERENT project's next run was then bound to it and judged by the wrong
    numbers.

    A window that says it is showing writes nothing.

    MUTATION: let either the radio or a shipped column's cell write here and
    this goes red.
    """
    from core.settings import compliance_overrides_of

    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    s, dlg = _dlg(qapp, tmp_path, run=run)          # run_editable defaults False
    try:
        assert not dlg._run_editable, "the premise failed"
        was_default = s.get("compliance_default_set", "chromiq_default")
        was_overrides = compliance_overrides_of(s)

        other = next(c for c, rb in dlg._default_radios.items()
                     if not rb.isChecked() and rb.isEnabled())
        dlg._default_radios[other].setChecked(True)
        assert s.get("compliance_default_set", "chromiq_default") == was_default, (
            "a showing window moved the default set for every future run")
        assert dlg._default_radios[other].isChecked() is False, (
            "the radio was left showing a default that is not the default")

        # AND THE CONTROLS DO NOT INVITE A WRITE THEY WILL NOT MAKE. Guarding
        # the write alone left the spin box taking a typed number and showing
        # it for ever while the settings held something else, and left a
        # "Restore this column" button that wiped the column on screen only.
        cell = _cell(dlg, "chromiq_default", "all_de00_max")
        assert not hasattr(cell, "setValue"), (
            "a showing window offers a spin box on an app-wide column")
        for w in dlg._column_widgets.get("chromiq_default", []):
            assert not isinstance(w, QPushButton), (
                "a showing window offers 'Restore this column'")
        assert compliance_overrides_of(s) == was_overrides, (
            "a showing window changed the app-wide limits")
    finally:
        dlg.deleteLater()
