"""Changing the Calculation method moves the LABELS, never the input boxes.

Knut, 2026-09-10:

    "With 'By columns / rows...' the labels for 'Calculation method', 'Strips
     (columns)' and 'Patches per strip (rows)' are not stretched out between
     the label column and the help icon the way 'By patch width' is. They are
     pushed to the right and the calculation method is hard to read. Changing
     the calculation method should move neither the position nor the size of
     the input boxes."

Measured on screen on 2026-09-11, in the real window: "By patch width" put its
labels at x 0..158 and its controls at 164..452; "By columns / rows" put the
labels at 164..315 and the controls at 321..452. The Calculation-method combo
moved **157 px** to the right and lost **157 px** of width, 288 down to 131,
which is why it elided to "By colum...".

Two causes, one symptom, and both are checked here.

1. Every bare spin box in the control column carries ``setMaximumWidth(96)``,
   which gives the COLUMN a maximum of 96 -- so ``setColumnStretch(1, 1)`` had
   nowhere to put the slack and the right-aligned label column took it. The
   one row that behaved, "Minimum patch width", is the one whose control is
   wrapped by ``mm_inch``, which ends in a stretch.
2. The two methods show different rows, so the label column was sized by
   whichever labels happened to be visible. Fixed with an invisible,
   zero-height strut that asks the column to PREFER the widest label of every
   row -- a size hint rather than a minimum, so the panel's own floor does not
   rise and the German labels can still wrap in a narrow pane.
"""
import pathlib
import sys

import pytest

pytest.importorskip("PyQt6")
from PyQt6.QtWidgets import QApplication, QLabel  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ui.dialogs.layout_options_panel import LayoutOptionsPanel  # noqa: E402

#: The pane this panel lives in is locked at 580 px, so it is measured at a
#: width it actually gets.
PANE_W = 580


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp):
    p = LayoutOptionsPanel(with_selectors=True)
    p.resize(PANE_W, 900)
    p.show()
    qapp.processEvents()
    qapp.processEvents()
    yield p
    p.hide()
    p.deleteLater()


def _method(panel, qapp, which):
    panel.area_method.setCurrentIndex(panel.area_method.findData(which))
    qapp.processEvents()
    qapp.processEvents()


def _visible(panel):
    """Every visible item of the area-first grid, by column."""
    lay = panel._area_fields_grid
    labels, controls, tips = [], [], []
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if w is None or not w.isVisible() or w.height() == 0:
            continue
        _r, c, _rs, _cs = lay.getItemPosition(i)
        g = w.geometry()
        entry = (g.x(), g.width(), w)
        (labels if c == 0 else controls if c == 1 else tips).append(entry)
    return labels, controls, tips


def _control_column(panel):
    labels, controls, tips = _visible(panel)
    assert controls, "no visible control in the area grid"
    return (min(x for x, _w, _o in controls),
            max(x + w for x, w, _o in controls))


# ---------------------------------------------------------------------------
# the fault
# ---------------------------------------------------------------------------
def test_the_control_column_starts_in_the_same_place_in_both_methods(panel, qapp):
    _method(panel, qapp, "by_width")
    a = _control_column(panel)
    _method(panel, qapp, "by_grid")
    b = _control_column(panel)
    assert a == b, (
        f"the input boxes moved: by patch width {a}, by columns / rows {b}")


def test_the_calculation_method_combo_never_moves_or_resizes(panel, qapp):
    """It is the ONE control both methods show, so it is the sharpest test:
    same widget, same row, two states."""
    seen = set()
    for which in ("by_width", "by_grid", "by_width", "by_grid"):
        _method(panel, qapp, which)
        g = panel.area_method.geometry()
        seen.add((g.x(), g.width()))
    assert len(seen) == 1, f"the combo moved between the methods: {sorted(seen)}"


def test_the_combo_is_wide_enough_not_to_elide_its_own_options(panel, qapp):
    """131 px could not hold "By columns / rows" and the window showed
    "By colum...". Measured against the text the combo is actually offering."""
    from PyQt6.QtGui import QFontMetrics
    for which in ("by_width", "by_grid"):
        _method(panel, qapp, which)
        fm = QFontMetrics(panel.area_method.font())
        need = max(fm.horizontalAdvance(panel.area_method.itemText(i))
                   for i in range(panel.area_method.count()))
        have = panel.area_method.geometry().width()
        assert have >= need, (
            f"{which}: the combo is {have} px wide and its longest option "
            f"needs {need} px, so it elides")


