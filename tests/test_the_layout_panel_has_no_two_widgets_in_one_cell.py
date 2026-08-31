"""No two widgets may share a grid cell in the layout panel.

Reported from beta 5 on a ColorMunki: "Offset every second strip" was drawn on
top of the Clip-border checkbox, two pixels apart, tooltip buttons and all.
Both are placed unconditionally; the clip-border pair only exists when the
panel owns the selectors, and only a ColorMunki shows both at once, so every
other instrument hid the collision.

This asserts the property rather than the row number: a cell may hold one
widget. It reads the LIVE layout, so a widget added later is covered without
anyone remembering this file.
"""
import pytest
from PyQt6.QtWidgets import QGridLayout, QWidget


def _grid_cells(root: QWidget):
    """Every (layout, row, column) that a widget occupies, live."""
    for grid in root.findChildren(QGridLayout):
        for i in range(grid.count()):
            item = grid.itemAt(i)
            if item is None or item.widget() is None:
                continue
            r, c, rs, cs = grid.getItemPosition(i)
            for dr in range(max(1, rs)):
                for dc in range(max(1, cs)):
                    yield grid, r + dr, c + dc, item.widget()


@pytest.mark.parametrize("with_selectors", [True, False])
def test_every_cell_holds_at_most_one_widget(qapp, with_selectors):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel

    try:
        panel = LayoutOptionsPanel(None, with_selectors=with_selectors)
    except TypeError:
        panel = LayoutOptionsPanel(None)
        if with_selectors != (getattr(panel, "mode", None) is not None):
            pytest.skip("this build offers only one panel shape")

    seen: dict = {}
    clashes = []
    for grid, r, c, w in _grid_cells(panel):
        key = (id(grid), r, c)
        if key in seen and seen[key] is not w:
            clashes.append(f"({r},{c}): {seen[key].objectName() or type(seen[key]).__name__}"
                           f" and {w.objectName() or type(w).__name__}"
                           f" — {getattr(seen[key], 'text', lambda: '')()!r}"
                           f" / {getattr(w, 'text', lambda: '')()!r}")
        seen[key] = w
    assert not clashes, "widgets share a grid cell:\n  " + "\n  ".join(clashes)
