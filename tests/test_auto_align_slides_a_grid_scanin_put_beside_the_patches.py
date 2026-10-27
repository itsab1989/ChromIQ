"""Knut, 4.3.17: Auto align on his flatbed scan of a ChromIQ chart.

    "Looking for the patches… Auto align left your corners exactly where they
    are. This chart's patches look the same whichever way round it is turned,
    so ChromIQ cannot work out which way your scan was made."

His log: ``found=False/ambiguous-orientation fitted=False/too-far-to-fit
candidates=2``, both candidates refused as "reads the same more than one way
up (margin 0.04)". Placed by hand, the grid fitted perfectly.

Two faults, both reproduced on simulated scans of ChromIQ charts built like his
(1944 patches, 24 strips x 27 per page, coloured spacers, helper markers):

1. scanin finds a ChromIQ chart by its straight patch edges, and every strip
   and row has the same pitch, so it can put its rectangle WHOLE STRIPS to the
   side. It did for its second candidate in 36 of 36 scans, and for both in 4,
   which then ended exactly as his log does.
2. A rectangle in the wrong place reads badly in all four orientations, and
   four equally bad readings have a small margin just as four equally good
   ones do. So the window called the chart symmetric and sent him to the
   Rotate button.

And, found while testing the fix on a black scanner lid: the boundary check
refused correct placements, because the band "a patch further out" ran off the
paper onto the lid. On a chart whose patch order is shuffled the colours pin
the position by themselves, so that check is now overruled when they do.
"""
from __future__ import annotations

import math
import os
import random
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow import scan_auto_align as A                       # noqa: E402
from workflow.cht_parser import parse_cht                        # noqa: E402
from workflow.layout_engine.cht_writer import build_cht_text     # noqa: E402

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageFilter  # noqa: E402


class _FakeRun:
    """Stands in for subprocess.run; replays canned scanin logs."""

    def __init__(self, *logs):
        self.logs = list(logs)

    def __call__(self, args, **kw):
        text = self.logs.pop(0) if self.logs else ""
        return subprocess.CompletedProcess(args, 0, stdout=text, stderr="")


def _cand(quad, bbox, cc=0.8):
    """One scanin candidate line whose affine lands on *quad* (no rotation)."""
    sx = (quad[1][0] - quad[0][0]) / (bbox[2] - bbox[0])
    sy = (quad[3][1] - quad[0][1]) / (bbox[3] - bbox[1])
    return (f"cc = {cc}, irot = 0.000000, xoff = {quad[0][0] - bbox[0] * sx:f}, "
            f"yoff = {quad[0][1] - bbox[1] * sy:f}, xscale = {sx:f}, "
            f"yscale = {sy:f}\n")


