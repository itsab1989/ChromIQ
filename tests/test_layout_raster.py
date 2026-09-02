"""Tests for the TIFF raster, contrast guard, and strip geometry."""
import numpy as np
import tifffile

from workflow.layout_engine import contrast, geometry, instruments, raster
from workflow.layout_engine.colorants import to_display_rgb
from workflow.layout_engine.ti1_reader import ColorTarget


def _rgb_target(n):
    patches = []
    for i in range(n):
        patches.append(((float(i * 9 % 100), float(i * 17 % 100), float(i * 5 % 100)),
                        (40.0, 45.0, 50.0)))
    return ColorTarget(color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
                       patches=patches)


def _nchan_target(n, fields, color_rep):
    """A synthetic N-colorant target (device values 0–100, plausible XYZ)."""
    ch = len(fields)
    patches = []
    for i in range(n):
        dev = tuple(float((i * (7 + c * 3)) % 100) for c in range(ch))
        patches.append((dev, (40.0, 45.0, 50.0)))
    return ColorTarget(color_rep=color_rep, device_fields=fields, patches=patches)


def test_render_dimensions_and_pages():
    target = _rgb_target(60)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    res = raster.render_pages(target, lay, geom, seed=42,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=150)
    assert len(res.images) == lay.pages == 1
    w, h = res.images[0].size
    assert w == round(210.0 * 150 / 25.4)
    assert h == round(297.0 * 150 / 25.4)


def test_by_grid_loaded_patchset_honours_requested_rows(tmp_path):
    """Knut #34: a LOADED patch set (1170) with area-first 'By columns / rows'
    set to 15 columns × 16 rows must render 16 rows per full page — not 15.
    Exercised through the full build_chart path (not just geometry.compute),
    because the fixed count feeds area-first via area_target_count and an
    off-by-one in the row-fit would silently drop a row (needs 17 to get 16)."""
    import random
    from workflow.layout_engine import chart as le_chart, instruments, papers
    from workflow.layout_engine.presets import default_recipe
    import workflow.ti2_relayout as R

    random.seed(3)
    prog = [(random.random() * 100, random.random() * 100, random.random() * 100)
            for _ in range(1170)]
    R.write_ti1(R.ChartSpec.new("i1", "A4"), prog, tmp_path / "g.ti1")
    rec = default_recipe("i1", "A4")
    rec.randomize = False
    rec.layout_mode = "area_first"
    rec.area_method = "by_grid"
    rec.area_cols, rec.area_rows = 15, 16
    kw = rec.build_kwargs(); kw["dpi"] = 150
    res = le_chart.build_chart(str(tmp_path / "g.ti1"), tmp_path / "g", **kw)

    kw["area_target_count"] = res.layout.total_patches
    geom = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm("A4")
    rects = geometry.patch_rects_px(geom, w, h, res.layout, 150)
    page0 = [d for d in rects if d["page"] == 0]
    n_cols = len({d["x"] for d in page0})
    n_rows = len({d["y"] for d in page0})
    assert (n_cols, n_rows) == (15, 16), \
        f"requested 15×16, got {n_cols}×{n_rows} (off-by-one row drop)"


def test_hex_strip_count_matches_columns_not_interlock(tmp_path):
    """Knut #30: on a SpectroScan hexagonal chart the interlocking rows LOOK
    like an extra column between A and B, but that is the honeycomb tessellation
    — it must NOT be counted as a separate strip. The number of strips (label
    letters) must equal the number of patch columns, and columns × rows must
    equal the patch count (no phantom strip)."""
    import random
    from workflow.layout_engine import chart as le_chart, instruments, papers
    from workflow.layout_engine.presets import default_recipe
    import workflow.ti2_relayout as R

    random.seed(5)
    prog = [(random.random() * 100,) * 3 for _ in range(300)]
    R.write_ti1(R.ChartSpec.new("SS", "A4"), prog, tmp_path / "h.ti1")
    rec = default_recipe("SS", "A4", mode="hex")     # hflag=True
    rec.randomize = False
    rec.layout_mode = "area_first"
    rec.area_method = "by_grid"
    rec.area_cols, rec.area_rows = 10, 20
    kw = rec.build_kwargs(); kw["dpi"] = 150
    res = le_chart.build_chart(str(tmp_path / "h.ti1"), tmp_path / "h", **kw)

    kw["area_target_count"] = res.layout.total_patches
    geom = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm("A4")
    rects = geometry.patch_rects_px(geom, w, h, res.layout, 150)
    page0 = [d for d in rects if d["page"] == 0]
    n_rows = len({d["y"] for d in page0})
    n_letters = len({d["loc"][0] for d in page0})    # distinct strip labels
    assert n_letters == 10                           # not 2×-1 interlock columns
    assert n_letters * n_rows == len(page0)          # no phantom strip
    # patch_rects_px returns the hexagon's OWN box, honeycomb shift included, so
    # a column has two x values (one per row parity) — 20 for 10 strips, and
    # they must pair up. Counting raw x values would read that as 20 columns.
    xs = sorted({d["x"] for d in page0})
    assert len(xs) == 20
    half = [b - a for a, b in zip(xs[::2], xs[1::2])]
    assert len(set(half)) == 1                       # one uniform stagger step


