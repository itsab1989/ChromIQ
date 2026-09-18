"""B8-346 F1 — the blank has TWO lines to respect, and they can cross.

"Show only measured patches" paints an unread column white. Above that column
there are two things it must get right at once:

* the strip LETTER, which must stay whole, and
* the first row of printed INK, which must be covered.

Round 12 photographed both failing on the shipped build, on the same night, on
different charts: a turned CR30 honeycomb kept **87.45 %** of its letters (`E`
read as `F`, `I` read as `T`) while a pointy one left a green dash on the tip
of every column. The cause was one number and one rounding:

* `label_band_bottom_px` was the NOMINAL font size below the band's top, and a
  capital is drawn from the ascender line to the BASELINE, one to three pixels
  lower, with an antialiased row below that again. The blank cut at the old
  line and took the letters' feet off.
* the cut was rounded to a whole WIDGET pixel, which is six image rows on an A4
  sheet in a 700 px window, and the gap between the letters and the ink is six
  image rows. One widget pixel is the whole of the gap.

**THE FIXTURES ARE REAL CHARTS.** A hand-drawn sheet cannot be trusted here:
the previous guard drew its own band line six pixels clear of the apex, so the
case that failed on paper could not arise in it, and the guard passed the whole
time. These build through `workflow.layout_engine.chart.build_chart` and then
measure the page that comes out, so the geometry is the product's own.
"""
from __future__ import annotations

import json
import re

import pytest
from PIL import Image
from PyQt6.QtCore import QRect

pytestmark = pytest.mark.usefixtures("qapp")

GREEN = (0, 255, 0)
RING = (0, 0, 255)


def _ti1(path, n):
    rows = ["CTI1", "", 'DESCRIPTOR "b8-346"', 'ORIGINATOR "ChromIQ"',
            'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
            "END_DATA_FORMAT", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    rows += [f"{i + 1} 0 100 0 40 45 50" for i in range(n)]
    rows += ["END_DATA", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows), encoding="utf-8")
    return path


def _build(tmp_path, name, *, ring, edge, flat, n=120,
           palette="#0000ff"):
    """A real CR30 A4 honeycomb: green patches, a blue ring, no randomising.

    The colours are the point. Green IS a patch and blue IS a spacer, so the
    question "did any printed ink survive the blank" needs no alignment and no
    threshold: it is a colour test on the rendered page.
    """
    from workflow.layout_engine import chart as le
    from workflow.layout_engine.presets import LayoutRecipe
    work = tmp_path / name
    stem = work / name
    rc = LayoutRecipe(instrument="CR30", paper="A4", dpi=300, hflag=True,
                      hex_flat_top=flat,
                      spacer_mode=("none" if ring <= 0 else "colored"),
                      spacer_width_mm=ring, edge_spacers=edge,
                      spacer_palette=[palette],
                      layout_mode="patch_first", patch_w_mm=0.0, patch_h_mm=0.0,
                      show_strip_indicators=True, cm_stagger=False,
                      use_instrument_margins=False, randomize=False,
                      seed=1, seed_fixed=True)
    kw = dict(rc.build_kwargs())
    kw.pop("instrument", None)
    kw.pop("paper", None)
    kw["randomize"] = False
    kw["seed"] = 1
    le.build_chart(_ti1(work / "src.ti1", n), stem, instrument="CR30",
                   paper="A4", **kw)
    side = json.loads((stem.parent / f"{name}.strips.json")
                      .read_text(encoding="utf-8"))
    # ...and the sidecar the MEASURE TAB reads, folded the way
    # `workflow.chart_creator._fold_engine_geometry` folds it, because that is
    # where `hex_ring_px_from_sidecar` and the two new readers look. Without it
    # the ring reads 0 and the guard measures a chart the product never draws.
    from workflow.layout_engine import papers
    pw, ph = papers.dimensions_mm("A4")
    layout = dict(side)
    layout.update({"engine": "chromiq", "engine_version": 1, "dpi": 300,
                   "paper_mm": [pw, ph], "recipe": rc.to_dict()})
    (stem.parent / f"{name}.channels.json").write_text(
        json.dumps({"ink_channels": ["r", "g", "b"], "layout": layout}, indent=1),
        encoding="utf-8")
    pages = sorted(work.glob(f"{name}_*.tif")) or [stem.with_suffix(".tif")]
    return side, pages[0]


