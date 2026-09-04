"""Auto align must not accept a placement that is geometrically wrong, however
well it agrees with the chart's colours. (beta 8, B8-02.)

The fault this file guards is not a bug in a line of code; it is a shape.
``scan_auto_align.corners_from_candidate`` rebuilds the placement out of the
five numbers ``scanin`` prints, and that arithmetic can only ever produce a
**rotated rectangle** — a rotation and two scales, five degrees of freedom
where a placement needs eight. A sheet photographed off square is a keystone,
which no rectangle is, so the grid comes out right in the middle of the sheet
and worst at one corner. And every gate that existed before this file looks at
COLOUR: a rank correlation is blind to shear, because the patches keep their
brightness ORDER while they slide onto their neighbours.

Measured with a pinhole camera at three sheet-widths, compound pitch+yaw: at
8 degrees, 20 of 23 targets accepted and ten were more than half a patch pitch
out — reading the neighbouring patch — while the window printed "agrees … to
0.98" beside its own sentence "anything below 0.80 is refused". Costed on
Knut's real Wolf Faust scan at 10 degrees: 33 of 288 patches move by more than
3 ΔE00 and the profile is a median 2.23 ΔE00 out.

Every synthetic case below is built so that the OLD gates pass it. Test 4 is
the one that matters: it asserts, on the same image and the same quad, that
the reference agreement is ≥ 0.99 and ``border_agreement`` is True — and that
the drift still sees it.
"""
from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.cht_parser import parse_cht                       # noqa: E402
from workflow.layout_engine.cht_writer import build_cht_text     # noqa: E402
from workflow.scan_auto_align import (                           # noqa: E402
    SEATING_DRIFT_LIMIT, SEATING_SAMPLE_AREA, auto_align, border_agreement,
    corners_from_candidate, expected_luminance, reference_agreement_at,
    seating_drift)

pytest.importorskip("PIL")
pytest.importorskip("numpy")
import numpy as np                                               # noqa: E402
from PIL import Image, ImageDraw                                 # noqa: E402


# ---------------------------------------------------------------------------
# a painted chart, big enough that one patch pitch is many pixels
# ---------------------------------------------------------------------------
def _chart(tmp_path: Path, cols=8, rows=10, box=60, margin=90):
    """A grey ramp laid out column by column, patches edge to edge.

    The ramp is deliberate: with neighbours one step apart, a placement shifted
    by a whole pitch keeps almost every rank, which is exactly the blind spot
    being demonstrated.
    """
    boxes, colors = [], {}
    for c in range(cols):
        for r in range(rows):
            loc = f"{chr(65 + c)}{r + 1:02d}"
            boxes.append({"loc": loc, "x": float(c * box), "y": float(r * box),
                          "w": float(box), "h": float(box)})
            v = 20 + (c * rows + r) * 220 // (cols * rows)
            colors[loc] = (v, v, v)
    exp = [(b["loc"], colors[b["loc"]][0] / 2.55, colors[b["loc"]][0] / 2.55,
            colors[b["loc"]][0] / 2.55) for b in boxes]
    text = build_cht_text(boxes, exp)
    img = Image.new("RGB", (cols * box + 2 * margin, rows * box + 2 * margin),
                    (255, 255, 255))
    dr = ImageDraw.Draw(img)
    for b in boxes:
        dr.rectangle([b["x"] + margin, b["y"] + margin,
                      b["x"] + b["w"] + margin - 1, b["y"] + b["h"] + margin - 1],
                     fill=colors[b["loc"]])
    scan = tmp_path / "scan.tif"
    img.save(scan)
    (tmp_path / "chart.cht").write_text(text, encoding="utf-8")
    (tmp_path / "chart.cie").write_text("", encoding="utf-8")
    truth = [(float(margin), float(margin)),
             (float(margin + cols * box), float(margin)),
             (float(margin + cols * box), float(margin + rows * box)),
             (float(margin), float(margin + rows * box))]
    return scan, text, truth, float(box)


def _homography(src, dst):
    a = []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.asarray(a, dtype=float))
    h = vt[-1].reshape(3, 3)
    return h / h[2, 2]


def _apply(h, pts):
    out = []
    for x, y in pts:
        d = h[2, 0] * x + h[2, 1] * y + h[2, 2]
        out.append(((h[0, 0] * x + h[0, 1] * y + h[0, 2]) / d,
                    (h[1, 0] * x + h[1, 1] * y + h[1, 2]) / d))
    return out


