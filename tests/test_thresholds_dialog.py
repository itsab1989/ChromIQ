"""The Report limits window (#182): shape A, editable where Knut ruled it,
read-only ISO columns, per-run column memory, per-column restore, the buffered
Preferences door and the write-as-edited report door, and the "This run" column.

Offscreen: enabled/values/round-trips are reliable there; visibility and
geometry are proven on screen by the driver, not here.
"""
from __future__ import annotations

from tests.helpers import legacy_run_meta
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


@pytest.fixture
def a_hand_marked_recommendation(tmp_path, monkeypatch):
    """One row marked ``[number, "should"]``, the way a licence holder's file
    marks one.

    KNUT TOOK THE LAST RECOMMENDATION OUT OF CHROMIQ'S OWN SETS on 2026-09-21
    (*"Remove them, so a bracket only ever appears where a standard is
    involved"*), so nothing ChromIQ ships is a should-limit any more and the
    two tests below had no vehicle left. The MECHANISMS they guard are
    untouched by that ruling and still have to work -- the bracket on the spin
    box, and F4's rule that a trip through zero does not turn a recommendation
    into a requirement -- so they are driven through the one source that
    remains, which is also the route Basti told Knut the note path would be
    demonstrated by.

    3.0 is ChromIQ default's own maximum. No figure from any standard is used
    here or anywhere in this suite.
    """
    import json

    from workflow import compliance_sets as cs
    f = tmp_path / "iso12647-marked.json"
    f.write_text(json.dumps({
        "iso_12647_7": {"grey_balance_neutral_ramp_avg": [3.0, "should"]},
        "iso_12647_8": {},
    }), encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(f))
    cs.reset_iso_cache()
    yield "custom_iso_12647_7", "grey_balance_neutral_ramp_avg", 3.0
    cs.reset_iso_cache()


def test_the_read_only_iso_cells_read_what_ships(qapp, tmp_path, monkeypatch):
    """#182 S-2, §23: the two ISO columns are LABELS in both states of the
    shipped file. With the repository's file they carry its figure, in the
    spin boxes' own number format; over an empty shipped file, made by
    fixture, they read ?. The expected figure comes from the data file, never
    from this source. Red on its mutation: make a read-only column a spin box,
    or drop the shipped figure from the cell.
    """
    from tests.helpers.iso_files import (shipped_limits, use_empty_shipped_iso,
                                         use_repo_iso)
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    use_repo_iso(monkeypatch)
    s, dlg = _dlg(qapp, tmp_path)
    try:
        for col in ("iso_12647_7", "iso_12647_8"):
            w = _cell(dlg, col, "all_de00_avg")
            want = ThresholdsDialog._cell_text(shipped_limits(col)["all_de00_avg"])
            assert isinstance(w, QLabel) and w.text() == want, col
            assert w.text() not in ("?", "–", "✕"), col
    finally:
        dlg.deleteLater()
    empty = tmp_path / "empty"
    empty.mkdir()
    use_empty_shipped_iso(empty, monkeypatch)
    s, dlg = _dlg(qapp, tmp_path)
    try:
        for col in ("iso_12647_7", "iso_12647_8"):
            w = _cell(dlg, col, "all_de00_avg")
            assert isinstance(w, QLabel) and w.text() == "?", col
    finally:
        dlg.deleteLater()


