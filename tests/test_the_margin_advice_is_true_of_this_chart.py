"""Beta 8 — the inspector told the user to reduce a setting that moves nothing.

Agent B reproduced both of the long messages Knut asked about, in one state
(A4, ChromIQ engine, row indicators ON, a 26 mm clip border on the left, left
margin asked for 4 mm, Clip 4 mm) and found them contradicting each other on
screen at the same moment:

* the red warning under the preview ended *"To get that paper back, switch
  “Show row indicators” off, use a smaller label size, or **reduce “Clip”**."*
* the black note four inches away said *"“Clip” starts moving them again once
  you set it above 26.0 mm."*

Both cannot be right. `floor = max(Clip, the clip border's width, the
instrument's own left furniture)`, so below the floor's other terms Clip is
inert — which `docs/design/row_label_geometry.md` §R2 states as a consequence of
R1.3 in as many words: *"Below the width of a clip border, Clip has no visible
effect."* The advice is only valid when Clip is the term that won the `max()`.

The same panel also gained the framed, collapsible box Basti asked for
(*"Maybe put a frame around it like other sections and make it a collapsible
info section"*). §R2 puts one condition on it: the automatic left-margin raise
must be REPORTED, and §R5 correction 3 exists because an earlier version of that
document claimed a panel said so while nothing did. So the box may collapse for
tidying away, never for arriving.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.tabs.tab_chart import TabChart                    # noqa: E402
from workflow.layout_engine import instruments            # noqa: E402
from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402


class _Btn:
    def isChecked(self):
        return True


class _Settings:
    def get(self, key, default=None):
        return True if key == "use_chromiq_layout_engine" else default


class _Tab:
    """Just enough TabChart for the real method to run — nothing calculated."""
    _manual_btn = _Btn()
    _manual_layout_panel = object()
    _settings = _Settings()

    def __init__(self, recipe):
        self._recipe = recipe

    def _current_layout_recipe(self):
        return self._recipe


def _recipe(*, margin_l=4.0, clip=4.0, border=False, border_w=26.0,
            instrument="CM"):
    r = LayoutRecipe()
    r.instrument, r.paper, r.layout_mode = instrument, "A4", "area_first"
    r.show_strip_indicators, r.show_row_indicators = True, True
    r.clip_border = border
    if border:
        r.clip_border_width_mm = border_w
        r.clip_side = "left"
        r.clip_content_mode = "notes"
    r.text_edge_clip_mm = clip
    r.margin_top = r.margin_right = r.margin_bottom = 10.0
    r.margin_left = margin_l
    return r


def _raise_warning(r) -> str:
    lines = [w for w in TabChart._engine_text_overflow_warnings(_Tab(r))
             if "left margin was widened" in w]
    assert lines, "the premise failed: this chart's margin was not raised"
    return lines[0]


def _geom(r):
    return instruments.geom_from_build_kwargs(r.build_kwargs())


# ------------------------------------------------------------------ the fix
def test_the_advice_does_not_name_clip_when_clip_cannot_move_anything():
    """Knut's own state: a 26 mm clip border with Clip at 4 mm."""
    r = _recipe(border=True)
    g = _geom(r)
    assert g.row_label_floor > g.text_edge_clip_mm + 0.05, (
        f"the premise failed: the floor is {g.row_label_floor:.2f} mm and Clip "
        f"is {g.text_edge_clip_mm:.2f} mm, so Clip IS the anchor here")
    msg = _raise_warning(r)
    assert "reduce “Clip”" not in msg, (
        "the inspector still tells the user to reduce a setting that cannot "
        f"move the labels:\n  {msg}")


def test_it_says_plainly_that_clip_is_not_the_lever():
    """Silence about it would leave the black note's *"Clip starts moving them
    again once you set it above 26.0 mm"* unexplained beside a warning that
    never mentions Clip at all."""
    msg = _raise_warning(_recipe(border=True))
    assert "“Clip” is set to 4.0 mm" in msg, msg
    assert "lowering it moves nothing" in msg, msg


def test_the_advice_still_names_clip_when_clip_is_what_holds_them():
    """The other half. A message that never mentions Clip would lose the one
    case in which Clip really is the lever — §R2: *"Above the border's width,
    Clip moves the labels one for one."*"""
    r = _recipe(border=True, clip=30.0)
    g = _geom(r)
    assert g.text_edge_clip_mm >= g.row_label_floor - 0.05, (
        "the premise failed: Clip did not win the max() at 30 mm")
    msg = _raise_warning(r)
    assert "reduce “Clip”" in msg, msg