def test_saved_tiff_colours_match_ti2_at_every_location(tmp_path):
    """The chartread-critical property end to end: every patch in the SAVED .tif
    must show the exact device colour the .ti2 records at that SAMPLE_LOC — so
    what gets printed is what chartread expects, for a *randomised* chart (#93)."""
    import random
    from PIL import Image
    from workflow.layout_engine import chart as le_chart, papers
    from workflow.layout_engine.presets import default_recipe
    import workflow.ti2_relayout as R

    random.seed(11)
    prog = [(random.random() * 100, random.random() * 100, random.random() * 100)
            for _ in range(300)]
    R.write_ti1(R.ChartSpec.new("i1", "A4"), prog, tmp_path / "s.ti1")
    rec = default_recipe("i1", "A4"); rec.randomize = True; rec.seed = 777
    kw = rec.build_kwargs(); kw["dpi"] = 200
    res = le_chart.build_chart(str(tmp_path / "s.ti1"), tmp_path / "chart", **kw)

    # The .ti2 chartread reads: SAMPLE_LOC -> device value.
    spec = R.ChartSpec.from_ti2(tmp_path / "chart.ti2")
    loc_dev = {p.loc: p.dev for p in spec.patches if p.loc}
    assert loc_dev, "no SAMPLE_LOC patches parsed from .ti2"

    # build_chart sizes area-first patches to fill the box for the actual patch
    # count, so recompute the geom with the same count or the rects diverge.
    kw["area_target_count"] = len(spec.patches)
    geom = instruments.geom_from_build_kwargs(kw)
    w, h = papers.dimensions_mm("A4")
    rects = geometry.patch_rects_px(geom, w, h, res.layout, kw["dpi"],
                                    rec.strip_pattern, rec.patch_pattern)
    imgs = [np.asarray(Image.open(p).convert("RGB")) for p in res.tiff_paths]

    checked = 0
    for d in rects:
        dev = loc_dev.get(d["loc"])
        if dev is None:
            continue
        cx, cy = d["x"] + d["w"] // 2, d["y"] + d["h"] // 2
        got = tuple(int(v) for v in imgs[d["page"]][cy, cx])
        assert got == tuple(to_display_rgb(dev, spec.color_rep)), \
            f"{d['loc']}: tif {got} != ti2 {to_display_rgb(dev, spec.color_rep)}"
        checked += 1
    assert checked >= 300


def test_raster_matches_ti2_slot_assignment():
    # randomize=False -> patch 0 sits at slot 0 = top of column A.
    target = _rgb_target(60)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    res = raster.render_pages(target, lay, geom, seed=1, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=300)
    rects = geometry.strip_rects_px(geom, 210.0, 297.0, lay, 300)
    r0 = rects[0]
    cx, cy = r0["x"] + r0["w"] // 2, r0["y"] + geometry.placement(
        geom, 210.0, 297.0, lay).plen * 300 / 25.4 / 2
    px = res.images[0].getpixel((int(cx), int(cy)))
    assert px == to_display_rgb(target.patches[0][0], "iRGB")


def test_strip_rects_within_bounds():
    target = _rgb_target(60)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    rects = geometry.strip_rects_px(geom, 210.0, 297.0, lay, 300)
    assert len(rects) == lay.passes          # single strip per page → passes columns
    W = round(210.0 * 300 / 25.4)
    H = round(297.0 * 300 / 25.4)
    for r in rects:
        assert 0 <= r["x"] and r["x"] + r["w"] <= W
        assert 0 <= r["y"] and r["y"] + r["h"] <= H


def test_save_tiff_resolution(tmp_path):
    target = _rgb_target(40)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 40)
    res = raster.render_pages(target, lay, geom, seed=7,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=200)
    paths = raster.save_tiffs(res.images, tmp_path / "c.tif", dpi=200)
    assert len(paths) == 1 and paths[0].exists()
    with tifffile.TiffFile(str(paths[0])) as tf:
        page = tf.pages[0]
        xres = page.tags["XResolution"].value
        unit = page.tags["ResolutionUnit"].value
        res_val = xres[0] / xres[1]
        assert int(unit) == 3                      # CENTIMETER, like printtarg
        assert abs(res_val * 2.54 - 200) < 1.0     # px/cm -> dpi


def test_patch_rects_known_for_every_slot():
    target = _rgb_target(60)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    pr = geometry.patch_rects_px(geom, 210.0, 297.0, lay, 300)
    # one rect per slot, each labelled, all inside the page
    assert len(pr) == lay.total_patches
    assert pr[0]["loc"] == "A1"
    assert pr[20]["loc"] == "A21"
    assert pr[21]["loc"] == "B1"
    W, H = round(210.0 * 300 / 25.4), round(297.0 * 300 / 25.4)
    for r in pr:
        assert 0 <= r["x"] and r["x"] + r["w"] <= W
        assert 0 <= r["y"] and r["y"] + r["h"] <= H


