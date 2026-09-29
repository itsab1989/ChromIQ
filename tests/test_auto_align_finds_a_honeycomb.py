"""Auto align on a hexagonal chart: the search scanin cannot do.

**What this file exists for.** ``scanin``'s recogniser finds a chart by the
continuous straight edges in the picture, and an interlocking honeycomb has
none to give it. Measured on Knut's own CR30 chart (2026-09-11,
``~/Desktop/ChromIQ-knut-hex/records/G-placement-stages.json``) it returns
*not recognised* with **zero** candidates from every starting placement, from
the app's own seed and from a rough hand placement alike, so the button
declined and moved the corners 0.0 px while the same drive on a rectangular
chart of the same 648 colours landed 0.6 px from truth.

Only step 1 fails. Steps 2 and 3 were measured on the same honeycomb and behave
exactly as they do on a grid of squares: the refinement reshapes it onto the
patches, and the checks score a right placement 0.969 against a wrong one's
0.514 with the floor at 0.80. So :mod:`workflow.hex_block_search` is a step 1
for charts scanin cannot see — it finds the INK, never the patch shape — and
:func:`workflow.scan_placement.place_grid` asks it only when the caller says
the chart is a honeycomb AND the first search came back empty.

**The regression argument is structural and it is tested as such.**
``hexagonal`` defaults to False and the window passes
``chart_is_hexagonal(...)``, so a rectangular chart cannot reach a line of the
new code. That is asserted here by watching the module, not by reasoning about
it. It is also measured: 77 pictures of 8 honeycomb charts in
``~/Desktop/ChromIQ-hex-autoalign``, and the same rectangular sweep before and
after the change.

**And the downside is bounded.** Nothing this finds is VOUCHED FOR by it.
Every quad goes to the same refinement and the same three gates as scanin's own
answers, so the worst case remains "auto align still does not work" and never
"auto align put the grid somewhere wrong and said it was right" — which is what
``test_a_scan_missing_an_edge_is_never_vouched_for`` is here to keep true.

Since Knut's ruling of 2026-09-11 (#182) a quad the gates refuse IS applied, so
the user can see and correct it, and the window says it could not confirm it.
That is why the test above asks `trusted` rather than `ok`: what must never
happen is a wrong placement announced as a good one, and that is unchanged.
"""
from __future__ import annotations

import inspect
import json
import math
import os
import random
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.text_io import read_text                              # noqa: E402
from workflow import hex_block_search as HBS                    # noqa: E402
from workflow.cht_parser import parse_cht                       # noqa: E402
from workflow.scan_auto_align import (AutoAlignResult,          # noqa: E402
                                      agreement_scorer,
                                      expected_luminance,
                                      reference_agreement_at)
from workflow.scan_placement import place_grid                  # noqa: E402

CHART_DPI = 100
SCAN_DPI = 150
TURN_DEG = -1.4


# ---------------------------------------------------------------------------
# a real honeycomb, built by the engine that builds the shipped ones
# ---------------------------------------------------------------------------
def _write_ti1(path: Path, n: int) -> None:
    rng = random.Random(20260911)
    rows = [(i + 1,) + tuple(round(rng.uniform(2, 98), 3) for _ in range(3))
            for i in range(n)]
    body = "\n".join(f"{i} {r} {g} {b}" for i, r, g, b in rows)
    path.write_text(
        'CTI1   \n\nDESCRIPTOR "honeycomb fixture"\n'
        'ORIGINATOR "ChromIQ test"\nKEYWORD "APPROX_WHITE_POINT"\n'
        'APPROX_WHITE_POINT "95.045781 100.000003 108.905751"\n'
        'COLOR_REP "RGB"\n\nNUMBER_OF_FIELDS 4\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID RGB_R RGB_G RGB_B\nEND_DATA_FORMAT\n\n'
        f'NUMBER_OF_SETS {n}\nBEGIN_DATA\n{body}\nEND_DATA\n',
        encoding="utf-8")


def _srgb_xyz(r: float, g: float, b: float) -> tuple[float, float, float]:
    """A measurement of a patch printed in sRGB, without ArgyllCMS.

    `fakeread` would give the same shape of answer and needs a binary this
    suite must not depend on. What the ladder actually uses out of a .cie is
    the ORDER of the luminances, and that is the same either way.
    """
    def lin(v):
        v = max(0.0, min(1.0, v / 100.0))
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    rl, gl, bl = lin(r), lin(g), lin(b)
    return (100 * (0.4124 * rl + 0.3576 * gl + 0.1805 * bl),
            100 * (0.2126 * rl + 0.7152 * gl + 0.0722 * bl),
            100 * (0.0193 * rl + 0.1192 * gl + 0.9505 * bl))


