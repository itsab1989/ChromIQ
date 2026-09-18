"""The layout help is a promise, so it is measured against real sheets.

Knut asked for the two layout methods to be explained properly. The first
attempt said of "Prioritise chart area": *"Here your margins are the law. The
patch area lands exactly where you defined it."* An adversary round measured
that false. The second attempt said the leftover width "all goes to the LEFT",
and the next round measured THAT false on 154 of the 160 built-in charts, on
both counts of the vertical claim, and backwards on the 75 presets whose clip
band sits on the right.

What is actually going on is one rule the app already stated correctly two rows
below, in the Margins tooltip: a clip border takes its own width on the side it
is printed on, and that margin is `max(your number, the band)`
(`instruments.py`, `ml = max(ml, clip_w)`). The instrument's own reserves above
and below the patches are the other claimant, and they are not the same size as
each other, so top and bottom come out larger than asked by DIFFERENT amounts.

Two rules for this file, and the second is why the first attempt shipped:

* every claim in the text is measured against built sheets, across instruments,
  papers and both clip sides;
* BOTH places that describe the mode are read. The promise was written into two
  texts and removed from one, and the guard only knew about that one.
"""
from __future__ import annotations

import inspect
import json

import pytest

#: Promises no sheet keeps. Each was in a shipped help text.
FORBIDDEN = (
    "margins are the law",
    "lands exactly where you",
    "the patch area lands exactly",
    "all goes to the LEFT",
    "come out equal to each other",
    # round 11: false on a ColorMunki, a SpectroScan and a CR30, where the
    # instrument's own claim is the larger one and the band changes nothing
    "Switch it off and your number stands",
)


def _area_first_texts() -> "dict[str, str]":
    """Every place that describes "Prioritise chart area" to a user."""
    from ui.dialogs import layout_options_panel as lop
    from ui.tabs import tab_chart
    panel = inspect.getsource(lop)
    i = panel.index("Prioritise chart area, then fit patches to it")
    j = panel.index("PATCH-FIRST FIELDS", i)
    card = inspect.getsource(tab_chart)
    k = card.index('"Prioritise chart area, then fit patches to it\\" is')
    m = card.index("If you are unsure", k)
    return {"the Create layout tooltip": panel[i:j],
            "the Create Chart step 1 card": card[k:m]}


def _sheet(tmp_path, tag, **recipe_kw) -> dict:
    """Build a real sheet and measure its patch area, in mm."""
    from workflow.layout_engine import chart as le, papers
    from workflow.layout_engine.presets import LayoutRecipe
    rec = LayoutRecipe(layout_mode="area_first", area_min_patch_mm=8.0,
                       use_instrument_margins=False, dpi=300, **recipe_kw)
    d = tmp_path / tag
    d.mkdir(parents=True, exist_ok=True)
    src = d / "s.ti1"
    rows = ["CTI1", "", 'DESCRIPTOR "help"', 'ORIGINATOR "ChromIQ"',
            'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
            "END_DATA_FORMAT", "NUMBER_OF_SETS 120", "BEGIN_DATA"]
    rows += [f"{i + 1} {(i * 7) % 101} {(i * 11) % 101} {(i * 29) % 101} 40 45 50"
             for i in range(120)]
    rows += ["END_DATA", ""]
    src.write_text("\n".join(rows), encoding="utf-8")
    kw = dict(rec.build_kwargs())
    kw.pop("instrument", None)
    kw.pop("paper", None)
    kw["randomize"] = False
    kw["seed"] = 1
    le.build_chart(src, d / "s", instrument=rec.instrument, paper=rec.paper, **kw)
    pats = [p for p in json.loads(
        (d / "s.strips.json").read_text(encoding="utf-8"))["patches"]
            if int(p["page"]) == 0]
    assert pats
    k = 25.4 / 300.0
    pw, ph = papers.dimensions_mm(rec.paper)
    return {"left": min(p["x"] for p in pats) * k,
            "right": pw - max(p["x"] + p["w"] for p in pats) * k,
            "top": min(p["y"] for p in pats) * k,
            "bottom": ph - max(p["y"] + p["h"] for p in pats) * k}


def test_neither_help_text_promises_an_exact_margin():
    """MUTATION: put "margins are the law" back into either text and this goes
    red, naming which one."""
    for where, text in _area_first_texts().items():
        for promise in FORBIDDEN:
            assert promise not in text, (
                f"{where} still promises {promise!r}, which no sheet keeps")