def test_no_vertical_gap_between_patches_and_spacers():
    """Walking down a strip there must be no white (paper) row between a patch
    and the spacer below it, nor between the spacer and the next patch — the
    old code rounded plen/pspa as fixed heights, leaving a 1 px gap on every
    other row (#93).

    All patches are a uniform light grey and spacers are forced to ``bw`` so the
    spacer between two light patches is always black — that way any white pixel
    found in the column is genuine paper showing through a gap, not a spacer that
    the colour palette happened to pick white."""
    patches = [((75.0, 75.0, 75.0), (40.0, 45.0, 50.0)) for _ in range(120)]
    target = ColorTarget(color_rep="iRGB",
                         device_fields=["RGB_R", "RGB_G", "RGB_B"], patches=patches)
    # patch ×0.95 (a common scale, and the one in the bug report) gives a
    # fractional patch/spacer pitch — exactly what made round(plen)+round(pspa)
    # drift from round(plen+pspa) and open the 1 px gaps.
    geom = instruments.build("i1", pscale=0.95)
    lay = geometry.compute(geom, 210.0, 297.0, 120)
    dpi = 300
    res = raster.render_pages(target, lay, geom, seed=3, randomize=False,
                              spacer_mode="bw",
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=dpi)
    img = res.images[0]
    place = geometry.placement(geom, 210.0, 297.0, lay)
    mm2px = dpi / 25.4
    steps = lay.steps_in_pass
    cx = int(round((place.x_of(0) + place.pwid / 2) * mm2px))
    n_rows = min(steps, lay.total_patches)
    y_top = int(round(place.y_of(0) * mm2px))
    y_bot = int(round((place.y_of(n_rows - 1) + place.plen) * mm2px))
    white_rows = [y for y in range(y_top, y_bot)
                  if img.getpixel((cx, y)) == (255, 255, 255)]
    assert not white_rows, f"paper showing through at rows {white_rows[:5]}"


def test_ink_names_from_fields():
    assert raster.ink_names_from_fields(
        ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]) == \
        ["Cyan", "Magenta", "Yellow", "Black"]
    assert raster.ink_names_from_fields(
        ["CMYKOG_O", "CMYKOG_G", "CMYKOG_V"]) == ["Orange", "Green", "Violet"]
    # unknown suffix falls back to a title-cased name (still valid InkNames)
    assert raster.ink_names_from_fields(["XY_ZZ"]) == ["Zz"]


def test_device_pages_exact_patch_values_and_furniture_in_k():
    """Tier D (#72): the collected device raster carries each patch's EXACT ink
    coverage (0–100 % → 0..255), and all furniture folds into the K channel with
    the colour inks left clean — so patches stay bit-exact for chartread."""
    import numpy as np
    fields = ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]
    target = _nchan_target(120, fields, "CMYK")
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 120)
    res = raster.render_pages(target, lay, geom, seed=5, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=150,
                              chart_text="ChromIQ", collect_device_geom=True)
    assert res.patch_geom is not None and len(res.patch_geom) == 1
    arrs = raster.build_device_pages(res, target)
    arr = arrs[0]
    assert arr.shape[2] == 4 and arr.dtype == np.uint8

    # every non-media patch's exact 8-bit tuple appears in the raster
    # (round-half-up, matching build_device_pages' +0.5 quantisation)
    for dev, _ in target.patches[:10]:
        exp = np.array([int(v / 100 * 255 + 0.5) for v in dev], dtype=np.uint8)
        assert np.all(arr == exp, axis=2).sum() > 0, f"missing patch {dev}"

    # furniture (chart text + strip labels) lands in K with clean colour inks
    c, m, y, k = (arr[..., i] for i in range(4))
    pure_k = (k > 10) & (c == 0) & (m == 0) & (y == 0)
    assert pure_k.sum() > 0, "no pure-black furniture found"


def test_to_device_approx_colours():
    from workflow.layout_engine.colorants import to_device_approx
    f = ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]
    # red (255,0,0) → magenta+yellow, no K (printtarg's "Red" primary)
    assert to_device_approx((255, 0, 0), f) == (0.0, 100.0, 100.0, 0.0)
    # yellow → Y only
    assert to_device_approx((255, 255, 0), f) == (0.0, 0.0, 100.0, 0.0)
    # near-neutral black → single K ink (clean, not 300 % rich black)
    c, m, y, k = to_device_approx((0, 0, 0), f)
    assert (c, m, y) == (0.0, 0.0, 0.0) and k == 100.0
    # white → paper (no ink)
    assert to_device_approx((255, 255, 255), f) == (0.0, 0.0, 0.0, 0.0)


def test_coloured_spacers_carry_device_ink():
    """Tier D (#72): a coloured contrast spacer keeps its colour in the device
    raster (chromatic ink), rather than flattening to black — matching
    printtarg's coloured spacers."""
    import numpy as np
    fields = ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]
    # alternating light/dark patches force vivid contrast spacers between them
    target = _nchan_target(120, fields, "CMYK")
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 120)
    res = raster.render_pages(target, lay, geom, seed=5, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=150,
                              spacer_mode="colored", collect_device_geom=True)
    assert any(k == "spacer" for row in res.patch_geom for (k, *_ ) in row)
    arr = raster.build_device_pages(res, target)[0]
    c, m, y, k = (arr[..., i] for i in range(4))
    chromatic = ((m > 60) | (y > 60) | (c > 60)) & (k < 20)
    assert chromatic.sum() > 0, "coloured spacers collapsed to black in device raster"


def test_device_pages_no_k_channel_uses_composite_black():
    """With no K channel the furniture is painted into every colour channel
    (rich composite black) so it stays visible."""
    import numpy as np
    fields = ["CMY_C", "CMY_M", "CMY_Y"]           # 3 inks, no black
    # force the device path by treating it as n>=... here we call build directly
    target = _nchan_target(120, fields, "CMY")
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 120)
    res = raster.render_pages(target, lay, geom, seed=5, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=150,
                              chart_text="ChromIQ", collect_device_geom=True)
    assert raster._k_channel_index(fields) is None
    arr = raster.build_device_pages(res, target)[0]
    # a furniture pixel in the bottom text band has ink in all three channels
    band = arr[-int(8 * 150 / 25.4):]
    inked = (band > 10).all(axis=2)
    assert inked.sum() > 0, "composite-black furniture not applied to all inks"