def _loc(c, r):
    """A patch name for column *c*, row *r*: A..Z, then AA.., like a .cht."""
    name = chr(65 + c % 26) if c < 26 else chr(64 + c // 26) + chr(65 + c % 26)
    return f"{name}{r + 1:02d}"


def _chart(tmp_path: Path, *, shuffled=True, cols=12, rows=10, box=30,
           margin=110, seed=3, half_turn_symmetric=False, period=None):
    """A grid of patches edge to edge on white paper. *shuffled*: colours in
    random order, the way a ChromIQ chart's patches are; otherwise a smooth
    grey ramp, whose neighbours look alike. *period*: the shuffled colours of
    the first *period* columns repeat across the whole chart, the way a chart
    printed in its original order or a chart definition that repeats a block
    can."""
    rng = random.Random(seed)
    boxes, colors = [], {}
    for c in range(cols):
        for r in range(rows):
            loc = _loc(c, r)
            boxes.append({"loc": loc, "x": float(c * box), "y": float(r * box),
                          "w": float(box), "h": float(box)})
            if shuffled:
                colors[loc] = tuple(rng.randrange(20, 236) for _ in range(3))
            else:
                v = 20 + (c * rows + r) * 210 // (cols * rows)
                colors[loc] = (v, v, v)
    if half_turn_symmetric:
        for c in range(cols):
            for r in range(rows):
                if c * rows + r >= cols * rows // 2:
                    colors[_loc(c, r)] = colors[_loc(cols - 1 - c, rows - 1 - r)]
    if period:
        for c in range(period, cols):
            for r in range(rows):
                colors[_loc(c, r)] = colors[_loc(c % period, r)]
    exp = []
    for b in boxes:
        r_, g_, b_ = colors[b["loc"]]
        y = 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_
        exp.append((b["loc"], y / 2.55, y / 2.55, y / 2.55))
    text = build_cht_text(boxes, exp)
    import numpy as np
    a = np.empty((rows * box + 2 * margin, cols * box + 2 * margin, 3),
                 np.uint8)
    a[:, :] = (250, 250, 248)
    for b in boxes:
        y0, x0 = int(b["y"]) + margin, int(b["x"]) + margin
        a[y0:y0 + int(b["h"]), x0:x0 + int(b["w"])] = colors[b["loc"]]
    img = Image.fromarray(a)
    scan = tmp_path / "scan.tif"
    img.save(scan)
    cht = tmp_path / "chart.cht"
    cht.write_text(text, encoding="utf-8")
    cie = tmp_path / "chart.cie"
    cie.write_text("", encoding="utf-8")
    m = float(margin)
    truth = [(m, m), (m + cols * box, m), (m + cols * box, m + rows * box),
             (m, m + rows * box)]
    boxes_p = parse_cht(text).patches
    bbox = (min(b.x1 for b in boxes_p), min(b.y1 for b in boxes_p),
            max(b.x2 for b in boxes_p), max(b.y2 for b in boxes_p))
    return dict(scan=scan, cht=cht, cie=cie, boxes=boxes_p,
                exp=A.expected_luminance(text), size=img.size, truth=truth,
                bbox=bbox, box=box)


def _shift(quad, dx, dy):
    return [(x + dx, y + dy) for x, y in quad]


def _align(c, *logs, **kw):
    return A.auto_align("scanin", c["scan"], c["cht"], c["cie"], c["boxes"],
                        c["exp"], c["size"], runner=_FakeRun(*logs), **kw)


def _worst(a, b):
    return max(math.dist(p, q) for p, q in zip(a, b))


# ---------------------------------------------------------------------------
# 1. a rectangle whole strips beside the patches is slid onto them
# ---------------------------------------------------------------------------
def test_both_answers_whole_strips_out_is_his_case_and_it_now_lands(tmp_path):
    """Knut's log, made exact: two candidates, one strip one way and two the
    other, and no orientation of either reads the chart."""
    c = _chart(tmp_path)
    t, p = c["truth"], c["box"]
    log = (_cand(_shift(t, -p, 0), c["bbox"])
           + _cand(_shift(t, 2 * p, 0), c["bbox"], cc=0.79))
    r = _align(c, log)
    assert r.ok, f"refused: {r.reason} {r.rejected}"
    assert _worst(r.corners, t) < 1.0, r.corners
    assert r.rho > 0.95


@pytest.mark.parametrize("di,dj", [(3, 0), (0, -2), (-2, 1), (1, 3)])
def test_a_slip_of_up_to_three_pitches_either_way_is_recovered(tmp_path, di, dj):
    c = _chart(tmp_path)
    t, p = c["truth"], c["box"]
    r = _align(c, _cand(_shift(t, di * p, dj * p), c["bbox"]))
    assert r.ok, f"{di},{dj}: refused: {r.reason} {r.rejected}"
    assert _worst(r.corners, t) < 1.0


def test_an_upside_down_answer_beside_the_patches_is_turned_and_slid(tmp_path):
    c = _chart(tmp_path)
    t, p = c["truth"], c["box"]
    off = _shift(t, p, 0)
    r = _align(c, _cand(off[2:] + off[:2], c["bbox"]))
    assert r.ok, f"refused: {r.reason} {r.rejected}"
    assert _worst(r.corners, t) < 1.0


def test_a_correct_answer_is_left_exactly_where_it_is(tmp_path):
    c = _chart(tmp_path)
    r = _align(c, _cand(c["truth"], c["bbox"]))
    assert r.ok and _worst(r.corners, c["truth"]) < 0.5


def test_a_smooth_chart_is_not_slid(tmp_path):
    """Neighbouring positions of a grey ramp read nearly as well as the right
    one, so the colours pin nothing and the slide must not choose. The ramp
    keeps the boundary check, which is what refuses a one-patch slip on it."""
    c = _chart(tmp_path, shuffled=False)
    score = A.agreement_scorer(c["scan"], c["exp"])
    assert A.pitch_search(score, c["boxes"], c["truth"], c["size"]) is None
    r = _align(c, _cand(_shift(c["truth"], 0, c["box"]), c["bbox"]),
               _cand(_shift(c["truth"], 0, c["box"]), c["bbox"]))
    assert not r.ok
    assert any("edges" in s for s in r.rejected), r.rejected


# ---------------------------------------------------------------------------
# 2. four equally BAD readings are not a symmetric chart
# ---------------------------------------------------------------------------
def test_a_grid_that_reads_nothing_is_not_called_symmetric(tmp_path):
    """The reference here belongs to a different chart, so no way up and no
    position reads anything. That is the honest answer, and the message for it
    must not send the user to the Rotate button."""
    from workflow import measurement_messages as M
    c = _chart(tmp_path)
    vals = list(c["exp"].values())
    random.Random(9).shuffle(vals)
    c["exp"] = dict(zip(c["exp"], vals))
    r = _align(c, _cand(c["truth"], c["bbox"]), _cand(c["truth"], c["bbox"]))
    assert not r.ok
    assert r.reason == "off-the-patches", (r.reason, r.rejected)
    assert not any("more than one way up" in s for s in r.rejected)
    msg = M.scan_align_refusal(r.reason)
    assert msg is M.M_SCAN_ALIGN_OFF_PATCHES
    title, body = msg.render(chart_row="Measured chart (.ti3)")
    assert "whichever way round" not in body
    assert "Rotate" not in body
    assert "Measured chart (.ti3)" in body and "{" not in body
    assert "—" not in title + body


def test_the_placement_ending_carries_the_new_reason_through(tmp_path):
    """`place_grid` speaks with the search's diagnosis when nothing could be
    placed, so the new reason has to be one of its diagnoses."""
    from workflow.scan_placement import ENDINGS, _ending
    assert "off-the-patches" in ENDINGS
    assert _ending("off-the-patches", "too-far-to-fit") == "off-the-patches"


def test_a_chart_that_really_reads_the_same_turned_is_still_symmetric(tmp_path):
    """The other half: a chart whose colours repeat under a half turn reads
    WELL both ways up, and that is still the ambiguity message."""
    c = _chart(tmp_path, half_turn_symmetric=True)
    r = _align(c, _cand(c["truth"], c["bbox"]), _cand(c["truth"], c["bbox"]))
    assert not r.ok
    assert r.reason == "ambiguous-orientation", (r.reason, r.rejected)


# ---------------------------------------------------------------------------
# 3. colours that pin the grid overrule a boundary the scanner bed spoils
# ---------------------------------------------------------------------------
def test_a_pinned_grid_is_not_refused_for_its_boundary(tmp_path, monkeypatch):
    c = _chart(tmp_path)
    monkeypatch.setattr(A, "border_agreement", lambda *a, **k: False)
    r = _align(c, _cand(c["truth"], c["bbox"]))
    assert r.ok, f"refused: {r.reason} {r.rejected}"


def test_an_unpinned_grid_still_answers_to_its_boundary(tmp_path, monkeypatch):
    c = _chart(tmp_path, shuffled=False)
    monkeypatch.setattr(A, "border_agreement", lambda *a, **k: False)
    r = _align(c, _cand(c["truth"], c["bbox"]), _cand(c["truth"], c["bbox"]))
    assert not r.ok
    assert any("edges" in s for s in r.rejected)


def test_the_final_check_lets_the_colours_overrule_the_boundary_too(
        tmp_path, monkeypatch):
    """`place_grid` asks `seated_verdict` once more about the corners it is
    about to set. With the chart's colours it is the same rule; without them
    (any caller that does not pass them) nothing changed."""
    from workflow import scan_placement as sp
    c = _chart(tmp_path)
    monkeypatch.setattr(A, "border_agreement", lambda *a, **k: False)
    assert sp.seated_verdict(c["scan"], c["boxes"], c["truth"],
                             expected_y=c["exp"], image_size=c["size"])[0]
    assert not sp.seated_verdict(c["scan"], c["boxes"], c["truth"])[0]
    off = _shift(c["truth"], c["box"], 0)
    assert not sp.seated_verdict(c["scan"], c["boxes"], off,
                                 expected_y=c["exp"], image_size=c["size"])[0]


# ---------------------------------------------------------------------------
# 3b. ...but never on a chart whose colours repeat (release review r4, SF-2)
# ---------------------------------------------------------------------------
# A chart printed in its original order, or a chart definition that repeats a
# block, can repeat its colours every few patches along a row. A grid one whole
# repeat off then reads it almost perfectly (0.88 against 1.00 measured), and
# the right position is OUTSIDE the pitch search's three-patch window, so the
# wrong one wins that window by a wide margin. Before the fix the colours then
# overruled the boundary check and the grid was accepted whole strips out.
@pytest.mark.parametrize("period", [4, 5, 6])
@pytest.mark.parametrize("repeats_off", [1, -1, "1+1"])
def test_a_grid_one_repeat_off_a_repeating_chart_is_never_accepted(
        tmp_path, monkeypatch, period, repeats_off):
    from workflow import scan_placement as sp
    c = _chart(tmp_path, cols=60, rows=12, box=20, margin=160, seed=period,
               period=period)
    t, p = c["truth"], c["box"]
    off = (period + 1) if repeats_off == "1+1" else repeats_off * period
    alias = _shift(t, off * p, 0) if repeats_off != "1+1" else _shift(
        t, period * p, 0)
    given = _shift(t, off * p, 0)
    # The boundary check is what refuses this in 4.3.17. Make it say "not the
    # chart's" everywhere, as a dark scanner lid does, so the only thing that
    # can still refuse is the colours declining to overrule it.
    monkeypatch.setattr(A, "border_agreement", lambda *a, **k: False)
    r = _align(c, _cand(given, c["bbox"]))
    assert not r.ok or _worst(r.corners, t) < 1.0, (
        f"accepted a grid {_worst(r.corners, t) / p:.1f} patches out")
    assert not r.ok and r.reason == "repeating-colours", (r.reason, r.rejected)
    from workflow import measurement_messages as M
    assert M.scan_align_refusal(r.reason) is M.M_SCAN_ALIGN_REPEATS
    # the final check place_grid asks of the corners it is about to set
    assert not sp.seated_verdict(c["scan"], c["boxes"], alias,
                                 expected_y=c["exp"], image_size=c["size"])[0]
    score = A.agreement_scorer(c["scan"], c["exp"])
    assert not A.position_is_pinned(score, c["boxes"], alias, c["size"])
    hit = A.colours_repeat_along_the_chart(
        score, c["boxes"], alias, c["size"], score(c["boxes"], alias))
    assert hit is not None and hit[1] == 0 and hit[0] % period == 0, hit


def test_a_repeating_chart_still_lands_when_its_edges_agree(tmp_path):
    """The repeat check takes away only the colours' right to overrule the
    boundary. A grid a patch out on a chart repeating every six patches, on
    white paper, is still slid onto the patches (the next repeat is outside
    the slide's reach), and the boundary agrees there."""
    c = _chart(tmp_path, cols=60, rows=12, box=20, margin=160, seed=6,
               period=6)
    t, p = c["truth"], c["box"]
    r = _align(c, _cand(_shift(t, p, 0), c["bbox"]))
    assert r.ok, f"refused: {r.reason} {r.rejected}"
    assert _worst(r.corners, t) < 1.0


def test_a_shuffled_chart_has_nothing_repeating_so_its_colours_still_pin(
        tmp_path):
    """Knut's case: a ChromIQ chart in its usual shuffled order. No straight
    shift anywhere along its rows or columns reads like the patches, so the
    colours still overrule a boundary the scanner bed spoils."""
    c = _chart(tmp_path, cols=24, rows=27, box=20, margin=70)
    score = A.agreement_scorer(c["scan"], c["exp"])
    rho = score(c["boxes"], c["truth"])
    assert rho > 0.95
    assert A.colours_repeat_along_the_chart(
        score, c["boxes"], c["truth"], c["size"], rho) is None
    assert A.position_is_pinned(score, c["boxes"], c["truth"], c["size"])


# ---------------------------------------------------------------------------
# 3c. "none of them matched" only when none of them did (review r4, N-2)
# ---------------------------------------------------------------------------
def test_a_symmetric_chart_a_patch_off_is_called_symmetric(tmp_path):
    """The grid is a patch off, so the four ways up of the rectangle itself
    read nothing; but one patch over the chart reads perfectly, twice, once
    each way round. That is a symmetric chart, and saying "in none of them did
    the colours match" would be false."""
    from workflow import measurement_messages as M
    c = _chart(tmp_path, half_turn_symmetric=True)
    off = _shift(c["truth"], c["box"], 0)
    r = _align(c, _cand(off, c["bbox"]), _cand(off, c["bbox"]))
    assert not r.ok
    assert r.reason == "ambiguous-orientation", (r.reason, r.rejected)
    assert M.scan_align_refusal(r.reason) is M.M_SCAN_ALIGN_AMBIGUOUS


@pytest.mark.parametrize("period", [2, 3])
def test_a_chart_repeating_inside_the_window_a_patch_off_says_it_repeats(
        tmp_path, period):
    """A repeat short enough for the slide to see: several positions the same
    way up read the chart perfectly. Neither "off the patches" nor
    "symmetric" is true; the colours repeat."""
    from workflow import measurement_messages as M
    c = _chart(tmp_path, cols=60, rows=12, box=20, margin=160, period=period)
    off = _shift(c["truth"], c["box"], 0)
    r = _align(c, _cand(off, c["bbox"]), _cand(off, c["bbox"]))
    assert not r.ok
    assert r.reason == "repeating-colours", (r.reason, r.rejected)
    msg = M.scan_align_refusal(r.reason)
    assert msg is M.M_SCAN_ALIGN_REPEATS
    title, body = msg.render(chart_row="Measured chart (.ti3)")
    assert "{" not in title + body and "\u2014" not in title + body
    assert "none of them" not in body and "whichever way round" not in body
    from workflow.scan_placement import ENDINGS, _ending
    assert "repeating-colours" in ENDINGS
    assert _ending("repeating-colours", "too-far-to-fit") == "repeating-colours"


def test_place_grid_reads_the_picture_once_for_its_colour_questions(
        tmp_path, monkeypatch):
    """Review r4, N-1: both searches and the final seating check score
    against one reading of the picture."""
    from workflow import scan_placement as sp
    c = _chart(tmp_path)
    made = []
    real = A.agreement_scorer

    def counting(*a, **k):
        made.append(1)
        return real(*a, **k)
    monkeypatch.setattr(A, "agreement_scorer", counting)
    monkeypatch.setattr(A, "border_agreement", lambda *a, **k: False)
    log = _cand(_shift(c["truth"], c["box"], 0), c["bbox"])
    r = sp.place_grid("scanin", c["scan"], c["cht"], c["cie"], c["boxes"],
                      c["exp"], c["size"], runner=_FakeRun(log, log))
    assert r.ending == "placed", (r.ending, r.find_reason, r.rejected)
    assert len(made) == 1, f"the picture was read {len(made)} times"


# ---------------------------------------------------------------------------
# 4. the whole button, on a real ChromIQ chart, through the real scanin
# ---------------------------------------------------------------------------
def _knut_like_chart(out: Path):
    """A 1944-patch, 3-page ChromIQ chart as his log describes it: i1Pro, A4,
    24 strips x 27 per page, coloured spacers, helper markers top and bottom
    (4 mm, 7 per patch), and a patch set crowded in the dark greens like his."""
    import json
    import shutil
    import workflow.ti2_relayout as R
    from workflow import scanin_target as ST
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import LayoutRecipe
    rng = random.Random(21)
    prog = []
    for _ in range(1944):
        if rng.random() < 0.6:
            prog.append((rng.uniform(0, 35), rng.uniform(20, 70),
                         rng.uniform(15, 60)))
        else:
            prog.append(tuple(rng.random() * 100 for _ in range(3)))
    R.write_ti1(R.ChartSpec.new("i1", "A4"), prog, out / "s.ti1")
    rec = LayoutRecipe(instrument="i1", paper="A4", dpi=300, pscale=0.9,
                       sscale=0.9, helper_markers=True,
                       helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0,
                       helper_marker_per_patch=7, helper_markers_top_bottom=True,
                       helper_markers_sides=False, area_cols=24, area_rows=27,
                       area_method="by_grid", layout_explicit=True, seed=21)
    le_chart.build_from_recipe(out / "s.ti1", out / "chart", rec)
    strips = json.loads((out / "chart.strips.json").read_text(encoding="utf-8"))
    strips["engine"] = "chromiq"
    (out / "chart.channels.json").write_text(json.dumps({"layout": strips}),
                                             encoding="utf-8")
    shutil.copy(out / "chart.ti2", out / "chart.ti3")
    ST.build_scanin_target_from_paths(out / "chart.channels.json",
                                      out / "chart.ti3", out / "chart")
    return out / "chart_01.tif", out / "chart_01.cht", out / "chart.cie"


def _scan_of(page: Path, out: Path, turn: int, bed: str, tilt=2.5):
    """A flatbed scan of the printed page: muted ink on warm paper, the sheet
    near one corner of a larger bed, tilted, blurred, a little noise, and
    turned on the glass. Returns the scan and the true patch-area corners."""
    import numpy as np
    src = Image.open(page).convert("RGB")
    a = np.asarray(src).astype(np.float32) / 255.0
    a = np.array([0.96, 0.95, 0.91], np.float32) * (0.08 + 0.92 * a ** 1.1)
    img = Image.fromarray((a * 255).clip(0, 255).astype(np.uint8))
    w, h = img.size
    pl, pt, pr, pb = round(0.01 * w), round(0.008 * h), round(0.06 * w), \
        round(0.035 * h)
    rgb = (238, 238, 236) if bed == "light" else (22, 22, 24)
    canvas = Image.new("RGB", (w + pl + pr, h + pt + pb), rgb)
    canvas.paste(img, (pl, pt))
    canvas = canvas.rotate(tilt, resample=Image.BICUBIC, fillcolor=rgb,
                           center=(pl + w / 2, pt + h / 2))
    canvas = canvas.filter(ImageFilter.GaussianBlur(2.0))
    c = np.asarray(canvas).astype(np.float32)
    c += np.random.default_rng(turn).normal(0, 2.0, c.shape)
    canvas = Image.fromarray(c.clip(0, 255).astype(np.uint8))
    size0 = canvas.size
    if turn:
        canvas = canvas.rotate(-turn, expand=True)
    scan = out / f"scan-{turn}-{bed}.tif"
    canvas.save(scan)
    return scan, size0


@pytest.mark.slow
def test_a_scan_of_a_chromiq_chart_aligns_by_itself_every_way_up(tmp_path):
    from tests.argyll_env import argyll_tool
    from workflow.scan_placement import place_grid
    scanin = argyll_tool("scanin")
    if scanin is None:
        pytest.skip("ArgyllCMS scanin not present")
    page, cht, cie = _knut_like_chart(tmp_path)
    text = cht.read_text(encoding="utf-8")
    boxes = parse_cht(text).patches
    exp = A.expected_luminance(text, cie, chart_ids=[b.name for b in boxes])
    minx = min(b.x1 for b in boxes); maxx = max(b.x2 for b in boxes)
    miny = min(b.y1 for b in boxes); maxy = max(b.y2 for b in boxes)
    pitch_mm = A.chart_pitch(boxes)
    mmpx = 300 / 25.4
    for turn, bed in ((0, "light"), (90, "dark"), (180, "light"),
                      (270, "dark")):
        scan, (cw0, ch0) = _scan_of(page, tmp_path, turn, bed)
        with Image.open(scan) as im:
            size = im.size
            w0 = Image.open(page).size
        pl, pt = round(0.01 * w0[0]), round(0.008 * w0[1])
        cx, cy = pl + w0[0] / 2, pt + w0[1] / 2
        ang = math.radians(2.5)

        def to_scan(x, y):
            X, Y = pl + x * mmpx, pt + y * mmpx
            dx, dy = X - cx, Y - cy
            X = cx + dx * math.cos(ang) + dy * math.sin(ang)
            Y = cy - dx * math.sin(ang) + dy * math.cos(ang)
            cw, ch = cw0, ch0
            for _ in range(turn // 90):
                X, Y, cw, ch = ch - Y, X, ch, cw
            return X, Y
        truth = [to_scan(minx, miny), to_scan(maxx, miny),
                 to_scan(maxx, maxy), to_scan(minx, maxy)]
        # The window's first press: its own opening rectangle is not a
        # placement, so nothing is passed for the search to beat.
        r = place_grid(scanin, scan, cht, cie, boxes, exp, size,
                       current_corners=None)
        assert r.ending == "placed", (turn, bed, r.ending, r.find_reason,
                                      r.rejected)
        err = _worst(r.corners, truth) / (min(pitch_mm) * mmpx)
        assert err < 0.113, f"{turn} {bed}: {err:.3f} of a patch out"
        scan.unlink()