def _keystone(tmp_path: Path, scan: Path, truth, k: float):
    """Photograph the sheet from below: the top edge pulled in by *k* of the
    width. Returns (image path, the true corners, the best RECTANGLE through
    them — which is all `corners_from_candidate` can ever produce)."""
    with Image.open(scan) as im:
        w, h = im.size
        src = [(0, 0), (w, 0), (w, h), (0, h)]
        dst = [(w * k, 0), (w * (1 - k), 0), (w, h), (0, h)]
        hm = _homography(src, dst)
        inv = np.linalg.inv(hm)
        inv = inv / inv[2, 2]
        warped = im.transform((w, h), Image.Transform.PERSPECTIVE,
                              tuple(inv.flatten()[:8]),
                              resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    out = tmp_path / f"keystone-{k}.tif"
    warped.save(out)
    tw = _apply(hm, truth)
    cx = sum(p[0] for p in tw) / 4.0
    cy = sum(p[1] for p in tw) / 4.0
    hw = (abs(tw[1][0] - tw[0][0]) + abs(tw[2][0] - tw[3][0])) / 4.0
    hh = (abs(tw[3][1] - tw[0][1]) + abs(tw[2][1] - tw[1][1])) / 4.0
    rect = [(cx - hw, cy - hh), (cx + hw, cy - hh),
            (cx + hw, cy + hh), (cx - hw, cy + hh)]
    return out, tw, rect


# ---------------------------------------------------------------------------
# 1. why nothing about the QUAD can ever answer this
# ---------------------------------------------------------------------------
def test_the_quad_the_recogniser_can_return_is_always_a_rectangle():
    """`compute_ptrans` is a rotation and two scales, so the two edge vectors
    of the returned quad are orthogonal BY CONSTRUCTION — at every rotation,
    every scale, every offset. There is no keystone term to recover and no
    amount of checking the quad's shape can find one."""
    bbox = (0.0, 0.0, 120.0, 200.0)
    rng = np.random.default_rng(11)
    for _ in range(200):
        cand = (0.9, float(rng.uniform(-360, 360)), float(rng.uniform(-500, 500)),
                float(rng.uniform(-500, 500)), float(rng.uniform(0.2, 40)),
                float(rng.uniform(0.2, 40)))
        q = corners_from_candidate(cand, bbox)
        e1 = (q[1][0] - q[0][0], q[1][1] - q[0][1])
        e2 = (q[3][0] - q[0][0], q[3][1] - q[0][1])
        dot = e1[0] * e2[0] + e1[1] * e2[1]
        norm = math.hypot(*e1) * math.hypot(*e2)
        assert abs(dot) <= 1e-9 * max(norm, 1.0), (cand, q)


# ---------------------------------------------------------------------------
# 2-3. what the drift says about a placement that IS right, and one that is not
# ---------------------------------------------------------------------------
def test_a_correct_placement_has_no_seating_drift(tmp_path):
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    assert seating_drift(scan, boxes, truth) < 0.001


def test_a_flat_chart_with_no_texture_is_not_refused_for_being_flat(tmp_path):
    """The first version of this measure divided by the patch's own dispersion,
    so a patch painted in one exact colour — dispersion zero — tied at every
    offset and the ratio reported a confident 1.0 about pure tie-breaking.
    Measured: a CORRECT placement on this very chart came out at 0.088, above
    the limit. The floor in the denominator is what stops it, and this chart is
    painted in exact flat colours precisely so that it would fire."""
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    assert seating_drift(scan, boxes, truth) <= SEATING_DRIFT_LIMIT / 10.0


def test_a_half_pitch_shift_is_seen(tmp_path):
    """Half a pitch is where a sample box starts reading the neighbouring
    patch. On a ramp the ranks barely move; the seating does."""
    scan, text, truth, box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    shifted = [(x + box * 0.5, y) for x, y in truth]
    assert seating_drift(scan, boxes, shifted) > 4 * SEATING_DRIFT_LIMIT


# ---------------------------------------------------------------------------
# 4. THE ONE THAT MATTERS
# ---------------------------------------------------------------------------
def test_a_keystone_is_seen_although_every_older_gate_passes_it(tmp_path):
    """Same image, same quad, all four judgements side by side."""
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    exp = expected_luminance(text)
    img, _true_quad, rect = _keystone(tmp_path, scan, truth, 0.06)

    rho = reference_agreement_at(img, boxes, rect, exp, 0.6)
    assert rho is not None and rho >= 0.99, (
        "the demonstration is only worth anything if the OLD gate passes it")
    assert border_agreement(img, boxes, rect) is not False, (
        "likewise: border_agreement must not be the thing that catches it")

    drift = seating_drift(img, boxes, rect)
    assert drift is not None and drift > SEATING_DRIFT_LIMIT, drift


def test_the_true_corners_of_the_same_photograph_are_not_refused(tmp_path):
    """The keystone itself is not the fault — a quad has four free corners and
    can express one exactly. Only the RECTANGLE cannot. So the same image at
    its true corners must pass, or this gate would be refusing photography
    rather than refusing a wrong answer."""
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    for k in (0.02, 0.04, 0.06, 0.08):
        img, true_quad, _rect = _keystone(tmp_path, scan, truth, k)
        assert seating_drift(img, boxes, true_quad) <= SEATING_DRIFT_LIMIT, k


# ---------------------------------------------------------------------------
# 5-6. the button's decision, with scanin faked so the DECISION is the subject
# ---------------------------------------------------------------------------
class _FakeRun:
    """Stands in for subprocess.run; replays a canned scanin log."""

    def __init__(self, *logs):
        self.logs = list(logs)
        self.calls = []

    def __call__(self, args, **kw):
        self.calls.append(list(args))
        text = self.logs.pop(0) if self.logs else ""
        return subprocess.CompletedProcess(args, 0, stdout=text, stderr="")


def _log_for(quad, bbox):
    """A scanin log whose affine lands exactly on *quad* (no rotation)."""
    sx = (quad[1][0] - quad[0][0]) / (bbox[2] - bbox[0])
    sy = (quad[3][1] - quad[0][1]) / (bbox[3] - bbox[1])
    xoff = quad[0][0] - bbox[0] * sx
    yoff = quad[0][1] - bbox[1] * sy
    return (f"cc = 0.9, irot = 0.000000, xoff = {xoff:f}, yoff = {yoff:f}, "
            f"xscale = {sx:f}, yscale = {sy:f}\n")


def _bbox(boxes):
    return (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))


