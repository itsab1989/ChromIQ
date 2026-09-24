"""A control this window builds and never puts on screen is a control nobody
can use, and three betas running have shipped one.

**KNUT, 2026-09-20, REVIEWING BETA 26 (B8-520).** *"In the Measurement Report
window, relating to the new layout of buttons and elements, you removed the
'Unlock this run's limits' checkbox and its help icon. They should still be
there and work as before."*

He was right about the window and wrong about the cause, and the difference is
the whole reason this file exists. The widget is BUILT and ADDED TO A LAYOUT in
beta 25 and beta 26 alike -- `judged_row.addWidget(self._unlock_check)`, byte
for byte the same line. What removed it from his screen was a `setVisible`
call, on a rule this project invented in round 6 and never showed him.

So there are two ways a control goes missing and this file guards both:

1. **Built and never laid out.** The generic guard: every widget this window
   keeps a name for must be reachable from the window's own layout tree.
   Nothing catches this today, and it is silent -- the widget exists, every
   test that pokes it passes, and it is simply not on screen.
2. **Laid out and hidden.** Measured the only way it can be measured: in a
   SHOWN window, in the state the user meets, asking the widget what a person
   would see. `isVisible()` on a dialog nobody showed is False for every widget
   in it, which is why the two assertions in
   `test_a_set_change_asks_before_it_rewrites_history.py` that claimed to check
   this were vacuous for as long as they existed.
"""
from __future__ import annotations

import pytest

import workflow.measurement_report as mr

pytestmark = pytest.mark.usefixtures("qapp")


# --------------------------------------------------------------------------
# 1. BUILT AND NEVER LAID OUT
# --------------------------------------------------------------------------
def _widgets_in_layout_tree(root) -> set:
    """Every widget reachable from *root*'s layout, its sub-layouts and the
    layouts of the widgets it contains."""
    from PyQt6.QtWidgets import QLayout, QWidget

    seen_w: set = set()
    seen_l: set = set()

    def walk_layout(lay) -> None:
        if lay is None or id(lay) in seen_l:
            return
        seen_l.add(id(lay))
        for i in range(lay.count()):
            it = lay.itemAt(i)
            if it is None:
                continue
            w = it.widget()
            if isinstance(w, QWidget):
                walk_widget(w)
            sub = it.layout()
            if isinstance(sub, QLayout):
                walk_layout(sub)

    def walk_widget(w) -> None:
        if w is None or id(w) in seen_w:
            return
        seen_w.add(id(w))
        walk_layout(w.layout())
        # **THE CONTAINERS THAT PLACE A CHILD WITHOUT A LAYOUT ITEM.** A tab
        # page, a stack page and a scroll area's contents are on screen and
        # are in nobody's layout, so a walk that only followed layouts called
        # all four trend charts orphans on its first run. Only these are
        # followed, and each by the API that says what it SHOWS: recursing
        # into every child would make the guard vacuous, because every widget
        # in the window is a descendant of it.
        from PyQt6.QtWidgets import (QScrollArea, QSplitter, QStackedWidget,
                                     QTabWidget, QToolBox)
        if isinstance(w, QTabWidget):
            for i in range(w.count()):
                walk_widget(w.widget(i))
            from PyQt6.QtCore import Qt as _Qt
            for corner in (_Qt.Corner.TopLeftCorner, _Qt.Corner.TopRightCorner,
                           _Qt.Corner.BottomLeftCorner,
                           _Qt.Corner.BottomRightCorner):
                walk_widget(w.cornerWidget(corner))
        elif isinstance(w, QStackedWidget):
            for i in range(w.count()):
                walk_widget(w.widget(i))
        elif isinstance(w, QToolBox):
            for i in range(w.count()):
                walk_widget(w.widget(i))
        elif isinstance(w, QScrollArea):
            walk_widget(w.widget())
        elif isinstance(w, QSplitter):
            for i in range(w.count()):
                walk_widget(w.widget(i))

    walk_widget(root)
    return seen_w


