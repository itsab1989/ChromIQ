"""Every remedy the "Measured from Preview" frame offers has to move the ink.

**BETA 18 SHIPPED SIX THAT DID NOT**, and this is the fault class the project's
design authority has ruled against more than once: a message that names a
control which changes nothing teaches the reader to stop reading messages.
Measured by driving the real app, sheet by sheet
(`~/Desktop/ChromIQ-beta18-proof/knut-sweep-clipborder/` section 6 and
`knut-sweep-geometry/` section 2.5):

| remedy | measured |
|---|---|
| *"set a narrower Clip border width"* | inert in the branch that prints it: the band displaces the patches, so the measured margin follows the band down, and the box stops at 10 mm |
| *"put the clip border on the LEFT"* | removed the named message and immediately printed a different red one, with the ink still on the patches |
| *"set a smaller Size under Sheet text"* | 8, 7, 6 and 5 pt all produced the identical *"needs 4.2 mm ... 0.5 mm short"* |
| *"Lowering “B” ... buys the same room"* | false in "Prioritise patch size": a 10 mm drop moved the block 10.2 mm and the overlap by 0.22 mm |

So each clause is offered where it works and withheld, with the reason, where
it does not. This file is one test per clause, plus a sweep that refuses the
side-swap anywhere in the module.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6")

from ui.tabs import tab_chart as tc                             # noqa: E402
from workflow.layout_engine import raster                       # noqa: E402


# ---------------------------------------------------- the clip border width
def test_the_width_lever_is_offered_where_the_typed_margin_survives_it():
    """Band 24, typed margin 20: narrowing to 10 really did clear it."""
    note = tc._clip_width_lever_note(20.0, "right")
    assert "also makes room" in note, note
    assert f"{tc.CLIP_WIDTH_MIN_MM:.0f} mm" in note, note


@pytest.mark.parametrize("side", ("right", "left"))
def test_the_width_lever_is_withheld_where_it_cannot_work(side):
    """Typed margin 6 mm against a box that stops at 10 mm.

    Two of the three states that printed the message on beta 18 were in this
    branch, and in it the lever cannot work at any setting.

    MUTATION: return the positive clause unconditionally and this goes red.
    """
    note = tc._clip_width_lever_note(6.0, side)
    assert "will not help here" in note, note
    assert "10 mm" in note, note
    assert "also makes room" not in note, note


def test_no_message_in_the_panel_offers_the_other_side_of_the_sheet():
    """"Put the clip border on the LEFT" replaced one red line with another.

    Asserted over the module's source rather than over one message, because the
    sentence had been written into a second message once already.

    MUTATION: put the clause back into either clip message and this goes red.
    """
    import inspect
    src = inspect.getsource(tc)
    body = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    for phrase in ("put the clip border on the LEFT",
                   "put the clip border on the RIGHT"):
        assert phrase not in body, (
            f"the panel still offers {phrase!r}, which a driven sheet showed "
            "removes one red line and prints another with the ink still on "
            "the patches")


# --------------------------------------------------------- the Sheet text Size
def test_the_size_lever_is_offered_while_the_type_is_above_the_floor():
    """At 28 pt a smaller Size really does shrink the prediction."""
    big = raster.sheet_text_line_mm(28.0 * 25.4 / 72.0, "Inter", False, False,
                                    300)
    note = tc._size_lever_note(big, 300)
    assert "also makes room" in note, note


def test_the_size_lever_is_withheld_below_the_prediction_floor():
    """`sheet_text_line_mm` floors at the 4.2 mm pitch this dpi can express, so
    below about 8.5 pt a smaller Size changes the prediction by nothing.

    MUTATION: offer the clause unconditionally and this goes red.
    """
    floor = raster.sheet_text_reserve_mm(300)
    note = tc._size_lever_note(floor, 300)
    assert "will not help here" in note, note
    assert "also makes room" not in note, note
    # …and the floor it names is the one the renderer really uses.
    assert f"{floor:.1f} mm" in note, note


def test_the_floor_really_is_where_the_prediction_stops():
    """The measurement behind the clause, not a claim about it.

    5, 6, 7 and 8 pt all predict the same line box, which is why the message
    could go on naming the lever at 5 pt.
    """
    got = {round(raster.sheet_text_line_mm(pt * 25.4 / 72.0, "Inter", False,
                                           False, 300), 4)
           for pt in (5.0, 6.0, 7.0, 8.0)}
    assert len(got) == 1, (
        f"the prediction still moves below 8 pt ({sorted(got)}), so this "
        "test's premise is wrong and the clause should be offered")


# ------------------------------------------------------------------ "B"
def test_lowering_b_is_promised_only_where_the_block_stays_put():
    """In "Prioritise chart area" the patch block does not follow "B" down.

    Measured on beta 18: the frame's bottom margin read 19.759 mm at "B" 4 and
    at "B" 14, so the sentence is true there.
    """
    note = tc._bottom_lever_note(4.0, 4.0, 4.0, patch_first=False)
    assert "buys the same room" in note, note


def test_lowering_b_is_not_promised_in_patch_first():
    """In "Prioritise patch size" the block follows "B" down the page.

    Measured on beta 18, CR30 honeycomb, "Bottom" held at 12, "B" lowered
    18 → 8: the text moved down 10 mm, the block moved down 10.2 mm, and the
    overlap changed by 0.22 mm.

    MUTATION: drop the `patch_first` branch and this goes red.
    """
    note = tc._bottom_lever_note(4.0, 4.0, 4.0, patch_first=True)
    assert "buys the same room" not in note, note
    assert "buys almost nothing" in note, note
    assert "Prioritise patch size" in note, note


def test_the_markers_branch_still_wins_over_both():
    """When the ruler markers hold the block, "B" is not the lever at all, and
    that was already true before this round. It must not be lost to the new
    branch."""
    note = tc._bottom_lever_note(4.0, 7.0, 4.0, patch_first=True)
    assert "ruler helper markers hold the text" in note, note


# ------------------- the clip border width, against what the text actually needs
#
# **AND "AT LEAST THE MINIMUM" WAS STILL THE WRONG TEST (B8-245).** The gate was
# `typed >= CLIP_WIDTH_MIN_MM`, so at a typed margin of 12 mm the clause was
# offered while the function's OWN measured table says the lever cannot help
# below about 13. Reached from the app and driven on screen, i1Pro / A4 / clip
# border on the right / Run 1 Chart Notes filled in, the notes needing 2.7 mm at
# 7 pt (`~/Desktop/ChromIQ-beta18-proof/beta19-round-2/q9.json`):
#
# | band | "Right" | offered | after narrowing to 10.0 |
# |---|---|---|---|
# | 12 | 12 | *"also makes room, down to 10 mm"* | **still red**: 2.7 mm wanted, 1.6 mm there |
# | 24 | 12 | *"also makes room"* | **still red**, the same line |
# | 24 | 20 | *"also makes room"* | cleared |
#
# Narrowing frees `typed - CLIP_WIDTH_MIN_MM`, and the text still has to fit in
# it, so that is the comparison.
def test_the_width_lever_is_withheld_when_the_room_it_frees_is_too_small():
    """The driven state: "Right" 12 mm, notes needing 2.7 mm.

    MUTATION: gate on `typed >= CLIP_WIDTH_MIN_MM` again and this goes red.
    """
    note = tc._clip_width_lever_note(12.0, "right", 2.7)
    assert "will not help here" in note, note
    assert "2.7 mm" in note, note
    assert "also makes room" not in note, note


def test_the_width_lever_is_still_offered_where_the_room_is_enough():
    """"Right" 20 mm and the same notes: narrowing to 10 cleared it on screen."""
    note = tc._clip_width_lever_note(20.0, "right", 2.7)
    assert "also makes room" in note, note


@pytest.mark.parametrize("side", ("right", "left"))
def test_the_reason_it_gives_is_true_on_both_sides_of_the_old_line(side):
    """The sentence this replaced said the border "would still be what decides
    where the patches start", which is false at a typed 12 against a 10 mm
    floor: there the MARGIN decides. One reason now covers both.

    MUTATION: put the old wording back and this goes red for the 12 mm case.
    """
    for typed in (6.0, 12.0):
        note = tc._clip_width_lever_note(typed, side, 2.7)
        assert "will not help here" in note, (typed, note)
        assert "what decides where the patches start" not in note, (typed, note)
        assert "the text needs" in note, (typed, note)


def test_every_call_site_hands_over_the_room_the_text_needs():
    """A call that forgets the third argument silently gets the old gate back.

    MUTATION: drop `_o.needed_mm` from any of the three call sites and this
    goes red.
    """
    import ast
    import inspect
    import textwrap
    src = textwrap.dedent(inspect.getsource(tc.TabChart._engine_text_notes))
    calls = [n for n in ast.walk(ast.parse(src))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_clip_width_lever_note"]
    assert len(calls) == 3, f"{len(calls)} call sites, this assumed three"
    for c in calls:
        assert len(c.args) + len(c.keywords) >= 3, (
            "a `_clip_width_lever_note` call no longer says how much room the "
            "text needs, so it is back to offering the lever on the margin "
            "alone: " + ast.unparse(c))
