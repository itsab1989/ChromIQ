"""The left-margin warning reads the MEASURED margin, and knows when a value
it might name would be a lie.

Both halves come from one report by the design authority on beta 19, on a chart
in "Prioritise patch size" he attached (staged at
`~/Desktop/ChromIQ-beta20-proof/knut-beta19/chart-pps/`).

**HALF ONE - THE CHECK WAS READING THE SETTING, NOT THE SHEET.**

    The warning talks about the widening of the left area to 16.4mm, but the
    measured margin is already stating 26.0mm, while the left margin setting is
    10.0mm. Thus, the check seems to use the left margin setting, and not the
    measured margin for controlling what is needed, so reporting wrong numbers.
    ... This makes it very important that the measured margins are used in the
    checks for when warnings happen.

Reproduced from his own `channels.json`: typed 10.00 mm, the raise computes
**16.31 mm**, the sheet measures **26.04 mm**. Measured off his rendered
`test_01.tif` at 200 dpi (`fault5-tiff-measurement.txt`), the row indicators'
ink ends at **14.99 mm** and the first patch ink begins at **26.04 mm**, so
there is **11.05 mm of clear paper** where the panel printed a red warning. He
saw it too: *"there is plenty of space between the row indicators and the
measured left margin"*.

**HALF TWO - AND IN THAT LAYOUT A NAMED MARGIN VALUE IS NOT TRUE.**

    Changing left margin setting has no effect until the setting is brought
    above the measured left margin, so setting left margin to 26.0mm has no
    effect on the patch area left margin, but setting left margin to 27.0mm
    makes measured margin jump to 35.9mm. This is the result of how the original
    printtarg was designed to place patches. ... Stating what to set the left
    margin, while in "Prioritise patch size..." is selected, is not reliable.
    Only when "Prioritise chart area..." this is reliable. Thus, the warning
    messages while in "Prioritise patch size..." should not specifically mention
    what to set the margin settings to, but rather say which parameters can be
    altered to attempt removing a warning.

So `margin_values_are_reliable` gates every sentence that would name a value for
a margin box. It is about MARGIN boxes: "Label offset" is not one, and it was
measured moving the strip letters one millimetre per millimetre in patch-first,
so its number is still given.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                              # noqa: E402


# ------------------------------------------------- half one: ask the sheet
def test_the_raise_is_dropped_when_the_sheet_already_gives_the_room():
    """His three numbers, in the predicate that decides the warning.

    MUTATION: delete the `_got_l <= _meas_l + _tol` guard from
    `_engine_text_notes` and this goes red.
    """
    from ui.tabs import tab_chart as tc
    body = "\n".join(
        l for l in inspect.getsource(tc.TabChart._engine_text_notes).splitlines()
        if not l.strip().startswith("#"))
    assert "_raised_l and _meas_l is not None and _got_l <= _meas_l - _tol" in body, (
        "the left-margin warning no longer asks where the patches really "
        "landed, so it fires on a sheet with centimetres to spare")


@pytest.mark.parametrize(
    "asked,got,meas,fires",
    [
        # his chart: the raise computes 16.31, the sheet gives 26.04
        (10.0, 16.31, 26.04, False),
        # THE SHEET SHOWING EXACTLY THE RAISE still speaks, and must: in
        # "Prioritise chart area" the margins are law, so this is every chart
        # in that layout, and the raise is a disclosure §R1.5 requires.
        (10.0, 16.31, 16.31, True),
        # genuinely short: the sheet puts the patches inside what the labels need
        (10.0, 16.31, 14.0, True),
        # no sheet yet: the geometry's answer is the only fact there is
        (10.0, 16.31, None, True),
        # never raised at all
        (20.0, 20.0, 26.04, False),
    ])
def test_the_predicate_in_its_five_states(asked, got, meas, fires):
    """The arithmetic on its own, so the table is readable.

    `_tol` is `edge_tolerance_mm`, 0.2 mm at his 200 dpi.
    """
    tol = 0.2
    raised = bool(got > asked + 0.05)
    if raised and meas is not None and got <= meas - tol:
        raised = False
    assert raised is fires


def test_his_sheet_really_has_the_room_the_fix_assumes():
    """Not the report, the RASTER. Skipped when his chart is not on this machine.

    A prediction can only be checked against a rendered page, and the whole
    fault was a check trusting a number instead of the sheet.
    """
    from pathlib import Path
    tif = Path.home() / "Desktop" / "ChromIQ-beta20-proof" / "knut-beta19" / \
        "chart-pps" / "test_01.tif"
    if not tif.is_file():
        pytest.skip("a data file is not on this machine: his chart-pps TIFF")
    import numpy as np
    from PIL import Image
    a = np.asarray(Image.open(tif).convert("RGB")).astype(int)
    px2mm = 25.4 / 200.0
    mx, mn = a.max(2), a.min(2)
    black = (mx < 100) & ((mx - mn) < 30)
    coloured = (a.sum(2) < 720) & ((mx - mn) > 25)
    patch_left = float(np.where(coloured.any(0))[0][0]) * px2mm
    rows = np.where(coloured.any(1))[0]
    cols = np.where(black[rows[0]:rows[-1] + 1, :int(patch_left / px2mm)].any(0))[0]
    # the last cluster before the patches is the row-indicator digits
    groups, cur = [], [cols[0]]
    for c in cols[1:]:
        if c - cur[-1] <= 6:
            cur.append(c)
        else:
            groups.append(cur)
            cur = [c]
    groups.append(cur)
    labels_end = float(groups[-1][-1] + 1) * px2mm
    assert patch_left == pytest.approx(26.04, abs=0.1), (
        f"his sheet's patches start at {patch_left:.2f} mm, not the 26.0 his "
        f"panel showed; this case is not the one he reported")
    assert patch_left - labels_end > 5.0, (
        f"only {patch_left - labels_end:.2f} mm between the row indicators and "
        f"the patches; the warning would not have been false after all")


# --------------------------------------- half two: what a message may name
def test_a_margin_value_is_named_only_where_it_means_something():
    from ui.tabs.tab_chart import margin_values_are_reliable

    class _R:
        layout_mode = "area_first"
    assert margin_values_are_reliable(_R()) is True
    _R.layout_mode = "patch_first"
    assert margin_values_are_reliable(_R()) is False


def test_every_margin_remedy_is_gated_on_the_layout():
    """The three places a value for a margin box could be named.

    MUTATION: drop `margin_values_are_reliable` from any of the three and this
    goes red on that one.
    """
    from ui.tabs import tab_chart as tc
    body = "\n".join(
        l for l in inspect.getsource(tc.TabChart._engine_text_notes).splitlines()
        if not l.strip().startswith("#"))
    # 1. the left-margin raise
    assert "_name_margin_value = margin_values_are_reliable(r)" in body
    assert "_raised_l and _clip_is_the_anchor and _name_margin_value" in body
    assert "elif _raised_l and _name_margin_value:" in body
    # 2. the bottom-text rise, which is not even searched for in patch-first
    assert "if margin_values_are_reliable(r) else None)" in body, (
        "the bottom-text search still names a rise in a layout where the "
        "design authority has said a margin value cannot be trusted")


def test_the_patch_first_wordings_name_controls_and_no_margin_value():
    """*"say which parameters can be altered to attempt removing a warning."*

    Each patch-first wording must name its controls and must not tell the
    reader a number to type into a margin box.
    """
    from ui.tabs import tab_chart as tc
    src = inspect.getsource(tc.TabChart._engine_text_notes)
    for marker in ('"size” the margin boxes are requests the layout may place "',):
        assert marker in src, marker
    # The patch-first left-margin sentences exist, say why, and offer controls.
    assert src.count("no single value can be named ") == 2, (
        "one of the two patch-first left-margin wordings is missing")
    assert src.count("to measure each attempt.") == 2, (
        "a patch-first wording no longer sends the reader back to Generate "
        "Chart, which is the only thing that can say what an attempt did")
    # …and neither of them says "to {got:.1f} mm", which is the banned form.
    # EACH BLOCK ON ITS OWN, up to its `.format(`: a fixed-size window run
    # forward from the first match spills into the NEXT message, which is the
    # chart-first one and is entitled to that number.
    at = -1
    checked = 0
    while True:
        at = src.find("no single value can be named ", at + 1)
        if at < 0:
            break
        block = src[at:src.index(".format(", at)]
        checked += 1
        assert "to {got:.1f} mm" not in block, (
            "a patch-first wording still names a value for the Left box")
        assert "Margins (mm)" in block, (
            "a patch-first wording stopped naming the control to try")
    assert checked == 2, f"only {checked} patch-first wordings were checked"


def test_the_label_offset_keeps_its_number_in_patch_first():
    """The ruling is about MARGIN boxes. "Label offset" is not one, and it was
    measured moving the letters one millimetre per millimetre in this layout,
    so stripping its number would make the message less useful for no reason.
    """
    from ui.tabs import tab_chart as tc
    src = inspect.getsource(tc.TabChart._engine_text_notes)
    i = src.index("hang from the top margin. Raise “Label offset” ")
    block = src[i:i + 900]
    assert "by about " in block and "{over:.1f} mm" in block, (
        "the Label offset remedy lost the number it is entitled to")
    # …while "Top" in the same sentence is named without one.
    assert "Raising “Top” under “Margins (mm)” also moves " in block