def _page_facts(side, page):
    """Measured off the rendered page: where the letters end, where ink starts.

    Restricted to the patch columns' own x range, so the row numbers down the
    left margin and the title down the right cannot be counted as letters.
    """
    import numpy as np
    im = np.array(Image.open(page).convert("RGB"))
    pats = [p for p in side["patches"] if int(p["page"]) == 0]
    x0 = min(p["x"] for p in pats)
    x1 = max(p["x"] + p["w"] for p in pats)
    sub = slice(x0, x1)
    g = ((im[:, :, 1] > 150) & (im[:, :, 0] < 110) & (im[:, :, 2] < 110))
    b = ((im[:, :, 2] > 150) & (im[:, :, 0] < 110) & (im[:, :, 1] < 110))
    dark = (im[:, :, 0] < 90) & (im[:, :, 1] < 90) & (im[:, :, 2] < 90)
    ink_rows = np.where((g | b)[:, sub].any(axis=1))[0]
    lines = np.where(dark[:int(ink_rows[0]) + 40, sub].any(axis=1))[0]
    return {"first_ink": int(ink_rows[0]),
            "letters": (int(lines[0]), int(lines[-1])),
            "x": (int(x0), int(x1)),
            "box_top": min(p["y"] for p in pats)}


# --------------------------------------------------------------- the sidecar

@pytest.mark.parametrize("ring,edge,flat", [(6.0, True, True), (0.0, False, False)])
def test_the_recorded_label_line_is_below_the_letters_last_inked_row(
        tmp_path, ring, edge, flat):
    """`label_band_bottom_px` has to bound the INK, not the nominal font size.

    MUTATION M1, proven to land: drop `_label_ink_bottom` and put the nominal
    `label_band_h` back. Both cases of this test go red (the recorded line
    comes back as 145 where the letters ink to 147, and as 154 where they ink
    to 155); the painting test below does NOT see it, because at these three
    window sizes the device-row rounding happens to absorb three image rows.
    That is why this assertion exists separately.
    """
    side, page = _build(tmp_path, f"band-{int(ring * 10)}-{int(edge)}-{int(flat)}",
                        ring=ring, edge=edge, flat=flat)
    facts = _page_facts(side, page)
    line = side.get("label_band_bottom_px")
    assert isinstance(line, int), side.get("label_band_bottom_px")
    assert line > facts["letters"][1], (
        f"the recorded label line is {line} and the letters' last inked row is "
        f"{facts['letters'][1]}: a blank cut there paints over their feet")
    # ...and not so low that it has swallowed the field it is supposed to sit
    # above. One row of tolerance: on a chart whose apex overhangs INTO the
    # band the two genuinely overlap, which is the collision F1 records.
    assert line <= facts["first_ink"] + 3, (
        f"the recorded label line {line} is below the first inked row "
        f"{facts['first_ink']} by more than the overlap the chart itself has")


@pytest.mark.parametrize("ring,edge,flat", [(6.0, True, True), (0.0, False, False),
                                            (3.0, True, False)])
def test_the_recorded_ink_top_is_the_pages_own_first_inked_row(
        tmp_path, ring, edge, flat):
    """`patch_ink_top_px` is recorded where the engine draws, and nothing
    downstream can work it out: measured across these three charts the first
    inked row lands 18 px BELOW the first recorded box top, 20 above it, and 40
    above it, for the same 122.8 px slot.

    MUTATION M2, proven to land: record only the hexagon and let the spacer
    polygons go unrecorded. Five of the fourteen cases in this file go red.
    """
    side, page = _build(tmp_path, f"inktop-{int(ring * 10)}-{int(edge)}-{int(flat)}",
                        ring=ring, edge=edge, flat=flat)
    facts = _page_facts(side, page)
    tops = side.get("patch_ink_top_px")
    assert isinstance(tops, list) and tops, side.get("patch_ink_top_px")
    assert tops[0] == facts["first_ink"], (
        f"the engine recorded its first inked row as {tops[0]} and the page it "
        f"drew starts at {facts['first_ink']}")


# ------------------------------------------------------------- the blank itself