def test_every_widget_this_window_names_is_in_its_layout(report_window):
    """THE GENERIC GUARD. A named widget that no layout contains is invisible,
    and nothing else in this suite would say so.

    MUTATION PROVEN: commenting out `judged_row.addWidget(self._unlock_check)`
    in `measurement_report_dialog.py` turns this red with
    `_unlock_check is built and never added to a layout`; putting the line
    back turns it green. Run before this sentence was written.
    """
    from PyQt6.QtWidgets import QWidget

    dlg = report_window
    placed = _widgets_in_layout_tree(dlg)
    orphans = []
    for name, obj in sorted(vars(dlg).items()):
        if not isinstance(obj, QWidget):
            continue
        if obj.isWindow():
            continue           # a window of its own is not laid out by this one
        if id(obj) not in placed:
            orphans.append(name)
    assert not orphans, (
        "built and never added to a layout, so nobody can see it: "
        + ", ".join(orphans))


# --------------------------------------------------------------------------
# 2. LAID OUT AND HIDDEN -- measured in a SHOWN window
# --------------------------------------------------------------------------
def _help_icon_beside(widget):
    """The `TooltipButton` sharing *widget*'s layout row, or None.

    "Its help icon" is Knut's phrase for the (i) that rides beside the unlock
    box, and finding it through the LAYOUT rather than through an attribute
    name is the point: an icon that is no longer on that row is not beside it,
    whatever the window still calls it.
    """
    from ui.tooltip_button import TooltipButton
    parent = widget.parentWidget()
    if parent is None:
        return None
    from PyQt6.QtWidgets import QLayout

    def rows(lay):
        if lay is None:
            return
        items = [lay.itemAt(i) for i in range(lay.count())]
        widgets = [it.widget() for it in items if it is not None]
        if widget in widgets:
            yield widgets
        for it in items:
            if it is None:
                continue
            sub = it.layout()
            if isinstance(sub, QLayout):
                yield from rows(sub)

    for lay in parent.findChildren(QLayout) + [parent.layout()]:
        for row in rows(lay):
            after = row[row.index(widget) + 1:]
            for w in after:
                if isinstance(w, TooltipButton):
                    return w
    return None


# RETIRED BY K31 (beta 40): `test_the_unlock_box_and_its_help_icon_are_on_screen`.
# Knut put the unlock box back in beta 26 (B8-520) and removed it in K31
# (5801677743): 'I agree that the Unlock this run's limits is no longer
# needed'. tests/test_k31_report_model.py pins that no report window builds
# it.


# RETIRED BY K31 (beta 40): `test_a_box_that_cannot_be_pressed_says_why`.
# The unlock box is gone (K31); the rule it applied, a dim control says why,
# is pinned for Generate report in tests/test_rw_report_window_fixes.py.


# RETIRED BY K31 (beta 40): `test_the_box_is_still_offered_when_two_runs_are_loaded`.
# The unlock box is gone (K31).


# --------------------------------------------------------------------------
# 3. THE TEXT BESIDE "Report shown" WRAPS, AND STOPS AT THREE LINES (K32)
# --------------------------------------------------------------------------
def test_the_hint_beside_report_shown_wraps_to_two_lines(report_window):
    """Knut: *"This text is cut off and the window must be far too wide to see
    the whole text. It is better that the text is wrapped down to a second
    line."*

    Two things are asserted because two things can go wrong: a label that does
    not wrap shows one elided line, and a label that wraps without a cap asks
    for a height the 800 px screen has not got (this window has been pushed off
    the bottom of a screen by exactly that, twice).

    MUTATION PROVEN: `label.setWordWrap(False)` in
    `_wrap_beside_the_pulldown` turns the first assertion red; removing
    `label.setMaximumHeight(two)` turns the third red.
    """
    from PyQt6.QtGui import QFontMetrics

    dlg = report_window
    long = ("The only saved report of a dated verification is kept: its "
            "verdict is this run's record of that date, and deleting it "
            "would leave the measurement with no report at all.")
    dlg._set_saved_note(long)
    note = dlg._saved_note
    assert note.wordWrap(), "the label still shows one elided line"
    assert note.isVisible()
    fm = QFontMetrics(note.font())
    from ui.dialogs.measurement_report_dialog import _BESIDE_PULLDOWN_LINES
    assert _BESIDE_PULLDOWN_LINES == 3, "K32: Knut asked for three lines"
    assert note.maximumHeight() <= 3 * fm.lineSpacing() + 2, (
        "an uncapped wrapped label is what took this window off an 800 px "
        "screen twice")
    assert note.toolTip() == long, "the whole sentence is still readable"


