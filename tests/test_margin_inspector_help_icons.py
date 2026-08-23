"""Every tick box in "Measured from Preview" explains itself (#164, Basti).

*"At its bottom there are 3 options with checkboxes but only one of them has a
tooltip icon assigned to it."*

There was one icon, against the FIRST of the three, carrying a single body that
explained the panel and all three boxes at once — so it read as that box's help,
and anyone after the third one had to wade through the other two to reach it.

The project already had the rule. Knut, beta.8 of #152, about this very panel:
*"the help icon is not vertically centered with the other objects on the line"* —
an icon belongs to the line it explains. Each tick box now answers for itself,
and the overview of the numbers table stays on the panel's own icon, up on the
table where those numbers are.

His other ruling for this panel is the one this file must not break. Beta.3 of
4.0.2: *"The info icons on the right side of the 'Measured from Preview' frame
are not aligned to each other and the frame is too wide."*
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def panel(qapp):
    from ui.margin_inspector_panel import MarginInspectorPanel
    from workflow.margin_inspector import MarginReport

    p = MarginInspectorPanel()
    p.update_report(
        MarginReport(left_mm=8.0, right_mm=8.0, top_mm=10.0, bottom_mm=10.0,
                     strip_width_mm=13.7, page_w_mm=210.0, page_h_mm=297.0,
                     strip_length_mm=210.0),
        [], thresholds_defined=True, notify=True)
    p.resize(560, 400)
    p.show()
    return p


def _tips(panel):
    from ui.tooltip_button import TooltipButton
    return panel.findChildren(TooltipButton)


def test_every_tick_box_has_its_own_help_icon(panel):
    tips = _tips(panel)
    # three tick boxes + the panel's own overview
    assert len(tips) == 4, f"expected four ⓘ, got {len(tips)}"
    titles = {t._title for t in tips}
    assert "About the margin inspector" in titles
    for expected in ("Instrument-margin guide lines", "Margin guide lines",
                     "Measurement coordinates on pointer"):
        assert expected in titles, f"no help of its own for {expected!r}"


def test_each_icon_sits_on_the_line_it_explains(panel):
    """Knut's beta.8 rule. The three tick-box icons must be level with their own
    tick boxes — not floating against a block of them."""
    boxes = [panel._guide_check, panel._measured_check, panel._coord_check]
    by_title = {t._title: t for t in _tips(panel)}
    pairs = [
        (boxes[0], by_title["Instrument-margin guide lines"]),
        (boxes[1], by_title["Margin guide lines"]),
        (boxes[2], by_title["Measurement coordinates on pointer"]),
    ]
    for box, tip in pairs:
        box_mid = box.mapTo(panel, box.rect().center()).y()
        tip_mid = tip.mapTo(panel, tip.rect().center()).y()
        assert abs(box_mid - tip_mid) <= 3, (
            f"the ⓘ for {tip._title!r} is {abs(box_mid - tip_mid)} px off its line")


def test_the_icons_still_share_one_right_edge(panel):
    """Knut's beta.3 rule, which the extra icons must not undo."""
    rights = {t.mapTo(panel, t.rect().topLeft()).x() + t.width()
              for t in _tips(panel)}
    assert len(rights) == 1, f"the ⓘ icons end at different x positions: {rights}"


def test_the_frame_did_not_get_wider(panel):
    """His other half of the same sentence — *"and the frame is too wide"*. The
    panel's ⓘ moved onto the numbers table rather than adding a column of its
    own, so the width is the one 4.1.2 shipped."""
    assert panel.sizeHint().width() <= 460, (
        f"the frame grew to {panel.sizeHint().width()} px")


def test_each_body_explains_its_own_box_and_says_what_the_default_is(panel):
    """Friendly and self-contained: a reader who opens one icon should not have
    to open the others to understand it."""
    by_title = {t._title: t for t in _tips(panel)}
    for title in ("Instrument-margin guide lines", "Margin guide lines",
                  "Measurement coordinates on pointer"):
        body = by_title[title]._body
        assert len(body) > 200, f"{title}: the help is a stub"
        assert "Default:" in body, f"{title}: never says what the default is"
    # The two guide-line boxes are easy to confuse, so each must draw the line
    # between them rather than leaving the reader to.
    assert "instrument" in by_title["Margin guide lines"]._body.lower()