def test_save_separated_tiffs_tags(tmp_path):
    """The saved N-channel TIFF is photometric='separated' with InkNames, InkSet
    and (for >4 inks) ExtraSamples — so a RIP knows every ink channel."""
    import numpy as np
    import tifffile as tf
    # CMYK → InkSet 1 (CMYK), no extra samples, single strip, Orientation set
    a4 = np.zeros((10, 10, 4), dtype=np.uint8)
    p = raster.save_separated_tiffs([a4], tmp_path / "cmyk.tif", dpi=200,
                                    ink_names=["Cyan", "Magenta", "Yellow", "Black"])
    with tf.TiffFile(str(p[0])) as t:
        pg = t.pages[0]
        assert int(pg.photometric) == 5                # SEPARATED
        assert pg.tags["InkSet"].value == 1
        assert pg.tags["NumberOfInks"].value == 4
        assert "Cyan" in pg.tags["InkNames"].value
        assert int(pg.tags["Orientation"].value) == 1
        assert pg.tags.get("ExtraSamples") is None
    # 6-ch CMYKOG → Photoshop-compatible: NO InkSet, InkNames kept, and the two
    # surplus inks declared "unspecified" (extra ink data, not alpha → opaque).
    a6 = np.zeros((10, 10, 6), dtype=np.uint16)
    p6 = raster.save_separated_tiffs(
        [a6], tmp_path / "cmykog.tif", dpi=200,
        ink_names=["Cyan", "Magenta", "Yellow", "Black", "Orange", "Green"])
    with tf.TiffFile(str(p6[0])) as t:
        pg = t.pages[0]
        assert pg.tags.get("InkSet") is None           # omitted → defaults to CMYK
        assert pg.tags["NumberOfInks"].value == 6
        assert "Orange" in pg.tags["InkNames"].value
        assert len(pg.tags["ExtraSamples"].value) == 2
        assert int(pg.tags["Orientation"].value) == 1


def test_build_chart_cmyk_writes_separated_tiff(tmp_path):
    """End to end: build_chart on a CMYK .ti1 writes a device-native separated
    TIFF whose patch pixels equal the .ti2 device values (Tier D, #72)."""
    import numpy as np
    import tifffile as tf
    from workflow.layout_engine import chart as le_chart

    # write a CMYK .ti1 directly (single-table N-channel format)
    ti1 = tmp_path / "c.ti1"
    fields = ["CMYK_C", "CMYK_M", "CMYK_Y", "CMYK_K"]
    rows = []
    for i in range(60):
        rows.append(tuple(float((i * (7 + c * 3)) % 100) for c in range(4)))
    _write_cmyk_ti1(ti1, fields, rows)

    res = le_chart.build_chart(str(ti1), tmp_path / "chart", instrument="i1",
                               paper="A4", seed=3, dpi=150)
    with tf.TiffFile(str(res.tiff_paths[0])) as t:
        pg = t.pages[0]
        assert int(pg.photometric) == 5
        assert pg.tags["InkNames"].value.replace("\x00", " ").split() == \
            ["Cyan", "Magenta", "Yellow", "Black"]
        arr = pg.asarray()
    assert arr.shape[2] == 4
    # exact patch value present in raster (round-half-up like build_device_pages)
    exp = np.array([int(v / 100 * 255 + 0.5) for v in rows[1]], dtype=arr.dtype)
    assert np.all(arr == exp, axis=2).sum() > 0


def _write_cmyk_ti1(path, fields, rows):
    """Minimal single-table CMYK .ti1 (COLOR_REP + device columns + XYZ)."""
    hdr = ["CTI1", 'COLOR_REP "CMYK"', 'TOTAL_INK_LIMIT "320.0"',
           f"NUMBER_OF_FIELDS {len(fields) + 4}", "BEGIN_DATA_FORMAT",
           "SAMPLE_ID " + " ".join(fields) + " XYZ_X XYZ_Y XYZ_Z",
           "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(rows)}", "BEGIN_DATA"]
    for i, dev in enumerate(rows, 1):
        hdr.append(f"{i} " + " ".join(f"{v:.4f}" for v in dev) + " 40.0 45.0 50.0")
    hdr.append("END_DATA")
    path.write_text("\n".join(hdr) + "\n", encoding="utf-8")


def test_contrast_spacer_choice():
    assert contrast.spacer_rgb((255, 255, 255), (240, 240, 240)) == (0, 0, 0)
    assert contrast.spacer_rgb((0, 0, 0), (10, 10, 10)) == (255, 255, 255)


def test_colored_spacer_is_in_palette_and_contrasts():
    sp = contrast.colored_spacer_rgb((128, 128, 128), (130, 130, 130))
    assert sp in contrast._COLOURED_PALETTE
    # a coloured spacer between two mid-greys should be far from grey
    assert contrast._rgb_dist(sp, (128, 128, 128)) > 100
    # spacer_for_mode routes correctly
    assert contrast.spacer_for_mode("bw", (255, 255, 255), (240, 240, 240)) == (0, 0, 0)
    assert contrast.spacer_for_mode("colored", (128, 128, 128), (130, 130, 130)) == sp