def test_both_forms_still_carry_the_two_numbers_the_raise_is_made_of():
    """§R2 requires the report to name the margin asked for and the margin
    used. Neither form may lose them."""
    for r in (_recipe(border=True), _recipe(border=True, clip=30.0)):
        got = _geom(r).margin_l
        msg = _raise_warning(r)
        assert f"{r.margin_left:.1f} mm" in msg and f"{got:.1f} mm" in msg, msg


def test_the_advice_that_is_left_is_advice_that_works():
    """BOTH remaining suggestions really do give the paper back.

    Dropping the Clip clause is only honest if the two that are left are true,
    so both are exercised against the real geometry rather than asserted.
    """
    before = _geom(_recipe(border=True)).margin_l

    off = _recipe(border=True)
    off.show_row_indicators = False
    assert _geom(off).margin_l < before, \
        "switching the row indicators off did not give any paper back"

    small = _recipe(border=True)
    small.indicator_size_mm = 1.5          # well under the auto size
    got = _geom(small).margin_l
    assert got < before, (
        f"a smaller label size did not give any paper back: {got:.2f} mm "
        f"against {before:.2f} mm")


# ------------------------------------------------- where the notice lives ---
# It was a line inside `self._status` until 2026-09-03, a framed collapsible
# box (B8-38) for one day, and since 2026-09-04 it is the live note on the
# panel's own ⓘ. Basti ruled the box out with everything like it — *"the info
# text in create chart tab that is directly inside the sections (even that that
# you made collapsible) - i want that gone"* — and, asked what then discloses
# the §R1.5 raise, *"a tooltip will be enough"*.
def test_a_live_notice_reaches_the_panels_own_icon(qapp):
    """§R2, and §R5 correction 3: the raise must be disclosed SOMEWHERE, and a
    check that only proves a widget exists is what correction 3 was written
    about. So this asks for the words."""
    from ui.margin_inspector_panel import MarginInspectorPanel
    from workflow.margin_inspector import MarginReport
    panel = MarginInspectorPanel()
    try:
        report = MarginReport(left_mm=34, right_mm=10, top_mm=10, bottom_mm=10,
                              strip_width_mm=8.0, strip_length_mm=200.0,
                              page_w_mm=210.0, page_h_mm=297.0)
        panel.update_report(report, [], thresholds_defined=True, notify=True,
                            text_warnings=["⚠ The left margin was widened."])
        assert "The left margin was widened" in panel.text_notes()
        assert "The left margin was widened" in panel._panel_tip.dialog_body()
        # …and a reader who never clicks still meets it on hover.
        assert "The left margin was widened" in panel._panel_tip.toolTip()
        # The standing help is still under it, not replaced by it.
        assert "easy to measure" in panel._panel_tip.dialog_body()
        # …and a second identical report does not stack it up twice.
        panel.update_report(report, [], thresholds_defined=True, notify=True,
                            text_warnings=["⚠ The left margin was widened."])
        assert panel._panel_tip.dialog_body().count(
            "The left margin was widened") == 1
    finally:
        panel.deleteLater()


def test_the_icon_carries_nothing_when_there_is_nothing_to_report(qapp):
    from ui.margin_inspector_panel import MarginInspectorPanel
    from workflow.margin_inspector import MarginReport
    panel = MarginInspectorPanel()
    try:
        report = MarginReport(left_mm=34, right_mm=10, top_mm=10, bottom_mm=10,
                              strip_width_mm=8.0, strip_length_mm=200.0,
                              page_w_mm=210.0, page_h_mm=297.0)
        panel.update_report(report, [], thresholds_defined=True, notify=True,
                            text_warnings=[])
        assert panel.text_notes() == ""
        assert "widened" not in panel._panel_tip.toolTip()
        assert panel._status.text() == "Margins: OK"
    finally:
        panel.deleteLater()


def test_a_text_notice_never_appears_under_a_green_verdict(qapp):
    """The single joined label suppressed the green "Margins: OK" whenever a
    text warning was live. Splitting the label must not quietly restore it."""
    from ui.margin_inspector_panel import MarginInspectorPanel
    from workflow.margin_inspector import MarginReport
    panel = MarginInspectorPanel()
    try:
        report = MarginReport(left_mm=34, right_mm=10, top_mm=10, bottom_mm=10,
                              strip_width_mm=8.0, strip_length_mm=200.0,
                              page_w_mm=210.0, page_h_mm=297.0)
        panel.update_report(report, [], thresholds_defined=True, notify=True,
                            text_warnings=["⚠ The left margin was widened."])
        assert "OK" not in panel._status.text()
        assert not panel._status.isVisibleTo(panel)
    finally:
        panel.deleteLater()
