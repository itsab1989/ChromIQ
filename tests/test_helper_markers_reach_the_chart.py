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
    src = inspect.getsource(TabChart._remember_helper_markers)
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
def layout_panel(app):
    """The Manual layout panel, which owns the ruler-marker controls since #158."""
    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    p = LayoutOptionsPanel(None, with_selectors=True, with_calibration=True)
    p.resize(p.sizeHint())
    p.show()
    app.processEvents()
    yield p
    p.close()


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
    They were 28 px apart; they now share one grid column.

    Only the icons the user can SEE. This panel starts on its placeholder — "
    Generate a preview to measure its margins" — with the numbers table hidden,
    and the table's own ⓘ hidden with it, unplaced. Measuring an unplaced widget
    reports the layout's origin, not a misalignment, and Knut's complaint was
    about icons visibly out of line with each other.
    ``tests/test_margin_inspector_help_icons.py`` makes the same check with the
    table shown, which is the state that has four of them.
    """
    from ui.tooltip_button import TooltipButton
    rights = {t.mapTo(panel, t.rect().topLeft()).x() + t.width()
              for t in panel.findChildren(TooltipButton)
              if t.isVisibleTo(panel)}
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


def test_the_spin_boxes_are_not_twice_the_width_they_need(layout_panel):
    """*"The two spinboxes … are double as wide as needed."* Qt's default hint
    was 142 px for content measuring 54 px."""
    for box in (layout_panel.helper_marker_edge,
                layout_panel.helper_marker_len):
        # A cap was actually applied (the default is Qt's 16777215).
        assert box.maximumWidth() < 16_777_215, "no width cap on the spin box"
        # And it is close to what the content needs, not double it. Measured
        # against the text rather than against sizeHint(), because sizeHint
        # depends on the theme's QSS padding and this test runs unstyled.
        widest = f"{box.maximum():.{box.decimals()}f}{box.suffix()}"
        needed = box.fontMetrics().horizontalAdvance(widest)
        # In the layout panel the house style governs: these must be no wider
        # than the millimetre boxes already sitting beside them, which is what
        # keeps the group from being the widest thing in Expert Options (it was
        # 535 px against 472 for the next one until this was fixed).
        siblings = [b.maximumWidth() for b in layout_panel.findChildren(type(box))
                    if b is not box and b.maximumWidth() < 16_777_215]
        assert box.maximumWidth() <= max(siblings), (
            f"{box.maximumWidth()} px is wider than every other box in the "
            f"panel ({max(siblings)} px)")


def test_the_spin_boxes_still_show_their_largest_value(layout_panel):
    """The counterweight to the test above, and the reason the reduction stops
    where it does: the first attempt at 55 % clipped " mm" off the end and
    displayed "1,0 m". Narrower is only better while the value is still legible.
    """
    for box in (layout_panel.helper_marker_edge,
                layout_panel.helper_marker_len):
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

def test_the_controls_and_their_labels_all_grey_together(layout_panel):
    """Greying the whole group takes its labels with it, which is what Knut
    asked for — a live label beside a dead spin box reads as a glitch."""
    layout_panel.set_helper_markers_supported(False)
    grp = layout_panel._helper_markers_grp
    assert not grp.isEnabled()
    dead = (grp, layout_panel.helper_markers_cb, layout_panel.helper_marker_edge,
            layout_panel.helper_marker_len, layout_panel.helper_marker_per_patch)
    assert not any(w.isEnabled() for w in dead)
    assert all(w.toolTip() for w in dead), "greyed with no reason given"


def test_they_come_back(layout_panel):
    """…and the distances then obey the tick box again, rather than all coming
    back live: with the markers off they stay greyed, which is the rule added
    on 2026-08-20."""
    layout_panel.helper_markers_cb.setChecked(True)
    layout_panel.set_helper_markers_supported(False)
    layout_panel.set_helper_markers_supported(True)
    for w in (layout_panel._helper_markers_grp, layout_panel.helper_markers_cb,
              layout_panel.helper_marker_edge, layout_panel.helper_marker_len,
              layout_panel.helper_marker_per_patch):
        assert w.isEnabled()
        assert not w.toolTip()

    layout_panel.helper_markers_cb.setChecked(False)
    assert layout_panel.helper_markers_cb.isEnabled()
    assert not layout_panel.helper_marker_edge.isEnabled()


def test_the_reason_reaches_the_help_icon_too(layout_panel):
    """Knut asked for it in both places a user might look — the hover tooltip
    and the ⓘ. The reason now rides on every control in the group."""
    layout_panel.set_helper_markers_supported(False)
    tip = layout_panel.helper_markers_cb.toolTip()
    assert "hexagon" in tip.lower() or "ruler" in tip.lower(), tip[:200]


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


# --- the preview must not promise dashes the file does not have -------------

def test_the_help_says_generate_chart_is_still_needed(layout_panel):
    """From Knut's beta.5 log (#152): he ticked the markers on at 22:11:46, after
    his last Generate Chart at 22:11:27, and nothing re-rendered — auto-update
    was off, which is the default.

    So the preview showed dashes while the chart file on disk had none. The
    checkbox says "(visible on print)" and the preview agrees with it, which is
    exactly the reading that ends with a printed sheet that has no dashes on it.
    The overlay is still the right behaviour — judging the distances without a
    rebuild is the whole point — but the help has to say plainly where the line
    between preview and file falls.
    """
    from ui.tooltip_button import TooltipButton
    tips = layout_panel._helper_markers_grp.findChildren(TooltipButton)
    body = "\n".join(getattr(t, "_body", "") for t in tips)
    assert "Generate Chart" in body, "the help never mentions the missing step"
    assert "print" in body.lower()
    assert "Auto-update preview" in body, (
        "users with auto-update on must be told they need do nothing extra")
    assert "Markers per patch" not in body or "3" in body


def test_every_row_has_its_own_help_icon(layout_panel):
    """Knut, beta.8 (#152): the ⓘ has to sit on the line it explains, not float
    against a block of them. Each row of the group carries its own."""
    from ui.tooltip_button import TooltipButton
    grp = layout_panel._helper_markers_grp
    tips = grp.findChildren(TooltipButton)
    # One per labelled row, plus the group's own on the tick box. Derived rather
    # than hard-coded so adding a row (#164 added "Show markers for") keeps the
    # RULE — an ⓘ on every line — instead of just moving a number.
    expected = len(layout_panel._hm_rows) + 1
    assert len(tips) == expected, f"expected one ⓘ per row, got {len(tips)}"
    rights = {t.mapTo(grp, t.rect().topLeft()).x() + t.width() for t in tips}
    assert len(rights) == 1, f"the ⓘ icons end at different x positions: {rights}"


# --- the distances follow the tick box (Basti, 2026-08-20) ------------------

def test_the_distances_grey_out_when_the_markers_are_off(layout_panel):
    """The three distances mean nothing while the markers are switched off, so
    they grey with the tick box — labels included."""
    from PyQt6.QtWidgets import QLabel
    from ui.tooltip_button import TooltipButton
    layout_panel.helper_markers_cb.setChecked(False)
    rows = layout_panel._hm_rows
    assert len(rows) >= 3, "the distances and the edge choice all live here"
    for row in rows:
        for w in row:
            if isinstance(w, TooltipButton):
                assert w.isEnabled(), "the ⓘ must stay readable on a greyed row"
            else:
                assert not w.isEnabled(), f"{w} stayed live with the markers off"

    layout_panel.helper_markers_cb.setChecked(True)
    for row in rows:
        for w in row:
            assert w.isEnabled()


def test_the_greyed_labels_actually_look_greyed(layout_panel):
    """Disabling a plain QLabel changes nothing on screen in this theme — its
    Disabled palette entry is the same colour as the normal one. The labels
    therefore carry the app's dimmed-caption object name, which both themes
    style for :disabled (ui/styles.py, ui/light_styles.py)."""
    from PyQt6.QtWidgets import QLabel
    labels = [w for row in layout_panel._hm_rows for w in row
              if isinstance(w, QLabel)]
    assert len(labels) == len(layout_panel._hm_rows)
    assert {l.objectName() for l in labels} == {"param_label"}


def test_a_loaded_preset_leaves_the_rows_in_the_right_state(layout_panel):
    """Loading a chart that uses markers must leave the distances usable, and
    one that does not must leave them greyed — the state has to follow the
    recipe, not whatever was on screen before."""
    from workflow.layout_engine.presets import LayoutRecipe
    layout_panel.helper_markers_cb.setChecked(False)
    layout_panel.set_recipe(LayoutRecipe.from_dict(
        {"helper_markers": True, "helper_marker_edge_mm": 4.0}))
    assert layout_panel.helper_marker_edge.isEnabled()
    layout_panel.set_recipe(LayoutRecipe.from_dict({"helper_markers": False}))
    assert not layout_panel.helper_marker_edge.isEnabled()


def test_the_greyed_labels_read_as_greyed_in_BOTH_themes():
    """Basti asked whether the greying looks right in light mode as well as
    dark. It relies on ``#param_label:disabled``, so both stylesheets must carry
    the rule AND dim it enough to read as disabled without vanishing.

    Measured against each theme's panel background: dark #c8c8c8 → #6a6a6a
    (contrast 169 → 75) and light #22211f → #a8a4a0 (222 → 90). Near-identical
    ratios, which is why the two themes look consistent.
    """
    import re
    from pathlib import Path
    import ui.light_styles as L

    def lum(h):
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    dark = Path("ui/styles.py").read_text(encoding="utf-8")
    normal = re.search(r"QLabel#param_label,[^\n]*color: (#\w+)", dark)
    faint = re.search(r"QLabel#param_label:disabled,[^\n]*color: (#\w+)", dark)
    assert normal and faint, "the dark theme lost its #param_label rules"
    d_on = abs(lum(normal.group(1)) - lum("#1f1f1f"))
    d_off = abs(lum(faint.group(1)) - lum("#1f1f1f"))

    light = Path("ui/light_styles.py").read_text(encoding="utf-8")
    assert "QLabel#param_label:disabled" in light, (
        "light mode has no dimmed-caption rule, so the labels would disable "
        "without looking disabled")
    l_on = abs(lum("#ffffff") - lum(L.LM_TEXT_MAIN))
    l_off = abs(lum("#ffffff") - lum(L.LM_TEXT_FAINT))

    for name, on, off in (("dark", d_on, d_off), ("light", l_on, l_off)):
        assert off < on * 0.75, f"{name}: greyed text is not visibly dimmer"
        assert off > 25, f"{name}: greyed text has all but vanished ({off:.0f})"