def test_font_supports_bundled():
    # JetBrains Mono is a weight-axis variable font (bold yes, italic no in-file).
    has_bold, has_italic = raster.font_supports("JetBrains Mono")
    assert has_bold is True
    assert has_italic is False
    # Instrument Serif ships a real Italic face (used by the masthead "IQ"), but
    # no Bold face — so italic yes, bold no.
    assert raster.font_supports("Instrument Serif") == (False, True)
    # An unknown family supports nothing (renderer would fall back to default).
    assert raster.font_supports("No Such Font 123") == (False, False)


def test_instrument_serif_italic_face_resolves():
    """The masthead "IQ" needs the real Instrument Serif Italic face, not a
    sheared Regular — so italic must resolve to a different file (#93)."""
    reg = raster._font_path("Instrument Serif", "regular")
    ital = raster._font_path("Instrument Serif", "italic")
    assert reg and ital and reg != ital
    assert str(ital).endswith("Italic.ttf")


def test_underline_modes():
    import numpy as np
    target = _rgb_target(120)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 120)
    kw = dict(seed=7, paper_w_mm=210.0, paper_h_mm=297.0, dpi=150)
    accents = set(raster.ACCENT_RGB)

    def has_accent(res):
        arr = np.asarray(res.images[0])
        return any((arr == np.array(c)).all(axis=2).any() for c in accents)

    def accents_present(res):
        arr = np.asarray(res.images[0])
        return {c for c in accents if (arr == np.array(c)).all(axis=2).any()}

    # off → no accent rule pixels.
    assert not has_accent(raster.render_pages(target, lay, geom, underline_mode="off", **kw))
    # segments → all five accents appear (5-part bar under each strip).
    assert accents_present(raster.render_pages(
        target, lay, geom, underline_mode="segments", **kw)) == accents
    # legacy "colored" aliases to the 5-segment bar.
    assert accents_present(raster.render_pages(
        target, lay, geom, underline_mode="colored", **kw)) == accents
    # per-strip cycle → at least one accent present.
    assert has_accent(raster.render_pages(target, lay, geom,
                                          underline_mode="cycle", **kw))
    # hiding indicators suppresses the rule even if a mode is set.
    assert not has_accent(raster.render_pages(
        target, lay, geom, underline_mode="segments", draw_indicators=False, **kw))


def test_clip_content_modes():
    import numpy as np
    target = _rgb_target(120)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 120)
    ax, ay, aw, ah = geometry.clip_area_px(geom, 297.0, 200)

    def clip_ink(mode, **kw):
        res = raster.render_pages(target, lay, geom, seed=7, paper_w_mm=210.0,
                                  paper_h_mm=297.0, dpi=200,
                                  clip_content_mode=mode, **kw)
        sub = np.asarray(res.images[0])[ay:ay + ah, ax:ax + aw]
        return int((sub < 200).any(axis=2).sum())

    assert clip_ink("off") == 0
    assert clip_ink("text", clip_text="Sample 12") > 0
    assert clip_ink("branding") > 0
    assert clip_ink("notes") > 0


def test_hexagon_points_shape_and_stagger():
    """The SpectroScan hexagon helper makes a pointed-top/bottom, flat-sided hex
    whose apexes reach beyond the slot, staggered ±¼w by patch index (#93)."""
    even = raster._hexagon_points(100, 200, 60, 60, 0)   # step 0 → shift left
    odd = raster._hexagon_points(100, 200, 60, 60, 1)    # step 1 → shift right
    # six vertices
    assert len(even) == 6
    top, ur, lr, bot, ll, ul = even
    # top & bottom apexes share the centre x; apexes overshoot the slot top/bottom
    assert top[0] == bot[0]
    assert top[1] < 200 and bot[1] > 260            # beyond [y0, y0+ph]
    # flat vertical sides: left pair share x, right pair share x
    assert ul[0] == ll[0] and ur[0] == lr[0] and ul[0] < ur[0]
    # stagger: even shifts left of odd by ~half the width
    assert odd[0][0] - even[0][0] == 30             # +w/4 - (-w/4) = w/2


def test_spectroscan_hex_pokes_above_first_row():
    """SpectroScan hex patches render as hexagons whose top apex pokes above the
    slot — a coloured first-row patch paints pixels above its slot top, in the
    hxeh space the geometry reserves (#93, Knut)."""
    import numpy as np
    geom = instruments.build("SS", hflag=True)
    lay = geometry.compute(geom, 210.0, 297.0, 80)
    res = raster.render_pages(_rgb_target(80), lay, geom, seed=1, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=200)
    hex_img = np.asarray(res.images[0])
    rects = geometry.patch_rects_px(geom, 210.0, 297.0, lay, 200)
    top_y = min(r["y"] for r in rects)                  # first patch row
    checked = 0
    for r in (r for r in rects if r["y"] == top_y):
        cy0 = r["y"] + r["h"] // 2
        # patch_rects_px already carries the honeycomb shift, so the rect centre
        # IS the apex x — re-applying it here (as this test used to) landed on
        # the hexagon's flank instead.
        cx = r["x"] + r["w"] // 2                       # apex x
        if max(hex_img[cy0, cx]) >= 240:               # skip near-white patches
            continue
        ay = r["y"] - r["h"] // 12                       # just above the slot top
        assert tuple(hex_img[ay, cx]) != (255, 255, 255)   # apex paints above slot
        checked += 1
        if checked >= 3:
            break
    assert checked >= 1