def _blank_pair(qapp, side, page, ring_px, flat, size=(700, 980)):
    """Paint the preview with the blank off and on, and hand back both images."""
    from ui.tiff_preview import TiffPreview
    pats = [p for p in side["patches"] if int(p["page"]) == 0]
    cols: dict[str, list] = {}
    for p in pats:
        cols.setdefault(re.match(r"([A-Z]+)", p["loc"]).group(1), []).append(p)
    order = sorted(cols, key=lambda c: min(p["x"] for p in cols[c]))
    boxes = [QRect(p["x"], p["y"], p["w"], p["h"]) for p in pats]
    rects = []
    line = int(side["label_band_bottom_px"])
    for c in order:
        ps = cols[c]
        x = min(p["x"] for p in ps)
        w = max(p["x"] + p["w"] for p in ps) - x
        bot = max(p["y"] + p["h"] for p in ps)
        rects.append(QRect(x, line, w, bot - line + 1))
    out = {}
    for blank in (False, True):
        p = TiffPreview()
        try:
            p.resize(*size)
            p.load_tiff([page])
            qapp.processEvents()
            p.set_hex_zigzag(True, flat_top=flat)
            p.set_hex_ring_px(ring_px)
            p.set_patch_ink_top_px({0: side["patch_ink_top_px"][0]})
            p.set_page_patch_boxes({0: boxes})
            p.set_stripe_rects(rects)
            p.set_stripe_read_map({i: False for i in range(len(rects))})
            p.set_show_only_measured(blank)
            p.show()
            qapp.processEvents()
            p._update_display()
            qapp.processEvents()
            pm = p._img_label.pixmap()
            out[blank] = pm.toImage() if pm is not None else None
        finally:
            p.close()
    return out


def _colours(img):
    """(patch ink, ring ink, dark) pixel counts over the whole canvas."""
    green = ring = dark = 0
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if g > 150 and r < 110 and b < 110:
                green += 1
            elif b > 150 and r < 110 and g < 110:
                ring += 1
            elif r < 90 and g < 90 and b < 90:
                dark += 1
    return green, ring, dark


@pytest.mark.parametrize("w,h", [(700, 980), (940, 880), (1100, 760)])
@pytest.mark.parametrize("ring,edge,flat", [(6.0, True, True), (0.0, False, False),
                                            (3.0, True, False)])
def test_no_printed_ink_survives_the_blank_and_the_letters_do(
        qapp, tmp_path, ring, edge, flat, w, h):
    """The whole of F1, in one measurement, on three real charts.

    With nothing read, every column is blanked, so ANY green or blue left on
    the canvas is chart ink the user was told is hidden, and any large loss of
    dark pixels is a letter losing its feet.

    Measured on screen before the fix: 5, 32 and 122 device pixels of ring on
    the 3.0 mm chart, 19 of patch ink on the ring-0 one, and 87.45 % of the
    letters left on the 6.0 mm turned one.

    THREE WINDOW SIZES, because the whole fault is a rounding phase: the
    shipped build was clean at two of the six sizes round 12 photographed and
    leaked at the other four, and a single-size guard is how it went unseen.

    MUTATIONS, each proven to land (5 of the 14 cases red for each):
      * M3, the shipped cut: `ceil` to a whole WIDGET pixel with the integer
        `QRegion`, and no ink line at all;
      * M4, keep the device-row rounding but drop the ink line.
    M2 (the engine recording the hexagon but not the spacers) also reddens this
    test, from the other end of the same pipe.
    """
    name = f"blank-{int(ring * 10)}-{int(edge)}-{int(flat)}-{w}"
    side, page = _build(tmp_path, name, ring=ring, edge=edge, flat=flat)
    from ui.tabs.tab_measure import hex_ring_px_from_sidecar
    ring_px = hex_ring_px_from_sidecar(
        (tmp_path / name / f"{name}.ti2"))
    out = _blank_pair(qapp, side, page, ring_px, flat, size=(w, h))
    assert out[False] is not None and out[True] is not None
    g_off, r_off, d_off = _colours(out[False])
    g_on, r_on, d_on = _colours(out[True])
    assert g_off > 0, "the fixture printed no patches"
    assert g_on == 0, f"{g_on} pixels of patch ink survived the blank"
    if ring > 0:
        assert r_off > 0, "the fixture printed no spacer ring"
        assert r_on == 0, f"{r_on} pixels of spacer ring survived the blank"
    # The letters are the dark pixels, and they are all that should be left of
    # the strip: at most the row the chart itself overlapped with its ink.
    assert d_off > 0, "the fixture printed no letters"
    # 98.5 %, MEASURED, NOT PICKED. The fixed build keeps 100.00 / 99.10 /
    # 100.00 % of the letters on these three charts; the 0.90 % is the row the
    # ring-0 chart's own apex overlaps them by. The shipped build kept 87.45 %
    # on a turned CR30 at 700x620, and the mutation table in the register shows
    # what each mutation does to this number.
    assert d_on >= 0.985 * d_off, (
        f"the blank ate the strip letters: {d_on} of {d_off} dark pixels left "
        f"({100.0 * d_on / d_off:.2f} %)")