def _ti3_from_ti2(ti2: Path, ti3: Path) -> None:
    """The .ti3 chartread would have written for this chart, in sRGB."""
    fields: list[str] = []
    in_fmt = in_data = False
    rows: list[list[str]] = []
    for line in ti2.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if t == "BEGIN_DATA_FORMAT":
            in_fmt = True
            continue
        if t == "END_DATA_FORMAT":
            in_fmt = False
            continue
        if in_fmt:
            fields = t.split()
            continue
        if t == "BEGIN_DATA":
            in_data = True
            continue
        if t == "END_DATA":
            break
        if in_data and t:
            rows.append(t.split())
    i_id = fields.index("SAMPLE_ID")
    i_loc = fields.index("SAMPLE_LOC")
    i_r, i_g, i_b = (fields.index(f"RGB_{c}") for c in "RGB")
    body = []
    for c in rows:
        x, y, z = _srgb_xyz(float(c[i_r]), float(c[i_g]), float(c[i_b]))
        body.append(f"{c[i_id]} {c[i_loc]} {c[i_r]} {c[i_g]} {c[i_b]} "
                    f"{x:.6f} {y:.6f} {z:.6f}")
    ti3.write_text(
        'CTI3   \n\nDESCRIPTOR "honeycomb fixture"\n'
        'ORIGINATOR "Argyll chartread"\nDEVICE_CLASS "OUTPUT"\n'
        'COLOR_REP "RGB_XYZ"\n\nNUMBER_OF_FIELDS 8\nBEGIN_DATA_FORMAT\n'
        'SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z\n'
        'END_DATA_FORMAT\n\n'
        f'NUMBER_OF_SETS {len(body)}\nBEGIN_DATA\n' + "\n".join(body)
        + "\nEND_DATA\n", encoding="utf-8")


def _simulate(src: Path, out: Path, deg: float = TURN_DEG):
    """A flatbed scan of that sheet: resampled to the scanner's dpi, turned a
    little, softened and speckled. Returns the map from chart pixels to picture
    pixels so the truth quad can be exact rather than guessed."""
    import numpy as np
    from PIL import Image, ImageFilter
    im = Image.open(src).convert("RGB")
    s = SCAN_DPI / CHART_DPI
    w, h = int(im.width * s), int(im.height * s)
    im = im.resize((w, h), Image.Resampling.LANCZOS)
    turned = im.rotate(deg, resample=Image.Resampling.BICUBIC, expand=True,
                       fillcolor=(252, 251, 249))
    turned = turned.filter(ImageFilter.GaussianBlur(0.6))
    arr = np.asarray(turned).astype(np.int16)
    rng = np.random.default_rng(11)
    arr = np.clip(arr + rng.normal(0, 1.6, arr.shape).astype(np.int16), 0, 255)
    Image.fromarray(arr.astype("uint8")).save(out, compression="tiff_lzw")
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = w / 2.0, h / 2.0
    ox, oy = turned.width / 2.0, turned.height / 2.0

    def to_picture(x, y):
        px, py = x * s - cx, y * s - cy
        return (ca * px + sa * py + ox, -sa * px + ca * py + oy)
    return to_picture, (turned.width, turned.height)


@pytest.fixture(scope="module")
def hexchart(tmp_path_factory):
    """A CR30 flat-top honeycomb, its measurement, its scanner target and a
    simulated scan of it — all from the app's own code, so the picture under
    test is a chart ChromIQ would really make."""
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import LayoutRecipe
    from workflow.scanin_target import build_scanin_target_from_paths

    d = tmp_path_factory.mktemp("honeycomb")
    _write_ti1(d / "hexfix.ti1", 60)
    kwargs = dict(instrument="CR30", paper="A4", hflag=True, hex_flat_top=True,
                  dpi=CHART_DPI, randomize=False, seed=1, border=5.0,
                  pscale=2.2)
    res = le_chart.build_chart(d / "hexfix.ti1", d / "hexfix", **kwargs)
    layout = json.loads((d / "hexfix.strips.json").read_text(
        encoding="utf-8"))
    layout.update({"engine": "chromiq", "engine_version": 1, "dpi": CHART_DPI,
                   "seed": res.seed, "color_rep": res.color_rep,
                   "recipe": LayoutRecipe.from_build_kwargs(kwargs).to_dict()})
    channels = d / "hexfix.channels.json"
    channels.write_text(json.dumps({"ink_channels": ["r", "g", "b"],
                                    "layout": layout}), encoding="utf-8")
    _ti3_from_ti2(d / "hexfix.ti2", d / "hexfix.ti3")
    target = build_scanin_target_from_paths(channels, d / "hexfix.ti3",
                                            d / "hexfix")
    cht = Path(target.cht_paths[0])
    text = read_text(cht, lenient=True)
    boxes = parse_cht(text).patches
    to_picture, size = _simulate(d / "hexfix.tif", d / "scan.tif")

    pats = [p for p in layout["patches"] if int(p["page"]) == 0]
    x0 = min(p["x"] for p in pats)
    y0 = min(p["y"] for p in pats)
    x1 = max(p["x"] + p["w"] for p in pats)
    y1 = max(p["y"] + p["h"] for p in pats)
    truth = [to_picture(x0, y0), to_picture(x1, y0),
             to_picture(x1, y1), to_picture(x0, y1)]
    from workflow.photo_fit import patch_pitch_px
    bbox = (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))
    return dict(dir=d, cht=cht, cie=Path(target.cie_path), boxes=boxes,
                scan=d / "scan.tif", size=size, truth=truth,
                channels=channels, base=d / "hexfix",
                pitch=patch_pitch_px(boxes, truth, bbox),
                expected=expected_luminance(text, Path(target.cie_path),
                                            chart_ids=[b.name for b in boxes]))


