"""Golden tests for the layout-engine packing math.

Each expected (steps, passes, total) was captured from a live ``printtarg``
run (Argyll 3.5.0) on a 60-patch RGB ``.ti1`` — see issue #93's feasibility
matrix. If these drift, the engine no longer matches printtarg's geometry.
"""
import pytest

from workflow.layout_engine import geometry, instruments

A4 = (210.0, 297.0)
A4R = (297.0, 210.0)

# key, paper, hflag, spacer_on, pscale, npat, steps, passes, total
CASES = [
    ("i1", A4,  False, True,  1.0,   60, 21, 3, 63),
    ("p3", A4,  False, True,  1.0,   60,  9, 7, 63),
    ("CM", A4,  False, True,  1.0,   60, 15, 4, 60),
    ("CM", A4,  True,  True,  1.0,   60, 15, 4, 60),   # -h (rig): same logical grid
    ("41", A4,  False, True,  1.0,   60, 25, 3, 75),
    ("51", A4,  False, True,  1.0,   60, 19, 4, 76),
    ("SS", A4,  False, True,  1.0,   60, 39, 2, 60),
    ("SS", A4,  True,  True,  1.0,   60, 45, 2, 60),   # hex
    ("i1", A4R, False, True,  1.0,   60, 16, 4, 64),
    ("i1", A4,  False, False, 1.0,   60, 24, 3, 72),   # -n no spacers
    ("i1", A4,  False, True,  0.857, 60, 25, 3, 75),   # -a 0.857
    ("i1", A4,  False, True,  1.5,   60, 14, 5, 70),   # -a 1.5
]


@pytest.mark.parametrize("key,paper,hflag,spacer,pscale,npat,steps,passes,total", CASES)
def test_matches_printtarg(key, paper, hflag, spacer, pscale, npat, steps, passes, total):
    # printtarg brackets every strip with a leading + trailing spacer, so the
    # parity comparison uses edge_spacers=True. The engine's default (edge off)
    # reclaims those two gaps and packs denser — covered separately (#93).
    geom = instruments.build(key, hflag=hflag, spacer_on=spacer, pscale=pscale,
                             edge_spacers=True)
    lay = geometry.compute(geom, paper[0], paper[1], npat)
    assert lay.steps_in_pass == steps
    assert lay.passes == passes
    assert lay.total_patches == total
    assert lay.padding == total - npat
    assert lay.pages == 1


def test_patches_per_sheet_i1_a4():
    geom = instruments.build("i1")
    # 21 steps down × 22 strips across = 462. printtarg reports 441 because it
    # reserves a ~5 mm page-label column; the engine reclaims that dead column
    # (the page label now lives in chart/clip text via placeholders), so it fits
    # MORE than printtarg here — strictly ≥ printtarg, by design (#93).
    assert geometry.patches_per_sheet(geom, *A4) == 462


def test_tiny_paper_raises():
    geom = instruments.build("i1")
    with pytest.raises(geometry.LayoutError):
        geometry.compute(geom, 40.0, 40.0, 60)


def test_delegated_instrument_rejected():
    with pytest.raises(ValueError):
        instruments.build("isis")


def test_independent_margins_reduce_capacity():
    base = instruments.build("i1")
    wide = instruments.build("i1", margins=(20.0, 20.0, 20.0, 20.0))
    # Top follows the box; the LEFT is floored to the clip-border width (26 mm),
    # since the clip band lives inside the clip-side margin (Knut beta-13).
    assert wide.margin_t == 20.0 and wide.margin_l == 26.0
    assert (geometry.patches_per_sheet(wide, *A4)
            < geometry.patches_per_sheet(base, *A4))
    # default margins (None) leave geometry identical to the uniform border
    assert (geometry.patches_per_sheet(instruments.build("i1"), *A4)
            == geometry.patches_per_sheet(instruments.build("i1", margins=(6.0,)*4), *A4))


def test_patch_size_override():
    g = instruments.build("i1", patch_w=12.0, patch_h=12.0)
    assert g.plen == 12.0 and g.pwid == 12.0
    # bigger patches → fewer fit per sheet
    assert (geometry.patches_per_sheet(g, *A4)
            < geometry.patches_per_sheet(instruments.build("i1"), *A4))


def test_colormunki_density_levels_increase_capacity():
    # ColorMunki: normal < high (rig, printtarg -h) < extra-high (ChromIQ ext).
    cap = []
    for d in (1, 2, 3):
        geom = instruments.build("CM", density=d)
        cap.append(geometry.patches_per_sheet(geom, *A4))
    assert cap[0] < cap[1] < cap[2]
    # level 2 reproduces printtarg's rig row spacing (13.7 mm) exactly
    assert instruments.build("CM", density=2).rrsp == 13.7
    # hflag back-compat still maps to the rig (density 2)
    assert instruments.build("CM", hflag=True).rrsp == 13.7


def test_colormunki_extra_high_is_native_dense_colormunki():
    """ColorMunki extra-high (density=3) is a NATIVE dense ColorMunki strip layout
    — our engine makes the small (~10.4 mm) patches directly, with the ColorMunki
    tag, NOT by borrowing the i1Pro geometry the old printtarg trick had to use
    (#93, Knut/Sebastian)."""
    g3 = instruments.build("CM", density=3, border=5.0)
    assert g3.key == "CM"
    assert g3.target_name == instruments.TARGET_INSTRUMENT_NAME["CM"]
    # Small, readable patches packed densely (denser than the rig, density 2).
    assert g3.pwid < instruments.build("CM", density=2).pwid
    assert (geometry.patches_per_sheet(g3, *A4)
            > geometry.patches_per_sheet(instruments.build("CM", density=2), *A4))


