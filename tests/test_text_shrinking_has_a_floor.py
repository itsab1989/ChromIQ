"""Shrinking a sheet's text has a floor, and only "auto" shrinks at all.

Knut, issue #182, 2026-09-11, testing 4.2.5 on his own CR30 hex chart:

    "if the Chart Notes are specified, or "Stamp settings used on the chart"
    checkbox is ON, and the right margin is 6mm, and the "Text distance from
    edge" Clip-setting is 4mm, then the text is reduced to a mini-sized font
    almost not readable, instead of warning of the text not having room to fit,
    like it was done for the strip labels. The shrinking of the text should have
    a lower limit so the shrinking stops and the warning comes instead. I
    suggest a font size limit of 8pt (if the Sheet text frame size parameter is
    set to auto). If the Sheet text frame size parameter is set to a value, no
    shrinking should happen and the warning instead shown as soon as the Text is
    being pushed out towards the page edges, crossing the "Text distance from
    edge" Clip-setting. The Sheet text frame Font and Size should be used for
    the Run Chart Notes text and the "Stamp settings used on the chart"
    checkbox, so that the text is controllable."

and, for the clip border's own text:

    "there should be a font size minimum limit before the clip-border text stops
    shrinking (suggest 8pt here too, when the size setting is auto under
    Clip-border content frame) … Setting a specific font size will prevent
    shrinking here too … Manually setting size below 8pt should be working fine
    also. It makes sense that only the Auto size setting allows automatic
    shrinking of the text. This should apply to Sheet Text frame also."

**MEASURED ON HIS OWN PROJECT, ON SCREEN, BEFORE ANY OF THIS WAS WRITTEN.**
`testHex` from his "test projects.zip", driven through the real window by
`scripts/drive_182_text_shrink_floor.py` at his own numbers (right margin
6.0 mm, Clip 4.0 mm, Chart Notes "This chart is a test", stamp on): the note
the app printed was **2.29 mm of ink across the sheet, 6.5 pt**, and typing
12 pt into the Sheet text frame's Size changed nothing at all, because that box
did not reach the note. The panel said nothing, because the floor it compared
against was 9 PIXELS (3.24 pt at 200 dpi, 1.08 pt at 600).

**AND THE FLOOR HE SUGGESTED WAS ONE POINT TOO HIGH, WHICH HE FOUND THE SAME
EVENING** (#182, 2026-09-11T21:23:10Z), on the two-run `test` project he
attached next:

    "Run 2 has a right side Chart Text, set in Sheet Text frame as size 7. (The
    auto setting shrunk the text to size 8, but that cause the long text to
    overflow the height of the page, so I changed to size 7). This showed me
    that the threshold of 8pt font size as the limit for when shrinking stops,
    when size is set to Auto, is too high. Please set the stop-shrinking
    threshold to 7, applicable for all the places font size is set and has Auto
    as a choice."

Driven through the real window against that project by
`scripts/drive_182_sheet_text_fit.py`: his 147-character note on the 130 x 180
card is printed 168.66 mm long at the 8 pt floor with its tail cut, and
161.16 mm long and whole at 7 pt. So this file says SEVEN, and every number in
it moved with the constant rather than being re-derived by hand.
"""
from __future__ import annotations

import numpy as np
import pytest

from workflow import text_edge_fit as tef
from workflow import tiff_metadata as tm
from workflow.layout_engine import raster

_NOTE = "Canon PRO-1000, PhotoRag 308, colour management OFF"


# --------------------------------------------------------------------------
# The law itself
# --------------------------------------------------------------------------

def test_the_floor_is_seven_point_and_only_for_auto():
    assert tef.AUTO_SHRINK_FLOOR_PT == 7.0
    assert tef.text_floor_pt(0.0) == 7.0, "auto must stop at the 7 pt floor"
    assert tef.text_floor_pt(12.0) == 12.0, "a typed size is its own floor"
    assert tef.text_floor_pt(6.0) == 6.0, (
        "a typed size below 7 pt must be honoured, not raised to the floor")


