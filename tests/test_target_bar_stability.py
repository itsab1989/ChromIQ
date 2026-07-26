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


def test_the_restore_button_fits_its_own_label(qapp, tmp_path):
    """Knut saw it drawn with the text cut off at both ends."""
    bar, _run = _bar(tmp_path, dates=("2026-07-20_100000",))
    btn = bar._restore_btn
    needed = btn.fontMetrics().horizontalAdvance(btn.text())
    assert btn.width() >= needed, f"{btn.width()}px for {needed}px of text"


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
