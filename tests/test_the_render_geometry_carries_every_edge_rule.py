"""#182, third challenge round: the geometry the RENDERER gets is the one the
panel promised, and a typed 0 in "Text distance from edge" means 4 mm to every
caller and not only to the ones that go through ``build_kwargs()``.

Two faults, both measured on screen by driving the real app and reading the ink
on the TIFFs it wrote (`scripts/drive_182_challenge_three.py`).

1. ``chart.build_chart`` assembles the dict for
   ``instruments.geom_from_build_kwargs`` BY HAND, and it left out the five
   ruler-helper-marker keys. They are in ``GEOM_BUILD_KEYS``, ``build()``
   takes them and ``geom_from_build_kwargs`` copies them onto the ``Geom`` --
   but only from the dict it is handed, so the geometry that laid out every
   real sheet was built with ``helper_markers=False`` while the same markers
   were passed to ``render_pages`` and drawn. The whole of #182's marker
   reserve reached the panel, the capacity estimate and the note stamper and
   reached the paper nowhere. ColorMunki / A4 / 200 dpi, markers 4.0 + 2.0 mm,
   "Clip" and "T" at 4.0, each element isolated against a control sheet:

   =========================== ============ ===========
   measured on the sheet        before       after
   =========================== ============ ===========
   clip band text, from the     4.70 mm      7.62 mm
   left page edge
   its pixels inside the        917          0
   4.0-6.0 mm dash band
   strip letters, from the top  5.97 mm      9.02 mm
   patch block, from the left   14.35 mm     17.40 mm
   (the panel said 17.38 mm
   both times)
   =========================== ============ ===========

2. ``LayoutRecipe.build_kwargs()`` writes ``self.text_edge_clip_mm or 4.0``, so
   a typed 0 is 4 mm for everything the engine draws, and the panel says so:
   *"A distance of 0.0 mm is not used. ChromIQ prints at 4.0 mm instead, so no
   text is set hard against the paper edge."*
   ``chart_creator._stamp_tiff_metadata`` read the three fields raw, so the
   run's chart note was the one piece of text that DID go hard against the
   edge: with all three boxes typed to 0 its ink ran from 1.40 mm of the top
   and 1.14 mm of the bottom (4.83 and 4.70 at a typed 4.0), and on a
   right-hand band its right end moved from 20.70 mm to 17.14 mm, while the
   clip band's text, the strip letters and the bottom sheet text did not move
   by a pixel.
"""
from __future__ import annotations

import pytest

from workflow.layout_engine import chart as le_chart
from workflow.layout_engine import instruments
from workflow.layout_engine.presets import TEXT_EDGE_DEFAULT_MM, LayoutRecipe


# --------------------------------------------------------------- the markers

MARKER_KEYS = ("helper_markers", "helper_marker_edge", "helper_marker_len",
               "helper_markers_top_bottom", "helper_markers_sides")


def test_the_render_geometry_is_told_about_the_helper_markers(monkeypatch,
                                                              tmp_path):
    ti1 = tmp_path / "t.ti1"
    ti1.write_text("CTI1\nBEGIN_DATA_FORMAT\nSAMPLE_ID RGB_R RGB_G RGB_B\n"
                   "END_DATA_FORMAT\nNUMBER_OF_SETS 1\nBEGIN_DATA\n"
                   "1 100 100 100\nEND_DATA\n", encoding="utf-8")
    r = LayoutRecipe(instrument="CM", paper="A4", helper_markers=True,
                     helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0,
                     helper_markers_top_bottom=True, helper_markers_sides=True)
    seen: dict = {}
    real = instruments.geom_from_build_kwargs

    def spy(kw, thresholds=None):
        if not seen:
            seen.update(kw)
        return real(kw, thresholds)

    monkeypatch.setattr(le_chart.instruments, "geom_from_build_kwargs", spy)

    class _Stop(RuntimeError):
        pass

    monkeypatch.setattr(le_chart.geometry, "compute",
                        lambda *a, **k: (_ for _ in ()).throw(_Stop()))
    with pytest.raises(_Stop):
        le_chart.build_chart(ti1, tmp_path / "out", **r.build_kwargs())

    missing = [k for k in MARKER_KEYS if k not in seen]
    assert not missing, (
        "chart.build_chart builds the render geometry without "
        f"{missing}; the markers are then False on the Geom and every #182 "
        "reserve is computed as if no dash were drawn")
    assert seen["helper_markers"] is True
    assert float(seen["helper_marker_edge"]) == pytest.approx(4.0)
    assert float(seen["helper_marker_len"]) == pytest.approx(2.0)