def test_clip_image_transform_changes_render(tmp_path):
    """The clip image's rotate / scale / move transform changes the rendered clip
    band (#93, Knut)."""
    import numpy as np
    from PIL import Image
    p = tmp_path / "logo.png"
    Image.new("RGBA", (80, 40), (255, 0, 0, 255)).save(p)

    def render(**xf):
        img = raster.render_clip_strip("image", width_px=120, height_px=900,
                                       dpi=200, image_path=str(p), **xf)
        return np.asarray(img.convert("RGB"))

    base = render()
    assert not np.array_equal(base, render(image_rotation=90))
    assert not np.array_equal(base, render(image_scale=50.0))
    assert not np.array_equal(base, render(image_offset_y_mm=25.0))


def test_branding_extra_text_uses_chosen_font():
    """The extra text under the ChromIQ branding clip content honours the user's
    chosen font, not the wordmark face (#93, Knut)."""
    import numpy as np

    def render(font):
        img = raster.render_clip_strip("branding", width_px=160, height_px=1200,
                                       dpi=200, text="Sample Lab",
                                       font_family=font, ctx=None)
        return np.asarray(img.convert("RGB"))

    assert not np.array_equal(render("Inter"), render("JetBrains Mono"))


def test_text_edge_mm_moves_bottom_text():
    """A larger 'text distance from edge' pushes the bottom sheet text further up
    from the page edge (#93, Knut: the text-distance parameter)."""
    import numpy as np
    target = _rgb_target(60)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)

    def lowest_ink_row(edge):
        res = raster.render_pages(target, lay, geom, seed=1, randomize=False,
                                  paper_w_mm=210.0, paper_h_mm=297.0, dpi=150,
                                  chart_text="ChromIQ", text_edge_mm=edge)
        img = np.asarray(res.images[0])
        H = img.shape[0]
        # scan the bottom 60 px band for the lowest row carrying text ink
        rows = [y for y in range(H - 60, H) if (img[y] < 120).any()]
        return max(rows) if rows else 0

    near = lowest_ink_row(2.0)
    far = lowest_ink_row(12.0)
    assert far < near        # bigger inset → text sits higher up the page


def test_spectroscan_row_labels_drawn_in_side_band():
    """SpectroScan labels the grid 2-D: column letters on top + row NUMBERS down
    the side, in the reserved rlwi band left of the patches — for both flat and
    hex. The number ink must stay LEFT of the patches; for hex it must also clear
    the ¼-width left stagger of the first column (#93, Knut). Light patches so the
    only dark ink is the labels."""
    import numpy as np
    # near-white patches → any dark pixel is label text, not a patch
    light = ColorTarget(color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
                        patches=[((95.0, 95.0, 95.0), (90.0, 95.0, 100.0))
                                 for _ in range(400)])

    def rightmost_label_x(geom):
        lay = geometry.compute(geom, 297.0, 210.0, 400)
        place = geometry.placement(geom, 297.0, 210.0, lay)
        res = raster.render_pages(light, lay, geom, seed=1, randomize=False,
                                  paper_w_mm=297.0, paper_h_mm=210.0, dpi=200)
        img = np.asarray(res.images[0])
        mm2px = 200 / 25.4
        x0 = round(place.x_of(0) * mm2px)
        strip_w = round(place.pwid * mm2px)
        x_lo = max(0, x0 - round(geom.rlwi * mm2px))
        # Scan only the patch-row band (exclude the top column-letter band), so
        # the only dark ink is the row numbers.
        y_lo = round(place.y_of(1) * mm2px)
        y_hi = round((place.y_of(lay.steps_in_pass - 1) + place.plen) * mm2px)
        zone = img[y_lo:y_hi, x_lo:x0 + strip_w]
        dark_cols = np.where((zone < 60).all(axis=2).any(axis=0))[0]
        rightmost = (x_lo + dark_cols.max()) if len(dark_cols) else 0
        return rightmost, x0, strip_w

    # flat: labels present and end left of the patch start.
    r, x0, _ = rightmost_label_x(instruments.build("SS"))
    assert 0 < r < x0
    # hex: labels must clear the ¼-width left stagger, not just x0.
    rh, x0h, sw = rightmost_label_x(instruments.build("SS", hflag=True))
    assert 0 < rh <= x0h - sw // 4
    # i1 has no row-label band reserved.
    assert instruments.build("i1").rlwi == 0


def test_spectroscan_hex_first_column_not_clipped():
    """The left-shifted (even-step) hexagons of the first column must stay inside
    the left margin — the stagger offset is reserved by hxew (#93, Knut)."""
    geom = instruments.build("SS", hflag=True)
    lay = geometry.compute(geom, 297.0, 210.0, 200)        # A4 landscape
    place = geometry.placement(geom, 297.0, 210.0, lay)
    dpi = 200
    mm2px = dpi / 25.4
    x0 = round(place.x_of(0) * mm2px)
    w = round((place.x_of(0) + place.pwid) * mm2px) - x0
    pts = raster._hexagon_points(x0, round(place.y_of(0) * mm2px), w,
                                 round(place.plen * mm2px), 0)   # even → shifts left
    left_vertex = min(p[0] for p in pts)
    assert left_vertex >= round(geom.margin_l * mm2px) - 1     # not past the margin


def test_right_clip_content_is_rotated_180(_no_op=None):
    """A clip on the right edge renders its content turned 180° vs the left, so
    it stays the right way up for the reader (#93, Knut)."""
    import numpy as np
    target = _rgb_target(120)

    def clip_sub(side):
        geom = instruments.build("i1", clip_side=side)
        lay = geometry.compute(geom, 210.0, 297.0, 120)
        ax, ay, aw, ah = geometry.clip_area_px(geom, 297.0, 200, 210.0)
        res = raster.render_pages(target, lay, geom, seed=7, paper_w_mm=210.0,
                                  paper_h_mm=297.0, dpi=200,
                                  clip_content_mode="text", clip_text="Sample 12")
        return np.asarray(res.images[0])[ay:ay + ah, ax:ax + aw]

    left, right = clip_sub("left"), clip_sub("right")
    assert left.shape == right.shape
    assert np.array_equal(right, np.rot90(left, 2))