def test_seven_point_is_the_same_paper_at_every_resolution():
    """A floor in POINTS is a floor on paper. The 9 px one was not."""
    for dpi in (150, 200, 300, 600, 1200):
        got = tef.px_to_pt(tef.pt_to_px(tef.AUTO_SHRINK_FLOOR_PT, dpi), dpi)
        # Half a pixel at the coarsest raster here is 0.24 pt, and a whole
        # pixel cannot be split; the point is that the ERROR is a rounding
        # one and does not grow with the resolution, which a pixel floor's
        # does (8 px is 2.88 pt at 200 dpi and 0.96 at 600).
        assert abs(got - tef.AUTO_SHRINK_FLOOR_PT) < 0.3, (dpi, got)


def test_knuts_own_numbers_now_earn_a_warning():
    """Right margin 6.0 mm, Clip 4.0 mm, at his chart's 200 dpi.

    6.0 less the 4.0 mm reserve and the 0.34 mm patch guard is 1.66 mm, and one
    line at the 7 pt floor plus its gap needs 2.723 mm. Under the 9 px floor
    this asked for 1.397 mm, fitted, and said nothing while printing 6.5 pt.
    """
    assert tef.chart_note_overlap("right", 6.0, 4.0, 200) is not None, (
        "the case Knut reported still prints a mini font and says nothing")
    # …and a roomy margin still says nothing at all.
    assert tef.chart_note_overlap("right", 20.0, 4.0, 200) is None


def test_a_typed_size_changes_how_much_paper_the_note_needs():
    small = tef.chart_note_overlap("right", 6.0, 4.0, 200, 0.0, 5.0)
    auto = tef.chart_note_overlap("right", 6.0, 4.0, 200, 0.0, 0.0)
    assert auto is not None
    assert small is None or small.overlap_mm < auto.overlap_mm, (
        "asking for 5 pt must need less paper than the 7 pt floor")
    big = tef.chart_note_overlap("right", 6.0, 4.0, 200, 0.0, 24.0)
    assert big is not None and big.overlap_mm > auto.overlap_mm


# --------------------------------------------------------------------------
# The chart note / settings stamp (K1, K2)
# --------------------------------------------------------------------------

def _sizes_asked_for(monkeypatch, **kw) -> list[int]:
    """Every font size `_render_fitted_rotated_line` actually asks for."""
    seen: list[int] = []
    real = tm._pick_font

    def spy(size_px, family=""):
        seen.append(int(size_px))
        return real(size_px, family)

    monkeypatch.setattr(tm, "_pick_font", spy)
    tm._render_fitted_rotated_line(_NOTE, 3000, kw.pop("strip_w", 14),
                                   np.uint8, 3,
                                   anchor_px=tm._NOTE_PATCH_GAP_PX, **kw)
    return seen


def test_auto_shrinking_stops_at_the_floor(monkeypatch):
    """A strip far too narrow for the floor still gets a line at the floor."""
    sizes = _sizes_asked_for(monkeypatch, strip_w=14, dpi=200.0)
    assert sizes, "nothing was rendered"
    floor = tef.pt_to_px(tef.AUTO_SHRINK_FLOOR_PT, 200.0)
    assert min(sizes) >= floor, (
        f"the note shrank to {tef.px_to_pt(min(sizes), 200.0):.2f} pt on a "
        f"14 px strip; the floor is {tef.AUTO_SHRINK_FLOOR_PT:.0f} pt "
        f"({floor} px at 200 dpi)")


def test_auto_still_shrinks_while_there_is_room(monkeypatch):
    """The floor must not turn into a fixed size: a wide strip still fits."""
    # Both strips must be above the floor (19 px at 200 dpi) and below
    # the renderer's own 28 px starting cap, or neither number moves.
    wide = _sizes_asked_for(monkeypatch, strip_w=60, dpi=200.0)
    narrow = _sizes_asked_for(monkeypatch, strip_w=26, dpi=200.0)
    assert max(narrow) < max(wide), (
        "auto no longer adapts the size to the strip it is given")