def _worst(a, b) -> float:
    return max(math.hypot(x - u, y - v) for (x, y), (u, v) in zip(a, b))


def _seed_quad(size, boxes):
    """The rectangle the marquee draws for itself — the patch block's aspect at
    90 % of the picture, centred (``ui/scan_grid_marquee._seed_corners``)."""
    iw, ih = float(size[0]), float(size[1])
    ar = ((max(b.x2 for b in boxes) - min(b.x1 for b in boxes))
          / (max(b.y2 for b in boxes) - min(b.y1 for b in boxes)))
    aw, ah = iw * 0.90, ih * 0.90
    if aw / ah > ar:
        h = ah
        w = h * ar
    else:
        w = aw
        h = w / ar
    cx, cy = iw / 2.0, ih / 2.0
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
            (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def _blind_scanin(monkeypatch):
    """scanin as it really behaves on a honeycomb: nothing found, no candidates.

    Measured, not imagined — `records/G-placement-stages.json`, three starting
    placements, 0 candidates each time.
    """
    import workflow.scan_auto_align as AA
    monkeypatch.setattr(AA, "auto_align",
                        lambda *a, **k: AutoAlignResult(reason="not-recognised"))


def _run(hexchart, monkeypatch, start=None, **kw):
    _blind_scanin(monkeypatch)
    return place_grid("scanin-not-run", hexchart["scan"], hexchart["cht"],
                      hexchart["cie"], hexchart["boxes"], hexchart["expected"],
                      hexchart["size"], current_corners=start,
                      sample_frac=0.60, **kw)


# ------------------------------------------------------------- the whole job
def test_the_ladder_places_a_honeycomb_from_the_apps_own_seed(
        hexchart, monkeypatch):
    """The case Basti asked about: a honeycomb, a scan, and nobody has touched
    the corners. Today it ends `not-recognised` and moves nothing."""
    start = _seed_quad(hexchart["size"], hexchart["boxes"])
    assert _worst(start, hexchart["truth"]) > 0.5 * hexchart["pitch"], (
        "the app's own seed already sits on the patches — this fixture cannot "
        "tell a working search from a broken one")
    r = _run(hexchart, monkeypatch, start=None, hexagonal=True)
    assert r.ok, f"the honeycomb was not placed: {r.ending} / {r.find_reason}"
    assert r.ending == "placed"
    assert r.find_reason == "hex-block-search"
    assert _worst(r.corners, hexchart["truth"]) < 0.25 * hexchart["pitch"], (
        f"placed {_worst(r.corners, hexchart['truth']):.1f} px from the true "
        f"corners, and a patch pitch is {hexchart['pitch']:.1f} px")
    assert r.rho is not None and r.rho >= 0.80


def test_the_same_picture_is_refused_when_the_caller_does_not_say_honeycomb(
        hexchart, monkeypatch):
    """The regression argument, from the other side: the flag is the whole of
    what lets the new search run, so with it off this is exactly the behaviour
    that shipped."""
    r = _run(hexchart, monkeypatch, start=None)
    assert not r.ok
    assert r.ending == "not-recognised"


def test_place_grid_does_not_look_for_a_honeycomb_unless_it_is_told_to():
    """`hexagonal` defaults to False, so every caller that does not know about
    it keeps the behaviour it has."""
    assert inspect.signature(place_grid).parameters["hexagonal"].default is False


def test_a_rectangular_chart_never_reaches_the_new_search(
        hexchart, monkeypatch):
    """Watched rather than reasoned about: nothing in `hex_block_search` is
    called on the path a rectangular chart takes."""
    calls = []
    import workflow.hex_block_search as H
    monkeypatch.setattr(H, "find_block",
                        lambda *a, **k: calls.append(a) or H.HexBlockResult())
    _run(hexchart, monkeypatch, start=None)
    assert calls == [], "the hexagonal search ran for a chart nobody called hex"


def test_a_block_the_new_search_found_is_applied_when_the_reshaping_declines(
        hexchart, monkeypatch):
    """The majority outcome on the old path — 175 of 290 measured cells — and
    it has to be the same on this one. A quad the new search found is a SEARCH
    ANSWER: when the reshaping finds nothing better it goes to the gates as it
    is, rather than being thrown away as "nothing was proposed"."""
    import workflow.photo_fit as PF
    from workflow.photo_fit import RefineResult
    monkeypatch.setattr(PF, "refine_corners",
                        lambda *a, **k: RefineResult(reason="too-far-to-fit"))
    r = _run(hexchart, monkeypatch, start=None, hexagonal=True)
    assert r.ok, f"the block that was found was discarded: {r.ending}"
    assert r.ending == "placed"
    assert not r.fitted


def test_the_search_does_not_run_when_scanin_already_found_the_chart(
        hexchart, monkeypatch):
    """It is a FALLBACK. A honeycomb scanin can see — and there may be one —
    must take the path that is measured over 290 placements, not this one."""
    calls = []
    import workflow.hex_block_search as H
    import workflow.scan_auto_align as AA
    monkeypatch.setattr(H, "find_block",
                        lambda *a, **k: calls.append(a) or H.HexBlockResult())
    monkeypatch.setattr(AA, "auto_align", lambda *a, **k: AutoAlignResult(
        corners=[tuple(p) for p in hexchart["truth"]], rho=0.99))
    r = place_grid("scanin-not-run", hexchart["scan"], hexchart["cht"],
                   hexchart["cie"], hexchart["boxes"], hexchart["expected"],
                   hexchart["size"], sample_frac=0.60, hexagonal=True)
    assert calls == []
    assert r.ok


# ------------------------------------------------------- what it will not do
def test_the_search_never_overrules_a_placement_somebody_made(hexchart):
    """The window passes the corners only when the marquee says a person put
    them there. A proposal that is not better than theirs is not an answer, and
    the ladder goes on to refine THEIR corners, which is what it does today."""
    r = HBS.find_block(hexchart["scan"], hexchart["boxes"],
                       hexchart["expected"], hexchart["size"],
                       current_corners=hexchart["truth"], sample_frac=0.60)
    assert not r.ok
    assert r.reason == "no-better"
    assert r.rho_before is not None and r.rho_before >= 0.80


def test_a_scan_missing_an_edge_is_never_vouched_for(
        hexchart, monkeypatch, tmp_path):
    """A block that runs off the picture cannot be found, and the answer that
    matters is that nothing claims it was. Measured over the bench's 8 charts,
    all 22 cropped pictures ended `not-seated`.

    UNTIL 2026-09-11 THIS ASSERTED THAT NOTHING WAS APPLIED. Knut's #182 ruling
    changed that and only that: *"place its best attempt and tell user to check
    it."* The picture check still refuses, the ending is still `not-seated`,
    and the window still tells the user in its own words that it could not
    confirm the placement. `trusted` is the flag that carries the verdict, and
    it is what a caller must read.
    """
    from PIL import Image
    im = Image.open(hexchart["scan"])
    cut = int(im.width * 0.22)
    clipped = tmp_path / "clipped.tif"
    im.crop((cut, 0, im.width, im.height)).save(clipped, compression="tiff_lzw")
    _blind_scanin(monkeypatch)
    r = place_grid("scanin-not-run", clipped, hexchart["cht"], hexchart["cie"],
                   hexchart["boxes"], hexchart["expected"],
                   (im.width - cut, im.height), sample_frac=0.60,
                   hexagonal=True)
    assert not r.trusted, (
        f"a chart with an edge missing was vouched for anyway: {r.ending}")
    assert r.ending in ("not-seated", "below-floor"), r.ending


def test_the_region_the_window_computes_is_a_hint_and_not_a_fence(hexchart):
    """`search_region_for` hands over any quad covering less than 70 % of the
    sheet, and on a scan just loaded that quad is the APP's own centred
    rectangle. On a part-full last page it is tall and narrow and cuts the real
    block in half: measured on page 2 of the CR30 chart, searching only inside
    it ended 337 px out and was refused, where searching the whole picture
    ended 2.6 px out."""
    xs = [p[0] for p in hexchart["truth"]]
    ys = [p[1] for p in hexchart["truth"]]
    # a region that keeps the right two thirds of the block and nothing else
    region = (min(xs) + (max(xs) - min(xs)) * 0.34, min(ys),
              max(xs), max(ys))
    r = HBS.find_block(hexchart["scan"], hexchart["boxes"],
                       hexchart["expected"], hexchart["size"],
                       sample_frac=0.60, search_region=region)
    assert r.ok, "a region that cuts the block left nothing findable"
    assert _worst(r.corners, hexchart["truth"]) < 0.5 * hexchart["pitch"]


# ------------------------------------------------------------ the mechanisms
def test_the_four_ways_up_are_scored_and_the_colours_pick_one(hexchart):
    """A honeycomb has no fiducials, so which corner is 'top left' is a
    question only the colours can answer."""
    r = HBS.find_block(hexchart["scan"], hexchart["boxes"],
                       hexchart["expected"], hexchart["size"], sample_frac=0.60)
    assert r.ok
    score = agreement_scorer(hexchart["scan"], hexchart["expected"])
    upright = score(hexchart["boxes"], r.corners, 0.60)
    for k in (1, 2, 3):
        turned = r.corners[k:] + r.corners[:k]
        other = score(hexchart["boxes"], turned, 0.60)
        assert other is None or other < upright, (
            f"the chart read as well turned {k} quarter(s): "
            f"{other} against {upright}")


def test_a_sheet_put_on_the_glass_upside_down_is_still_found(
        hexchart, tmp_path):
    """The reason all four are scored and not just the one that comes out of
    the calipers first. A honeycomb has no fiducials and a rotated rectangle
    has no top, so which corner is the chart's top-left is a question only the
    colours answer — and a sheet dropped on the platen the other way round is
    the commonest way for the answer to be 'the other one'."""
    from PIL import Image
    im = Image.open(hexchart["scan"])
    flipped = tmp_path / "upside-down.tif"
    im.rotate(180, expand=True).save(flipped, compression="tiff_lzw")
    w, h = im.size
    truth = [(w - x, h - y) for x, y in hexchart["truth"]]
    r = HBS.find_block(flipped, hexchart["boxes"], hexchart["expected"],
                       (w, h), sample_frac=0.60)
    assert r.ok, "an upside-down sheet was not found at all"
    assert _worst(r.corners, truth) < 0.5 * hexchart["pitch"], (
        "the block was found and then read the wrong way up: "
        f"{_worst(r.corners, truth):.0f} px out on a "
        f"{hexchart['pitch']:.0f} px pitch")


def test_min_area_quad_finds_a_rectangle_at_any_angle():
    """Rotating calipers over the hull, which is exact — and unlike the
    prototype's 0.25-degree sweep over +-12 degrees it does not stop being
    right outside a window."""
    for deg in (0.0, 3.0, -17.0, 41.0, 88.0):
        a = math.radians(deg)
        ca, sa = math.cos(a), math.sin(a)
        pts = [(x * ca - y * sa + 500, x * sa + y * ca + 400)
               for x, y in ((0, 0), (300, 0), (300, 120), (0, 120),
                            (150, 60), (75, 30))]
        quad = HBS.min_area_quad(pts)
        assert quad is not None
        sides = sorted(math.hypot(quad[i][0] - quad[(i + 1) % 4][0],
                                  quad[i][1] - quad[(i + 1) % 4][1])
                       for i in range(4))
        assert abs(sides[0] - 120) < 0.6 and abs(sides[3] - 300) < 0.6, sides


def test_every_hull_edge_is_tried_and_the_answer_is_the_true_minimum():
    """The minimum-area rectangle is flush with SOME hull edge, and which one
    is not known in advance: the hull starts at the leftmost point, and on
    anything but a rectangle that is not where the minimum is. So the answer is
    checked against a brute-force sweep of a tenth of a degree — if the
    calipers are ever beaten by simply trying every angle, they are not
    computing a minimum but reporting whichever edge the sort order handed
    them first."""
    pts = [(600 + 200 * math.cos(t) * math.cos(math.radians(33))
            - 60 * math.sin(t) * math.sin(math.radians(33)),
            500 + 200 * math.cos(t) * math.sin(math.radians(33))
            + 60 * math.sin(t) * math.cos(math.radians(33)))
           for t in (math.radians(9 * k) for k in range(40))]
    quad = HBS.min_area_quad(pts)
    got = (math.hypot(quad[1][0] - quad[0][0], quad[1][1] - quad[0][1])
           * math.hypot(quad[3][0] - quad[0][0], quad[3][1] - quad[0][1]))
    brute = min(
        (max(x * math.cos(a) + y * math.sin(a) for x, y in pts)
         - min(x * math.cos(a) + y * math.sin(a) for x, y in pts))
        * (max(-x * math.sin(a) + y * math.cos(a) for x, y in pts)
           - min(-x * math.sin(a) + y * math.cos(a) for x, y in pts))
        for a in (math.radians(k / 10.0) for k in range(1800)))
    assert got <= brute * 1.001, (
        f"the calipers returned {got:.0f} where a blind sweep of every angle "
        f"found {brute:.0f}")


def test_a_proposal_is_never_the_charts_mirror_image():
    """The four cyclic rotations of a quad are the four ways UP a chart can
    sit in it. They are only that if the quad is wound the way the chart's own
    bounding box is wound in `scan_auto_align._agreement`; wound the other way,
    all four are mirror images and none of them is the chart.

    `_wound_like_the_chart` is asked directly as well as through
    `min_area_quad`, because the calipers build their answer from a
    right-handed pair of axes and so cannot produce the other winding
    themselves. Nothing in the module can today, and a quad arriving from
    anywhere else still must not be able to."""
    def shoelace(q):
        return sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1]
                   for i in range(4))
    chart_box = [(0, 0), (10, 0), (10, 6), (0, 6)]
    assert shoelace(chart_box) > 0
    backwards = [(0, 0), (0, 20), (40, 20), (40, 0)]
    assert shoelace(backwards) < 0
    assert shoelace(HBS._wound_like_the_chart(backwards)) > 0
    assert sorted(HBS._wound_like_the_chart(backwards)) == sorted(backwards), (
        "winding a quad the right way round moved one of its corners")
    for pts in ([(0, 0), (40, 0), (40, 20), (0, 20)],
                [(0, 20), (0, 0), (40, 0), (40, 20)],
                [(5, 30), (35, 2), (60, 30), (30, 58)]):
        assert shoelace(HBS.min_area_quad(pts)) > 0, pts


