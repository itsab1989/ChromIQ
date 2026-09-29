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
    # round 12 (B8-346 F7), measured over 540 built sheets: the clip band and
    # the instrument's claim ADD on the same side (an A4 SpectroScan with the
    # band on the left comes out at 30.48, not at the larger of 26 and 8.47),
    # so no "largest of" formulation is true; a ColorMunki claims exactly what
    # an i1Pro does, which is nothing; and the top comes out EXACTLY the
    # number typed on a SpectroScan and a CR30.
    "largest of three things",
    "LARGEST of three things",
    "30 mm on the left and 9 on the right",
    "slightly larger than you asked",
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
    # **JOINED AND COLLAPSED, OR A SENTENCE CAN HIDE IN THE GAPS.** These are
    # read out of the SOURCE, where a paragraph is a run of adjacent string
    # literals, so "... need " + "nothing there" carries a quote, a newline and
    # an indent in the middle of a phrase a reader sees as one. A guard that
    # matched the raw source could be defeated by a line break, which is the
    # same shape as the fault B8-344 fixed in the site check.
    def _flat(s: str) -> str:
        return " ".join(s.replace('"', " ").split())
    return {"the Create layout tooltip": _flat(panel[i:j]),
            "the Create Chart step 1 card": _flat(card[k:m])}


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
    """MUTATION, proven to land: put any of the FORBIDDEN clauses back into
    either text and this goes red, naming which one."""
    for where, text in _area_first_texts().items():
        for promise in FORBIDDEN:
            assert promise not in text, (
                f"{where} still promises {promise!r}, which no sheet keeps")


def test_both_help_texts_say_what_raises_a_margin():
    """The two claimants, in the words the sheets support.

    **THESE ARE DELIBERATELY THE NEW SENTENCES' OWN WORDS.** Round 12 deleted
    each clause of the previous version of this text one at a time and the
    guard stayed green every time, because every assertion it made was already
    satisfied by a sentence that had been there for months (its F9). So the
    phrases below appear nowhere else in either text, and each one carries a
    fact the tests underneath measure.

    MUTATION, proven to land: delete any one of these phrases from either text.
    """
    for where, text in _area_first_texts().items():
        low = " ".join(text.lower().split())
        for phrase, what in (
                ("two things can raise it",
                 "that the number typed is a minimum two things can raise"),
                ("at least the band", "that the side is raised TO the band, "
                                      "not that the band is added to it"),
                ("need nothing", "that some instruments claim nothing"),
                ("colormunki", "which instruments claim nothing"),
                ("room at both sides",
                 "that a SpectroScan and a CR30 claim BOTH sides"),
                ("8.5 mm", "how much a SpectroScan or a CR30 does claim"),
                ("need not match", "that the top and bottom differ"),
        ):
            n = low.count(phrase)
            assert n, f"{where} no longer says {what} ({phrase!r})"
            # **EXACTLY ONCE, OR THE ASSERTION PROVES NOTHING.** Round 13
            # deleted the whole new sentence from the panel and this test
            # stayed green, because two of the seven phrases it looked for
            # also occur in a sentence that predates the fix -- which is the
            # same fault (F9) the guard was written to close, in the guard
            # written to close it.
            assert n == 1, (
                f"{where} says {phrase!r} {n} times, so finding it proves "
                f"nothing about the sentence this test is here for")


@pytest.mark.slow
def test_switching_the_clip_band_off_takes_two_switches(tmp_path):
    """**THE CONTROL THIS FILE MEASURES AGAINST, PINNED.**

    `clip_border=False` is documented in `presets.py` as i1/p3 only, and it is:
    measured here at 5 mm on A4, it leaves the band's 26 mm on the left of a
    ColorMunki (25.99) and a SpectroScan (30.48) exactly as if it were on, and
    `clip_content_mode="off"` does the same to an i1Pro. Only both together
    give every instrument the number that was typed.

    This is not a footnote. The previous version of this guard switched the
    band off with `clip_border=False` alone and then recorded the band it had
    failed to switch off as "the ColorMunki's own claim" -- the false sentence
    the help text then repeated to the user (B8-346 F8).
    """
    for inst, only_border, only_content in (("i1", 5.0, 25.99),
                                            ("CM", 25.99, 5.0),
                                            ("SS", 30.48, 8.47)):
        a = _sheet(tmp_path, f"ob-{inst}", instrument=inst, paper="A4",
                   margin_left=5.0, margin_right=5.0, margin_top=5.0,
                   margin_bottom=5.0, clip_border=False)
        b = _sheet(tmp_path, f"oc-{inst}", instrument=inst, paper="A4",
                   margin_left=5.0, margin_right=5.0, margin_top=5.0,
                   margin_bottom=5.0, clip_content_mode="off")
        assert abs(a["left"] - only_border) < 0.5, (
            f"{inst}: clip_border=False alone gives {a['left']:.2f}, "
            f"measured {only_border}")
        assert abs(b["left"] - only_content) < 0.5, (
            f"{inst}: clip_content_mode='off' alone gives {b['left']:.2f}, "
            f"measured {only_content}")


def _band_off(tmp_path, tag, **kw):
    """A sheet with the clip band REALLY off, both switches thrown."""
    return _sheet(tmp_path, tag, clip_border=False, clip_content_mode="off",
                  **kw)


