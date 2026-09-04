"""B8-14 / B8-21 §4 — "Strip && row labels" must say which control reaches
which label, and it says it by its SHAPE.

Knut, beta.7:

> *"the Underline, beginning line thickness and line distance, as well as
> rotation and Label offset, they all only relate to Strip labels. Only Font
> and size (and the 'Text distance from edge' parameters) actually are used for
> both strip and row labels. This is not really clear. The help text only
> refers to strip labels."*

He is right, and it was measured from the printed INK rather than from the code
(`beta 8/04-chart-layout-ui`): one real Generate per control at a fixed seed,
each variant's TIFF differenced against a baseline, the changed pixels counted
separately in the row-label band and the strip-label band.

| control | strip px | row px |
|---|---|---|
| Font | 15 785 | **97 987** (and the page is re-laid) |
| Size | 13 397 | **126 162** (and the page is re-laid) |
| Bold | 5 640 | **11 086** |
| Underline / thickness / distance / rotation / Label offset | 11 790 … 68 914 | **0** |

So **Bold** belongs on Knut's "both" list too, and exactly one piece of help
text was factually untrue: the Font row's tooltip said *"Typeface, size and
style of the strip letter labels"* while three of its controls demonstrably
re-draw the row labels and move the left margin. That tooltip is fixed, and the
first three tests here hold it fixed.

WHAT CHANGED ON 2026-09-04, AND WHY THIS FILE NO LONGER LOOKS FOR A SENTENCE.
B8-14 first answered the rest of it with a paragraph: forty words of grey prose
above the controls, naming each control's reach. Basti, ruling on B8-21 §4:

> *"keep the first note, drop the second, and rule on sub-frames… the paragraph
> is the option I'd argue against — it's correct, and correct is not the same
> as clear."*

So the paragraph is retired and the frame is split in two, along exactly the
line the ink drew: **"Strip letters and row numbers"** holds Font, Size and
Bold; **"Strip letters only"** holds Underline, line thickness, line distance,
rotation and Label offset. The answer is now structural, read once by looking,
and it costs no reading at all.

These tests therefore assert MEMBERSHIP, live, off the built widgets — which
control is inside which box — rather than the words of a sentence. A test that
reads the source can be satisfied by a comment; a test that walks the parent
chain of the real ``self.indicator_size`` cannot.

Italic is deliberately in neither claim: it is greyed out because neither
bundled font has an italic face (Agent B's F-4, correct behaviour), it moved 0
pixels of either kind, and a sub-frame title that claimed it would be the next
untrue thing in this frame.
"""
from __future__ import annotations

import inspect
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.dialogs import layout_options_panel as lop        # noqa: E402

#: Measured from the ink: these three redraw BOTH sets of labels.
_BOTH = ("indicator_font", "indicator_size", "ind_bold")

#: Measured from the ink: these five moved 0 row-label pixels, every time.
_STRIP_ONLY = ("underline_mode", "underline_thickness", "underline_gap",
               "indicator_rotation", "strip_label_offset")


def _panel_source() -> str:
    return inspect.getsource(lop)


def _owning_group(widget):
    """The nearest QGroupBox above *widget*, walking the real parent chain."""
    from PyQt6.QtWidgets import QGroupBox
    box = widget.parent()
    while box is not None and not isinstance(box, QGroupBox):
        box = box.parent()
    return box


# ---- the tooltip that was untrue ------------------------------------------
def test_the_font_tooltip_no_longer_says_strip_only():
    """The one tooltip that was untrue. Its old sentence must be gone, not
    merely joined by a new one — a help text that contains both claims is still
    a help text that contains the wrong one."""
    src = _panel_source()
    assert "Typeface, size and style of the strip letter " not in src, (
        "the Font tooltip still describes itself as reaching the strip labels "
        "only, while Font, Size and Bold all move 11 000 to 126 000 pixels of "
        "row-label ink")


def test_the_font_tooltip_names_both_sets_of_labels():
    src = _panel_source()
    i = src.index("Indicator font")
    block = src[i:i + 1600]
    assert "row numbers down the left" in block, block[:400]
    assert "strip letters across" in block, block[:400]


def test_the_font_tooltip_says_bold_reaches_both():
    """Knut's own list omits Bold. The ink does not: 11 086 row-label pixels."""
    src = _panel_source()
    i = src.index("Indicator font")
    assert "Bold applies to both" in src[i:i + 1600]