def test_a_typed_size_is_used_exactly_and_never_shrunk(monkeypatch):
    sizes = _sizes_asked_for(monkeypatch, strip_w=14, dpi=200.0, size_pt=12.0)
    want = tef.pt_to_px(12.0, 200.0)
    assert set(sizes) == {want}, (
        f"a typed 12 pt was rendered at {sorted(set(sizes))} px, not {want}")


def test_a_typed_size_below_the_floor_works(monkeypatch):
    """*"Manually setting size below 8pt should be working fine also."*"""
    sizes = _sizes_asked_for(monkeypatch, strip_w=40, dpi=200.0, size_pt=6.0)
    want = tef.pt_to_px(6.0, 200.0)
    assert set(sizes) == {want}, (
        f"a typed 6 pt was raised to {sorted(set(sizes))} px, not kept at {want}")


def test_the_sheet_text_font_reaches_the_note():
    """The face is the Sheet text frame's Font, not the stamper's own."""
    a = tm._pick_font(24, "JetBrains Mono")
    b = tm._pick_font(24, "Inter")
    assert a.getname() != b.getname(), (
        f"two different Sheet-text fonts rendered the same face: {a.getname()}")
    plain = tm._pick_font(24)
    assert plain is not None, "the no-family fallback stopped working"


def test_the_note_is_drawn_in_the_family_it_is_given(monkeypatch):
    """…and the family travels all the way into the renderer."""
    seen: list[str] = []
    real = tm._pick_font

    def spy(size_px, family=""):
        seen.append(family)
        return real(size_px, family)

    monkeypatch.setattr(tm, "_pick_font", spy)
    tm._render_fitted_rotated_line(_NOTE, 3000, 40, np.uint8, 3,
                                   anchor_px=tm._NOTE_PATCH_GAP_PX,
                                   font_family="JetBrains Mono")
    assert seen and set(seen) == {"JetBrains Mono"}, seen


def test_the_builder_hands_the_stamper_the_sheet_text_font_and_size(
        tmp_path, monkeypatch):
    """`chart_creator` must read them off the layout recipe (K2)."""
    import tifffile
    from workflow.chart_creator import ChartParams
    from workflow.layout_engine.presets import LayoutRecipe

    from tests.test_chart_creator import _make_creator

    creator, _ = _make_creator(tmp_path)
    run = creator._file_mgr.project().current_run()
    run.ensure_dir()
    (run.dir / f"{run.stem}.ti1").write_text("NUMBER_OF_SETS 484\n",
                                             encoding="utf-8")
    tiff = run.dir / f"{run.stem}_01.tif"
    tifffile.imwrite(str(tiff), np.zeros((100, 100, 3), np.uint8),
                     resolution=(200, 200), resolutionunit="INCH")

    seen: list[tuple] = []
    monkeypatch.setattr(
        tm, "stamp_chart_metadata",
        lambda tiffs, lines, edge=0.0, band=0.0, family="", size_pt=0.0:
            seen.append((family, size_pt)))

    rec = LayoutRecipe()
    rec.chart_text_font = "JetBrains Mono"
    rec.chart_text_size_mm = 12.0 * 25.4 / 72.0          # 12 pt
    params = ChartParams(instrument="i1", paper="A4", patches=100,
                         chart_notes="a note", stamp_commands=False,
                         is_manual=True)
    params.layout_recipe = rec
    creator._stamp_tiff_metadata([tiff], params)

    assert seen, "the stamper was never called"
    family, size_pt = seen[0]
    assert family == "JetBrains Mono", family
    assert abs(size_pt - 12.0) < 0.01, size_pt


# --------------------------------------------------------------------------
# The clip border's own text (K6)
# --------------------------------------------------------------------------