def test_a_sentence_too_long_for_two_lines_is_cut_not_stretched(report_window):
    """The cap has to be honoured by the TEXT as well as by the height, or the
    third line is simply clipped mid-word.

    MUTATION PROVEN: return after `label.setText(full)` unconditionally and
    this goes red.
    """
    from PyQt6.QtCore import QRect, Qt
    from PyQt6.QtGui import QFontMetrics

    dlg = report_window
    dlg._set_saved_note("Sentence. " * 200)
    note = dlg._saved_note
    fm = QFontMetrics(note.font())
    # **THE LABEL'S OWN WIDTH, NOT THE WINDOW'S.** This assertion measured the
    # window's remaining room and passed over a label that was drawing three
    # clipped lines on screen, because the label shares its row with a second
    # label and a stretch and gets far less than the window has left. The
    # photograph caught it; this number now asks the same question the
    # photograph did.
    room = note.width()
    assert room > 20, "the layout has not given the label a width yet"
    used = fm.boundingRect(QRect(0, 0, room, 10_000),
                           int(Qt.TextFlag.TextWordWrap), note.text()).height()
    assert used <= 3 * fm.lineSpacing() + 2, (
        f"the text needs {used} px where three lines are "
        f"{3 * fm.lineSpacing() + 2}")
    assert note.text().endswith("…"), note.text()[-40:]


# --------------------------------------------------------------------------
# 4. THE ONE-PAGE SUMMARY SAYS WHAT IT CANNOT DO
# --------------------------------------------------------------------------
def test_the_one_page_summary_disables_the_detail_box_and_says_why(
        report_window):
    """Knut: *"the 'Show detailed data for each run' can still be clicked so I
    assumed the created new report should have a detailed section. If this is
    not allowed … then also means the 'Show detailed data for each run' should
    be disabled, and function explained in help text, and have a tool-tip
    explaining why."*

    It has never been allowed: `_report_body_html` has returned
    `_one_page_html` before the detail section since T1 was built.

    **AND THE LIST IS NOT DISABLED WITH IT (B8-591).** This used to assert
    `not dlg._profile_list.isEnabled()` as well, from the same rule: a one-page
    summary is about one sheet, so the list was greyed to show it. Knut,
    2026-09-20, on what that looked like from the outside: *"Now I tried
    selecting report type Colour summary. Then the 'included measurements in
    report' became unticked for all measurements and it froze, so I cannot
    scroll or select."* A disabled QListWidget does not scroll, does not take a
    click and gives no reason. The detail box is a different case and keeps its
    disabling: there is nothing to choose behind it, and it says so.

    So the list stays live and carries the sentence instead, and a press with
    more than one measurement ticked is refused at Generate.

    MUTATION PROVEN: `det.setEnabled(True)` unconditionally in
    `_show_that_a_one_page_summary_is_one_sheet` and the first assertion goes
    red; `lst.setEnabled(False)` there and the third does.
    """
    from tests.helpers.report_window import choose_report_type

    dlg = report_window
    choose_report_type(dlg, mr.REPORT_TYPE_SUMMARY)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    assert not dlg._detail_check.isEnabled(), (
        "a tick box that changes nothing is still offered")
    assert "no per-run detail section" in dlg._detail_check.toolTip(), \
        dlg._detail_check.toolTip()
    assert dlg._profile_list.isEnabled(), (
        "the measurement list is frozen under “Colour summary”, which is the "
        "fault Knut reported")
    assert dlg._profile_list.viewport().isEnabled()
    assert "ONE measurement" in dlg._profile_list.toolTip(), \
        dlg._profile_list.toolTip()

    choose_report_type(dlg, mr.REPORT_TYPE_FULL)
    dlg._forget_limits()
    dlg._sync_limit_controls()
    assert dlg._detail_check.isEnabled(), "the box never came back"
    assert dlg._profile_list.isEnabled()
    assert dlg._profile_list.toolTip() == dlg._list_tooltip