def test_export_clip_template(tmp_path):
    from PIL import Image
    paths = raster.export_clip_template(
        tmp_path / "tpl", width_px=160, height_px=2240,
        width_mm=20.0, height_mm=285.0, dpi=200)
    names = {p.suffix for p in paths}
    assert names == {".png", ".pdf"}
    for p in paths:
        assert p.exists() and p.stat().st_size > 0
    with Image.open(str(tmp_path / "tpl.png")) as im:
        assert im.size == (160, 2240)          # exact clip pixel size


def test_no_interstrip_gaps_from_rounding():
    """Touching strips must tile with no 1px white gap from px rounding (the
    8mm pitch rounds 94/95 while a fixed width stayed 94, gapping every other
    strip)."""
    import numpy as np
    # all patches the same non-white colour → strips form one solid block
    patches = [((50.0, 60.0, 70.0), (40.0, 45.0, 50.0)) for _ in range(441)]
    target = ColorTarget(color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=patches)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 441)
    res = raster.render_pages(target, lay, geom, seed=1, randomize=False,
                              paper_w_mm=210.0, paper_h_mm=297.0, dpi=300)
    a = np.asarray(res.images[0])
    # within the patch band, no fully-white column between the first and last patch
    band = a[(a < 250).any(2).mean(1) > 0.3]
    colwhite = (band >= 250).all(2).mean(0)
    inked = np.where(colwhite <= 0.85)[0]
    interior = colwhite[inked.min():inked.max() + 1]
    assert not (interior > 0.85).any(), "found a white gap column between strips"


def test_indicator_rotation_renders():
    """Rotated strip labels still ink the leader area (0/90/180/270)."""
    import numpy as np
    target = _rgb_target(60)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    for deg in (0, 90, 180, 270):
        res = raster.render_pages(target, lay, geom, seed=1, paper_w_mm=210.0,
                                  paper_h_mm=297.0, dpi=150, indicator_rotation=deg)
        a = np.asarray(res.images[0])
        # the top leader band should contain black label ink
        band = a[: int(a.shape[0] * 0.12)]
        assert (band < 60).all(axis=2).any(), f"no label ink at {deg}°"


def test_indicator_align_rotated_multiletter():
    """For side-rotated labels, Left vs Right alignment must change the render
    once two-letter labels (AA…) appear — Left grows the label away from the
    patches, Right toward them (#93)."""
    import numpy as np
    n = 700                                   # >26 strips → AA, AB, … exist
    target = _rgb_target(n)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, n)

    def render(align):
        return raster.render_pages(
            target, lay, geom, seed=1, paper_w_mm=210.0, paper_h_mm=297.0,
            dpi=150, indicator_rotation=90, indicator_align=align)

    left, right = render("left"), render("right")
    assert any(not np.array_equal(np.asarray(l), np.asarray(r))
               for l, r in zip(left.images, right.images)), \
        "Left and Right alignment rendered identically"


def test_indicator_align_noop_without_multiletter():
    """Alignment is a no-op when every label is a single letter (no band to
    justify within) — Left / Center / Right then render identically."""
    import numpy as np
    n = 120                                   # well under 26 strips → A…single
    target = _rgb_target(n)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, n)

    def page0(align):
        return np.asarray(raster.render_pages(
            target, lay, geom, seed=1, paper_w_mm=210.0, paper_h_mm=297.0,
            dpi=150, indicator_rotation=90, indicator_align=align).images[0])

    assert np.array_equal(page0("left"), page0("right"))
    assert np.array_equal(page0("left"), page0("center"))


def test_edge_spacers_reclaim_when_off_and_draw_when_on():
    """Edge spacers bracket each strip when ON (printtarg parity); when OFF the
    two end gaps are reclaimed for patches (denser than printtarg). The render
    draws them only when on, and the block fits the page either way (#93)."""
    import numpy as np
    # Capacity: OFF reclaims, so it never fits fewer than ON; on a height-bound
    # page with a fat spacer it fits strictly more.
    on = geometry.patches_per_sheet(
        instruments.build("i1", spacer_width=8.0, edge_spacers=True), 210.0, 297.0)
    off = geometry.patches_per_sheet(
        instruments.build("i1", spacer_width=8.0, edge_spacers=False), 210.0, 297.0)
    assert off > on

    # Render: edge spacers appear only when on, and nothing overflows.
    target = _rgb_target(120)
    g_on = instruments.build("i1", spacer_width=8.0, edge_spacers=True)
    lay = geometry.compute(g_on, 210.0, 297.0, 120)
    pl = geometry.placement(g_on, 210.0, 297.0, lay)

    def render(edge):
        return raster.render_pages(
            target, lay, g_on, seed=1, randomize=False, paper_w_mm=210.0,
            paper_h_mm=297.0, dpi=150, spacer_mode="bw", edge_spacers=edge)

    img_off = np.asarray(render(False).images[0])
    img_on = np.asarray(render(True).images[0])
    assert not np.array_equal(img_off, img_on)        # spacers drawn when on
    # leading edge spacer sits in the reserved gap above the first patch
    first_top = int(pl.y_of(0) * 150 / 25.4)
    band = img_on[max(0, first_top - int(g_on.pspa * 150 / 25.4)):first_top]
    assert (band < 250).any(), "no leading edge spacer drawn"
    # trailing edge spacer stays within the usable area
    last_bottom = pl.y_of(lay.steps_in_pass - 1) + pl.plen + g_on.pspa
    assert last_bottom <= 297.0 - max(g_on.margin_b, g_on.tspa) + 0.5


