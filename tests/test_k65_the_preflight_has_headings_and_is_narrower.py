"""k65 (Knut, #182 6095388856, 2026-10-10): the "Before you measure this
verification chart" window drew ALL its text bold, because macOS draws a
QMessageBox's text in the bold system font and the window handed it plain
text. Only the headings may stand out; the body is in the normal weight. And
the window is 20-25 % narrower (920 -> 720 for the text, a 968 -> 768 px box,
measured on screen in all 14 languages).

Measured on screen: ~/Desktop/ChromIQ-work/2026-10-10_434b1_B3/shots/k65/.
"""
from __future__ import annotations

import inspect
import re

import pytest


def test_headings_are_bold_and_the_body_is_not():
    """MUTATION: give every block weight 700 (the old look), or drop the
    explicit 400 (macOS then keeps the label's bold), and this goes red."""
    from ui.tabs.tab_measure import preflight_html
    html = preflight_html([(True, "Heading"), (False, "Body one\n\nBody two"),
                           (True, "Second heading"), (False, "Under it")])
    weights = dict(re.findall(r'font-weight:(\d+)">([^<]*)<', html)[i][::-1]
                   for i in range(5))
    assert weights == {"Heading": "700", "Body one": "400", "Body two": "400",
                       "Second heading": "700", "Under it": "400"}


def test_the_metric_list_keeps_its_indent_and_markup_is_escaped():
    """An indented reason must stay indented when it wraps, which spaces at
    the start of a line did not do (the second line began at the left edge).

    MUTATION: render the indent as &nbsp; again, or skip html.escape, and
    this goes red."""
    from ui.tabs.tab_measure import _PREFLIGHT_INDENT_PX, preflight_html
    html = preflight_html([(False, "It cannot answer these\n  × A < B & C")])
    assert f"margin-left:{2 * _PREFLIGHT_INDENT_PX}px" in html
    assert "&nbsp;" not in html
    assert "A &lt; B &amp; C" in html


def test_the_window_shows_the_rich_text_with_both_headings(monkeypatch):
    """The window's own builder: its title and M-VERIFY-UNCHECKED-METRICS's
    title are headings, everything else body; the plain version (what the
    tests of its content read) is unchanged.

    MUTATION: mark the unchecked-metrics title as body, or show the plain
    text in the window again, and this goes red."""
    from ui.dialogs import preset_verification_dialog as PVD
    from ui.tabs.tab_measure import TabMeasure
    from workflow import measurement_messages as M

    class _A:
        checked = True
        missing = ["x"]

    class _Row:
        assessment = _A()

    monkeypatch.setattr(PVD, "summary_lines", lambda row, generic=False: [])
    monkeypatch.setattr(PVD, "gamut_only_shortfalls", lambda row: False)
    tab = TabMeasure.__new__(TabMeasure)
    title, blocks = TabMeasure._verification_preflight_blocks(tab, _Row())
    u_title = M.M_VERIFY_UNCHECKED_METRICS.render()[0]
    assert [t for h, t in blocks if h] == [title, u_title]
    plain = TabMeasure._verification_preflight_message(tab, _Row())[1]
    assert plain.startswith(title + "\n\n")
    src = inspect.getsource(TabMeasure._show_verification_preflight_now)
    assert "self._verification_preflight_html(row)" in src
    assert "setTextFormat(Qt.TextFormat.RichText)" in src
    assert "_verification_preflight_html(\n                    row, short=True)" in src


def test_the_window_is_20_to_25_percent_narrower():
    """MUTATION: put 920 back and this goes red."""
    from ui.tabs.tab_measure import PREFLIGHT_TEXT_WIDTH
    assert 0.75 * 920 <= PREFLIGHT_TEXT_WIDTH <= 0.80 * 920


def test_a_rich_text_box_is_not_widened_to_its_markup(qapp):
    """`keep_message_box_inside_the_work_area` widened a box to its longest
    LINE of text; a rich-text body is one line of markup, so the pre-flight's
    one-line version came up 998 px wide instead of 768 (measured on screen).

    MUTATION: drop the rich-text condition and this goes red."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QMessageBox

    from ui.widgets import keep_message_box_inside_the_work_area
    para = "word " * 80      # one paragraph, short enough to stay in the box

    def width(rich: bool) -> int:
        box = QMessageBox()
        if rich:
            box.setTextFormat(Qt.TextFormat.RichText)
            box.setText(f"<p>{para}</p>")
        else:
            box.setText(para)
        def spacer_widths():
            lay = box.layout()
            return [lay.itemAt(i).spacerItem().sizeHint().width()
                    for i in range(lay.count()) if lay.itemAt(i).spacerItem()]
        before = spacer_widths()
        keep_message_box_inside_the_work_area(box)
        added = spacer_widths()[len(before):]
        box.deleteLater()
        return max(added, default=0)

    assert width(rich=False) > 0       # a plain long line is still widened
    assert width(rich=True) == 0