@pytest.mark.slow
@pytest.mark.parametrize("asked,expect", [(5.0, 26.0), (40.0, 40.0)])
def test_the_clip_side_is_raised_to_the_band_and_not_added_to_it(tmp_path,
                                                                 asked, expect):
    """Claim 1 of the text: the clip side is raised to AT LEAST the band's own
    width, and the band is never added on top of the number.

    Measured on an i1Pro A4 sheet, which is the instrument that claims nothing
    of its own, so the band is the only thing moving: 5 mm asked comes out at
    25.99 and 40 mm asked comes out at 39.96. Adding would have given 31 and 66.

    MUTATION, proven to land: change `ml = max(ml, clip_w)` in
    `instruments.py` to `ml += clip_w`.
    """
    got = _sheet(tmp_path, f"clipside-{int(asked)}", instrument="i1",
                 paper="A4", margin_left=asked, margin_right=asked,
                 margin_top=asked, margin_bottom=asked, clip_border=True,
                 clip_border_width_mm=26.0, clip_side="left")
    assert abs(got["left"] - expect) < 0.5, (
        f"asking {asked} mm on the clip side gives {got['left']:.2f}, "
        f"measured {expect}")
    # ...and the other side is untouched by the band.
    assert abs(got["right"] - asked) < 0.5, got


@pytest.mark.slow
@pytest.mark.parametrize("instrument,claims,right", [
    ("i1", 0.0, 0.0), ("p3", 0.0, 0.0), ("CM", 0.0, 0.0),
    ("SS", 8.55, 3.50), ("CR30", 8.55, 5.87)])
def test_only_a_spectroscan_or_a_cr30_claims_the_edge_of_the_sheet(
        tmp_path, instrument, claims, right):
    """Claim 2 of the text, with the band REALLY off and nothing asked for.

    Measured on A4: an i1Pro, a Pro-300 and a ColorMunki leave the patches at
    the very edge (0.00), and a SpectroScan and a CR30 keep 8.55. The previous
    text named the ColorMunki among the claimants; it claims exactly what an
    i1Pro does, which is nothing, and the number that made it look otherwise
    was a clip band the test had not switched off.
    """
    got = _band_off(tmp_path, f"edge-{instrument}", instrument=instrument,
                    paper="A4", margin_left=0.0, margin_right=0.0,
                    margin_top=0.0, margin_bottom=0.0)
    assert abs(got["left"] - claims) < 0.6, (
        f"{instrument} keeps {got['left']:.2f} mm at the left with nothing "
        f"asked and no band; the text says {claims}")
    # ...AND THE RIGHT SIDE, WHICH THE TEXT USED TO LEAVE OUT. A CR30 keeps
    # 5.87 mm at the right of the same sheet and a SpectroScan 3.50, so
    # "8.5 mm at the left" was true and incomplete, and this test asserted
    # only the side the text happened to name (R13-5).
    assert abs(got["right"] - right) < 0.6, (
        f"{instrument} keeps {got['right']:.2f} mm at the RIGHT with nothing "
        f"asked and no band; the text says {right}")


@pytest.mark.slow
def test_the_top_and_the_bottom_are_worked_out_separately(tmp_path):
    """Claim 3 of the text: the two can both come out larger than asked, and
    they need not match each other.

    Measured on an i1Pro A4 sheet at 5 mm: top 6.01, bottom 6.42. The text no
    longer says they are ALWAYS larger, because on a SpectroScan and a CR30 the
    top is exactly the number typed (5.00) -- which is what round 12 caught the
    previous version claiming.
    """
    i1 = _sheet(tmp_path, "vert-i1", instrument="i1", paper="A4",
                margin_left=5.0, margin_right=5.0, margin_top=5.0,
                margin_bottom=5.0)
    assert i1["top"] > 5.2 and i1["bottom"] > 5.2, i1
    assert abs(i1["top"] - i1["bottom"]) > 0.2, (
        f"top {i1['top']:.2f} and bottom {i1['bottom']:.2f} now match, so the "
        f"text's last clause needs re-measuring")
    ss = _sheet(tmp_path, "vert-ss", instrument="SS", paper="A4",
                margin_left=5.0, margin_right=5.0, margin_top=5.0,
                margin_bottom=5.0)
    assert abs(ss["top"] - 5.0) < 0.1, (
        f"a SpectroScan's top is {ss['top']:.2f}, not the 5.00 that makes "
        f'"slightly larger than you asked" a false sentence')


@pytest.mark.slow
@pytest.mark.parametrize("instrument", ["i1", "p3", "CM", "SS", "CR30"])
def test_every_margin_is_at_least_what_was_asked(tmp_path, instrument):
    """The only promise the text makes about all four edges at once.

    The tolerance is a measured pixel, not a fudge: the patch grid lands on
    whole pixels, so asking 9 mm on an i1Pro A4 sheet gives 8.97 and asking 40
    gives 39.96. One pixel at 300 dpi is 0.085 mm; the slack here is 0.1.
    """
    got = _sheet(tmp_path, f"least-{instrument}", instrument=instrument,
                 paper="A4", margin_left=5.0, margin_right=5.0,
                 margin_top=5.0, margin_bottom=5.0)
    for edge, mm in got.items():
        assert mm >= 5.0 - 0.1, f"{instrument}: the {edge} margin is {mm:.2f}"