def test_components_are_four_connected_and_counted_by_area():
    import numpy as np
    mask = np.zeros((7, 7), bool)
    mask[1, 1:4] = True
    mask[2, 3] = True          # touches the run above: one blob of 4
    mask[4, 4] = True          # alone
    mask[5, 5] = True          # diagonal DOWN-RIGHT of it, not the same blob
    mask[3, 6] = True          # alone
    mask[4, 5] = False         # (kept clear so the two above stay apart)
    labels, sizes = HBS._components(mask)
    assert labels[1, 1] == labels[2, 3]
    assert labels[4, 4] != labels[5, 5], "a diagonal touch joined two blobs"
    assert labels[3, 6] != labels[4, 4], "a diagonal touch joined two blobs"
    assert sorted(sizes[1:].tolist()) == [1, 1, 1, 4]


def test_a_speck_of_ink_is_never_offered_as_a_chart():
    """`MIN_AREA_FRACTION` is the guard that stops a dust mote, a staple or a
    pen mark being proposed and scored. It is cheap and it is the only thing
    between the search and a candidate list full of nothing."""
    size = (2000, 3000)
    speck = [(100.0, 100.0), (160.0, 100.0), (160.0, 160.0), (100.0, 160.0)]
    block = [(100.0, 100.0), (1600.0, 100.0), (1600.0, 2600.0), (100.0, 2600.0)]
    assert HBS._plausible(block, size)
    assert not HBS._plausible(speck, size)