# ---------------------------------------------------------------------------
# Round 13 on these fixes: a fixture too small to hold the letter that broke,
# a fix that reached only charts built after it, and a white patch counted as
# ink.
# ---------------------------------------------------------------------------

def test_the_band_clears_the_deepest_letter_on_every_page(tmp_path):
    """R13-1: `Q` is the only capital with a TAIL, and the first version of
    this fix left it out of the probe to keep the band clear of a spacer ring.
    On a 17-strip chart the `Q` column then lost its tail and read as `O`, with
    twelve clear rows below it: 15 dark device pixels gone, photographed.

    **THE FIXTURE IS THE POINT.** Every other case in this file builds 120
    patches, which is eleven strips, A to K: a chart that cannot contain a `Q`
    cannot see this fault, and the guard written to close B8-346 F1 was blind
    to it for exactly that reason. This one builds 900.

    MUTATION, proven to land: probe `_ALL_CAPS` minus `Q`, or the whole
    alphabet regardless of the chart (the first clips the tail, the second puts
    the band below the first inked row on a chart with no `Q` at all).
    """
    import numpy as np
    side, page = _build(tmp_path, "deepest", ring=3.0, edge=False, flat=True,
                        n=900)
    band = int(side["label_band_bottom_px"])
    pages = sorted(page.parent.glob(f"{page.stem.rsplit('_', 1)[0]}_*.tif"))
    assert len(pages) > 1, "the fixture must span pages to reach a Q"
    seen = set()
    for pg, tif in enumerate(pages):
        im = np.array(Image.open(tif).convert("RGB"))
        dark = (im[:, :, 0] < 90) & (im[:, :, 1] < 90) & (im[:, :, 2] < 90)
        own = [p for p in side["patches"] if int(p["page"]) == pg]
        if not own:
            continue
        for c in {re.match(r"([A-Z]+)", p["loc"]).group(1) for p in own}:
            ps = [p for p in own
                  if re.match(r"([A-Z]+)", p["loc"]).group(1) == c]
            x0 = min(p["x"] for p in ps)
            x1 = max(p["x"] + p["w"] for p in ps)
            rows = np.where(dark[:900, x0:x1].any(axis=1))[0]
            assert len(rows), f"{c} printed no letter"
            seen.add(c)
            assert int(rows[-1]) < band, (
                f"the strip letter {c!r} inks down to row {int(rows[-1])} and "
                f"the band is recorded at {band}: the blank cuts through it")
    assert "Q" in seen, f"the fixture never printed a Q: {sorted(seen)}"


def test_a_chart_built_before_the_key_existed_is_measured_off_its_page(
        tmp_path):
    """R13-2: the fix is carried by a new sidecar key, and nothing migrates a
    chart. Every chart already on disk kept the leak: measured on screen, 30,
    36 and 30 device pixels of spacer ring at three window sizes.

    The page itself is asked instead, BY COLOUR: a strip letter is drawn in
    black and fades through neutral greys, so a row with chroma in it cannot be
    a letter, whatever else it holds.

    MUTATION, proven to land: return `{}` when the key is absent.
    """
    import json as _json
    import shutil
    from ui.tabs.tab_measure import patch_ink_top_px_from_sidecar
    name = "oldchart"
    side, _page = _build(tmp_path, name, ring=3.0, edge=True, flat=False)
    ti2 = tmp_path / name / f"{name}.ti2"
    channels = tmp_path / name / f"{name}.channels.json"
    recorded = patch_ink_top_px_from_sidecar(ti2)
    assert recorded, "the fixture recorded no ink top at all"
    doc = _json.loads(channels.read_text(encoding="utf-8"))
    doc["layout"].pop("patch_ink_top_px", None)
    shutil.copy2(channels, channels.with_suffix(".keep"))
    channels.write_text(_json.dumps(doc), encoding="utf-8")
    try:
        measured = patch_ink_top_px_from_sidecar(ti2)
    finally:
        shutil.move(str(channels.with_suffix(".keep")), str(channels))
    assert measured, (
        "a chart built before the key existed gets no ink line at all, so the "
        "blank goes back to cutting at the band and the ring shows")
    assert measured == recorded, (
        f"the page says {measured} and the engine recorded {recorded}")