def test_both_help_texts_name_the_clip_band_and_the_instrument_reserves():
    """The two claimants on the space, which is what the numbers really show.

    MUTATION: drop the clip-border sentence from either text and this goes red.
    """
    for where, text in _area_first_texts().items():
        low = text.lower()
        assert "clip border" in low, (
            f"{where} does not say that a clip border takes its own width")
        assert "reserve" in low or "strip letters" in low, (
            f"{where} does not say the instrument's own reserves take space")
        # THE THIRD CLAIMANT, which round 11 measured and the second version
        # of this text did not mention: the instrument's own minimum. Asking
        # 5 mm on an A4 SpectroScan gives 30 mm on the left with the clip band
        # off, so "switch it off and your number stands" was false.
        assert "instrument needs" in low, (
            f"{where} does not say the instrument itself claims a margin")
        assert "spectroscan" in low or "colormunki" in low, (
            f"{where} does not name an instrument the claim applies to")


@pytest.mark.slow
def test_the_clip_band_is_what_claims_the_margin(tmp_path):
    """The mechanism the text now gives, measured three ways.

    MUTATION: neuter `ml = max(ml, clip_w)` in `instruments.py` and this goes
    red.
    """
    on = _sheet(tmp_path, "band-left", instrument="p3", paper="A4",
                margin_left=5.0, margin_right=5.0, margin_top=5.0,
                margin_bottom=5.0, clip_border=True,
                clip_border_width_mm=26.0, clip_side="left")
    assert on["left"] > 20.0, on          # the band, not the number typed
    off = _sheet(tmp_path, "band-off", instrument="p3", paper="A4",
                 margin_left=5.0, margin_right=5.0, margin_top=5.0,
                 margin_bottom=5.0, clip_border=False)
    assert abs(off["left"] - 5.0) < 1.0, off   # the number typed stands
    right = _sheet(tmp_path, "band-right", instrument="p3", paper="A4",
                   margin_left=5.0, margin_right=5.0, margin_top=5.0,
                   margin_bottom=5.0, clip_border=True,
                   clip_border_width_mm=26.0, clip_side="right")
    assert abs(right["left"] - 5.0) < 1.0, right
    assert right["right"] > 20.0, right        # and it moves to the other side
    # ...and asking for more than the band gets more than the band.
    wide = _sheet(tmp_path, "band-wide", instrument="p3", paper="A4",
                  margin_left=40.0, margin_right=40.0, margin_top=40.0,
                  margin_bottom=40.0, clip_border=True,
                  clip_border_width_mm=26.0, clip_side="left")
    assert wide["left"] > 38.0, wide


@pytest.mark.slow
@pytest.mark.parametrize("instrument,band_off_keeps_the_number",
                         [("i1", True), ("p3", True), ("CM", False),
                          ("SS", False), ("CR30", False)])
def test_the_band_is_not_the_only_claimant(tmp_path, instrument,
                                           band_off_keeps_the_number):
    """With the clip band OFF, the typed number stands on an i1Pro and does
    not on the other three: their own carriage claims more. Measured at 5 mm
    on A4: i1 and i1Pro 3+ 5.00, ColorMunki 25.99, SpectroScan and CR30 30.48.

    MUTATION: put "Switch it off and your number stands" back in the text and
    `test_neither_help_text_promises_an_exact_margin` goes red.
    """
    got = _sheet(tmp_path, f"band-off-{instrument}", instrument=instrument,
                 paper="A4", margin_left=5.0, margin_right=5.0,
                 margin_top=5.0, margin_bottom=5.0, clip_border=False)
    if band_off_keeps_the_number:
        assert abs(got["left"] - 5.0) < 1.0, got
    else:
        assert got["left"] > 20.0, (
            f"{instrument} no longer claims a left margin of its own, so the "
            f"help text's third claimant needs re-measuring")


@pytest.mark.slow
@pytest.mark.parametrize("instrument", ["i1", "p3", "CM", "SS", "CR30"])
def test_every_margin_is_at_least_what_was_asked(tmp_path, instrument):
    """The only promise the text makes about the four edges, and it holds on
    every instrument a user can pick. It deliberately does NOT claim that top
    and bottom are equal: measured, they are up to 2.9 mm apart, because the
    reserve above the patches and the run-out below them are different sizes.
    """
    got = _sheet(tmp_path, f"least-{instrument}", instrument=instrument,
                 paper="A4", margin_left=5.0, margin_right=5.0,
                 margin_top=5.0, margin_bottom=5.0)
    for edge, mm in got.items():
        assert mm >= 5.0 - 0.1, f"{instrument}: the {edge} margin is {mm:.2f}"