def test_agreement_scorer_answers_what_reference_agreement_at_answers(hexchart):
    """It exists to read the picture once instead of fifty times, and it must
    not become a second opinion while doing it."""
    score = agreement_scorer(hexchart["scan"], hexchart["expected"])
    for quad in (hexchart["truth"],
                 [(x + 40, y + 25) for x, y in hexchart["truth"]]):
        assert score(hexchart["boxes"], quad, 0.60) == pytest.approx(
            reference_agreement_at(hexchart["scan"], hexchart["boxes"], quad,
                                   hexchart["expected"], 0.60))


def test_every_route_is_scored_rather_than_one_being_chosen(hexchart):
    """The prototype this grew from was ONE pipeline, and four variants of its
    region-finding step scored between 0/30 and 30/30 on one chart's pictures.
    Picking the winner by hand is how that 30/30 was got. So several routes are
    proposed and the ladder's own agreement decides between them."""
    cands = HBS.block_candidates(hexchart["scan"], hexchart["size"])
    assert len(cands) >= 3, [n for n, _ in cands]
    assert len({n for n, _ in cands}) == len(cands), "routes are not distinct"


def test_the_window_tells_place_grid_whether_the_chart_is_a_honeycomb():
    """The flag is read from the chart's own sidecar in the window, because
    that is the only place that knows which chart is on screen."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    src = inspect.getsource(ScannerProfileDialog._on_auto_align)
    assert "chart_is_hexagonal" in src
    assert "hexagonal=hexagonal" in src


# ------------------------------------- which quad, and which placement of it
def _scaled(quad, fx: float, fy: float = 1.0):
    """*quad* stretched about its own centre — a placement of the same chart,
    not a different chart, which is exactly the difference the agreement cannot
    see and the seating can."""
    cx = sum(p[0] for p in quad) / 4.0
    cy = sum(p[1] for p in quad) / 4.0
    return [(cx + (x - cx) * fx, cy + (y - cy) * fy) for x, y in quad]


def _fixed_scorer(scores):
    """An `agreement_scorer` that answers from a table keyed by the quad, so a
    test can say what the colours think and watch what is done about it."""
    def scorer(boxes, quad, frac):
        for want, value in scores:
            if _worst(quad, want) < 1e-6:
                return value
        return 0.0
    return lambda *a, **k: scorer


def test_the_search_does_not_move_when_the_users_sample_area_does(
        hexchart, monkeypatch):
    """Which quad holds the chart is a fact about the PICTURE.

    It used to be decided with whatever fraction the Sample area spinbox was
    on, because the window's number was handed all the way down to the scoring
    — so changing 60 % to 50 % could hand back a different placement of the
    same chart, which is what Knut reported on 2026-09-11 as "the auto align
    varies". (His log shows four presses at ONE setting returning the same
    answer to every decimal, and his two screenshots of them are identical to
    the pixel: the setting was the only thing that moved.)
    """
    seen = []
    import workflow.hex_block_search as H
    real = H.find_block

    def watch(*a, **k):
        seen.append(k.get("sample_frac", "not-passed"))
        return real(*a, **k)

    monkeypatch.setattr(H, "find_block", watch)
    _run(hexchart, monkeypatch, start=None, hexagonal=True)
    assert seen and all(f == "not-passed" for f in seen), (
        f"the ladder handed the search a sample fraction: {seen}")


def test_the_search_scores_on_a_share_it_chooses_itself(hexchart):
    """And the share it chooses is the one the drift gate already uses, so the
    two halves of "is this the chart, and is it seated" look at the same area."""
    from workflow.scan_auto_align import SEATING_SAMPLE_AREA
    assert HBS.SEARCH_SAMPLE_AREA == SEATING_SAMPLE_AREA
    assert (inspect.signature(HBS.find_block).parameters["sample_frac"].default
            == HBS.SEARCH_SAMPLE_AREA)


def test_the_patches_break_a_tie_the_colours_cannot(hexchart, monkeypatch):
    """Two quads that agree with the chart equally well, and only one of them
    is seated on the patches.

    The agreement is a rank correlation over the patch luminances and it
    SATURATES: measured on a two-page CR30 honeycomb whose truth is known to
    the pixel, quads 11.0, 16.0 and 12.0 px from the truth all scored 1.0000,
    and so did the truth. None of the routes here bounds the patch block
    anyway — they bound the INK, and a flat-top honeycomb's apexes reach a
    sixth of the slot past the first and last columns, so an ink-bounded quad
    is about 1/(3*columns) too wide. The seating drift can see that; the
    colours cannot, so they must not be the ones to choose.
    """
    truth = [tuple(p) for p in hexchart["truth"]]
    stretched = _scaled(truth, 1.02)
    monkeypatch.setattr(HBS, "block_candidates",
                        lambda *a, **k: [("seated", truth),
                                         ("stretched", stretched)])
    # the colours prefer the WRONG one, by less than the band
    import workflow.scan_auto_align as AA
    monkeypatch.setattr(AA, "agreement_scorer",
                        _fixed_scorer([(stretched, 0.99), (truth, 0.98)]))
    r = HBS.find_block(hexchart["scan"], hexchart["boxes"],
                       hexchart["expected"], hexchart["size"])
    assert r.ok
    assert r.route == "seated", (
        f"the stretched placement won on {r.rho}: the tie went to the colours, "
        "which cannot see a stretch")
    assert _worst(r.corners, truth) < 1e-6


def test_the_colours_still_say_which_chart_it_is(hexchart, monkeypatch):
    """The other half of the same rule. A candidate the colours put OUTSIDE the
    band is never reached by the tie-break, whatever the patches think of it —
    so a quad that reads as a different chart cannot be chosen for sitting
    neatly on something."""
    truth = [tuple(p) for p in hexchart["truth"]]
    stretched = _scaled(truth, 1.02)
    monkeypatch.setattr(HBS, "block_candidates",
                        lambda *a, **k: [("seated", truth),
                                         ("stretched", stretched)])
    import workflow.scan_auto_align as AA
    monkeypatch.setattr(AA, "agreement_scorer",
                        _fixed_scorer([(stretched, 0.99), (truth, 0.90)]))
    r = HBS.find_block(hexchart["scan"], hexchart["boxes"],
                       hexchart["expected"], hexchart["size"])
    assert r.ok
    assert r.route == "stretched", (
        "a candidate 0.09 of agreement behind was chosen for its seating; the "
        f"band is {HBS.AGREEMENT_TIE_BAND}")


def test_a_seating_that_cannot_be_measured_leaves_the_colours_in_charge(
        hexchart, monkeypatch):
    """A check that cannot be made is not evidence of a fault. When the drift
    comes back None for every candidate the winner is the one the agreement
    picked, which is what this module did before the tie-break existed."""
    truth = [tuple(p) for p in hexchart["truth"]]
    stretched = _scaled(truth, 1.02)
    monkeypatch.setattr(HBS, "block_candidates",
                        lambda *a, **k: [("seated", truth),
                                         ("stretched", stretched)])
    import workflow.scan_auto_align as AA
    monkeypatch.setattr(AA, "agreement_scorer",
                        _fixed_scorer([(stretched, 0.99), (truth, 0.98)]))
    monkeypatch.setattr(AA, "seating_drift", lambda *a, **k: None)
    r = HBS.find_block(hexchart["scan"], hexchart["boxes"],
                       hexchart["expected"], hexchart["size"])
    assert r.ok
    assert r.route == "stretched"
    assert r.drift is None


# --------------------------------------- the ink is not the patch block
class _Box:
    __slots__ = ("x1", "y1", "x2", "y2", "name")

    def __init__(self, x1, y1, x2, y2, name="A1"):
        self.x1, self.y1, self.x2, self.y2, self.name = x1, y1, x2, y2, name


def _lattice(cols: int, rows: int, w: float, h: float, flat_top: bool):
    """The box list a honeycomb's .cht carries: straight columns half a slot
    apart down the page (flat-top), or straight rows half a slot apart across
    it (pointy-top)."""
    out = []
    for c in range(cols):
        for r in range(rows):
            if flat_top:
                x, y = c * w, r * h + (h / 2 if c % 2 else 0.0)
            else:
                x, y = c * w + (w / 2 if r % 2 else 0.0), r * h
            out.append(_Box(x, y, x + w, y + h))
    return out


def test_the_apex_overhang_is_read_off_the_chart_not_guessed():
    """A hexagon reaches a sixth of its slot past the slot on the axis its
    apexes point along, and that is the whole difference between the INK every
    route here bounds and the SLOTS the marquee is defined on. The factor is
    the span, not the column count, so a part-full last page gets its own."""
    from workflow.layout_engine.hexagon import APEX_FRACTION
    flat = _lattice(18, 22, 10.0, 12.0, flat_top=True)
    fu, fv = HBS.apex_factors(flat)
    span = 18 * 10.0
    assert fv == 1.0, "a flat-top honeycomb's apexes point sideways"
    assert fu == pytest.approx(span / (span + 2 * APEX_FRACTION * 10.0))
    assert fu == pytest.approx(18 / (18 + 1 / 3), rel=1e-9)

    pointy = _lattice(18, 22, 10.0, 12.0, flat_top=False)
    pu, pv = HBS.apex_factors(pointy)
    assert pu == 1.0, "a pointy-top honeycomb's apexes point up and down"
    assert pv == pytest.approx((22 * 12.0) / (22 * 12.0 + 2 * APEX_FRACTION * 12.0))

    # a part-full page is narrower, so its correction is bigger
    assert HBS.apex_factors(_lattice(6, 22, 10.0, 12.0, True))[0] < fu
    # and a chart that is not a honeycomb at all is left alone
    square = [_Box(c * 10.0, r * 10.0, c * 10.0 + 9.0, r * 10.0 + 9.0)
              for c in range(10) for r in range(10)]
    assert HBS.apex_factors(square) == (1.0, 1.0)


def test_every_route_is_offered_corrected_as_well_as_raw(hexchart):
    """Neither reading is trusted. The ink-bounded quad may be right (a chart
    with a spacer ring between its hexagons has less overhang than a flush one)
    and the corrected quad may be right, so both are scored and the seating
    picks. Measured: on a flush 18-column sheet the corrected largest-blob goes
    from 24.6 px out to 5.9, and on this 6-column ringed fixture the corrected
    profile-quarter goes the other way, from 8.4 px to 20.4."""
    r = HBS.find_block(hexchart["scan"], hexchart["boxes"],
                       hexchart["expected"], hexchart["size"])
    names = [n for n, _ in r.scores]
    assert any(n.endswith("+apex") for n in names), names
    assert any(not n.endswith("+apex") for n in names), names


def test_the_answer_beats_what_the_agreement_alone_would_have_picked(hexchart):
    """The whole point of the two measures together, on a real picture.

    The agreement saturates — three of this fixture's candidates score 0.9860
    and they are 8.4, 16.0 and 20.4 px from the truth — so picking the highest
    is picking the first of a tie. The seating separates them.
    """
    from workflow.scan_auto_align import agreement_scorer
    score = agreement_scorer(hexchart["scan"], hexchart["expected"])
    fu, fv = HBS.apex_factors(hexchart["boxes"])
    by_rho = None
    for name, quad in HBS.block_candidates(hexchart["scan"], hexchart["size"]):
        for q0 in (quad, HBS.scaled_about_centre(quad, fu, fv)):
            for k in range(4):
                turned = q0[k:] + q0[:k]
                rho = score(hexchart["boxes"], turned, HBS.SEARCH_SAMPLE_AREA)
                if rho is not None and (by_rho is None or rho > by_rho[0]):
                    by_rho = (rho, turned)
    assert by_rho is not None
    r = HBS.find_block(hexchart["scan"], hexchart["boxes"],
                       hexchart["expected"], hexchart["size"])
    assert r.ok
    mine = _worst(r.corners, hexchart["truth"])
    theirs = _worst(by_rho[1], hexchart["truth"])
    assert mine < theirs, (
        f"the seating chose a placement {mine:.1f} px out where the agreement's "
        f"own best was {theirs:.1f} px out, on a {hexchart['pitch']:.0f} px pitch")
    assert mine < 0.10 * hexchart["pitch"]


def test_handing_the_picture_over_does_not_change_the_seating(hexchart):
    """The tie-break asks about up to eight placements of ONE scan, so it reads
    the picture once and hands the result to each call. That is an optimisation
    and it must be nothing else: measured on a 300 dpi A4 scan it takes the
    search from 7.0 s to 2.5 s, and the number it returns has to be the same
    number to the last bit."""
    from workflow.scan_auto_align import drift_sampler, seating_drift
    quad = [(x + 9, y - 5) for x, y in hexchart["truth"]]
    sampler = drift_sampler(hexchart["scan"])
    assert sampler is not None
    for q in (hexchart["truth"], quad):
        alone = seating_drift(hexchart["scan"], hexchart["boxes"], q)
        shared = seating_drift(hexchart["scan"], hexchart["boxes"], q,
                               sampler=sampler)
        assert alone == shared, (alone, shared)
