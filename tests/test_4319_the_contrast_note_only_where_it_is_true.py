"""4.3.19: the "low patch/spacer contrast" note, only where it is true.

The guard imagines a black-or-white bar between neighbouring patches, which is
the "Black & white" spacer rule. Until 4.3.19 it was asked about every chart:
on "Coloured" spacers (the default) it was a false alarm, and with Spacers
"None" it named the pairs with the HIGHEST patch-to-patch contrast on the
sheet. Investigation: ~/Desktop/ChromIQ-work/2026-10-27_spacer_contrast_note.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from workflow.layout_engine import chart, contrast

GREY = (50.0, 50.0, 50.0)
BLACK = (0.0, 0.0, 0.0)
WHITE = (100.0, 100.0, 100.0)


def _write_ti1(path: Path, rows: list[tuple[float, float, float]]) -> None:
    body = "\n".join(f"{i} {r:.4f} {g:.4f} {b:.4f}"
                     for i, (r, g, b) in enumerate(rows, 1))
    path.write_text(
        'CTI1\nCOLOR_REP "RGB"\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n'
        f'NUMBER_OF_SETS {len(rows)}\nBEGIN_DATA\n{body}\nEND_DATA\n',
        encoding="utf-8")


def _steps(tmp_path: Path) -> int:
    ti1 = tmp_path / "probe.ti1"
    _write_ti1(ti1, [GREY] * 120)
    res = chart.build_chart(str(ti1), str(tmp_path / "probe"), instrument="i1",
                            paper="A4", randomize=False, dpi=36)
    return res.layout.steps_in_pass


@pytest.fixture
def chart_with_two_pairs(tmp_path: Path):
    """Mid grey everywhere, except a black patch directly above a white one in
    the THIRD strip and again in the FIFTH, laid out in order."""
    steps = _steps(tmp_path)
    rows = [GREY] * (6 * steps)
    for strip in (2, 4):
        rows[strip * steps + 3] = BLACK
        rows[strip * steps + 4] = WHITE
    ti1 = tmp_path / "pairs.ti1"
    _write_ti1(ti1, rows)
    return ti1, steps


def _build(tmp_path: Path, ti1: Path, mode: str, name: str, **kw):
    return chart.build_chart(
        str(ti1), str(tmp_path / name), instrument="i1", paper="A4",
        randomize=False, dpi=36, spacer_on=mode != "none", spacer_mode=mode,
        edge_spacers=mode != "none", **kw)


def test_black_and_white_flags_the_dark_light_strips(tmp_path, chart_with_two_pairs):
    ti1, steps = chart_with_two_pairs
    res = _build(tmp_path, ti1, "bw", "bw")
    assert list(res.low_contrast_passes) == [2, 4]
    # Named as the sheet and the .ti2 name them: the black patch's location
    # in the .ti2 starts with the strip's label.
    ti2 = (tmp_path / "bw.ti2").read_text(encoding="utf-8")
    locs = dict(re.findall(r'^(\d+) "([A-Z0-9]+)"', ti2, re.M))
    for label, strip in zip(res.low_contrast_labels, (2, 4)):
        loc = locs[str(strip * steps + 3 + 1)]
        assert re.fullmatch(re.escape(label) + r"\d+", loc), (label, loc)
    assert res.low_contrast_labels == ["C", "E"]


@pytest.mark.parametrize("mode", ["colored", "none"])
def test_coloured_and_none_never_flag(tmp_path, chart_with_two_pairs, mode):
    ti1, _steps_ = chart_with_two_pairs
    res = _build(tmp_path, ti1, mode, mode)
    assert list(res.low_contrast_passes) == []
    assert list(res.low_contrast_labels) == []


def test_a_grey_chart_is_clean_under_black_and_white(tmp_path):
    ti1 = tmp_path / "g.ti1"
    _write_ti1(ti1, [GREY] * 80)
    res = _build(tmp_path, ti1, "bw", "g")
    assert list(res.low_contrast_passes) == []


# ---- the rule itself ------------------------------------------------------

DARK, LIGHT, MID = (10, 10, 10), (245, 245, 245), (128, 128, 128)


def test_only_black_and_white_spacers_are_tested():
    slots = [MID, DARK, LIGHT, MID]
    for mode in ("colored", "none"):
        assert contrast.drawn_low_contrast_passes(
            slots, 4, spacer_mode=mode, spacers_drawn=True) == []
    assert contrast.drawn_low_contrast_passes(
        slots, 4, spacer_mode="bw", spacers_drawn=True) == [0]
    # "Black & white" with no room for a spacer draws none.
    assert contrast.drawn_low_contrast_passes(
        slots, 4, spacer_mode="bw", spacers_drawn=False) == []


def test_the_old_rule_still_flags_what_it_flagged_under_black_and_white():
    """Same strips as `low_contrast_passes` whenever bars are drawn."""
    import random
    rnd = random.Random(4319)
    slots = [tuple(rnd.choice((0, 20, 128, 235, 255)) for _ in range(3))
             for _ in range(400)]
    assert contrast.drawn_low_contrast_passes(
        slots, 20, spacer_mode="bw", spacers_drawn=True) \
        == contrast.low_contrast_passes(slots, 20)


def test_a_hand_set_colour_is_tested_only_when_it_is_black_or_white():
    slots = [MID, DARK, LIGHT, MID]       # the pair is boundary 1 of strip 0
    kw = dict(spacer_mode="bw", spacers_drawn=True)
    assert contrast.drawn_low_contrast_passes(
        slots, 4, spacer_overrides={1: (255, 0, 0)}, **kw) == []
    for bw in ((0, 0, 0), (255, 255, 255)):
        assert contrast.drawn_low_contrast_passes(
            slots, 4, spacer_overrides={1: bw}, **kw) == [0]
    # an override somewhere else changes nothing here
    assert contrast.drawn_low_contrast_passes(
        slots, 4, spacer_overrides={0: (255, 0, 0)}, **kw) == [0]


def test_a_hand_set_red_spacer_reaches_the_renderer(tmp_path, chart_with_two_pairs):
    ti1, steps = chart_with_two_pairs
    res = _build(tmp_path, ti1, "bw", "ov",
                 spacer_overrides={str(2 * steps + 3): "#ff0000"})
    assert list(res.low_contrast_passes) == [4]


# ---- review 4.3.19 r1: the edge bars (N3) ---------------------------------

def test_an_edge_bar_beside_a_very_dark_first_or_last_patch_is_tested():
    """With "Edge spacers" the bar before the first patch sits between the
    paper and that patch. Under "Black & white" it is black (the paper is
    white), so beside a very dark patch it is as hard to find as any bar."""
    kw = dict(spacer_mode="bw", spacers_drawn=True)
    for slots in ([DARK, MID, MID, MID], [MID, MID, MID, DARK]):
        assert contrast.drawn_low_contrast_passes(
            slots, 4, edge_spacers=True, **kw) == [0], slots
        assert contrast.drawn_low_contrast_passes(
            slots, 4, edge_spacers=False, **kw) == [], slots
    # A very light end patch gets a black bar too, far from both sides.
    for slots in ([LIGHT, MID, MID, MID], [MID, MID, MID, LIGHT]):
        assert contrast.drawn_low_contrast_passes(
            slots, 4, edge_spacers=True, **kw) == [], slots
    # Only "Black & white" draws a black or white edge bar.
    assert contrast.drawn_low_contrast_passes(
        [DARK, MID, MID, MID], 4, spacer_mode="colored", spacers_drawn=True,
        edge_spacers=True) == []


def test_the_edge_bar_is_the_one_the_renderer_draws():
    from workflow.layout_engine.colorants import luminance
    bar = contrast.spacer_for_mode("bw", (255, 255, 255), DARK)
    assert bar == (0, 0, 0)
    assert abs(luminance(bar) - luminance(DARK)) < contrast.LOW_CONTRAST_THRESHOLD


def test_a_strip_that_starts_on_black_is_named_with_edge_spacers(tmp_path):
    steps = _steps(tmp_path)
    rows = [GREY] * (4 * steps)
    rows[1 * steps] = BLACK                   # strip B starts on black
    rows[3 * steps - 1] = BLACK               # strip C ends on black
    ti1 = tmp_path / "ends.ti1"
    _write_ti1(ti1, rows)
    res = _build(tmp_path, ti1, "bw", "ends")          # edge_spacers on
    assert list(res.low_contrast_passes) == [1, 2]
    assert res.low_contrast_labels == ["B", "C"]
    off = chart.build_chart(
        str(ti1), str(tmp_path / "ends-off"), instrument="i1", paper="A4",
        randomize=False, dpi=36, spacer_on=True, spacer_mode="bw",
        edge_spacers=False)
    # No edge bars drawn: the black end patches stand next to bare paper.
    assert list(off.low_contrast_passes) == []


# ---- review 4.3.19 r1: a hand-set black or white bar, by its own gap (N4) --

def test_a_hand_set_black_bar_between_a_dark_and_a_mid_patch_is_named():
    slots = [MID, MID, MID, DARK, MID, MID]   # boundary 3: dark | mid
    black = {3: (0, 0, 0)}
    for mode in ("bw", "colored"):
        assert contrast.drawn_low_contrast_passes(
            slots, 6, spacer_mode=mode, spacers_drawn=True,
            spacer_overrides=black) == [0], mode
    # ChromIQ's own bar there is white under "Black & white", far from both.
    assert contrast.drawn_low_contrast_passes(
        slots, 6, spacer_mode="bw", spacers_drawn=True) == []
    # A hand-set white bar beside a light patch, in "Coloured" mode.
    slots_l = [MID, MID, LIGHT, MID, MID, MID]
    assert contrast.drawn_low_contrast_passes(
        slots_l, 6, spacer_mode="colored", spacers_drawn=True,
        spacer_overrides={2: (255, 255, 255)}) == [0]
    # ...and a hand-set black bar far from both its neighbours is fine.
    assert contrast.drawn_low_contrast_passes(
        slots_l, 6, spacer_mode="colored", spacers_drawn=True,
        spacer_overrides={2: (0, 0, 0)}) == []


@pytest.mark.parametrize("mode", ["bw", "colored"])
def test_a_hand_set_colour_that_is_not_black_or_white_is_never_named(mode):
    slots = [MID, MID, MID, DARK, LIGHT, MID]
    for colour in ((255, 0, 0), (12, 12, 12), (128, 128, 128)):
        got = contrast.drawn_low_contrast_passes(
            slots, 6, spacer_mode=mode, spacers_drawn=True,
            spacer_overrides={3: colour})
        assert got == [], (mode, colour)


def test_spacers_none_draws_no_hand_set_bar_either():
    assert contrast.drawn_low_contrast_passes(
        [MID, DARK, MID, MID], 4, spacer_mode="none", spacers_drawn=True,
        spacer_overrides={0: (0, 0, 0)}) == []


def test_a_hand_set_black_bar_reaches_the_renderer_in_coloured_mode(
        tmp_path, chart_with_two_pairs):
    ti1, steps = chart_with_two_pairs
    res = _build(tmp_path, ti1, "colored", "ovc",
                 spacer_overrides={str(2 * steps + 3): "#000000"})
    assert list(res.low_contrast_passes) == [2]
    assert res.low_contrast_labels == ["C"]


# ---- review 4.3.19 r1: charts read patch by patch (N5) ---------------------

def test_a_chart_read_patch_by_patch_gets_no_note():
    """The SpectroScan's table and the CR30 are put on each patch by position
    and never look for a patch edge, so the note's "the instrument may find
    that patch edge less easily" says nothing true about them."""
    from workflow.layout_engine import instruments
    assert instruments.READ_PATCH_BY_PATCH == {"SS", "CR30"}
    assert contrast.drawn_low_contrast_passes(
        [MID, DARK, LIGHT, MID], 4, spacer_mode="bw", spacers_drawn=True,
        edge_spacers=True, reads_strips=False) == []
    for key in ("i1", "p3", "CM", "41", "51"):
        assert instruments.reads_along_strips(instruments.build(key)), key
    for key in ("SS", "CR30"):
        assert not instruments.reads_along_strips(instruments.build(key)), key