def test_a_white_patch_is_not_counted_as_ink(tmp_path):
    """R13-6: `_note_ink` fired for every polygon the renderer drew, whatever
    colour it was, so a chart whose first row is pure white recorded an inked
    row where the printer lays nothing down. The blank's cut is then pulled up
    for no reason, and on a chart where the letters and the field are close
    that costs a row of letter.

    MUTATION, proven to land: drop the white test from `_note_ink`.
    """
    from workflow.layout_engine import chart as le
    from workflow.layout_engine.presets import LayoutRecipe
    work = tmp_path / "white"
    stem = work / "white"
    src = work / "src.ti1"
    work.mkdir(parents=True, exist_ok=True)
    rows = ["CTI1", "", 'DESCRIPTOR "white"', 'ORIGINATOR "ChromIQ"',
            'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
            "END_DATA_FORMAT", "NUMBER_OF_SETS 24", "BEGIN_DATA"]
    rows += [f"{i + 1} 100 100 100 95 100 108" for i in range(24)]
    rows += ["END_DATA", ""]
    src.write_text("\n".join(rows), encoding="utf-8")
    rc = LayoutRecipe(instrument="CR30", paper="A4", dpi=300, hflag=True,
                      hex_flat_top=False, spacer_mode="none",
                      spacer_width_mm=0.0, edge_spacers=False,
                      layout_mode="patch_first", patch_w_mm=8.0,
                      patch_h_mm=8.0, show_strip_indicators=True,
                      use_instrument_margins=False, randomize=False,
                      seed=1, seed_fixed=True)
    kw = dict(rc.build_kwargs())
    kw.pop("instrument", None)
    kw.pop("paper", None)
    kw["randomize"] = False
    kw["seed"] = 1
    le.build_chart(src, stem, instrument="CR30", paper="A4", **kw)
    side = json.loads((stem.parent / "white.strips.json")
                      .read_text(encoding="utf-8"))
    tops = side.get("patch_ink_top_px")
    assert isinstance(tops, list) and tops, side.get("patch_ink_top_px")
    assert not [v for v in tops if v], (
        f"a sheet of pure white patches claims it inked row {tops}")


# ---------------------------------------------------------------------------
# Round 14 on round 13: the fall-back's own limits, pinned so that a later
# change cannot quietly widen them.
# ---------------------------------------------------------------------------

def test_the_fall_back_is_silent_rather_than_wrong_on_a_black_ring(tmp_path):
    """R14-F1: the fall-back proves a row is ink by its COLOUR, and a spacer
    ring drawn in BLACK has none. `contrast.spacer_rgb` returns black or white,
    and "Black & white" is a spacer mode a user can choose, so on such a chart
    the first row with chroma in it is a PATCH, well below the ring that really
    is the top of the ink.

    Reporting that as "the first inked row" is a wrong number dressed as a
    measurement, and it is worse than saying nothing: the caller only ever
    acts on this line when it lands ABOVE the label band. So a row found below
    the band is dropped, and the chart behaves exactly as it did before the key
    existed.

    **THE FIXTURE IS THE POINT AGAIN.** Every other case in this file paints
    its ring `#0000ff`, and round 14 turned the guard red by changing that one
    string to `#000000` and nothing else.

    MUTATION, proven to land: drop the `row < band_bot` test.
    """
    import json as _json
    import shutil
    from ui.tabs.tab_measure import patch_ink_top_px_from_sidecar
    name = "blackring"
    side, _page = _build(tmp_path, name, ring=3.0, edge=True, flat=False,
                         palette="#000000")
    ti2 = tmp_path / name / f"{name}.ti2"
    channels = tmp_path / name / f"{name}.channels.json"
    doc = _json.loads(channels.read_text(encoding="utf-8"))
    recorded = doc["layout"].get("patch_ink_top_px")
    assert recorded and recorded[0], recorded
    doc["layout"].pop("patch_ink_top_px", None)
    shutil.copy2(channels, channels.with_suffix(".keep"))
    channels.write_text(_json.dumps(doc), encoding="utf-8")
    try:
        measured = patch_ink_top_px_from_sidecar(ti2)
    finally:
        shutil.move(str(channels.with_suffix(".keep")), str(channels))
    assert measured == {}, (
        f"the fall-back answered {measured} on a chart whose ring is black; "
        f"the engine recorded {recorded[0]}, and anything else here is a "
        f"guess presented as a measurement")