def test_only_the_labels_are_allowed_to_differ(panel, qapp):
    """What Knut asked for, stated as it was asked: the labels change, the
    boxes do not."""
    _method(panel, qapp, "by_width")
    a_lbl = sorted(w.text() for _x, _w, w in _visible(panel)[0]
                   if isinstance(w, QLabel))
    a_ctl = _control_column(panel)
    _method(panel, qapp, "by_grid")
    b_lbl = sorted(w.text() for _x, _w, w in _visible(panel)[0]
                   if isinstance(w, QLabel))
    b_ctl = _control_column(panel)
    assert a_lbl != b_lbl, "the two methods are supposed to show other labels"
    assert a_ctl == b_ctl


def test_the_mutation_lands(panel, qapp):
    """Both halves of the fix, taken away one at a time.

    A geometry check that passes with the fix removed is measuring the wrong
    thing, and this project has been bitten by exactly that.
    """
    # (a) the strut: without it the column is sized by the visible labels only.
    from PyQt6.QtWidgets import QSizePolicy
    panel._area_label_strut.changeSize(0, 0, QSizePolicy.Policy.Maximum,
                                       QSizePolicy.Policy.Fixed)
    panel._area_fields_grid.invalidate()
    qapp.processEvents()
    _method(panel, qapp, "by_width")
    a = _control_column(panel)
    _method(panel, qapp, "by_grid")
    b = _control_column(panel)
    panel._pin_area_label_column()
    qapp.processEvents()
    assert a != b, (
        "removing the label-column strut changed nothing, so the strut is not "
        f"what holds the columns still: {a} vs {b}")

    # (b) the trailing stretch: capping the wrapper the way the bare spin box
    # used to be capped hands the slack straight back to the label column.
    _method(panel, qapp, "by_grid")
    before = _control_column(panel)
    wrapper = [w for _x, _w, w in _visible(panel)[1]
               if w is not panel.area_method]
    assert wrapper, "the by-grid method shows no wrapped control"
    for w in wrapper:
        w.setMaximumWidth(96)
    qapp.processEvents()
    qapp.processEvents()
    after = _control_column(panel)
    for w in wrapper:
        w.setMaximumWidth(16777215)
    qapp.processEvents()
    assert after != before, (
        "capping the control column at 96 px moved nothing, so the trailing "
        f"stretch is not what gives it the slack: {before} vs {after}")


# ---------------------------------------------------------------------------
# …and the floor that must not rise
# ---------------------------------------------------------------------------
def test_the_panel_can_still_shrink(panel, qapp):
    """The labels wrap on purpose: an unwrapped QLabel reports its whole text
    as a hard minimum, and in German that put a horizontal scroll bar under the
    whole Expert section (Basti, twice). The strut reports its width as a size
    HINT and zero as its minimum, so the floor is where it was.
    """
    strut = panel._area_label_strut
    assert strut.minimumSize().width() == 0
    assert strut.sizeHint().width() > 0
    assert panel._area_fields_grid.columnMinimumWidth(0) == 0, (
        "a column MINIMUM would raise the panel's floor; measured at +43 px in "
        "English and +34 in German when it was tried")
    assert panel._area_fields_w.minimumSizeHint().width() < PANE_W


def test_the_strut_is_not_a_widget_and_costs_no_height(panel, qapp):
    """It shares the first label's cell, which a WIDGET may never do (see
    `test_the_layout_panel_has_no_two_widgets_in_one_cell.py`, written after two
    checkboxes were drawn two pixels apart). A spacer paints nothing and is zero
    pixels tall, so it cannot be that fault; a row of its own would have cost
    the grid's row spacing, measured at +6 px of empty height."""
    from PyQt6.QtWidgets import QSpacerItem
    lay = panel._area_fields_grid
    idx = [i for i in range(lay.count()) if lay.itemAt(i) is panel._area_label_strut]
    assert len(idx) == 1
    assert isinstance(panel._area_label_strut, QSpacerItem)
    assert lay.itemAt(idx[0]).widget() is None
    r, c, _rs, _cs = lay.getItemPosition(idx[0])
    assert (r, c) == (0, 0)
    assert panel._area_label_strut.sizeHint().height() == 0
    assert lay.rowCount() == 5, (
        f"the area grid has {lay.rowCount()} rows; the five it is meant to "
        "have are the method, the two by-width rows and the two by-grid ones")


def test_no_two_widgets_share_a_cell_in_the_area_grid(panel, qapp):
    """The rule the whole panel is already held to, checked here as well, so
    this file's own strut can never be the thing that breaks it."""
    lay = panel._area_fields_grid
    seen = {}
    for i in range(lay.count()):
        w = lay.itemAt(i).widget()
        if w is None:
            continue
        r, c, rs, cs = lay.getItemPosition(i)
        for dr in range(max(1, rs)):
            for dc in range(max(1, cs)):
                key = (r + dr, c + dc)
                assert key not in seen, (
                    f"({key}) holds {type(seen[key]).__name__} and "
                    f"{type(w).__name__}")
                seen[key] = w
