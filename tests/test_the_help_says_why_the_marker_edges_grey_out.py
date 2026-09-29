"""A ticked box that prints nothing has to say why, in the HELP and not only
in a tooltip on the control that went grey.

The design authority, 2026-09-16, having loaded the CR30 hexagonal presets:

    "I notice that the helper markers are enabled, but the 'Show markers for'
    'top/bottom' is greyed out and not selectable, but they should have been ON
    and showing on the preview (but are not showing on the preview). ... It is
    not clear why they are unavailable and help text does not say the
    conditions where they are not available."

**WHAT HE WAS LOOKING AT**, and it is worth writing down because the shape is
not obvious. A honeycomb can carry a comb of dashes on ONE axis only, and which
one depends on the way it is turned:

| chart | staggered | the live comb | the greyed one |
|---|---|---|---|
| upright honeycomb (`-Hexagonal`) | every second ROW, sideways | **Sides** | Top/bottom |
| turned honeycomb (`-Hexagonal-Straight`) | every second COLUMN | **Top/bottom** | Sides |

`_CR30_BASE` asks for `helper_markers_top_bottom` and NOT
`helper_markers_sides`. So on the eight upright charts the one axis the recipe
asked for was the one that is greyed, and the only axis that could have printed
was switched off: a ticked "Print helper markers", both sub-options dead, and a
clean sheet. The eight presets now ship with the box OFF (B8-280); this file is
about the second half of his report, which is that the app never said why.

The reason DID exist, on the tooltip of the greyed control. That is the one
place a reader in his position will not look, because a control that cannot be
clicked is a control he has already stopped asking about.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402

from ui.dialogs import layout_options_panel as lop         # noqa: E402


@pytest.fixture(scope="module")
def panel(qapp):
    p = lop.LayoutOptionsPanel()
    yield p
    p.deleteLater()


def _marker_help(panel) -> str:
    """The ⓘ text on "Print helper markers" itself, off the BUILT widget.

    Read from the live panel rather than from the source, because a test that
    greps the module is satisfied by a comment.
    """
    from ui.tooltip_button import TooltipButton
    grp = panel.helper_markers_cb.parent()
    tips = [w for w in grp.findChildren(TooltipButton)
            if "ruler helper marker" in (w._title or "").lower()]
    assert tips, "the helper-marker group has no ⓘ button of its own"
    return "\n".join((t._title or "") + "\n" + (t._body or "") for t in tips)


def test_the_help_on_the_master_box_explains_the_greying(panel):
    """His words: the conditions must be in the HELP TEXT, not only on the
    control that went grey."""
    text = _marker_help(panel).lower()
    assert "hexagonal" in text, (
        "the help never mentions hexagonal patches, so a reader on a "
        "honeycomb is told nothing about why his edges are unavailable")
    assert "grey" in text or "gray" in text, (
        "the help never says that a pair of edges is GREYED OUT, which is "
        "the thing the reader can see and cannot explain")
    # THE MECHANISM, not just the fact. "It is not available" is what the
    # greyed control already said; what was missing is why.
    assert "half a patch" in text, (
        "the help states the restriction without the half-patch stagger that "
        "causes it")
    assert "seam" in text, (
        "the help does not say what a dash would point AT instead of a patch")


def test_the_help_says_which_pair_survives_rather_than_naming_one(panel):
    """It must NOT say "the top and bottom pair is the one that goes".

    Which pair survives follows the TURN, and a help text that named one would
    be false on half the honeycombs in the app: on an upright comb the sides
    live and top/bottom greys, and on a turned one it is the other way round.
    That exact mistake was in the panel itself for nine rounds, greying the
    comb that prints and offering the one that does nothing.
    """
    text = _marker_help(panel).lower()
    assert "depends on" in text, (
        "the help does not say that WHICH pair is unavailable depends on "
        "anything, so a reader will take it as a fixed rule")
    for false_claim in ("the top and bottom dashes are not available",
                        "the side dashes are not available",
                        "sides cannot be used",
                        "top and bottom cannot be used"):
        assert false_claim not in text, (
            f"the help states {false_claim!r} as a fixed rule; which pair "
            "goes depends on the turn")


def test_the_help_warns_that_a_ticked_box_can_print_nothing(panel):
    """The state he was actually in, named in the help so the next reader
    recognises it: markers on, the live pair unticked, a blank sheet."""
    text = _marker_help(panel).lower()
    assert "nothing" in text, (
        "the help never says that this box can be ticked and still print "
        "nothing, which is the state that was reported")


def test_the_greyed_control_still_carries_its_own_reason(panel):
    """The tooltip is not REPLACED by the help. It was right, it was just in
    the one place the reader had stopped looking."""
    # Driven through the panel's own greying, not by poking setEnabled: the
    # tooltip is written by `_sync_helper_marker_availability`, so a test that
    # disables the box by hand reads whatever was there before and proves
    # nothing at all. This is the honeycomb case, which is the one that greys.
    panel.helper_markers_cb.setChecked(True)
    panel.set_helper_markers_supported(True, one_axis_only=True)
    tips = (panel.helper_markers_top_bottom.toolTip()
            + panel.helper_markers_sides.toolTip()).lower()
    assert not (panel.helper_markers_top_bottom.isEnabled()
                and panel.helper_markers_sides.isEnabled()), (
        "the premise failed: neither edge box is greyed on a honeycomb, so "
        "there is no tooltip here to check")
    assert "honeycomb" in tips or "hexagonal" in tips, (
        "neither edge checkbox explains itself any more")


def test_the_explanation_is_its_own_translatable_string(panel):
    """It must be a `tr()` key of its own, not folded into the paragraph above.

    Folding it in changes that paragraph's key and turns all thirteen shipped
    translations of it stale in one edit, which is what B8-270 records paying
    for. Separate, the tooltip keeps every translation it has and only the new
    paragraph falls back to English until each catalogue catches up.
    """
    import inspect
    src = inspect.getsource(lop)
    i = src.index("On a chart with hexagonal patches")
    # Walk back to the nearest `tr(` and check nothing but whitespace, string
    # continuation and the concatenation sits between it and this sentence.
    head = src[max(0, i - 400):i]
    assert 'tr(' in head, "the paragraph is not inside a tr() call at all"
    between = head[head.rindex('tr(') + 3:]
    assert '\\n\\n' not in between.replace('"\n', ''), (
        "the paragraph shares a tr() key with the text before it")
    assert '+ "\\n\\n" + tr(' in src[max(0, i - 400):i], (
        "the paragraph is not appended as its own tr() key")
