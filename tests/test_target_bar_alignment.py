"""#130 (Knut, 2026-07-26): the Profile-run / Run-type bar must keep its boxes
and labels left-aligned and in sequence — switching Run type to Verification
adds boxes on the right rather than spreading the existing ones apart.

The regression this guards against was geometric, not logical: the location line
beneath the row is long, so it set the column's width, and a row with no trailing
stretch shared that slack out *between* the boxes. Every assertion here is made
on real laid-out geometry, at a width far wider than the bar needs.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtCore import QSettings                        # noqa: E402
from PyQt6.QtWidgets import QApplication                  # noqa: E402

from core.file_manager import FileManager, Project        # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,  # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                     # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,        # noqa: E402
                                       MeasurementTargetController)

WIDE = 1400          # far wider than the bar's own content needs


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _bar(tmp_path, run_type=RUN_TYPE_PROFILING):
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    root = tmp_path / "ChromIQ"; root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    Project.create(root / "My-Printer", "My-Printer").current_run().ensure_dir()
    fm.set_target_name("My-Printer")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(run_type)
    bar = MeasurementTargetBar(ctl)
    bar.resize(WIDE, bar.sizeHint().height())
    bar.show()
    QApplication.processEvents()
    bar.layout().activate()
    return bar


def _visible_row_widgets(bar):
    """Left-to-right, the widgets actually sitting in the top row."""
    row = bar.layout().itemAt(0).layout()
    out = []
    for i in range(row.count()):
        w = row.itemAt(i).widget()
        if w is not None and w.isVisible():
            out.append(w)
    return sorted(out, key=lambda w: w.x())


def test_the_row_does_not_stretch_across_the_window(qapp, tmp_path):
    """Profiling shows two boxes; they must sit at the left, not at the edges."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # box positions pivot on real text widths
    bar = _bar(tmp_path)
    widgets = _visible_row_widgets(bar)
    assert widgets, "the row should have visible widgets"
    rightmost = max(w.x() + w.width() for w in widgets)
    assert rightmost < WIDE * 0.6, (
        f"the row spans {rightmost}px of {WIDE}px — the boxes are being spread "
        f"apart instead of packed to the left")


def test_neighbours_stay_at_the_row_spacing(qapp, tmp_path):
    """No two adjacent items may drift apart — "justified across the screen"
    meant gaps of hundreds of pixels between a label and its own box.

    The allowance covers the row's own spacing plus the one deliberate 4px
    separator between the selector group and the ⓘ; anything beyond that is the
    layout sharing out slack, which is the bug.
    """
    bar = _bar(tmp_path)
    spacing = bar.layout().itemAt(0).layout().spacing()
    allowed = spacing + 4 + 1
    widgets = _visible_row_widgets(bar)
    gaps = [b.x() - (a.x() + a.width())
            for a, b in zip(widgets, widgets[1:])]
    assert all(g <= allowed for g in gaps), \
        f"gaps {gaps} exceed the {allowed}px a packed row can show"


def test_verification_adds_its_boxes_on_the_right(qapp, tmp_path):
    """Knut's requirement stated positively: the extra boxes appear to the
    right of the existing ones, which do not move."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # box positions pivot on real text widths
    bar = _bar(tmp_path)
    before = {id(w): w.x() for w in _visible_row_widgets(bar)}
    # Measured up to the last *selector* — the bar's ⓘ closes the row and the
    # new boxes are inserted ahead of it.
    profiling_right = max(w.x() + w.width() for w in _visible_row_widgets(bar)
                          if w is bar._type_combo)

    bar._ctl.set_run_type(RUN_TYPE_VERIFICATION)
    QApplication.processEvents()
    bar.layout().activate()

    after = _visible_row_widgets(bar)
    assert len(after) > len(before), "verification should add boxes"
    # Everything up to the insertion point must stay exactly where it was.
    # The widgets that sit AFTER it are pushed along, which is the point: the
    # bar's own ⓘ, and — since #130 — the Restore Used Chart button and its ⓘ,
    # which are shown for both run types and so are not "new" boxes.
    # Since #130's Delete button (2026-07-28) that is five widgets, not three:
    # the fields' ⓘ now sits directly after the Verification box rather than at
    # the end of the row, so it and BOTH buttons with their own ⓘ are pushed
    # along when the Verification boxes appear. All five are shown for either
    # run type, so none of them is a "new" box.
    # Seven since the Duplicate button and its ⓘ joined them (#130, 2026-08-01,
    # "course B") — same reasoning: shown for either run type, so pushed along
    # rather than added.
    pushed = {id(bar._tip_btn), id(bar._restore_btn), id(bar._restore_tip),
              id(bar._duplicate_btn), id(bar._duplicate_tip),
              id(bar._delete_btn), id(bar._delete_tip)}
    for w in after:
        if id(w) in before and id(w) not in pushed:
            assert w.x() == before[id(w)], \
                "an existing box moved when the verification boxes appeared"
    added = [w for w in after if id(w) not in before]
    assert added, "verification adds its date label and box"
    assert min(w.x() for w in added) >= profiling_right - 1, \
        "the new boxes must be added on the right of the Run type box"
    # …and the widened row still does not reach across the window.
    assert max(w.x() + w.width() for w in after) < WIDE * 0.75


def test_a_long_location_line_does_not_spread_the_row(qapp, tmp_path):
    """The location line is the widest thing in the bar — its width must not
    reach the row above it."""
    from _fontcheck import skip_without_fonts
    skip_without_fonts()                 # row width pivots on real text widths
    bar = _bar(tmp_path)
    bar._location.setText("ChromIQ/" + "a-very-long-project-name/" * 6)
    QApplication.processEvents()
    bar.layout().activate()

    widgets = _visible_row_widgets(bar)
    rightmost = max(w.x() + w.width() for w in widgets)
    assert rightmost < WIDE * 0.6, (
        "a long location line pulled the row apart — the row needs its own "
        "trailing stretch")