@pytest.mark.parametrize("inst,hexagons", [("SS", False), ("SS", True),
                                           ("CR30", False), ("CR30", True)])
def test_spectroscan_and_cr30_charts_never_name_a_strip(tmp_path, inst,
                                                        hexagons):
    ti1 = tmp_path / "bwbw.ti1"
    _write_ti1(ti1, [BLACK, WHITE] * 60)
    res = chart.build_chart(
        str(ti1), str(tmp_path / f"{inst}{hexagons}"), instrument=inst,
        paper="A4", randomize=False, dpi=36, spacer_on=True,
        spacer_mode="bw", edge_spacers=True, hflag=hexagons)
    assert list(res.low_contrast_passes) == []
    # the same patches on a strip reader are named
    strip = chart.build_chart(
        str(ti1), str(tmp_path / f"i1{inst}{hexagons}"), instrument="i1",
        paper="A4", randomize=False, dpi=36, spacer_on=True,
        spacer_mode="bw", edge_spacers=True)
    assert list(strip.low_contrast_passes)


# ---- the log line ---------------------------------------------------------

def _line(labels, randomized=True):
    from workflow.chart_creator import _low_contrast_log_line
    return _low_contrast_log_line(labels, randomized)


def test_no_strips_no_line():
    assert _line([]) == ""