def test_a_project_name_with_brackets_still_finds_its_pages(tmp_path):
    """R14-F3: the fall-back listed pages with `Path.glob` on the chart's own
    stem, and `[`, `]`, `*` and `?` are wildcards there. A chart called
    `Chart [v2]` found no pages and the fall-back returned nothing.

    MUTATION, proven to land: go back to `stem.parent.glob(stem.name + ...)`.
    """
    import json as _json
    import shutil
    from ui.tabs.tab_measure import patch_ink_top_px_from_sidecar
    # MULTI-PAGE ON PURPOSE. A one-page chart is written as `<stem>.tif` and
    # the page list falls back to that name directly, so the glob is never
    # asked anything and a broken one passes: round 14's own mutation stayed
    # green until this fixture spanned pages.
    name = "Chart [v2]"
    side, _page = _build(tmp_path, name, ring=3.0, edge=True, flat=False,
                         n=900)
    ti2 = tmp_path / name / f"{name}.ti2"
    channels = tmp_path / name / f"{name}.channels.json"
    doc = _json.loads(channels.read_text(encoding="utf-8"))
    doc["layout"].pop("patch_ink_top_px", None)
    shutil.copy2(channels, channels.with_suffix(".keep"))
    channels.write_text(_json.dumps(doc), encoding="utf-8")
    try:
        measured = patch_ink_top_px_from_sidecar(ti2)
    finally:
        shutil.move(str(channels.with_suffix(".keep")), str(channels))
    assert measured, (
        "a chart whose name holds brackets found none of its own pages")


@pytest.mark.parametrize("rgb,found", [((255, 212, 255), True),
                                       ((255, 217, 255), False),
                                       ((0, 0, 0), False),
                                       ((128, 128, 128), False)])
def test_what_the_ink_probe_can_and_cannot_see(tmp_path, rgb, found):
    """R14-F2: the chroma floor was a bare `40` that nothing in the suite
    guarded. Round 14 moved it to 0 and to 120 and the whole everyday tier,
    16,495 tests, stayed green both times.

    These are the measured edges: a 15 % magenta tint spreads 43 and is seen,
    (255, 217, 255) spreads 38 and is not, and neutrals of any darkness never
    are, which is the limit the test above is about.
    """
    from ui.tabs.tab_measure import _first_coloured_row
    page = tmp_path / f"probe-{rgb[0]}-{rgb[1]}-{rgb[2]}.tif"
    im = Image.new("RGB", (40, 30), (255, 255, 255))
    for x in range(8, 32):
        for y in range(10, 20):
            im.putpixel((x, y), rgb)
    im.save(page)
    got = _first_coloured_row(page, 0, 40, 30)
    assert (got is not None) is found, (
        f"{rgb} spreads {max(rgb) - min(rgb)} and the probe "
        f"{'found' if got is not None else 'missed'} it")


def test_an_ink_line_recorded_at_row_zero_reaches_the_preview(tmp_path):
    """R14-F6: row 0 is a row. The reader dropped a recorded 0 as falsy while
    the preview's own test said `is not None`, so the two halves disagreed
    about what "no ink line" means and nothing in the suite noticed.
    """
    import json as _json
    from ui.tabs.tab_measure import patch_ink_top_px_from_sidecar
    name = "atzero"
    _side, _page = _build(tmp_path, name, ring=3.0, edge=True, flat=False)
    channels = tmp_path / name / f"{name}.channels.json"
    doc = _json.loads(channels.read_text(encoding="utf-8"))
    doc["layout"]["patch_ink_top_px"] = [0]
    channels.write_text(_json.dumps(doc), encoding="utf-8")
    got = patch_ink_top_px_from_sidecar(tmp_path / name / f"{name}.ti2")
    assert got == {0: 0.0}, (
        f"a chart whose ink starts at row 0 hands the preview {got}")