def test_auto_align_refuses_the_keystone_and_names_the_reason(tmp_path):
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    exp = expected_luminance(text)
    img, _tq, rect = _keystone(tmp_path, scan, truth, 0.06)
    with Image.open(img) as im:
        size = im.size
    r = auto_align("scanin", img, tmp_path / "chart.cht", tmp_path / "chart.cie",
                   boxes, exp, size, current_corners=None,
                   runner=_FakeRun(_log_for(rect, _bbox(boxes))))
    assert not r.ok
    assert r.reason == "not-seated"
    assert r.corners is None, "a refusal must leave the user's corners alone"
    assert r.drift is not None and r.drift > SEATING_DRIFT_LIMIT
    assert any("do not sit" in s for s in r.rejected), r.rejected


def test_auto_align_still_applies_a_good_answer_and_records_its_drift(tmp_path):
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    exp = expected_luminance(text)
    with Image.open(scan) as im:
        size = im.size
    r = auto_align("scanin", scan, tmp_path / "chart.cht", tmp_path / "chart.cie",
                   boxes, exp, size, current_corners=None,
                   runner=_FakeRun(_log_for(truth, _bbox(boxes))))
    assert r.ok, r.reason
    assert r.drift is not None and r.drift <= SEATING_DRIFT_LIMIT
    for got, want in zip(r.corners, truth):
        assert got == pytest.approx(want, abs=0.5)


# ---------------------------------------------------------------------------
# 7-10. the gate's own edges
# ---------------------------------------------------------------------------
def test_the_gate_does_not_move_when_the_user_changes_the_sample_area(tmp_path):
    """The Sample area spinbox decides how much of each patch the READ
    averages. It must not decide how hard the safety check looks, or the check
    can be dragged open."""
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    exp = expected_luminance(text)
    img, _tq, rect = _keystone(tmp_path, scan, truth, 0.06)
    with Image.open(img) as im:
        size = im.size
    seen = set()
    for frac in (0.20, 0.60, 0.80):
        r = auto_align("scanin", img, tmp_path / "chart.cht",
                       tmp_path / "chart.cie", boxes, exp, size,
                       current_corners=None, sample_frac=frac,
                       runner=_FakeRun(_log_for(rect, _bbox(boxes))))
        assert not r.ok and r.reason == "not-seated", frac
        seen.add(round(r.drift, 9))
    assert len(seen) == 1, f"the drift moved with the spinbox: {seen}"
    assert SEATING_SAMPLE_AREA == 0.60


def test_a_chart_too_small_to_judge_says_nothing_rather_than_refusing(tmp_path):
    """Fewer than twelve patches cannot support a regional mean, and the honest
    answer is no evidence — never a refusal. A gate that refuses when it cannot
    see is a gate that gets switched off."""
    scan, text, truth, _box = _chart(tmp_path, cols=3, rows=3, box=60, margin=90)
    boxes = parse_cht(text).patches
    assert len(boxes) == 9
    assert seating_drift(scan, boxes, truth) is None


def test_an_unreadable_image_is_no_evidence_and_no_crash(tmp_path):
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    assert seating_drift(tmp_path / "not-here.tif", boxes, truth) is None


def test_the_limit_sits_between_the_two_measured_populations():
    """The window, pinned. 0.0631 is the highest reading of any of 328 CORRECT
    placements measured — a 24-patch half Passport at 15 degrees, with Knut's
    own noisy scan next at 0.0583 and his untouched scans at 0.0175 and 0.0139.
    0.0989 is the LOWEST reading of any of 106 placements that were more than
    half a patch pitch out — a ColorCheckerSG bowed 3 mm, through a phone-lens
    barrel, at 8 degrees. A later change that moves this constant outside that
    window has stopped being the thing that was measured, and must re-measure
    before it moves."""
    assert 0.0631 < SEATING_DRIFT_LIMIT < 0.0989


def test_the_refusal_has_words_of_its_own_and_is_not_approved_yet():
    from workflow import measurement_messages as M
    msg = M.scan_align_refusal("not-seated")
    assert msg is M.M_SCAN_ALIGN_NOT_SEATED
    assert not msg.approved, "new wording goes through §M-PROPOSED"
    assert "M-SCAN-ALIGN-NOT-SEATED" in M.PROPOSED
    title, body = msg.render(ref_row="Target reference data",
                             chart_row="Target type")
    assert "not-seated" not in title and "not-seated" not in body, (
        "the internal reason must never reach the screen")