def test_custom_spacer_palette():
    """Coloured spacers are drawn only from a supplied custom palette."""
    import numpy as np
    patches = [((50.0, 50.0, 50.0), (40.0, 45.0, 50.0)) for _ in range(60)]
    target = ColorTarget(color_rep="iRGB", device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=patches)
    geom = instruments.build("i1")
    lay = geometry.compute(geom, 210.0, 297.0, 60)
    res = raster.render_pages(target, lay, geom, seed=1, paper_w_mm=210.0,
                              paper_h_mm=297.0, dpi=150, spacer_mode="colored",
                              spacer_palette=[(255, 0, 0), (255, 255, 0)])
    a = np.asarray(res.images[0])
    assert (a == [255, 0, 0]).all(2).any()          # a palette colour is used
    assert not (a == [0, 255, 0]).all(2).any()      # a non-palette colour isn't


def test_strip_label_offset_moves_labels_up():
    """A negative strip-label offset moves the indicator letters higher (toward
    the top margin) without changing the patch positions (#93)."""
    import numpy as np
    target = _rgb_target(60)
    w_mm, h_mm = 210.0, 297.0
    geom = instruments.build("i1")
    lay = geometry.compute(geom, w_mm, h_mm, 60)

    def label_top_row(offset):
        res = raster.render_pages(target, lay, geom, seed=1, randomize=False,
                                  paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=150,
                                  strip_label_offset_mm=offset)
        a = np.asarray(res.images[0])
        # first row (from top) that has any dark ink = the indicator letters
        dark_rows = np.where((a < 100).any(axis=2).any(axis=1))[0]
        return int(dark_rows[0])

    base = label_top_row(0.0)
    up = label_top_row(-5.0)
    assert up < base                       # labels moved nearer the top edge


def test_chart_text_placeholders_resolved_per_page():
    """{page} resolves to 'page X/Y' per page and {paper} etc. to friendly values
    via text_ctx, drawn into the bottom text (#93)."""
    import numpy as np
    target = _rgb_target(60)
    w_mm, h_mm = 210.0, 297.0
    geom = instruments.build("i1")
    lay = geometry.compute(geom, w_mm, h_mm, 60)
    res = raster.render_pages(target, lay, geom, seed=1, randomize=False,
                              paper_w_mm=w_mm, paper_h_mm=h_mm, dpi=150,
                              chart_text="{page} {paper}",
                              text_ctx={"paper": "A4 portrait"})
    # bottom strip has ink (the resolved text rendered)
    a = np.asarray(res.images[0])
    assert (a[-int(8 * 150 / 25.4):] < 100).any()


def test_notes_clip_strip_renders_and_scales():
    """The notes clip design renders to the requested size, is non-blank, and
    auto-fills from ctx; a wider clip uses a larger font (more ink) (#93)."""
    import numpy as np
    from workflow.layout_engine import raster
    ctx = {"count": "768", "instrument": "i1Pro", "paper": "A4 landscape",
           "page": "page 1/2", "strips": "24", "date": "2026-06-28",
           "project": "My Profile"}

    def ink(wmm, hmm):
        dpi = 200
        w, h = round(wmm * dpi / 25.4), round(hmm * dpi / 25.4)
        img = raster.render_clip_strip("notes", width_px=w, height_px=h,
                                       dpi=dpi, font_family="Inter", ctx=ctx)
        assert img.size == (w, h)
        arr = np.asarray(img.convert("L"))
        return (arr < 128).sum()

    narrow = ink(20, 297)
    wide = ink(40, 297)
    assert narrow > 0 and wide > 0                 # both have content
    assert wide > narrow                           # thicker clip → bigger text

    # No ctx → sample values, still renders (panel preview / template export).
    img = raster.render_clip_strip("notes", width_px=200, height_px=2000,
                                   dpi=200, font_family="Inter")
    assert (np.asarray(img.convert("L")) < 128).any()


def test_auto_indicator_size_never_collapses_below_legibility():
    """#108 follow-up: a wide proportional font on a narrow-patch chart used to
    shrink the auto label size to a fraction of a millimetre — so small a user
    thought the labels were off. The auto fit now floors at
    INDICATOR_MIN_LEGIBLE_MM (while an explicit size is honoured verbatim)."""
    from types import SimpleNamespace
    from workflow.layout_engine import raster

    geom = SimpleNamespace(txhisl=3.0, pwid=4.0)   # 4 mm patches (Scanner-style)
    eff = raster.effective_indicator_size_mm(geom, 300, "Inter", 0.0)
    assert eff >= raster.INDICATOR_MIN_LEGIBLE_MM
    # Explicit sizes are the user's call, even tiny ones.
    assert raster.effective_indicator_size_mm(geom, 300, "Inter", 0.4) == 0.4
    # Roomy strips keep the full instrument text height (no floor inflation).
    wide = SimpleNamespace(txhisl=3.0, pwid=40.0)
    assert raster.effective_indicator_size_mm(wide, 300, "Inter", 0.0) == 3.0