# ---- the structure that replaced the paragraph ---------------------------
def test_the_frame_groups_the_controls_by_what_they_reach(qapp):
    """Every control sits in the sub-frame the INK says it belongs to.

    Asked of the live widgets, not of the source: the parent chain is what a
    user's eye follows, and it is the only thing that cannot be satisfied by a
    comment.
    """
    panel = lop.LayoutOptionsPanel()
    try:
        for attr in _BOTH:
            box = _owning_group(getattr(panel, attr))
            assert box is panel._label_sub_both, (
                f"{attr} reaches both sets of labels (measured: 11 086 to "
                f"126 162 row-label pixels) but sits under "
                f"{box.title() if box else None!r}")
        for attr in _STRIP_ONLY:
            box = _owning_group(getattr(panel, attr))
            assert box is panel._label_sub_strip_only, (
                f"{attr} moved 0 row-label pixels in the measurement but sits "
                f"under {box.title() if box else None!r}")
    finally:
        panel.deleteLater()


def test_both_sub_frames_are_inside_the_strip_and_row_labels_frame(qapp):
    """A sub-frame that has floated out of its parent answers nothing."""
    panel = lop.LayoutOptionsPanel()
    try:
        for sub in (panel._label_sub_both, panel._label_sub_strip_only):
            assert _owning_group(sub) is panel._label_style_grp, (
                f"{sub.title()!r} is not inside the strip-and-row-labels frame")
        assert "row labels" in panel._label_style_grp.title()
    finally:
        panel.deleteLater()


def test_the_titles_say_the_reach_in_the_readers_words(qapp):
    """The titles ARE the explanation, so they have to carry it.

    One names both sets of labels; the other says "only". Without that word the
    split is decoration and the reader is back to guessing.
    """
    panel = lop.LayoutOptionsPanel()
    try:
        both = panel._label_sub_both.title()
        only = panel._label_sub_strip_only.title()
        assert "Strip letters" in both and "row numbers" in both, both
        assert "Strip letters" in only and "only" in only, only
        assert both != only
    finally:
        panel.deleteLater()


def test_the_style_note_moved_to_the_tooltips_and_the_reach_paragraph_stayed_gone(qapp):
    """The two notes were not interchangeable, and neither was simply deleted.

    ``_label_style_note`` says where the setting LIVES — which cannot be
    deduced by looking at any arrangement of controls, and which was added
    (e440c133, 2026-09-01) because label style used to be app-wide: a size set
    for one instrument followed the user to the next chart, and on a real A4
    scanner chart the row-number band went 3.95 mm to 6.08 mm and the sheet
    lost 49 patches, a whole strip. It is still said — on the ⓘ of every
    control in the frame, since 2026-09-04 (Basti: *"You can fit it inside of a
    tooltip where it fits but not directly inside a section"*). This test used
    to be called ``test_the_style_note_stayed_and_the_reach_paragraph_went``.

    ``_label_reach_note`` said what the sub-frames now say. Bringing it back
    would put the same answer on screen twice, in the panel whose length is the
    complaint.
    """
    from ui.tooltip_button import TooltipButton
    panel = lop.LayoutOptionsPanel()
    try:
        assert not hasattr(panel, "_label_style_note"), (
            "the note is printed inside the frame again — Basti asked for no "
            "prose inside a Create Chart section")
        tips = panel._label_style_grp.findChildren(TooltipButton)
        assert tips, "the frame has no ⓘ left to carry the note"
        for tip in tips:
            assert "Saved with this chart" in tip.dialog_body(), (
                f"the ⓘ {tip._title!r} does not say where the setting lives")
        assert not hasattr(panel, "_label_reach_note"), (
            "the reach paragraph is back alongside the sub-frames — the same "
            "answer twice, in the panel already called too long")
    finally:
        panel.deleteLater()


def test_no_sub_frame_title_claims_italic_does_anything(qapp):
    """Italic changed 0 pixels of either kind, because neither bundled font has
    an italic face — correct behaviour (Agent B's F-4). A title that swept it
    into either group would be the next untrue sentence in this frame."""
    panel = lop.LayoutOptionsPanel()
    try:
        for sub in (panel._label_sub_both, panel._label_sub_strip_only):
            assert "talic" not in sub.title(), sub.title()
        # And it is still greyed for the bundled fonts, which is the reason.
        assert not panel.ind_italic.isEnabled()
    finally:
        panel.deleteLater()