def test_editable_and_read_only_columns_follow_the_rulings(qapp, tmp_path):
    s, dlg = _dlg(qapp, tmp_path)
    try:
        # ChromIQ's three sets and the two Custom sets have spin boxes …
        for col in ("chromiq_default", "chromiq_tight", "chromiq_quick",
                    "custom_iso_12647_7", "custom_iso_12647_8"):
            assert isinstance(_cell(dlg, col, "all_de00_avg"), NoScrollDoubleSpinBox), col
        # … the ISO columns are labels (read-only); what they read, in both
        # states of the shipped file, is pinned by the test above.
        for col in ("iso_12647_7", "iso_12647_8"):
            assert isinstance(_cell(dlg, col, "all_de00_avg"), QLabel), col
        # a row a set defines no limit for reads – ; an unmeasurable row ✕ / –
        assert _cell(dlg, "iso_12647_7", "best95_de00_avg").text() == "–"
        assert _cell(dlg, "iso_12647_7", "substrate_gloss_class").text() == "✕"
        assert _cell(dlg, "chromiq_default", "substrate_gloss_class").text() == "–"
        # NO BRACKET ANYWHERE, IN ANY COLUMN, AS CHROMIQ SHIPS. Knut,
        # 2026-09-21. The grey pair carried one in all three ChromIQ sets and
        # `ramps_30_70_dl_max` in Custom ISO 12647-7; all four are ordinary
        # limits now, keeping their numbers.
        sb = _cell(dlg, "chromiq_default", "grey_balance_neutral_ramp_avg")
        assert sb.prefix() == "" and sb.suffix() == "" and sb.value() == 1.5
        bracketed = sorted(
            f"{c}/{r}" for (c, r), w in dlg._cells.items()
            if (isinstance(w, QLabel) and w.text().startswith("("))
            or (isinstance(w, NoScrollDoubleSpinBox) and w.prefix() == "("))
        assert bracketed == [], bracketed
        # no "This run" column without a run
        assert not any(c == "__run__" for c, _r in dlg._cells)
    finally:
        dlg.deleteLater()


def test_a_hand_marked_recommendation_shows_its_brackets(
        qapp, tmp_path, a_hand_marked_recommendation):
    """The bracket NOTATION survives the ruling that emptied it of occupants.

    Knut kept it deliberately: *"The notation itself stays … They are what
    makes such a row readable on the day somebody does mark one."* This is that
    day, arranged by the fixture above.
    """
    col, rid, n = a_hand_marked_recommendation
    s, dlg = _dlg(qapp, tmp_path)
    try:
        sb = _cell(dlg, col, rid)
        assert sb.prefix() == "(" and sb.suffix() == ")" and sb.value() == n
        # …and the metric's name carries the reference number that points at
        # the note, which is the other half of the same ruling.
        from ui.dialogs.thresholds_dialog import ThresholdsDialog
        assert ThresholdsDialog.RECOMMENDED_MARK in dlg._row_labels[rid].text()
        assert dlg._any_row_is_recommended()
        # the fourth note is under the table, and says what the standard calls it
        assert ThresholdsDialog.RECOMMENDED_MARK in dlg._notes_text()
        assert "recommended rather than required" in dlg._notes_text()
    finally:
        dlg.deleteLater()


def test_with_nothing_marked_there_is_no_marker_and_no_fourth_note(qapp, tmp_path):
    """The shipping state: a numbered note nothing points at is not written.

    MUTATION: drop the `if self._any_row_is_recommended()` guard in
    `_notes_text` and this goes red.
    """
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    s, dlg = _dlg(qapp, tmp_path)
    try:
        assert not dlg._any_row_is_recommended()
        assert not [rid for rid, lab in dlg._row_labels.items()
                    if ThresholdsDialog.RECOMMENDED_MARK in lab.text()]
        assert ThresholdsDialog.RECOMMENDED_MARK not in dlg._notes_text()
        # …but the LEGEND still explains the notation, because a licence
        # holder's file can put one on screen at any time.
        assert "recommends rather than requires" in dlg._notes_text()
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