def test_colormunki_extra_high_patch_size_scales_with_pscale():
    """Extra-high honours the patch scale (Basti): the native size (pscale 1.0)
    is 10.4 x 13.0 mm with a 1.3 mm spacer — the readable size printtarg's -ii1
    triple-density trick gives at its -a1.3 default — and pscale grows/shrinks
    the patch AND its spacer from there (the leader/trailer furniture stays
    fixed), so a denser preset reproduces printtarg at any -a. The
    printtarg-> engine scale conversion (-a / 1.3) lives in chart_creator, so
    Guided (which passes -a1.3) still lands on the native size — proven in
    test_guided_and_manual_colormunki_extra_high_same_patch_geometry."""
    native = instruments.build("CM", density=3, border=5.0, pscale=1.0)
    assert (round(native.pwid, 1), round(native.plen, 1), round(native.pspa, 1)) \
        == (10.4, 13.0, 1.3)
    dense = instruments.build("CM", density=3, border=5.0, pscale=0.831)
    # A preset's -a1.08 → engine pscale 0.831 → printtarg's ~8.6 mm patch.
    assert round(dense.pwid, 2) == round(0.831 * 10.4, 2)
    assert round(dense.plen, 2) == round(0.831 * 13.0, 2)
    assert round(dense.pspa, 2) == round(0.831 * 1.3, 2)   # spacer scales too
    # Denser patch → strictly more patches per sheet than the native size.
    A4L = (297.0, 210.0)
    assert (geometry.patches_per_sheet(dense, *A4L)
            > geometry.patches_per_sheet(native, *A4L))


def test_colormunki_density_in_area_first():
    """In area-first the two area fields own the grid. Density 1 vs 2 (both the
    ColorMunki grid) stay inert; extra-high (3) is a denser layout so it differs.
    All stay tagged ColorMunki (no i1 borrow)."""
    def grid(d):
        g = instruments.geom_from_build_kwargs(
            {"instrument": "CM", "paper": "A4", "layout_mode": "area_first",
             "area_method": "by_width", "area_min_patch": 8.0, "density": d})
        return geometry.patches_per_sheet(g, *A4), g.key, g.target_name
    assert grid(1)[:2] == grid(2)[:2]          # grid densities inert
    assert grid(3)[1] == "CM"                  # native ColorMunki, not i1
    assert grid(3)[0] != grid(1)[0]            # denser → count differs
    # tag stays ColorMunki across all densities
    assert grid(3)[2] == instruments.TARGET_INSTRUMENT_NAME["CM"]


def test_clip_border_width_drives_lbord():
    # Default reserved clip zone is 26 mm; lbord = zone − margin.
    assert instruments.build("i1", border=6.0).lbord == pytest.approx(20.0)
    # Widening the zone widens the extra clip strip.
    assert instruments.build("i1", border=6.0, clip_border_width=40.0).lbord \
        == pytest.approx(34.0)
    # Margin already past the zone ⇒ no extra strip (never negative).
    assert instruments.build("i1", border=30.0, clip_border_width=26.0).lbord == 0.0
    # No clip border (-L) ⇒ no reserved zone regardless of width.
    assert instruments.build("i1", nolpcbord=True, clip_border_width=40.0).lbord == 0.0
    # p3 honours it too; non-clip instruments are unaffected (lbord stays 0).
    assert instruments.build("p3", clip_border_width=40.0).lbord == pytest.approx(34.0)
    assert instruments.build("CM", clip_border_width=40.0).lbord == 0.0


def test_clip_area_only_when_clip_border():
    # i1 with clip border → the full clip zone (26 mm) minus the printer-safe
    # inset, NOT shrunk by the patch margin, so the content stays wide (#93).
    inset = geometry.CLIP_CONTENT_INSET_MM
    a6 = geometry.clip_area_mm(instruments.build("i1", border=6.0), 297.0)
    a10 = geometry.clip_area_mm(instruments.build("i1", border=10.0), 297.0)
    assert a6 is not None
    assert a6[0] == pytest.approx(inset)              # starts at the inset
    assert a6[1] == pytest.approx(inset)              # full height: top inset only
    assert a6[2] == pytest.approx(26.0 - inset)       # full zone minus inset
    assert a6[3] == pytest.approx(297.0 - 2.0 * inset)  # full page height − insets
    # a larger patch margin must NOT shrink the clip content any more (Guided
    # used to come out narrower than Manual).
    assert a10[2] == pytest.approx(a6[2])
    # no clip border → no area.
    assert geometry.clip_area_mm(instruments.build("i1", nolpcbord=True), 297.0) is None
    assert geometry.clip_area_mm(instruments.build("CM"), 297.0) is None