def _clip_sizes(monkeypatch, **kw) -> list[int]:
    seen: list[int] = []
    real = raster._font

    def spy(px, family=raster.DEFAULT_INDICATOR_FONT, bold=False, italic=False):
        seen.append(int(px))
        return real(px, family, bold, italic)

    monkeypatch.setattr(raster, "_font", spy)
    raster._vtext(kw.pop("text", "one\ntwo\nthree\nfour"), "Inter",
                  kw.pop("width_px", 60), kw.pop("height_px", 2000), **kw)
    return seen


#: **THE WIDTH `_vtext` IS HANDED IS THE BAND LESS TWICE "Clip".**
#: `geometry.clip_area_px` insets the band by the "Text distance from edge" ->
#: Clip reserve on both of its long sides before the text is drawn into it, so
#: Knut's 16 mm band with Clip at 4 mm gives the text 8 mm, not 16. A test that
#: passes the whole 16 mm never reaches the floor at all: four lines then fit at
#: 25 px and the fit loop breaks on its first pass, which is how an earlier
#: version of this file stayed green with the floor mutated back to 8 PIXELS.
def _clip_area_px(band_mm: float, clip_mm: float, dpi: float) -> int:
    return max(1, int(round((band_mm - 2.0 * clip_mm) * dpi / 25.4)))


def test_the_clip_border_text_stops_shrinking_at_the_floor(monkeypatch):
    """A 16 mm band with four lines, which is Knut's own case."""
    sizes = _clip_sizes(monkeypatch, width_px=_clip_area_px(16.0, 4.0, 200.0),
                        dpi=200.0)
    floor = tef.pt_to_px(tef.AUTO_SHRINK_FLOOR_PT, 200.0)
    assert min(sizes) >= floor, (
        f"the clip text shrank to {tef.px_to_pt(min(sizes), 200.0):.2f} pt; "
        f"the floor is {tef.AUTO_SHRINK_FLOOR_PT:.0f} pt "
        f"({floor} px at 200 dpi)")


def test_the_clip_floor_is_the_same_paper_at_every_resolution(monkeypatch):
    """The floor it replaced was EIGHT PIXELS: 2.9 pt at 200 dpi, 0.96 at 600."""
    for dpi in (200.0, 600.0):
        sizes = _clip_sizes(monkeypatch,
                            width_px=_clip_area_px(16.0, 4.0, dpi), dpi=dpi)
        got = tef.px_to_pt(min(sizes), dpi)
        # A whole pixel cannot be split, so the floor in points is only ever a
        # pixel's worth low; what must NOT happen is the shortfall growing with
        # the resolution, which is exactly what a pixel floor does.
        assert got >= tef.AUTO_SHRINK_FLOOR_PT - tef.px_to_pt(1, dpi), (
            f"the clip text hit {got:.2f} pt at {dpi} dpi")


def test_a_typed_clip_size_is_printed_as_typed(monkeypatch):
    """Including below the floor, and without the fit loop stepping it down."""
    for pt in (6.0, 20.0):
        px = tef.pt_to_px(pt, 200.0)
        sizes = _clip_sizes(monkeypatch,
                            width_px=_clip_area_px(16.0, 4.0, 200.0),
                            dpi=200.0, size_px=px)
        assert set(sizes) == {px}, (
            f"a typed {pt:.0f} pt clip size was rendered at "
            f"{sorted(set(sizes))} px, not {px}")


def test_auto_clip_text_still_fits_a_roomy_band(monkeypatch):
    """The floor must not become the only size a band ever gets."""
    wide = _clip_sizes(monkeypatch, width_px=800, dpi=200.0)
    narrow = _clip_sizes(monkeypatch,
                         width_px=_clip_area_px(16.0, 4.0, 200.0), dpi=200.0)
    assert max(wide) > max(narrow), (
        "auto no longer grows the clip text to fill a wide band")