def test_the_first_column_is_written_once_on_close(qapp, tmp_path):
    """The first column (K31: "This report", the report's own limits) is
    edited in memory and handed back ONCE, on close (CH-29). K31 retired the
    half of this test that pinned a LOCKED run's column and its note "tick
    Unlock this run's limits": nothing is locked any more.

    MUTATION: write the column on every `valueChanged` and this goes red."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    legacy_run_meta.bind_run(run, "chromiq_default", {})
    s, dlg = _dlg(qapp, tmp_path, run=run, run_editable=False)
    try:
        notes = [x.text() for x in dlg._column_widgets["__run__"] if isinstance(x, QLabel)]
        assert not any("Unlock" in t for t in notes), notes
        assert dlg._header_text("__run__") == "This report"
    finally:
        dlg.deleteLater()
    # editable: spin boxes; the copy is written ONCE, on close (CH-29)
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


def test_a_default_radio_exists_only_for_selectable_sets(qapp, tmp_path,
                                                          monkeypatch):
    """CH-11: a column with no limit-bearing row is never a choice.

    THE TWO CUSTOM COLUMNS JOINED THE LIST ON 2026-09-11. They used to inherit
    their ISO parent's empty cells, so neither had a limit-bearing row and
    neither could be the default. Knut ruled that a custom threshold set must
    be usable (*"make sure the metrics have a value that can be tested
    against"*), so both now start from ChromIQ's own numbers and both are
    offerable. The two READ-ONLY ISO columns are unchanged and still are not:
    the last line here is what proves the difference is the placeholders and
    not a relaxed rule.

    #182 S-2, §23: SINCE THE ISO VALUES SHIP, the two read-only columns have
    limit-bearing rows and are offered too. The rule is the same in both
    states, so both are driven: the repository's file (both offered) and an
    empty shipped file made by fixture (neither offered, every cell ?). Red on
    its mutation: offer a radio for every column, and the empty half fails;
    offer only the editable ones, and the shipped half fails.
    """
    from tests.helpers.iso_files import use_empty_shipped_iso, use_repo_iso
    use_repo_iso(monkeypatch)
    s, dlg = _dlg(qapp, tmp_path)
    try:
        assert set(dlg._default_radios) == {"chromiq_default", "chromiq_tight",
                                            "chromiq_quick",
                                            "iso_12647_7", "iso_12647_8",
                                            "custom_iso_12647_7",
                                            "custom_iso_12647_8"}
        assert dlg._default_radios["chromiq_default"].isChecked()
    finally:
        dlg.deleteLater()
    empty = tmp_path / "empty"
    empty.mkdir()
    use_empty_shipped_iso(empty, monkeypatch)
    s, dlg = _dlg(qapp, tmp_path)
    try:
        assert set(dlg._default_radios) == {"chromiq_default", "chromiq_tight",
                                            "chromiq_quick",
                                            "custom_iso_12647_7",
                                            "custom_iso_12647_8"}
        assert dlg._default_radios["chromiq_default"].isChecked()
        assert factory_limits("iso_12647_7")["all_de00_avg"] == Limit.unknown()
    finally:
        dlg.deleteLater()


def test_this_run_recommendation_survives_a_trip_through_zero(
        qapp, tmp_path, a_hand_marked_recommendation):
    """F4: turning a bracketed cell to 0 and back must keep it a recommendation.

    Driven through a hand-marked should-limit, because after Knut's ruling of
    2026-09-21 no set ChromIQ ships has one. The rule is unchanged and matters
    more now, not less: the kind is what decides whether the row gets its
    numbered note, so losing it through a spin box would silently drop the
    note as well as the bracket.
    """
    col, rid, _n = a_hand_marked_recommendation
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run(); run.ensure_dir()
    legacy_run_meta.bind_run(run, col, {})
    s, dlg = _dlg(qapp, tmp_path, run=run, run_editable=True)
    try:
        sb = _cell(dlg, "__run__", rid)
        assert sb.prefix() == "(", "the run inherited the set's recommendation"
        sb.setValue(0.0)
        sb.setValue(2.0)
        assert dlg._run_limits[rid] == Limit.should(2.0)
        dlg.accept()
        assert run.load_meta().compliance_thresholds[rid] == [2.0, "should"]
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
    legacy_run_meta.bind_run(run, "chromiq_default", {})

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
    legacy_run_meta.bind_run(run, "chromiq_default", {})

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


# ---------------------------------------------------------------------------
# The "Show:" row has air in it (round 2 N5, restated as round 3 N7)
# ---------------------------------------------------------------------------
def _show_row(dlg):
    """The QHBoxLayout that holds the "Show:" label and the column ticks."""
    from PyQt6.QtWidgets import QHBoxLayout
    for lay in dlg.findChildren(QHBoxLayout):
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if isinstance(w, QLabel) and w.text().startswith("Show"):
                return lay
    return None


def test_the_show_row_leaves_a_gap_between_its_items(qapp, tmp_path):
    """Seven column names in one row, and no space between them.

    Reported twice and photographed: "ChromIQ default (recommended)" ended one
    pixel before the tick for "ChromIQ tight" began, so the row read as a
    sentence with squares in it.

    THIS ASSERTS THE LAYOUT'S SPACING, NOT THE PAINTED GAP, and that is not
    laziness. Offscreen the app's own fonts are not loaded, so every checkbox in
    this row comes out 73 px wide whatever its text says; a painted gap measured
    here would be measuring the wrong sheet. The painted gap is measured on
    screen instead, by drivers/drive_F9_show_row.py: with the style's own
    spacing it was -1 px, and with this one it is 13 px. What can be checked
    here is that the spacing is SET, and set well above the style's default,
    which is the whole of the fix.
    """
    from PyQt6.QtWidgets import QHBoxLayout
    from ui.dialogs.thresholds_dialog import SHOW_ROW_SPACING_PX

    s, dlg = _dlg(qapp, tmp_path)
    try:
        row = _show_row(dlg)
        assert row is not None, "the Show: row was not found at all"
        assert row.spacing() == SHOW_ROW_SPACING_PX, row.spacing()
        # A checkbox's own text has no right-hand padding, so a spacing at or
        # near the style's default paints as no gap at all.
        assert row.spacing() > QHBoxLayout().spacing() + 8, (
            f"the Show: row runs at {row.spacing()} px against a style default "
            f"of {QHBoxLayout().spacing()}; that is what ran the labels into "
            "the next tick")
    finally:
        dlg.deleteLater()


def test_the_show_row_still_holds_one_tick_per_set(qapp, tmp_path):
    """So the spacing above is spacing something, and a set cannot go missing
    from the row without this saying so."""
    from PyQt6.QtWidgets import QCheckBox

    from workflow.compliance_sets import SETS

    s, dlg = _dlg(qapp, tmp_path)
    try:
        row = _show_row(dlg)
        boxes = [row.itemAt(i).widget() for i in range(row.count())]
        boxes = [w for w in boxes if isinstance(w, QCheckBox)]
        assert len(boxes) == len(SETS), (
            f"{len(boxes)} ticks for {len(SETS)} sets")
    finally:
        dlg.deleteLater()


def test_the_bad_file_panel_is_painted_for_the_THEME_it_is_in(tmp_path, qapp,
                                                              monkeypatch):
    """PHOTOGRAPHED ON SCREEN: a dark brown box in the middle of a pale page.

    The panel that names a limits file ChromIQ could not read was styled
    `background: #3a2a00`, a dark-mode ground, with no branch on appearance. It
    was legible, and it belonged to a different window: every other colour in
    this dialog is chosen per appearance, so one that is not reads as a mistake
    rather than as a warning.

    MUTATION: put any single hard-coded ground back and this goes red, because
    the light and dark grounds become the same string.
    """
    import json as _json
    from core.settings import AppSettings
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from workflow import compliance_sets as cs

    bad = tmp_path / "wrong.json"
    bad.write_text(_json.dumps(
        {"iso_12647_7": {"all_de00_avg": {"kind": "value", "number": 2.5}}}),
        encoding="utf-8")
    monkeypatch.setenv(cs.ISO_DATA_ENV, str(bad))
    monkeypatch.setattr(cs, "_iso_cache", None, raising=False)
    monkeypatch.setattr(cs, "_iso_problems", None, raising=False)

    seen = {}
    for mode in ("light", "dark"):
        s = AppSettings()
        s.set("appearance", mode)
        dlg = ThresholdsDialog(s, None)
        try:
            panels = [w for w in dlg.findChildren(QLabel)
                      if w.objectName() == "isoFileTrouble"]
            assert panels, f"{mode}: the panel is not there at all"
            seen[mode] = panels[0].styleSheet()
        finally:
            dlg.close()
    assert seen["light"] != seen["dark"], \
        "the panel paints the same ground in both themes, so one of them is wrong"
    assert "#3a2a00" not in seen["light"], \
        "a dark-mode ground is being painted on the light window"