def test_spacer_rects_match_render_flat_index():
    """spacer_rects_px flat indices + positions match what the renderer paints,
    so an editor click maps to the spacer the engine recolours (#93)."""
    import numpy as np
    from workflow.layout_engine import raster
    from workflow.layout_engine.ti1_reader import ColorTarget
    target = ColorTarget(color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=[((50.0, 50.0, 50.0), (40.0, 45.0, 50.0))
                                  for _ in range(60)])
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rects = geometry.spacer_rects_px(geom, 210.0, 297.0, lay, 150)
    assert rects and rects[0]["flat"] == 0
    res = raster.render_pages(target, lay, geom, seed=1, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=150,
                              spacer_overrides={rects[0]["flat"]: (255, 0, 255)})
    a = np.asarray(res.images[0])
    r0 = rects[0]
    assert tuple(a[r0["y"] + r0["h"] // 2, r0["x"] + r0["w"] // 2]) == (255, 0, 255)


def test_strip_indicator_gap_reduces_capacity_and_stays_in_bounds():
    """A larger strip-indicator gap must reduce the patch count to fit, never
    push patches off the usable area; a smaller gap fits more (#93)."""
    pw, ph = 210.0, 297.0
    prev = None
    for gap in (0.0, 40.0, 60.0, 90.0):
        g = instruments.build("i1", strip_indicator_gap=gap)
        lay = geometry.compute(g, pw, ph, 1000)
        pl = geometry.placement(g, pw, ph, lay)
        block_bottom = pl.y_of(lay.steps_in_pass - 1) + pl.plen
        usable_bottom = ph - max(g.margin_b, g.tspa)
        # the last patch in a pass never crosses the bottom usable edge
        assert block_bottom <= usable_bottom + 0.5, f"overflow at gap={gap}"
        # capacity is monotonically non-increasing as the gap grows
        if prev is not None:
            assert lay.patches_per_page <= prev, f"gap={gap} didn't reduce count"
        prev = lay.patches_per_page
    # a big gap genuinely fits fewer than no gap
    g0 = instruments.build("i1", strip_indicator_gap=0.0)
    g9 = instruments.build("i1", strip_indicator_gap=90.0)
    assert (geometry.compute(g9, pw, ph, 1000).patches_per_page
            < geometry.compute(g0, pw, ph, 1000).patches_per_page)


def test_geom_from_build_kwargs_honours_clip_width():
    """The shared geom builder must apply clip_border_width so capacity
    estimates match the render — a wider clip fits fewer patches (#93)."""
    from workflow.layout_engine.presets import LayoutRecipe
    pw, ph = 210.0, 297.0
    def cap(width):
        r = LayoutRecipe(instrument="i1", paper="A4", clip_border=True,
                         clip_border_width_mm=width)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        return geometry.patches_per_sheet(g, pw, ph)
    wide, narrow = cap(60.0), cap(26.0)
    assert wide < narrow, f"wider clip ({wide}) should fit fewer than default ({narrow})"
    # and it matches building the geom the same way the renderer does
    r = LayoutRecipe(instrument="i1", paper="A4", clip_border=True,
                     clip_border_width_mm=60.0)
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    assert g.lbord == pytest.approx(60.0 - r.border)


def test_furniture_reserves_affect_capacity():
    """Rendered furniture (big/rotated indicators, underline, sheet text, stamp)
    must reserve space so capacity reflects it — while a default chart keeps its
    printtarg-parity count (#93)."""
    from workflow.layout_engine.presets import LayoutRecipe
    paper = "210x150"                     # short page → height-bound, not mxrowl
    w, h = geometry_papers(paper)

    def cap(**over):
        # Furniture reserves only apply in printtarg-style patch-first mode; law
        # mode (area-first OR "Use instrument margins") treats the margin box as the
        # law and puts furniture inside it (Knut), so pin patch-first with user
        # margins to exercise the reserve path.
        r = LayoutRecipe(instrument="i1", paper=paper, layout_mode="patch_first",
                         use_instrument_margins=False, **over)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        return geometry.patches_per_sheet(g, w, h)

    base = cap()
    # A large indicator reserves a taller label band → fewer patches fit
    assert cap(indicator_size_mm=30.0) < base
    # Underline / sheet text / stamp reserve space too (≤: they may sit in the
    # page's slack on a given size, but never exceed the no-furniture count)
    assert cap(underline_mode="black", underline_thickness_mm=3.0,
               underline_gap_mm=5.0) <= base
    assert cap(stamp_command=True, chart_text="{project}") <= base
    # an oversized stack of furniture clearly drops the count
    assert cap(indicator_size_mm=18.0, underline_mode="black",
               underline_thickness_mm=3.0, underline_gap_mm=6.0,
               stamp_command=True, chart_text="x") < base
    # Turning strip labels OFF, or choosing an explicit SMALL font, reclaims the
    # label band for more patches; auto size stays at the printtarg floor (#93).
    assert cap(show_strip_indicators=False) > base
    assert cap(indicator_size_mm=2.5) > base
    # A bare build() Geom (no furniture info) is unchanged from the default
    bare = geometry.patches_per_sheet(instruments.build("i1"), *geometry_papers("A4"))
    assert bare == geometry.patches_per_sheet(
        instruments.geom_from_build_kwargs(
            LayoutRecipe(instrument="i1", paper="A4",
                         layout_mode="patch_first").build_kwargs()),
        *geometry_papers("A4"))


def geometry_papers(code):
    from workflow.layout_engine import papers
    return papers.dimensions_mm(code)


def test_strip_gap_reduces_capacity():
    """Extra gap between strips widens the row pitch, so fewer strips (and
    patches) fit; 0 is the default (#93)."""
    base = instruments.build("i1")
    wide = instruments.build("i1", strip_gap=4.0)
    assert wide.rrsp == base.rrsp + 4.0
    assert (geometry.compute(wide, *A4, 100_000).patches_per_page
            < geometry.compute(base, *A4, 100_000).patches_per_page)


def test_page_label_column_reclaimed():
    """The page-label column (printtarg's pglth) is no longer reserved — its info
    lives in chart text / clip text via placeholders, so the ~5 mm is reclaimed
    for patches on every laid-out instrument (#93)."""
    for key in ("i1", "p3", "CM", "41", "SS", "51"):
        assert instruments.build(key).dopglabel is False


def test_strip_label_offset_does_not_change_capacity():
    """The strip-label offset only repositions the labels (handled at render
    time); it doesn't live in the geometry, so capacity is unchanged (#93)."""
    # offset is a render-time nudge; geometry/capacity stay put
    assert geometry.patches_per_sheet(instruments.build("i1"), *A4) == \
        geometry.patches_per_sheet(instruments.build("i1"), *A4)


def test_patch_area_alignment_positions_block_without_changing_capacity():
    """Patch-area alignment shifts the block within the usable area only — the
    patch count is identical, but the realised margins move toward the chosen
    anchor (#93). Default 'center-left' reproduces the prior placement."""
    def geom(align):
        return instruments.build("i1", patch_area_align=align)

    cap = geometry.patches_per_sheet(geom("center-left"), *A4)
    for align in ("top-left", "bottom-right", "center", "top-right"):
        assert geometry.patches_per_sheet(geom(align), *A4) == cap

    def insets(align):
        g = geom(align)
        lay = geometry.compute(g, *A4, cap)
        return geometry.realized_margins_mm(g, *A4, lay)  # (L, R, T, B)

    L0, R0, T0, B0 = insets("center-left")          # the prior default
    Lt, Rt, Tt, Bt = insets("top-left")
    Lb, Rb, Tb, Bb = insets("bottom-left")
    Lr, Rr, Tr, Br = insets("top-right")
    # top alignment → smaller top inset, larger bottom; bottom → the reverse
    assert Tt < T0 and Bt > B0
    assert Tb > T0 and Bb < B0
    # right alignment → smaller right inset, larger left
    assert Rr < R0 and Lr > L0


def test_align_default_matches_legacy_placement():
    """'center-left' must reproduce the exact placement the engine used before
    the alignment option existed (vertically centred, left-anchored)."""
    g = instruments.build("i1")
    assert g.patch_area_align == "center-left"
    lay = geometry.compute(g, *A4, 60)
    p = geometry.placement(g, *A4, lay)
    # left-anchored: patches start at the (clip-floored) left margin. The clip now
    # lives inside that margin, so x0 == margin_l (== 26 mm for the default clip),
    # the same absolute position as the old additive border+lbord (Knut beta-13).
    assert abs(p.x0 - g.margin_l) < 1e-9
    assert g.margin_l == 26.0


def test_area_first_fits_requested_grid():
    """Area-first sizes the patches so the requested columns/rows fill the usable
    area — capacity and the laid-out grid match (one chokepoint) (#93)."""
    from workflow.layout_engine.presets import default_recipe
    from dataclasses import replace

    def grid(**area):
        rec = replace(default_recipe("i1", "A4", mode="clip"),
                      layout_mode="area_first", area_method="by_grid", **area)
        g = instruments.geom_from_build_kwargs(rec.build_kwargs())
        lay = geometry.compute(g, *A4, geometry.patches_per_sheet(g, *A4))
        return lay.patches_per_page // lay.steps_in_pass, lay.steps_in_pass

    assert grid(area_cols=20, area_rows=30) == (20, 30)          # both pinned
    assert grid(area_cols=24)[0] == 24                           # columns pinned
    assert grid(area_rows=40)[1] == 40                           # rows pinned
    # ratio is height:width; with rows pinned, a taller ratio → narrower patches
    # → more columns fit.
    sq = grid(area_rows=40, area_ratio=1.0)[0]
    tall = grid(area_rows=40, area_ratio=2.0)[0]
    assert tall > sq


def test_colormunki_stagger_offsets_odd_strips_and_reserves_space():
    """ColorMunki 'offset every second strip' shifts odd strips down by ~half a
    patch and reserves hxeh so the count drops — independent of density (#93)."""
    plain = instruments.geom_from_build_kwargs({"instrument": "CM", "paper": "A4"})
    stag = instruments.geom_from_build_kwargs(
        {"instrument": "CM", "paper": "A4", "cm_stagger": True})
    assert plain.row_stagger_mm == 0 and stag.row_stagger_mm > 0
    assert stag.hxeh > 0                       # reservation for the overhang
    assert geometry.patches_per_sheet(stag, *A4) <= geometry.patches_per_sheet(plain, *A4)
    # odd strip's first patch sits lower than the even strip's by the stagger.
    lay = geometry.compute(stag, *A4, geometry.patches_per_sheet(stag, *A4))
    pr = geometry.patch_rects_px(stag, *A4, lay, 150)
    steps = lay.steps_in_pass
    even_y = next(r["y"] for r in pr if r["slot"] == 0)
    odd_y = next(r["y"] for r in pr if r["slot"] == steps)   # first patch of strip 1
    assert odd_y > even_y
    # decoupled from density: high density without the option does NOT stagger.
    hd = instruments.geom_from_build_kwargs(
        {"instrument": "CM", "paper": "A4", "density": 2})
    assert hd.row_stagger_mm == 0


def test_area_first_cols_pinned_rows_auto_fill_to_bottom():
    """Columns pinned + rows on auto: area-first grows the patch height so the
    rows fill the page down to the bottom margin/trailer, instead of leaving a
    big gap with square patches (#93, Knut beta-13)."""
    from workflow.layout_engine.presets import default_recipe
    from dataclasses import replace
    # area_ratio 1.0 (square, the UI default): rows-auto then grows the patch
    # height to the column width so the rows fill to the bottom.
    rec = replace(default_recipe("i1", "A4R", mode="clip"),
                  layout_mode="area_first", area_method="by_grid",
                  area_cols=18, area_rows=0, area_ratio=1.0,
                  margin_top=9.0, margin_bottom=9.0, margin_right=9.0)
    g = instruments.geom_from_build_kwargs(rec.build_kwargs())
    w, h = 297.0, 210.0
    lay = geometry.compute(g, w, h, geometry.patches_per_sheet(g, w, h))
    B = geometry.realized_margins_mm(g, w, h, lay)[1]
    # The rows reach the bottom: the gap collapses to the instrument trailer
    # (~tspa), nowhere near the old square-patch gap (Knut measured 33 mm).
    assert B < 13.0
    assert g.plen > g.pwid * 0.9            # patches grew vertically to fill


def test_area_first_by_grid_auto_dims_fill_at_natural_size():
    """by-grid with a dimension (or both) on auto picks the instrument's natural
    patch size for that dimension and fills the box — no leftover gap (Knut #93)."""
    from workflow.layout_engine.presets import LayoutRecipe
    w, h = A4

    def margins(**area):
        r = LayoutRecipe(instrument="i1", paper="A4", clip_border=True,
                         layout_mode="area_first", area_method="by_grid",
                         margin_bottom=6.0, margin_right=6.0, **area)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        lay = geometry.compute(g, w, h, 100_000)
        return geometry.realized_margins_mm(g, w, h, lay)   # L,R,T,B

    # cols auto + rows pinned → width fills (small right margin)
    assert margins(area_cols=0, area_rows=20)[1] < 10.0
    # both auto → both dimensions fill (small right AND bottom margins)
    L, R, T, B = margins(area_cols=0, area_rows=0)
    assert R < 10.0 and B < 12.0


def test_area_first_auto_aims_for_natural_size_with_override():
    """An area-first auto dimension aims for the instrument's natural patch size;
    the area_default_w/h kwargs let a caller override that target (the table was
    removed — natural size is a sufficient default on its own, Knut #93)."""
    from workflow.layout_engine.presets import LayoutRecipe
    base = dict(instrument="i1", paper="A4", clip_border=True,
                layout_mode="area_first", area_method="by_grid",
                area_cols=0, area_rows=0)
    nat = instruments.geom_from_build_kwargs(LayoutRecipe(**base).build_kwargs())
    big = instruments.geom_from_build_kwargs(
        {**LayoutRecipe(**base).build_kwargs(),
         "area_default_w": 16.0, "area_default_h": 20.0})
    assert big.pwid > nat.pwid + 4 and big.plen > nat.plen + 6   # override applied
    assert 15.0 <= big.pwid <= 18.0 and 19.0 <= big.plen <= 22.0


def test_area_first_noop_without_targets():
    """Area-first with no column/row target falls back to patch-first sizing."""
    from workflow.layout_engine.presets import default_recipe
    from dataclasses import replace
    base = instruments.geom_from_build_kwargs(
        default_recipe("i1", "A4", mode="clip").build_kwargs())
    rec = replace(default_recipe("i1", "A4", mode="clip"), layout_mode="area_first")
    area = instruments.geom_from_build_kwargs(rec.build_kwargs())
    assert area.pwid == base.pwid and area.plen == base.plen


def test_area_first_min_patch_autofit():
    """Knut's friendly path: min patch size + ratio, columns/rows on auto →
    the engine fits the most patches at >= the minimum and grows them to fill
    (so the realised patches are never smaller than the minimum) (#93)."""
    from workflow.layout_engine.presets import default_recipe
    from dataclasses import replace

    def geom(**area):
        rec = replace(default_recipe("i1", "A4", mode="clip"),
                      layout_mode="area_first", **area)
        return instruments.geom_from_build_kwargs(rec.build_kwargs())

    g8 = geom(area_min_patch_mm=8.0, area_ratio=1.0)
    assert g8.pwid >= 8.0 - 1e-6 and g8.plen >= 8.0 - 1e-6     # never below min
    g6 = geom(area_min_patch_mm=6.0, area_ratio=1.0)
    # a smaller minimum packs more patches
    assert (geometry.patches_per_sheet(g6, *A4)
            > geometry.patches_per_sheet(g8, *A4))
    # ratio is height:width — at 1.5 the patches grow taller than wide
    gr = geom(area_min_patch_mm=10.0, area_ratio=1.5)
    assert gr.plen > gr.pwid


def test_area_first_fills_box_past_ruler_cap():
    """Area-first is "margins are the law": the patch block fills the whole margin
    box height, even past the instrument ruler cap (i1Pro 240 mm). The leftover
    bottom margin shrinks to ~the box margin, and the strip ends up longer than
    the ruler — which a violation warning flags (Knut #93)."""
    from workflow.layout_engine.presets import LayoutRecipe
    r = LayoutRecipe(instrument="i1", paper="A4", clip_border=True,
                     layout_mode="area_first", area_method="by_width",
                     area_min_patch_mm=7.2, margin_bottom=6.0)
    g = instruments.geom_from_build_kwargs(r.build_kwargs())
    assert g.margins_are_law and g.ruler_mm == 240.0
    lay = geometry.compute(g, *A4, 100_000)
    bottom = geometry.realized_margins_mm(g, *A4, lay)[3]
    assert bottom < 10.0                       # box filled, not a 35 mm gap
    strip_len = lay.steps_in_pass * (g.plen + g.pspa)
    assert strip_len > g.ruler_mm              # legitimately over the ruler


def test_patch_first_keeps_ruler_cap():
    """Patch-first still caps the strip at the instrument ruler so the chart stays
    scannable — in BOTH margin modes. Only area-first fills past the ruler (Knut).
    The invariant is fill_beyond_ruler=False for patch-first, even when "Use
    instrument margins" makes the margins the law."""
    from workflow.layout_engine.presets import LayoutRecipe
    for use_instr in (True, False):
        r = LayoutRecipe(instrument="i1", paper="A4", clip_border=True,
                         layout_mode="patch_first", patch_w_mm=7.2, patch_h_mm=7.2,
                         use_instrument_margins=use_instr)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        assert g.fill_beyond_ruler is False        # patch-first never fills past ruler
        assert g.margins_are_law is bool(use_instr)  # law follows instrument margins
        lay = geometry.compute(g, *A4, 100_000)
        strip_len = lay.steps_in_pass * (g.plen + g.pspa)
        assert strip_len <= g.ruler_mm + g.plen    # capped near the ruler


def test_clip_side_left_right():
    """clip_side flips the clip band to the other edge and shifts the patch block
    accordingly, with the patch count unchanged (#93)."""
    gl = instruments.build("i1", clip_side="left")
    gr = instruments.build("i1", clip_side="right")
    # capacity is identical (the band reserves the same width either side)
    assert geometry.patches_per_sheet(gl, *A4) == geometry.patches_per_sheet(gr, *A4)
    lay = geometry.compute(gl, *A4, 60)
    pl = geometry.placement(gl, *A4, lay)
    pr = geometry.placement(gr, *A4, lay)
    # left: patches start after the clip band; right: at the left margin
    assert pl.x_of(0) > pr.x_of(0)
    al = geometry.clip_area_mm(gl, A4[1], A4[0])
    ar = geometry.clip_area_mm(gr, A4[1], A4[0])
    assert al[0] < ar[0]            # band moves from the left edge to the right
    assert ar[0] + ar[2] <= A4[0] + 1e-6


def test_right_clip_width_equals_setting():
    """A right-side clip zone must be exactly its set width, not wider: the patch
    block right-anchors against the clip so the horizontal slack falls on the
    LEFT, instead of piling onto the right and widening the clip (Knut beta.28)."""
    from workflow.layout_engine.presets import LayoutRecipe
    w, h = A4
    def whites(side):
        r = LayoutRecipe(instrument="i1", paper="A4", clip_border=True,
                         clip_side=side, clip_border_width_mm=26.0)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        lay = geometry.compute(g, w, h, 400)
        pl = geometry.placement(g, w, h, lay)
        n = lay.patches_per_page // lay.steps_in_pass if lay.steps_in_pass else 0
        block_w = max(0, n - 1) * g.rrsp + g.pwid
        return pl.x0, w - (pl.x0 + block_w)          # left white, right white
    lw, rw = whites("right")
    assert abs(rw - 26.0) < 0.5, f"right clip {rw:.1f} mm, expected ~26"
    lw2, rw2 = whites("left")
    assert abs(lw2 - 26.0) < 0.5                      # symmetric with left
    assert abs(rw - lw2) < 0.5                        # both clips the same width


def test_cm_ss_notes_band_reserves_space():
    """CM/SS have no native clip border, but a notes band can be reserved on
    either edge when clip content is on — reducing capacity (#93, Knut)."""
    from workflow.layout_engine.presets import default_recipe
    from dataclasses import replace

    def cap(content, side="left"):
        kw = replace(default_recipe("CM", "A4"), clip_content_mode=content,
                     clip_side=side).build_kwargs()
        g = instruments.geom_from_build_kwargs(kw)
        return geometry.patches_per_sheet(g, *A4), g

    base, gb = cap("off")
    withnotes, gn = cap("notes")
    assert gb.lbord == 0 and gn.lbord > 0          # band reserved only with notes
    assert withnotes < base                        # capacity drops for the band
    # band flips to the right edge
    area = geometry.clip_area_mm(gn, A4[1], A4[0])
    area_r = geometry.clip_area_mm(cap("notes", "right")[1], A4[1], A4[0])
    assert area[0] < area_r[0]


# --- "Margins are the law" mode (driven by area-first layout mode) ------------

def test_margins_are_law_only_in_area_first():
    """"Margins are the law" is now driven by the LAYOUT MODE (Knut #93): the
    patch area is exactly the margin box in area-first, so an un-capped strip
    packs MORE than the patch-first (printtarg-style) layout. The flag is no
    longer tied to use_instrument_margins."""
    # ColorMunki strip isn't length-capped, so the reclaimed leader/trailer shows.
    old = instruments.build("CM", spacer_on=True, edge_spacers=True,
                            margins_are_law=False)
    law = instruments.build("CM", spacer_on=True, edge_spacers=True,
                            margins_are_law=True)
    assert not old.margins_are_law and law.margins_are_law
    lay_old = geometry.compute(old, *A4, 60)
    lay_law = geometry.compute(law, *A4, 60)
    assert lay_law.steps_in_pass > lay_old.steps_in_pass     # patches at the margin


def test_geom_from_build_kwargs_law_follows_mode_or_instrument_margins():
    """geom_from_build_kwargs sets margins_are_law from area-first OR "Use
    instrument margins" — the instrument margin IS the whole top furniture zone, so
    patch-first with instrument margins must also treat the margins as the law
    (Knut beta.26). fill_beyond_ruler tracks area-first alone."""
    from workflow.layout_engine.presets import LayoutRecipe

    def geom(mode, use_instr):
        r = LayoutRecipe(instrument="i1", paper="A4", layout_mode=mode,
                         use_instrument_margins=use_instr)
        return instruments.geom_from_build_kwargs(r.build_kwargs())

    # margins_are_law = area_first OR use_instrument_margins
    assert geom("area_first", False).margins_are_law
    assert geom("area_first", True).margins_are_law
    assert geom("patch_first", True).margins_are_law         # the fixed case
    assert not geom("patch_first", False).margins_are_law
    # fill_beyond_ruler = area_first only (patch-first always honours the cap)
    assert geom("area_first", True).fill_beyond_ruler
    assert not geom("patch_first", True).fill_beyond_ruler


def test_margins_are_law_patch_top_at_margin_and_labels_at_edge():
    """In law mode the first patch row starts at the top margin and the strip
    label anchors at the top text-edge from the page edge (Knut)."""
    g = instruments.build("i1", margins=(38.0, 9.0, 9.0, 26.0),
                          margins_are_law=True, text_edge_top=4.0,
                          patch_area_align="top-left")
    lay = geometry.compute(g, *A4, 200)
    pl = geometry.placement(g, *A4, lay)
    assert abs(geometry.realized_margins_mm(g, *A4, lay)[2] - 38.0) < 0.6  # top≈margin
    assert abs(pl.leader_top - 4.0) < 1e-9                    # label 4 mm from edge


def test_margins_are_law_label_slides_to_edge_not_behind_patches():
    """In law mode a too-small top margin must push the strip label TOWARD the page
    edge (out of the patch block), never behind the patches (Knut #93). The label
    bottom stays at/above the patch-area top; a big margin still anchors at the
    text-edge distance."""
    from workflow.layout_engine.presets import LayoutRecipe
    w, h = geometry_papers("A4R")
    # Tight 7 mm top margin, label band ~7 mm → label must slide up to the edge.
    tight = instruments.geom_from_build_kwargs(
        LayoutRecipe(instrument="i1", paper="A4R", layout_mode="area_first",
                     area_method="by_width", area_min_patch_mm=8.0,
                     margin_top=7.0, text_edge_top_mm=4.0).build_kwargs())
    lay = geometry.compute(tight, w, h, 1000)
    pl = geometry.placement(tight, w, h, lay)
    lab_h = tight.label_band_mm if tight.label_band_mm >= 0 else tight.txhisl
    assert pl.leader_top >= 0.0                          # never off the page top
    assert pl.leader_top + lab_h <= tight.margin_t + 0.05  # bottom not behind patches
    # Roomy margin → label sits at the text-edge distance as before.
    roomy = instruments.geom_from_build_kwargs(
        LayoutRecipe(instrument="i1", paper="A4", layout_mode="area_first",
                     area_method="by_width", area_min_patch_mm=8.0,
                     margin_top=38.0, text_edge_top_mm=4.0).build_kwargs())
    w2, h2 = A4
    lay2 = geometry.compute(roomy, w2, h2, 200)
    assert abs(geometry.placement(roomy, w2, h2, lay2).leader_top - 4.0) < 1e-9


def test_margins_are_law_furniture_does_not_reduce_capacity():
    """In law (area-first) mode furniture (label band) lives inside the margin and
    does not change the patch count; in patch-first mode it still does (Knut)."""
    from workflow.layout_engine.presets import LayoutRecipe
    paper = "210x150"
    w, h = geometry_papers(paper)

    def cap(law, **over):
        # Pin use_instrument_margins=False so "law" is driven purely by the layout
        # mode here: area-first = law (furniture inside the margin), patch-first with
        # user margins = printtarg-style (furniture reserves reduce the count).
        r = LayoutRecipe(instrument="i1", paper=paper, use_instrument_margins=False,
                         layout_mode="area_first" if law else "patch_first", **over)
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        return geometry.patches_per_sheet(g, w, h)

    assert cap(True, indicator_size_mm=30.0) == cap(True)     # law: unchanged
    assert cap(False, indicator_size_mm=30.0) < cap(False)    # patch-first: reduces


def test_edge_spacers_counted_in_realized_margins():
    """Edge spacers bracket each strip one pspa beyond the patch block, so the
    realized top/bottom margins (which drive the measured-margin guides) must
    measure to the spacer, not the patch — else the guides sit inside the edge
    spacers and they look like they overflow the margins (Knut #18)."""
    w, h = A4
    # Pin the patch size (patch-first) so edge-on vs edge-off compare the same
    # block — the only difference is the bracket spacers.
    base = dict(instrument="i1", paper="A4", layout_mode="patch_first",
                patch_w=10.0, patch_h=10.0, inter_patch=3.5, spacer_on=True,
                margins=(6.0, 6.0, 6.0, 6.0))
    g_on = instruments.geom_from_build_kwargs({**base, "edge_spacers": True})
    g_off = instruments.geom_from_build_kwargs({**base, "edge_spacers": False})
    lay_on = geometry.compute(g_on, w, h, 576)
    lay_off = geometry.compute(g_off, w, h, 576)
    place_on = geometry.placement(g_on, w, h, lay_on)
    place_off = geometry.placement(g_off, w, h, lay_off)
    _, _, top_on, _ = geometry.realized_margins_mm(g_on, w, h, lay_on)
    _, _, top_off, _ = geometry.realized_margins_mm(g_off, w, h, lay_off)
    # Edge on: the realized top margin measures to the leading edge spacer, i.e.
    # one pspa ABOVE the first patch — so the measured-margin guide includes it.
    assert top_on == pytest.approx(place_on.y_of(0) - g_on.pspa, abs=0.2)
    # Edge off: it measures to the first patch (no overhang).
    assert top_off == pytest.approx(place_off.y_of(0), abs=0.2)


def test_area_first_fills_box_for_fixed_count():
    """Area-first must FILL the margin box for the chart's actual patch count
    (Knut: the box is law). A fixed count sizes the patches up/down so they fill —
    the minimum width is only a floor, not an exact size that leaves a gap."""
    from workflow.layout_engine import area_fit
    w, h = A4
    def fill(minw, n):
        kw = dict(instrument="i1", paper="A4", layout_mode="area_first",
                  area_method="by_width", area_min_patch=minw, area_ratio=1.0,
                  spacer_on=True, edge_spacers=True, clip_border=True,
                  clip_border_width=26.0, margins=(38.0, 9.0, 9.0, 26.0),
                  area_target_count=n)
        pw, ph = area_fit.derive_area_patch_size(kw)
        g = instruments.geom_from_build_kwargs({**kw, "patch_w": pw, "patch_h": ph})
        lay = geometry.compute(g, w, h, n)
        _, r, _, b = geometry.realized_margins_mm(g, w, h, lay)
        return pw, r, b, lay.pages
    # 576 patches with min 7.5 → patches grow ABOVE the min to fill (Knut's
    # "even if it becomes 8.7 mm"); right/bottom land on the ~9 mm margins.
    pw, r, b, _ = fill(7.5, 576)
    assert pw > 7.6                       # grew past the 7.5 minimum to fill
    assert r < 12.0 and b < 12.0         # fills to the margins, no big gap
    # Fewer patches → bigger; both still fill. Every below-capacity count must
    # fill BOTH axes on one page — including counts right at the capacity
    # boundary (the granularity edge that used to leave a gap, Knut 600-of-644).
    for n in (60, 100, 300, 500, 580, 600, 620, 640):
        pwn, r, b, pages = fill(7.5, n)
        assert pages == 1, f"{n} should fit one page"
        assert r < 12.0 and b < 14.0, f"{n} left a gap: R={r:.1f} B={b:.1f}"
        assert pwn >= 7.5 - 0.1            # never below the minimum
    assert fill(7.5, 300)[0] > fill(7.5, 600)[0]   # fewer patches → bigger
    # A count OVER one page does NOT shrink below the min — it overflows to more
    # pages at the min-fill size (Knut: overflow, not shrink — and not grown to
    # balance the pages either; the last page is partial at the first-page size).
    pw_over, _, _, pages_over = fill(7.5, 1600)
    assert pages_over >= 2 and 7.4 <= pw_over <= 7.8


@pytest.mark.slow
def test_area_first_height_is_a_minimum_floor():
    """The height-% is a MINIMUM, like the width: the patch height is never below
    width × (% / 100). When the area-fill would make it shorter, the patch must be
    stretched taller (fewer rows), overflowing to more pages if needed — it must
    never come out below the floor (Knut: 7.0 mm + 130 % gave 7.96 × 8.97, a 8.97
    height under the 10.35 floor)."""
    from workflow.layout_engine import area_fit
    w, h = A4
    for ratio in (1.0, 1.3, 1.5, 2.0):
        for n in (60, 100, 300, 500, 552, 600, 700, 1000):
            kw = dict(instrument="i1", paper="A4", layout_mode="area_first",
                      area_method="by_width", area_min_patch=7.0, area_ratio=ratio,
                      spacer_on=True, edge_spacers=True, clip_border=True,
                      clip_border_width=26.0, margins=(38.0, 9.0, 9.0, 26.0),
                      area_target_count=n)
            pw, ph = area_fit.derive_area_patch_size(kw)
            floor = pw * ratio
            assert ph >= floor - 0.05, (
                f"ratio={ratio} n={n}: ph={ph:.2f} below floor {floor:.2f}")
            assert pw >= 7.0 - 0.1            # width also never below its minimum


def test_area_first_by_grid_pinned_rows_render_exactly():
    """A pinned 'patches per strip' (rows) must render EXACTLY that many rows — no
    float-boundary one-short (Knut: 16 cols × 15 rows rendered 14 with a row-tall
    gap; _rows_filling(15)=15.6000001 → int(249/16.6) floats to 14)."""
    from workflow.layout_engine import area_fit
    w, h = A4
    for cols in (12, 16, 20):
        for rows in range(8, 25):
            kw = dict(instrument="i1", paper="A4", layout_mode="area_first",
                      area_method="by_grid", area_cols=cols, area_rows=rows,
                      area_ratio=1.0, spacer_on=True, edge_spacers=True,
                      clip_border=True, clip_border_width=26.0,
                      margins=(38.0, 9.0, 9.0, 26.0), area_target_count=546)
            pw, ph = area_fit.derive_area_patch_size(kw)
            g = instruments.geom_from_build_kwargs(
                {**kw, "patch_w": pw, "patch_h": ph})
            lay = geometry.compute(g, w, h, 546)
            assert lay.steps_in_pass == rows, (
                f"cols={cols} rows={rows}: rendered {lay.steps_in_pass} rows "
                f"(ph={ph:.2f})")


def test_every_strip_rect_bounds_exactly_its_own_patches():
    """A strip's rectangle must contain its patches and nothing more, on EVERY
    layout — the rule the ColorMunki stagger broke.

    Sebastian, 2026-08-13: on a staggered double-density ColorMunki chart the
    measure overlay's legend sat on the last patches of the lower strips. It
    places itself below the lowest strip rectangle, and every odd strip's
    rectangle was one `row_stagger_mm` (88 px at 300 dpi) above its own patches
    — the raster and patch_rects_px staggered, strip_rects_px did not. Stated
    as a general property rather than as one number, so the next layout that
    moves a strip is caught here instead of on screen.
    """
    from workflow.layout_engine import instruments
    from workflow.layout_engine.presets import default_recipe

    cases = [("CM", "rect", {"density": 2, "cm_stagger": True}),
             ("CM", "rect", {"cm_stagger": True}),
             ("CM", "rect", {}),
             ("i1", "rect", {}),
             ("SS", "hex", {}),
             ("SS", "rect", {})]
    for inst, mode, extra in cases:
        rec = default_recipe(inst, "A4", mode=mode)
        rec.randomize = False
        kw = rec.build_kwargs()
        kw["dpi"] = 300
        kw.update(extra)
        geom = instruments.geom_from_build_kwargs(kw)
        lay = geometry.compute(geom, 210.0, 297.0, 120)
        strips = geometry.strip_rects_px(geom, 210.0, 297.0, lay, 300)
        patches = geometry.patch_rects_px(geom, 210.0, 297.0, lay, 300)
        steps = lay.steps_in_pass
        checked = 0
        for s in strips:
            own = [p for p in patches
                   if p["page"] == s["page"]
                   and (p["slot"] % lay.patches_per_page) // steps == s["pass"]]
            if not own:
                continue
            checked += 1
            label = f"{inst}/{mode}{extra or ''} strip {s['pass']}"
            assert min(p["y"] for p in own) == s["y"], f"{label}: top"
            assert max(p["y"] + p["h"] for p in own) == s["y"] + s["h"], \
                f"{label}: bottom"
        assert checked > 1, f"{inst}/{mode}: nothing compared"


def test_hex_overhang_follows_an_explicit_patch_size():
    """A SpectroScan hexagon pokes plen/6 past its slot top and bottom and
    ¼·pwid past its sides, and the layout reserves exactly that as hxeh/hxew.

    Both were computed from `pscale` and never revisited when `patch_w`/
    `patch_h` set the size directly — and `hxew` was not even carried through
    the `replace()` — so a 20 mm hexagon still reserved the 7 mm geometry's
    1.75 mm and overhung it by 5 mm, printing past the margin. The Manual
    patch-size boxes and the area-first grid both take this path, and every
    patch size a CR30 chart would use (12–20 mm) is in the affected range.
    """
    from workflow.layout_engine import instruments
    for w_mm in (7.0, 12.0, 16.0, 20.0, 26.0):
        h_mm = w_mm * (3 ** 0.5) / 2
        g = instruments.build("SS", pscale=1.0, hflag=True, border=6.0,
                              patch_w=w_mm, patch_h=h_mm)
        assert abs(g.pwid - w_mm) < 1e-6
        assert abs(g.hxeh - g.plen / 6.0) < 1e-6, (
            f"{w_mm} mm hexagon reserves {g.hxeh:.2f} mm at the apex, "
            f"needs {g.plen / 6.0:.2f} mm")
        assert abs(g.hxew - g.pwid / 4.0) < 1e-6, (
            f"{w_mm} mm hexagon reserves {g.hxew:.2f} mm at the sides, "
            f"needs {g.pwid / 4.0:.2f} mm")


def test_an_explicit_patch_size_matches_the_same_size_via_pscale():
    """The two ways of asking for the same hexagon must agree. They did not:
    one route recomputed the overhang, the other kept the base geometry's."""
    from workflow.layout_engine import instruments
    for w_mm in (12.0, 20.0):
        a = instruments.build("SS", pscale=w_mm / 7.0, hflag=True, border=6.0)
        b = instruments.build("SS", pscale=1.0, hflag=True, border=6.0,
                              patch_w=w_mm, patch_h=w_mm * (3 ** 0.5) / 2)
        assert abs(a.hxeh - b.hxeh) < 1e-6
        assert abs(a.hxew - b.hxew) < 1e-6


def test_a_square_spectroscan_chart_reserves_no_hex_overhang():
    """The counterweight: without the hex flag there is no overhang to reserve,
    whatever the patch size."""
    from workflow.layout_engine import instruments
    g = instruments.build("SS", pscale=1.0, hflag=False, border=6.0,
                          patch_w=20.0, patch_h=20.0)
    assert g.hxeh == 0.0 and g.hxew == 0.0