def test_the_clip_inset_is_the_one_the_geometry_applies():
    """"Clip" is capped at a fifth of the band, and taken off ONE side.

    `geometry.clip_area_mm`: ``inset = min(text_edge_clip, clip_w * 0.2)``, and
    ``width = clip_w - inset``. The first version of the predicate took the
    TYPED value off BOTH sides, which on Knut's 16 mm band with Clip at 4 mm
    predicted 8.0 mm where the renderer gives 12.8.
    """
    assert tef.clip_inset_asked_mm(16.0, 4.0) == pytest.approx(3.2), (
        "the fifth-of-the-band cap is not applied")
    assert tef.clip_inset_asked_mm(26.0, 4.0) == pytest.approx(4.0), (
        "a roomy band should use the typed value")
    # Described no content, nothing is surrendered: this is what every caller
    # that only wants the band's placement gets.
    assert tef.clip_content_inset_mm(16.0, 4.0) == pytest.approx(3.2)
    assert tef.clip_content_inset_mm(26.0, 4.0) == pytest.approx(4.0)
    # Four lines at the floor take 11.85 mm and 16.0 less 3.2 is 12.8, so the
    # reserve survives whole and the band's room is what the renderer gives it.
    assert tef.clip_text_needed_mm(4) == pytest.approx(
        4 * 1.2 * tef.pt_to_mm(tef.AUTO_SHRINK_FLOOR_PT))
    assert tef.clip_content_inset_mm(16.0, 4.0, 4) == pytest.approx(3.2)
    assert tef.clip_text_push(16.0, 4.0, 4) is None
    assert tef.clip_text_squeeze(16.0, 4.0, 4) is None


def test_the_clip_squeeze_predicate_agrees_with_the_geometry_module():
    """Measured against the real `clip_area_mm`, not against a repeated rule."""
    from workflow.layout_engine import geometry, instruments
    from workflow.layout_engine.presets import LayoutRecipe
    for band in (16.0, 24.0, 40.0):
        r = LayoutRecipe()
        r.instrument, r.paper, r.layout_mode = "CM", "A4", "area_first"
        r.clip_border, r.clip_border_width_mm = True, band
        r.clip_side, r.clip_content_mode = "right", "text"
        r.text_edge_clip_mm = 4.0
        r.margin_right = max(band, 10.0)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        area = geometry.clip_area_mm(g, 297.0, 210.0)
        assert area is not None, band
        zone = g.lbord + g.border
        got = zone - tef.clip_content_inset_mm(zone, 4.0)
        assert got == pytest.approx(area[2], abs=0.01), (
            f"band {band}: the predicate says {got:.2f} mm and the geometry "
            f"gives the content {area[2]:.2f} mm")


def test_the_clip_squeeze_predicate_matches_the_renderer():
    """It fires only when the WHOLE band is too narrow.

    Since Knut's ruling of 2026-09-11 the band may take the page-edge reserve
    for text it cannot otherwise hold, so "does not fit" means "does not fit
    even then". Four lines at the 7 pt floor take 11.85 mm: an 11.0 mm band is
    too small however the reserve is spent, and a 12.0 mm one is not.
    """
    o = tef.clip_text_squeeze(11.0, 4.0, 4, 0.0, "right")
    assert o is not None, "an 11 mm band with four lines at the floor is silent"
    assert o.available_mm == pytest.approx(11.0), (
        "the whole band must be offered before this warns")
    assert o.needed_mm > 11.0
    assert tef.clip_text_squeeze(12.0, 4.0, 4, 0.0, "right") is None, (
        "a 12 mm band holds four lines once the reserve is given up")
    # Knut's own ColorMunki preset, 24 mm with the same four lines, is SILENT,
    # which is what he reports: at 24 mm the clip-border text is fine.
    assert tef.clip_text_squeeze(24.0, 4.0, 4, 0.0, "right") is None
    # A wide band with one line is silent.
    assert tef.clip_text_squeeze(60.0, 4.0, 1, 0.0, "left") is None
    # No text is no warning.
    assert tef.clip_text_squeeze(16.0, 4.0, 0, 0.0, "left") is None
    # A typed size that DOES fit is silent; one that does not, warns.
    assert tef.clip_text_squeeze(16.0, 4.0, 4, 4.0, "left") is None
    assert tef.clip_text_squeeze(16.0, 4.0, 4, 20.0, "left") is not None
