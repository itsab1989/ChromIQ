"""#130 (Knut, 2026-07-26): the bar's boxes must be readable and must not
change size or position as the user moves between tabs or changes a selection.

Knut saw the Verification box come up too narrow to read, the "Restore Used
Chart" button render with its text cut off at both ends, and the whole group
slide sideways when Run type changed. All three are geometry, so all three are
asserted on real laid-out geometry.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel          # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,        # noqa: E402
                                       MeasurementTargetController)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _bar(tmp_path, dates=()):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "My-Printer", "My-Printer")
    run = proj.current_run(); run.ensure_dir()
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    for d in dates:
        run.verification(d).ensure_dir()
    fm.set_target_name("My-Printer")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    bar = MeasurementTargetBar(ctl)
    # The real application's style sheet, applied to the bar's own tree: its
    # padding is part of what a box needs, and without it these widths are not
    # the widths the user sees.
    from ui.styles import APP_STYLESHEET
    bar.setStyleSheet(APP_STYLESHEET)
    bar.resize(1400, bar.sizeHint().height())
    bar.show()
    QApplication.processEvents(); bar.layout().activate()
    return bar, run


# ---- readable ------------------------------------------------------------
def _text_area(combo) -> int:
    """The width a combobox actually leaves for its text, per its own style —
    total width minus frame, padding and the drop-down arrow. Comparing against
    the total width is what let an elided "Run 1 (overwr…" slip through."""
    from PyQt6.QtWidgets import QStyle, QStyleOptionComboBox
    opt = QStyleOptionComboBox()
    opt.initFrom(combo)
    opt.frame = True
    return combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox, opt,
        QStyle.SubControl.SC_ComboBoxEditField, combo).width()


def test_every_box_is_wide_enough_for_its_longest_entry(qapp, tmp_path):
    bar, _run = _bar(tmp_path, dates=("2026-07-20_100000",))
    for combo in (bar._run_combo, bar._type_combo, bar._verify_combo):
        fm = combo.fontMetrics()
        widest = max(fm.horizontalAdvance(combo.itemText(i))
                     for i in range(combo.count()))
        assert _text_area(combo) >= widest, (
            f"{combo.objectName()} leaves {_text_area(combo)}px for text but "
            f"needs {widest}px for its longest entry — it will be elided")


def test_the_two_action_buttons_are_their_marks_and_nothing_more(qapp, tmp_path):
    """This used to check that "Restore Used Chart" fitted its own label, after
    Knut saw it drawn with the text cut off at both ends. The label is gone: he
    asked for the mark to replace the whole button (#130, 2026-07-29), so the
    requirement is now the opposite — a square the size of the row's height, with
    no room reserved for text that is never painted."""
    from ui.bar_icons import BarIconButton
    bar, _run = _bar(tmp_path, dates=("2026-07-20_100000",))
    side = BarIconButton.HEIGHT
    for btn in (bar._restore_btn, bar._delete_btn):
        assert (btn.width(), btn.height()) == (side, side), \
            f"{btn.text()!r} is {btn.width()}×{btn.height()}, not the {side}px square"


# ---- stable --------------------------------------------------------------
def test_a_date_gaining_a_measurement_does_not_resize_the_box(qapp, tmp_path):
    """The two labels a date can carry differ in length; the box is sized for
    the longer one either way, so measuring never moves the layout."""
    bar, run = _bar(tmp_path, dates=("2026-07-20_100000",))
    before = bar._verify_combo.width()

    run.verification("2026-07-20_100000").measurement_ti3.write_text("RESULT")
    bar.refresh()
    QApplication.processEvents(); bar.layout().activate()

    assert bar._verify_combo.width() == before


def test_widths_survive_repeated_refreshes(qapp, tmp_path):
    """Switching tabs calls refresh(); nothing may shrink or grow."""
    bar, _run = _bar(tmp_path, dates=("2026-07-20_100000", "2026-07-21_090000"))
    widths = [w.width() for w in (bar._run_combo, bar._type_combo,
                                  bar._verify_combo, bar._restore_btn)]
    for _ in range(3):
        bar.refresh()
        QApplication.processEvents(); bar.layout().activate()
    assert [w.width() for w in (bar._run_combo, bar._type_combo,
                                bar._verify_combo, bar._restore_btn)] == widths


def test_switching_run_type_does_not_move_the_boxes(qapp, tmp_path):
    bar, _run = _bar(tmp_path, dates=("2026-07-20_100000",))
    before = (bar._run_combo.x(), bar._type_combo.x())

    bar._ctl.set_run_type(RUN_TYPE_PROFILING)
    QApplication.processEvents(); bar.layout().activate()
    bar._ctl.set_run_type(RUN_TYPE_VERIFICATION)
    QApplication.processEvents(); bar.layout().activate()

    assert (bar._run_combo.x(), bar._type_combo.x()) == before


# ---- locked on the tabs that do not use it -------------------------------
def test_locking_greys_the_selection_and_explains_where_to_change_it(qapp,
                                                                     tmp_path):
    bar, _run = _bar(tmp_path, dates=("2026-07-20_100000",))
    live_tip = bar._run_combo.toolTip()

    bar.set_locked(True)
    for w in (bar._run_combo, bar._type_combo, bar._verify_combo):
        assert not w.isEnabled()
        assert "Create Chart" in w.toolTip() and "Measure" in w.toolTip()
    assert not bar._restore_btn.isEnabled()

    bar.set_locked(False)
    assert bar._run_combo.isEnabled()
    assert bar._run_combo.toolTip() == live_tip, \
        "the box's own tooltip must come back when the bar is live again"


# ---- the tooltip label is reused, so it must be reset every time ----------
def test_a_short_tooltip_after_a_long_one_is_not_left_oversized(qapp):
    """Qt reuses one label for every tooltip. Sizing it for a long text and
    then showing a short one in the same box is what made tooltips appear
    half empty; the reverse made them appear cut off."""
    from ui.widgets import TooltipWrapFilter
    f = TooltipWrapFilter()
    label = QLabel()

    label.setText("A very long tooltip. " * 40)
    f.fit(label)
    tall = label.height()
    assert label.wordWrap() and label.width() == f.MAX_W

    label.setText("Short.")
    f.fit(label)
    assert label.maximumWidth() > f.MAX_W, "the fixed size must be released"
    assert label.height() < tall, "a one-line tooltip must not keep the tall box"


def test_both_info_icons_follow_the_active_tab(qapp, tmp_path):
    """The Restore button's ⓘ kept the Measure tab's colour on every other tab
    (Knut, #130 2026-07-27)."""
    bar, _run = _bar(tmp_path, dates=("2026-07-20_100000",))

    bar.set_accent("#123456")

    assert bar._tip_btn._color_override == "#123456"
    assert bar._restore_tip._color_override == "#123456", "the Restore ⓘ must follow too"


# ---- the hint's box reaches the version text (Knut, #131 2026-07-27) ------
def _hint_bar(tmp_path, avail):
    """A bar whose hint is shown, sized the way the masthead sizes it: told how
    much rail there is, and then given exactly that much."""
    bar, _run = _bar(tmp_path)
    bar._hint_wanted = True
    bar._hint.setVisible(True)
    bar.set_available_width(avail)
    bar.resize(avail, bar.sizeHint().height())
    QApplication.processEvents(); bar.layout().activate()
    return bar


def test_the_hint_takes_the_room_up_to_the_version_text(qapp, tmp_path):
    """Knut's correction of my first fix: "This cell width should reach all the
    way to the left side of the app version number text … The invisible frame
    with the sentence inside should then follow any change of the window size."

    The masthead hands the bar exactly that room; the sentence must claim what
    is left of it rather than share it with the row's trailing stretch, which is
    what wrapped it into a narrow column of four lines.
    """
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # hint width pivots on real text widths
    bar = _hint_bar(tmp_path, 1400)
    row = bar.layout().itemAt(0).layout()
    boxes_end = max(row.itemAt(i).widget().geometry().right()
                    for i in range(row.count())
                    if row.itemAt(i).widget() is not None
                    and row.itemAt(i).widget() is not bar._hint)

    hint = bar._hint
    assert hint.x() > bar._restore_tip.x(), "it sits right of the second ⓘ"
    # Everything the row has left of it, give or take the row spacing.
    assert hint.width() >= (bar.width() - boxes_end) - row.spacing() - 2, (
        f"the sentence got {hint.width()}px of the "
        f"{bar.width() - boxes_end}px left in the row")


def test_the_box_follows_the_window_width(qapp, tmp_path):
    """Wider window, wider box — that is what "follows any change of the window
    size" means."""
    # The widths are chosen above the point where the sentence still fits beside
    # the boxes. That point moved out when the Delete button joined the row
    # (#130, 2026-07-28) — the row is about 110 px wider, so it needs a wider
    # window before there is 200 px left for the sentence. Below that it drops
    # to its own line, which is the designed behaviour and is covered by
    # test_a_narrow_bar_puts_the_sentence_under_the_row. What THIS test is
    # about is unchanged: while it does sit beside, its width follows the
    # window.
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # box width pivots on real text widths
    widths = []
    for avail in (1400, 1600, 1800):
        bar = _hint_bar(tmp_path, avail)
        if bar._hint_beside:
            widths.append((avail, bar._hint.width()))
    assert len(widths) >= 2, "the sentence should sit beside at these widths"
    assert [w for _a, w in widths] == sorted(w for _a, w in widths), widths
    assert widths[0][1] != widths[-1][1], "it must not be a fixed width"


def test_it_wraps_instead_of_running_off(qapp, tmp_path):
    bar = _hint_bar(tmp_path, 1400)
    hint = bar._hint
    assert hint.wordWrap()
    assert hint.x() + hint.width() <= bar.width() + 1
    needed = hint.fontMetrics().horizontalAdvance(hint.text())
    if needed > hint.width():
        assert hint.height() > hint.fontMetrics().height(), "cut off, not wrapped"


def test_a_rail_too_narrow_for_it_puts_it_under_the_row_instead(qapp, tmp_path):
    """At 900 px the boxes already fill the rail. Honouring the rule there would
    give the sentence forty pixels — one word wide and twenty-one lines tall
    (measured). It goes under the row at that point, and comes back up as soon
    as there is room."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # beside/below pivots on real text widths
    narrow = _hint_bar(tmp_path, 700)
    assert not narrow._hint_beside
    assert narrow._hint.y() > narrow.layout().itemAt(0).layout().geometry().bottom() - 1
    assert narrow.height() < 120, f"the bar grew to {narrow.height()}px"

    wide = _hint_bar(tmp_path, 1600)
    assert wide._hint_beside, "it must return to the row when there is room"


def test_the_bar_never_grows_absurdly_tall(qapp, tmp_path):
    """The failure this whole mechanism exists to prevent."""
    for avail in (600, 700, 900, 1100, 1400, 1900):
        bar = _hint_bar(tmp_path, avail)
        assert bar.height() < 140, f"{bar.height()}px at {avail}px of rail"


def test_only_the_location_line_is_below_when_it_fits_beside(qapp, tmp_path):
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # beside/below pivots on real text widths
    bar = _hint_bar(tmp_path, 1600)
    assert bar._hint_beside
    assert bar._hint.y() < bar._location.y()
