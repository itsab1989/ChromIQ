"""B8-757: Create Chart Manual at 1280 x 800 clipped text in two languages.

Measured on screen before the fix, 2026-09-28, all fourteen languages
(`scripts/drive_before_stable_b8_504_757_1342.py widths <lang>`): twelve were
clean; two were not.

* German: the "on screen" header of Chart layout information,
  "auf dem Bildschirm", sat in a fixed 72 px column and lost its first word.
* Japanese: two "Measured from Preview" check boxes and three row names of
  Chart layout information. `WrappingCheckBox` wraps at spaces, and Japanese
  has none, so "余白のガイド線をプレビューに表示（長い点線）" was ONE word
  whose width was the box's floor, and that floor squeezed the panel beside it.

MUTATIONS, proven red: split `WrappingCheckBox._units` on whitespace only
(the CJK tests fail); put `setFixedWidth(_COLW)` back on the headers (the
German test fails).
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("qapp")

JA = "余白のガイド線をプレビューに表示（長い点線）"


@pytest.fixture
def _german():
    import core.i18n as i18n
    previous = getattr(i18n, "_language", "en")
    i18n.set_language("de")
    try:
        yield
    finally:
        i18n.set_language(previous)


def test_a_japanese_check_box_can_wrap():
    from ui.widgets import WrappingCheckBox
    box = WrappingCheckBox(JA)
    full = box.sizeHint().width()
    assert box.minimumSizeHint().width() < full // 2, (
        "a label with no spaces must still be allowed to wrap")
    fm = box.fontMetrics()
    width = fm.horizontalAdvance(JA) // 2
    lines = box._lines(width)
    assert len(lines) >= 2, lines
    assert "".join(lines) == JA, "wrapping must not add or lose a character"
    assert all(fm.horizontalAdvance(line) <= width for line in lines), lines


def test_a_latin_label_still_breaks_only_at_its_spaces():
    from ui.widgets import WrappingCheckBox
    text = "Show instrument-margin guide lines on preview (dotted lines)"
    assert [p for p, _g in WrappingCheckBox._units(text)] == text.split()
    box = WrappingCheckBox(text)
    lines = box._lines(box.fontMetrics().horizontalAdvance(text) // 2)
    assert " ".join(lines) == text


def test_the_layout_panel_headers_show_their_whole_text_in_german(_german):
    from PyQt6.QtWidgets import QLabel
    from ui.chart_layout_info_panel import ChartLayoutInfoPanel
    panel = ChartLayoutInfoPanel()
    heads = [w for w in panel.findChildren(QLabel)
             if w.text() in ("auf dem Bildschirm", "Schätzung")]
    assert len(heads) == 2, [w.text() for w in panel.findChildren(QLabel)]
    for w in heads:
        need = w.fontMetrics().horizontalAdvance(w.text())
        assert w.maximumWidth() >= need, (w.text(), w.maximumWidth(), need)
