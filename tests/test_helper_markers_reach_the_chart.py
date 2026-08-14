"""#152, Knut's beta.3 report: *"Enabling 'Show helper markers…' checkbox does
nothing. No markers become visible in preview."*

He was right twice over, and the two halves are independent — which is why this
file exists separately from ``test_helper_markers.py``. That file proves the
dashes land in the right place; this one proves they ever get there at all.

**Half one: the recipe threw the values away.** The marker controls live in the
preview's "Measure from Preview" panel, but the dashes are printed, so the
*layout recipe* is what has to carry them to the renderer.
``LayoutOptionsPanel.get_recipe()`` builds a recipe from scratch out of its own
widgets on every call — and it has no marker widgets, so three fields set on the
recipe were silently dropped somewhere between the checkbox and Generate Chart.
Every marker test in the world passes with that bug in place, because the
geometry was never the problem.

**Half two: nothing on screen changed until the chart was rebuilt.** Even with
the recipe fixed, the sheet in the preview is a TIFF that was rendered before the
box was ticked. Knut tried switching tabs and paging the preview to force it.
The preview now draws the dashes itself, at the coordinates the renderer will
use, so the position can be judged while the spin boxes are being nudged.

Also here: the three layout complaints from the same report — misaligned ⓘ
icons, an over-wide frame, and spin boxes twice the width of their contents.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication              # noqa: E402

from workflow.layout_engine.presets import LayoutRecipe   # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# --- half one: the values survive the round trip to the renderer -------------

def _panel(app):
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    return LayoutOptionsPanel(with_selectors=True)


def test_the_panel_keeps_the_markers_it_was_given(app):
    """THE BUG. A recipe in, the same three values out."""
    p = _panel(app)
    r = LayoutRecipe(instrument="i1", paper="A4")
    r.helper_markers = True
    r.helper_marker_edge_mm = 2.5
    r.helper_marker_len_mm = 7.0
    p.set_recipe(r)

    out = p.get_recipe()
    assert out.helper_markers is True, (
        "the recipe lost the marker switch between the panel and the renderer")
    assert out.helper_marker_edge_mm == pytest.approx(2.5)
    assert out.helper_marker_len_mm == pytest.approx(7.0)


def test_markers_off_stay_off(app):
    p = _panel(app)
    r = LayoutRecipe(instrument="i1", paper="A4")
    r.helper_markers = False
    p.set_recipe(r)
    assert p.get_recipe().helper_markers is False


def test_a_panel_that_was_never_given_a_recipe_still_answers(app):
    """`get_recipe()` is called on a fresh panel in several places; it must not
    raise, and it must default to no markers."""
    assert _panel(app).get_recipe().helper_markers is False


def test_the_values_reach_the_renderer_arguments(app):
    """The last link in the chain: ``build_kwargs`` is what ``build_chart``
    is actually called with."""
    p = _panel(app)
    r = LayoutRecipe(instrument="i1", paper="A4")
    r.helper_markers = True
    r.helper_marker_edge_mm = 1.5
    r.helper_marker_len_mm = 4.0
    p.set_recipe(r)

    kw = p.get_recipe().build_kwargs()
    assert kw["helper_markers"] is True
    assert kw["helper_marker_edge"] == pytest.approx(1.5)
    assert kw["helper_marker_len"] == pytest.approx(4.0)


def test_build_chart_accepts_exactly_those_names():
    """A rename on either side of that dictionary would silence the feature
    again without failing anything else."""
    import inspect
    from workflow.layout_engine.chart import build_chart
    params = inspect.signature(build_chart).parameters
    for name in ("helper_markers", "helper_marker_edge", "helper_marker_len"):
        assert name in params, name


# --- half two: the preview shows them straight away --------------------------

def test_the_preview_can_be_given_markers(app):
    from ui.tiff_preview import TiffPreview
    prev = TiffPreview()
    prev.set_helper_markers([(0.1, 0.2, 0.3, 0.2)])
    assert prev._helper_markers == [(0.1, 0.2, 0.3, 0.2)]
    prev.set_helper_markers(None)
    assert prev._helper_markers == []


def test_the_preview_paints_them(app):
    """Not "the list is stored" — that the painter is asked to draw it. A
    stored-but-never-drawn overlay is exactly the fault being fixed."""
    import inspect
    from ui.tiff_preview import TiffPreview
    src = inspect.getsource(TiffPreview)
    assert "_draw_helper_markers" in src
    # and it is reached from the paint path, not only defined
    assert src.count("_draw_helper_markers") >= 2


def test_ticking_the_box_refreshes_the_overlay():
    """The handler must do more than remember the choice, or the user is back to
    switching tabs and hoping."""
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._on_helper_markers_changed)
    assert "_refresh_helper_marker_overlay" in src


def test_the_overlay_follows_the_chart_and_the_page():
    """Paging through a multi-page chart, or loading a different one, has to
    re-place the dashes — they belong to the sheet on screen."""
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart._update_margin_inspector)
    assert "_refresh_helper_marker_overlay" in src


# --- the three layout complaints ---------------------------------------------

@pytest.fixture
def panel(app):
    from ui.margin_inspector_panel import MarginInspectorPanel
    p = MarginInspectorPanel()
    p.resize(p.sizeHint())
    p.show()
    app.processEvents()
    yield p
    p.close()


def test_the_info_icons_line_up(panel):
    """*"The info icons on the right side … are not aligned to each other."*
    They were 28 px apart; they now share one grid column."""
    from ui.tooltip_button import TooltipButton
    rights = {t.mapTo(panel, t.rect().topLeft()).x() + t.width()
              for t in panel.findChildren(TooltipButton)}
    assert len(rights) == 1, f"the ⓘ icons end at different x positions: {rights}"


def test_the_frame_is_no_wider_than_its_widest_row(panel):
    """*"the frame is too wide (it is enough that the right edge of the frame
    includes the last row with 'Show helper markers…', which is the widest)."*

    So the panel's width is the helper row plus the ⓘ column and the frame's own
    margins — nothing beyond it. Asserted with a small allowance for the frame
    border rather than an exact number, which would break on any theme change.
    """
    from ui.tooltip_button import TooltipButton
    tips = panel.findChildren(TooltipButton)
    right_edge = max(t.mapTo(panel, t.rect().topLeft()).x() + t.width()
                     for t in tips)
    slack = panel.sizeHint().width() - right_edge
    assert 0 < slack <= 24, (
        f"{slack} px of unused width to the right of the last control")


def test_the_spin_boxes_are_not_twice_the_width_they_need(panel):
    """*"The two spinboxes … are double as wide as needed."* Qt's default hint
    was 142 px for content measuring 54 px."""
    for box in (panel._helper_edge, panel._helper_len):
        # A cap was actually applied (the default is Qt's 16777215).
        assert box.maximumWidth() < 16_777_215, "no width cap on the spin box"
        # And it is close to what the content needs, not double it. Measured
        # against the text rather than against sizeHint(), because sizeHint
        # depends on the theme's QSS padding and this test runs unstyled.
        widest = f"{box.maximum():.{box.decimals()}f}{box.suffix()}"
        needed = box.fontMetrics().horizontalAdvance(widest)
        assert box.width() <= needed + 60, (
            f"{box.width()} px for {needed} px of text is still too generous")


def test_the_spin_boxes_still_show_their_largest_value(panel):
    """The counterweight to the test above, and the reason the reduction stops
    where it does: the first attempt at 55 % clipped " mm" off the end and
    displayed "1,0 m". Narrower is only better while the value is still legible.
    """
    for box in (panel._helper_edge, panel._helper_len):
        widest = f"{box.maximum():.{box.decimals()}f}{box.suffix()}"
        needed = box.fontMetrics().horizontalAdvance(widest)
        assert box.width() >= needed, (
            f"{box.width()} px cannot show {widest!r} ({needed} px of text)")


# --- the hexagonal case really does grey out (Knut, beta.5) -----------------
#
# *"When instrument is SpectroScan and Patch shape is Hexagonal, the checkbox for
# 'Show helper markers' with its spinboxes and belonging labels are not greyed
# with explanation tool-tip, as specified."*
#
# Two faults behind that. The check asked `chart_instrument` in Preferences,
# which describes the last chart BUILT — so picking SpectroScan + Hexagonal in
# the Create Chart selectors left it reading "i1". And nothing re-ran the check
# when those selectors changed: it hung off the margin inspector's refresh,
# which fires on a chart or page change, long after the user has made the
# selection and wants to know why the option does nothing.

def test_the_controls_and_their_labels_all_grey_together(panel):
    panel.set_helper_markers_supported(False)
    dead = [panel._helper_check, panel._helper_edge, panel._helper_len,
            panel._helper_edge_lbl, panel._helper_len_lbl]
    assert not any(w.isEnabled() for w in dead), (
        "a live label beside a dead spin box reads as a glitch, not as "
        "'this option does not apply here'")
    assert all(w.toolTip() for w in dead), "greyed with no reason given"


def test_they_come_back(panel):
    panel.set_helper_markers_supported(False)
    panel.set_helper_markers_supported(True)
    for w in (panel._helper_check, panel._helper_edge, panel._helper_len,
              panel._helper_edge_lbl, panel._helper_len_lbl):
        assert w.isEnabled()
        assert not w.toolTip()


def test_the_reason_reaches_the_help_icon_too(panel):
    """Knut asked for it in both places a user might look — the hover tooltip
    and the ⓘ."""
    panel.set_helper_markers_supported(False)
    body = panel._helper_tip._body if hasattr(panel._helper_tip, "_body") else ""
    assert "six-sided" in body or "honeycomb" in body, body[:200]


def test_the_hex_check_reads_the_live_selectors_not_a_stored_setting():
    """The specific fault: `chart_instrument` describes the chart last BUILT.

    Judged on the parsed code with the docstring removed, because that docstring
    names the old setting in order to explain the fault.
    """
    import ast
    import inspect
    import textwrap
    from ui.tabs.tab_chart import TabChart

    fn = ast.parse(textwrap.dedent(
        inspect.getsource(TabChart._chart_is_hexagonal))).body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body.pop(0)                      # drop the docstring
    code = ast.dump(ast.Module(body=[fn], type_ignores=[]))
    assert "chart_instrument" not in code, (
        "back to asking a stored setting about a live selection")
    assert "currentData" in code


def test_choosing_hexagonal_greys_it_without_generating_a_chart():
    """It must react to the selectors, not wait for a chart/page change."""
    import inspect
    from ui.tabs.tab_chart import TabChart
    src = inspect.getsource(TabChart)
    assert "changed.connect(self._refresh_helper_marker_support)" in src