def test_the_help_text_lists_every_option_as_a_bullet(report_window):
    """*"The report type and judged agains help text need to be more organised
    with bullets for each option."*

    MUTATION PROVEN: drop the bullet prefix in `_types_and_pairing_help` and
    the first assertion goes red; drop `_sets_help()` from the "Judged against"
    tooltip and the second does.
    """
    from workflow.compliance_sets import SETS
    from ui.dialogs.measurement_report_dialog import (_sets_help,
                                                      _types_and_pairing_help)

    types_help = _types_and_pairing_help()
    assert types_help.count("•") >= len(mr.REPORT_TYPE_MENU), types_help[:400]
    assert "no detailed section" in types_help, (
        "the one-page summary's limit is still specified nowhere the user "
        "can read it")

    sets_help = _sets_help()
    for s in SETS:
        if s.blurb:
            assert "• " + s.label in sets_help, s.label


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def _write_ti3(path, scale: float) -> None:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from drive_one_page_report import _GRID, _srgb_to_xyz_d50
    rows, n = [], 0
    for r in _GRID:
        for g in _GRID:
            for b in _GRID:
                n += 1
                x, y, z = _srgb_to_xyz_d50(r, g, b)
                x, y, z = x * scale + 0.25, y * scale + 0.2, z * scale + 0.15
                rows.append(f"{n} {r:.4f} {g:.4f} {b:.4f} "
                            f"{x / 100:.6f} {y / 100:.6f} {z / 100:.6f}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        'CTI3\n\nDESCRIPTOR "x"\nKEYWORD "DEVICE_CLASS"\n'
        'DEVICE_CLASS "OUTPUT"\nCOLOR_REP "RGB_XYZ"\n\n'
        "NUMBER_OF_FIELDS 7\nBEGIN_DATA_FORMAT\n"
        "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\nEND_DATA_FORMAT\n\n"
        f"NUMBER_OF_SETS {n}\nBEGIN_DATA\n" + "\n".join(rows) + "\nEND_DATA\n",
        encoding="utf-8")


@pytest.fixture
def report_window(tmp_path, qapp):
    """A SHOWN window on a run with one dated verification.

    Shown on purpose: `isVisible()` is the only question worth asking about a
    control a user says has disappeared, and on a dialog nobody showed the
    answer is False for everything in it.
    """
    from PyQt6.QtCore import QSettings

    from core.file_manager import Project
    from core.settings import AppSettings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    work = tmp_path / "w"
    work.mkdir()
    st = AppSettings()
    st._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    st.set("custom_output_path", str(work))
    proj = Project.create(work / "One", "One")
    run = proj.current_run()
    run.ensure_dir()
    p = run.dir / "verifications" / "2026-09-01_100000" / "Alpha.ti3"
    _write_ti3(p, 0.985)
    rep = mr.build_report(p)
    rep["created"] = "2026-09-01T10:00:00"
    mr.save_report(rep, p.parent)
    from tests.helpers.legacy_run_meta import (ensure_bound)
    ensure_bound(run, None, "chromiq_default")

    dlg = MeasurementReportDialog(st, None, initial_ti3=p)
    dlg.resize(1400, 900)
    dlg.show()
    qapp.processEvents()
    yield dlg
    dlg.close()


@pytest.fixture
def second_project(tmp_path, qapp):
    """A measurement from ANOTHER profile run, to load beside the first."""
    from core.file_manager import Project

    work = tmp_path / "w2"
    work.mkdir()
    proj = Project.create(work / "Two", "Two")
    run = proj.current_run()
    run.ensure_dir()
    p = run.dir / "verifications" / "2026-09-05_100000" / "Bravo.ti3"
    _write_ti3(p, 0.93)
    rep = mr.build_report(p)
    rep["created"] = "2026-09-05T10:00:00"
    mr.save_report(rep, p.parent)
    return p


def test_a_sentence_of_three_lines_is_shown_whole(report_window):
    """K32, Knut on beta 41 (#182 5815133233): *"The text field should always
    wrap to up to 3 lines (since there is space for this vertically), and if
    still not enough space for the text, then end text with "..." as
    usual."* A sentence that needs three lines at the label's width is shown
    whole, with no "…", and all three lines fit the label's height.

    MUTATION, proved to land: `_BESIDE_PULLDOWN_LINES = 2`."""
    dlg = report_window
    note = dlg._saved_note
    dlg._set_saved_note("x")
    room = note.width()
    assert room > 20
    two = 2 * note.fontMetrics().lineSpacing() + 2
    three = 3 * note.fontMetrics().lineSpacing() + 2
    words = []
    text = ""
    while True:                      # the shortest sentence past two lines
        words.append("measurement")
        text = " ".join(words)
        note.setText(text)
        if note.heightForWidth(room) > two:
            break
    assert note.heightForWidth(room) <= three, "past three lines already"
    dlg._set_saved_note(text)
    assert note.text() == text, note.text()[-40:]
    assert not note.text().endswith("…")
    assert note.heightForWidth(room) <= note.maximumHeight()