def test_the_geom_the_renderer_uses_keeps_the_side_dashes_clear():
    """The end of the same chain: a Geom built the way the renderer builds one
    answers 7.0 mm on the side edge and 7.0 mm on the top, not 4.0."""
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import geometry

    r = LayoutRecipe(instrument="CM", paper="A4", helper_markers=True,
                     helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0,
                     text_edge_clip_mm=4.0, text_edge_top_mm=4.0)
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    assert g.helper_markers is True
    assert tef.geom_side_text_edge_mm(g) == pytest.approx(7.0)
    assert geometry.strip_label_reserve_mm(g) == pytest.approx(7.0)


# ------------------------------------------------------------- a typed zero

@pytest.mark.parametrize("field, prop", [
    ("text_edge_mm", "effective_text_edge_mm"),
    ("text_edge_top_mm", "effective_text_edge_top_mm"),
    ("text_edge_clip_mm", "effective_text_edge_clip_mm"),
])
def test_a_typed_zero_reads_as_the_default_everywhere(field, prop):
    zero = LayoutRecipe(**{field: 0.0})
    assert getattr(zero, prop) == pytest.approx(TEXT_EDGE_DEFAULT_MM)
    typed = LayoutRecipe(**{field: 2.5})
    assert getattr(typed, prop) == pytest.approx(2.5)


def test_build_kwargs_and_the_properties_cannot_disagree():
    """`build_kwargs()` is where the substitution used to be spelled out three
    times; it must now be the same answer the properties give."""
    for value in (0.0, 1.0, 4.0, 30.0):
        r = LayoutRecipe(text_edge_mm=value, text_edge_top_mm=value,
                         text_edge_clip_mm=value)
        kw = r.build_kwargs()
        assert kw["text_edge"] == pytest.approx(r.effective_text_edge_mm)
        assert kw["text_edge_top"] == pytest.approx(r.effective_text_edge_top_mm)
        assert kw["text_edge_clip"] == pytest.approx(
            r.effective_text_edge_clip_mm)


def test_the_note_stamper_gets_the_distance_the_sheet_uses(monkeypatch,
                                                           tmp_path):
    """A typed 0 must reach `stamp_chart_metadata` as 4 mm on all three edges.

    The three arguments are the side reserve and the note's two ends. Before
    this they were 0.0 / 0.0 / 0.0 for a recipe whose sheet used 4.0.
    """
    from workflow import chart_creator as cc
    from workflow import tiff_metadata

    seen: dict = {}

    def spy(tiffs, lines, text_edge_mm=0.0, clip_band_mm=0.0, font_family="",
            size_pt=0.0, clip_reach_mm=-1.0, gap_mm=0.0,
            text_edge_top_mm=-1.0, text_edge_bottom_mm=-1.0,
            patch_gap_mm=0.0):
        seen.update(side=text_edge_mm, top=text_edge_top_mm,
                    bottom=text_edge_bottom_mm)

    # Patched on the MODULE the stamper is imported from: `_stamp_tiff_metadata`
    # does its import inside the function body, so a name bound on
    # `chart_creator` would never be looked at.
    monkeypatch.setattr(tiff_metadata, "stamp_chart_metadata", spy)

    rec = LayoutRecipe(instrument="CM", paper="A4", text_edge_clip_mm=0.0,
                       text_edge_top_mm=0.0, text_edge_mm=0.0,
                       helper_markers=False)

    class _Params:
        layout_recipe = rec
        chart_layout_name = ""
        instrument = "CM"
        paper = "A4"
        left_clip_info = False
        disable_left_border = False
        chromiq_clip_style = False
        chart_notes = "a note down the right margin"
        stamp_commands = False
        cal_target = False
        patches = 1

    creator = cc.ChartCreator.__new__(cc.ChartCreator)
    creator._should_use_engine = lambda _p: True
    creator._count_patches_in_ti1 = lambda _p: 1
    creator._file_mgr = type("FM", (), {
        "chart_stem": staticmethod(lambda cal_target=False: "stem")})()

    creator._stamp_tiff_metadata([tmp_path / "page1.tif"], _Params())

    assert seen, "the stamper was never called"
    assert seen["side"] == pytest.approx(TEXT_EDGE_DEFAULT_MM)
    assert seen["top"] == pytest.approx(TEXT_EDGE_DEFAULT_MM)
    assert seen["bottom"] == pytest.approx(TEXT_EDGE_DEFAULT_MM)