def test_the_line_names_the_strips_by_label():
    one = _line(["D"])
    assert one.startswith("[ChromIQ layout engine] Note about strip D: ")
    assert "If this strip does not read cleanly" in one
    many = _line(["D", "T"])
    assert many.startswith("[ChromIQ layout engine] Note about strips D, T: ")
    assert "If one of these strips does not read cleanly" in many


def test_the_line_uses_the_panels_own_labels():
    text = _line(["D", "T"])
    for label in ("“Spacers”", "“Coloured”", "Expert Options",
                  "“New seed”", "Randomisation", "ChromIQ layout,"):
        assert label in text, label
    assert "—" not in text


def test_no_new_seed_advice_when_the_order_is_fixed():
    for labels in (["D"], ["D", "T"]):
        assert "New seed" not in _line(labels, randomized=False)
        assert "“Coloured”" in _line(labels, randomized=False)


def test_the_labels_named_exist_in_the_panel():
    """Each control the line names is a real one, by the same `tr()` key."""
    src = (Path(__file__).resolve().parents[1]
           / "ui/dialogs/layout_options_panel.py").read_text(encoding="utf-8")
    for key in ('tr("Coloured")', 'tr("Spacers:")', 'tr("New seed")',
                'tr("Expert Options")', 'tr("Randomisation")'):
        assert key in src, key
    tab = (Path(__file__).resolve().parents[1]
           / "ui/tabs/tab_chart.py").read_text(encoding="utf-8")
    assert 'tr("ChromIQ layout")' in tab


def test_the_old_english_only_line_is_gone():
    src = (Path(__file__).resolve().parents[1]
           / "workflow/chart_creator.py").read_text(encoding="utf-8")
    assert "low patch/spacer contrast" not in src


def test_the_engine_log_lines_reach_the_extractor():
    """`tr` imported under another name is invisible to scripts/i18n_extract.py,
    so "Drawing the pages" stayed English in every language until 4.3.19."""
    src = (Path(__file__).resolve().parents[1]
           / "workflow/chart_creator.py").read_text(encoding="utf-8")
    # ...and `count_phrase` under another name hides a plural from
    # tests/test_plural_forms.py, which reads the call by its name.
    assert not re.search(r"\b(tr|count_phrase) as _\w+", src)
    from scripts.i18n_extract import extract_keys
    keys = extract_keys()
    assert any(k.startswith("[ChromIQ layout engine] Drawing the pages.")
               for k in keys)
    assert sum(k.startswith("[ChromIQ layout engine] Note about strip")
               for k in keys) == 4
