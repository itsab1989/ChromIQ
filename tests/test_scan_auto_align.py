"""Auto align: the arithmetic, the refusals, and the button.

The interesting half of this feature is not "does it find the chart" -- Argyll
does that -- it is "does it ever move the user's corners onto a wrong answer".
So most of what is checked here is refusal.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from workflow.cht_parser import parse_cht                      # noqa: E402
from workflow.layout_engine.cht_writer import build_cht_text    # noqa: E402
from workflow.scan_auto_align import (                          # noqa: E402
    AGREEMENT_FLOOR, auto_align, border_agreement, chosen_index,
    corners_from_candidate, expected_luminance, parse_candidates,
    quad_is_sane, reference_agreement_at)

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

# One candidate line exactly as scanin -v2 prints it (scanrd.c::calc_rotation).
LOG_ONE = """About to match features
cc = 0.809397, irot = 0.000000, xoff = 0.000000, yoff = 0.000000, xscale = 10.000000, yscale = 10.000000
About to setup value scanrdg boxes
"""
LOG_TWO = """There are 2 candidate rotations:
cc = 0.809397, irot = 0.020914, xoff = 1.231953, yoff = 1.932483, xscale = 11.796459, yscale = 11.797182
cc = 0.801227, irot = 180.020914, xoff = -1935.845913, yoff = -2431.865972, xscale = 11.796458, yscale = 11.794144
Chosen rotation 180.020914 deg. as best
"""


# ---------------------------------------------------------------------------
# parsing scanin's own numbers
# ---------------------------------------------------------------------------
def test_a_single_candidate_is_read_out_of_the_log():
    c = parse_candidates(LOG_ONE)
    assert len(c) == 1
    assert c[0][0] == pytest.approx(0.809397)
    assert c[0][4] == pytest.approx(10.0)


def test_the_chosen_rotation_wins_over_the_first_one():
    c = parse_candidates(LOG_TWO)
    assert len(c) == 2
    # scanin named 180 deg, which is the SECOND line
    assert chosen_index(LOG_TWO, c) == 1


def test_no_chosen_line_means_the_first_candidate():
    c = parse_candidates(LOG_ONE)
    assert chosen_index(LOG_ONE, c) == 0


def test_a_log_with_no_candidates_yields_nothing():
    assert parse_candidates("Pattern match wasn't good enough\n") == []


def test_the_identity_affine_maps_the_bbox_by_the_scale():
    # irot 0, no offset, scale 10 -> the .cht bbox 0..20 becomes 0..200 px
    q = corners_from_candidate((0.9, 0.0, 0.0, 0.0, 10.0, 10.0), (0, 0, 20, 20))
    assert q == [(0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0)]


def test_a_ninety_degree_candidate_turns_the_quad():
    q = corners_from_candidate((0.9, 90.0, 0.0, 0.0, 1.0, 1.0), (0, 0, 10, 20))
    # top-left of the reference stays at the origin, the long side now runs up
    assert q[0] == pytest.approx((0.0, 0.0), abs=1e-9)
    assert q[1][0] == pytest.approx(0.0, abs=1e-6)
    assert q[1][1] == pytest.approx(-10.0, abs=1e-6)


# ---------------------------------------------------------------------------
# the cheap geometry gate
# ---------------------------------------------------------------------------
SQUARE_BBOX = (0.0, 0.0, 100.0, 100.0)


def test_a_plausible_quad_passes_the_geometry_gate():
    q = [(10, 10), (410, 10), (410, 410), (10, 410)]
    assert quad_is_sane(q, (500, 500), SQUARE_BBOX) == ""


@pytest.mark.parametrize("quad,size,why", [
    ([(10, 10), (900, 10), (900, 400), (10, 400)], (500, 500), "outside"),
    ([(10, 10), (20, 10), (20, 20), (10, 20)], (500, 500), "small"),
    ([(10, 10), (10, 10), (10, 10), (10, 10)], (500, 500), "degenerate"),
])
def test_the_geometry_gate_names_what_is_wrong(quad, size, why):
    assert why in quad_is_sane(quad, size, SQUARE_BBOX)


def test_a_quad_of_the_wrong_shape_is_refused():
    # the chart is square; this quad is 4:1
    q = [(10, 10), (410, 10), (410, 110), (10, 110)]
    assert "shape" in quad_is_sane(q, (500, 500), SQUARE_BBOX)


def test_a_ninety_degree_turn_is_not_the_wrong_shape():
    bbox = (0.0, 0.0, 100.0, 200.0)          # 1:2 chart
    q = [(10, 10), (410, 10), (410, 210), (10, 210)]   # 2:1 quad on screen
    assert quad_is_sane(q, (600, 400), bbox) == ""


def test_a_quad_with_a_nan_corner_is_refused():
    q = [(10, 10), (float("nan"), 10), (410, 410), (10, 410)]
    assert quad_is_sane(q, (500, 500), SQUARE_BBOX) != ""


# ---------------------------------------------------------------------------
# a small painted chart, and what the agreement number does on it
# ---------------------------------------------------------------------------
def _chart(tmp_path: Path, cols=6, rows=8, box=30, margin=40):
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
    px = img.load()
    for b in boxes:
        for y in range(int(b["y"]) + margin, int(b["y"] + b["h"]) + margin):
            for x in range(int(b["x"]) + margin, int(b["x"] + b["w"]) + margin):
                px[x, y] = colors[b["loc"]]
    p = tmp_path / "scan.tif"
    img.save(p)
    (tmp_path / "chart.cht").write_text(text, encoding="utf-8")
    truth = [(float(margin), float(margin)),
             (float(margin + cols * box), float(margin)),
             (float(margin + cols * box), float(margin + rows * box)),
             (float(margin), float(margin + rows * box))]
    return p, text, truth, box


def test_the_agreement_is_near_one_where_the_patches_are(tmp_path):
    scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    rho = reference_agreement_at(scan, boxes, truth,
                                 expected_luminance(text), 0.6)
    assert rho is not None and rho > 0.99


def test_a_rank_correlation_alone_does_not_see_a_one_patch_shift(tmp_path):
    """Recorded because it is the reason the border check exists. On a chart
    whose patches step smoothly, moving the grid a whole patch still reads
    patches, in the same order -- so the agreement number stays high while
    every single value belongs to the wrong patch."""
    scan, text, truth, box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    shifted = [(x, y + box) for x, y in truth]
    rho = reference_agreement_at(scan, boxes, shifted,
                                 expected_luminance(text), 0.6)
    assert rho is not None and rho > AGREEMENT_FLOOR


def test_the_border_check_does_see_a_one_patch_shift(tmp_path):
    scan, text, truth, box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    assert border_agreement(scan, boxes, truth) is True
    for shifted in ([(x, y + box) for x, y in truth],
                    [(x + box, y) for x, y in truth]):
        assert border_agreement(scan, boxes, shifted) is False


def test_the_border_check_is_none_when_the_image_cannot_be_read(tmp_path):
    _scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    assert border_agreement(tmp_path / "nope.tif", boxes, truth) is None


def test_the_agreement_is_none_when_the_image_cannot_be_read(tmp_path):
    _scan, text, truth, _box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    assert reference_agreement_at(tmp_path / "nope.tif", boxes, truth,
                                  expected_luminance(text), 0.6) is None


def test_expected_luminance_prefers_the_cht_and_falls_back_to_the_cie(tmp_path):
    _scan, text, _truth, _box = _chart(tmp_path)
    from_cht = expected_luminance(text)
    assert len(from_cht) == 48
    stripped = text[:text.index("EXPECTED XYZ")]
    cie = tmp_path / "r.cie"
    cie.write_text("\n".join(
        ["CGATS.17", "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
         "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
         "NUMBER_OF_SETS 1", "BEGIN_DATA", "A01 1 42 3", "END_DATA", ""]),
        encoding="utf-8")
    assert expected_luminance(stripped, cie) == {"A01": 42.0}


# ---------------------------------------------------------------------------
# auto_align's decisions, with scanin faked so the DECISION is what is tested
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


def _log_for(truth, bbox):
    """A scanin log whose affine lands exactly on *truth* (no rotation)."""
    sx = (truth[1][0] - truth[0][0]) / (bbox[2] - bbox[0])
    sy = (truth[3][1] - truth[0][1]) / (bbox[3] - bbox[1])
    xoff = truth[0][0] - bbox[0] * sx
    yoff = truth[0][1] - bbox[1] * sy
    return (f"cc = 0.9, irot = 0.000000, xoff = {xoff:f}, yoff = {yoff:f}, "
            f"xscale = {sx:f}, yscale = {sy:f}\n")


def _setup(tmp_path):
    scan, text, truth, box = _chart(tmp_path)
    boxes = parse_cht(text).patches
    bbox = (min(b.x1 for b in boxes), min(b.y1 for b in boxes),
            max(b.x2 for b in boxes), max(b.y2 for b in boxes))
    with Image.open(scan) as im:
        size = im.size
    cie = tmp_path / "chart.cie"
    cie.write_text("", encoding="utf-8")
    return (scan, tmp_path / "chart.cht", cie, boxes,
            expected_luminance(text), size, truth, bbox, box)


def test_a_good_answer_is_applied(tmp_path):
    scan, cht, cie, boxes, exp, size, truth, bbox, _box = _setup(tmp_path)
    r = auto_align("scanin", scan, cht, cie, boxes, exp, size,
                   current_corners=None,
                   runner=_FakeRun(_log_for(truth, bbox)))
    assert r.ok and r.reason == ""
    for got, want in zip(r.corners, truth):
        assert got == pytest.approx(want, abs=0.5)
    assert r.rho > 0.99


def test_the_recogniser_is_run_without_dash_p(tmp_path):
    """-p sends the answer through ppersp(), whose coefficients scanin never
    prints, so the recovered corners would be an approximation of an unseen
    number."""
    scan, cht, cie, boxes, exp, size, truth, bbox, _box = _setup(tmp_path)
    fake = _FakeRun(_log_for(truth, bbox))
    auto_align("scanin", scan, cht, cie, boxes, exp, size, runner=fake)
    assert fake.calls, "scanin was never run"
    assert "-p" not in fake.calls[0]
    assert "-v2" in fake.calls[0]


def test_the_ungated_dash_a_pass_only_runs_when_the_first_one_refuses(tmp_path):
    scan, cht, cie, boxes, exp, size, truth, bbox, _box = _setup(tmp_path)
    ok = _FakeRun(_log_for(truth, bbox))
    auto_align("scanin", scan, cht, cie, boxes, exp, size, runner=ok)
    assert len(ok.calls) == 1, "the -a fallback ran although auto succeeded"

    refused = _FakeRun("Pattern match wasn't good enough\n",
                       _log_for(truth, bbox))
    r = auto_align("scanin", scan, cht, cie, boxes, exp, size, runner=refused)
    assert len(refused.calls) == 2
    assert "-a" in refused.calls[1]
    assert r.ok and r.source == "auto -a"


def test_an_unrecognised_scan_changes_nothing(tmp_path):
    scan, cht, cie, boxes, exp, size, _t, _b, _box = _setup(tmp_path)
    r = auto_align("scanin", scan, cht, cie, boxes, exp, size,
                   runner=_FakeRun("Pattern match wasn't good enough\n",
                                   "Pattern match wasn't good enough\n"))
    assert not r.ok
    assert r.corners is None
    assert r.reason == "not-recognised"


def test_an_answer_one_patch_off_is_refused(tmp_path):
    """scanin is made to answer one patch off. The read would be every
    patch's neighbour, and nothing may move."""
    scan, cht, cie, boxes, exp, size, truth, bbox, box = _setup(tmp_path)
    off = [(x, y + box) for x, y in truth]
    r = auto_align("scanin", scan, cht, cie, boxes, exp, size,
                   runner=_FakeRun(_log_for(off, bbox), _log_for(off, bbox)))
    assert not r.ok, "a one-patch shift was applied"
    assert r.reason == "no-usable-candidate"
    assert any("edges" in s for s in r.rejected)


def test_an_answer_that_does_not_reach_the_floor_is_refused(tmp_path):
    """The floor itself, exercised by raising it out of reach: a placement
    that is otherwise perfect must still be refused when it cannot clear it."""
    scan, cht, cie, boxes, exp, size, truth, bbox, _box = _setup(tmp_path)
    r = auto_align("scanin", scan, cht, cie, boxes, exp, size, floor=1.5,
                   runner=_FakeRun(_log_for(truth, bbox)))
    assert not r.ok
    assert r.reason == "below-floor"
    assert r.rho is not None and r.rho > 0.9      # it WAS a good placement


def test_an_answer_on_blank_paper_is_refused(tmp_path):
    """The quad is the right size and shape but sits on the margin."""
    scan, cht, cie, boxes, exp, size, truth, bbox, _box = _setup(tmp_path)
    dx = truth[1][0] - truth[0][0]
    off = [(x - dx * 0.98, y) for x, y in truth]
    r = auto_align("scanin", scan, cht, cie, boxes, exp, size,
                   runner=_FakeRun(_log_for(off, bbox), _log_for(off, bbox)))
    assert not r.ok, f"accepted a quad off the chart: {r}"


def test_an_answer_of_the_wrong_shape_is_refused_before_it_is_measured(tmp_path):
    scan, cht, cie, boxes, exp, size, _t, bbox, _box = _setup(tmp_path)
    squashed = [(20.0, 20.0), (200.0, 20.0), (200.0, 40.0), (20.0, 40.0)]
    r = auto_align("scanin", scan, cht, cie, boxes, exp, size,
                   runner=_FakeRun(_log_for(squashed, bbox)))
    assert not r.ok
    assert r.reason == "no-usable-candidate"
    assert any("shape" in s for s in r.rejected)


def test_an_answer_no_better_than_the_user_is_not_applied(tmp_path):
    """The user is already on the patches. Moving the corners to an equally
    good place is churn, not help."""
    scan, cht, cie, boxes, exp, size, truth, bbox, _box = _setup(tmp_path)
    r = auto_align("scanin", scan, cht, cie, boxes, exp, size,
                   current_corners=truth,
                   runner=_FakeRun(_log_for(truth, bbox)))
    assert not r.ok
    assert r.reason == "no-better"


def test_a_chart_with_no_patch_boxes_is_refused_without_running_anything(tmp_path):
    scan, cht, cie, _boxes, exp, size, _t, _b, _box = _setup(tmp_path)
    fake = _FakeRun("")
    r = auto_align("scanin", scan, cht, cie, [], exp, size, runner=fake)
    assert not r.ok and r.reason == "no-chart-geometry"
    assert fake.calls == []


def test_a_scanin_that_never_returns_is_a_refusal_not_a_hang(tmp_path):
    scan, cht, cie, boxes, exp, size, _t, _b, _box = _setup(tmp_path)

    def _timeout(args, **kw):
        assert kw.get("timeout"), "scanin was run with no timeout"
        raise subprocess.TimeoutExpired(args, kw["timeout"])

    r = auto_align("scanin", scan, cht, cie, boxes, exp, size, runner=_timeout)
    assert not r.ok and r.reason == "not-recognised"


# ---------------------------------------------------------------------------
# the button
# ---------------------------------------------------------------------------
def test_the_button_sits_next_to_rotate_ninety(qapp, tmp_path):
    """Basti asked for it beside Rotate 90 deg, under the preview."""
    d = _dialog(qapp, tmp_path)
    assert d._auto_align_btn.text()
    lay = _row_of(d, d._rotate_btn)
    widgets = [lay.itemAt(i).widget() for i in range(lay.count())]
    assert widgets[widgets.index(d._rotate_btn) + 1] is d._auto_align_btn


def _row_of(dialog, btn):
    from PyQt6.QtWidgets import QHBoxLayout
    for lay in dialog.findChildren(QHBoxLayout):
        for i in range(lay.count()):
            if lay.itemAt(i).widget() is btn:
                return lay
    raise AssertionError("button not found in any row")


def _dialog(qapp, tmp_path):
    from core.settings import AppSettings
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    settings = AppSettings()

    class _Runner:
        is_running = False

        def run(self, *a, **k):
            raise AssertionError("no Argyll in this test")
    return ScannerProfileDialog(_Runner(), settings)


def test_pressing_it_with_nothing_loaded_says_so_and_moves_nothing(qapp, tmp_path):
    d = _dialog(qapp, tmp_path)
    before = d._marquee.corners_image_px()
    d._on_auto_align()
    assert d._marquee.corners_image_px() == before
    assert "Auto align" in d._log.toPlainText()


def test_a_refusal_leaves_the_corners_alone_and_offers_no_undo(qapp, tmp_path):
    from workflow.scan_auto_align import AutoAlignResult
    d = _dialog(qapp, tmp_path)
    before = d._marquee.corners_image_px()
    d._align_before = list(before)
    d._auto_align_done(AutoAlignResult(reason="below-floor", rho=0.4))
    assert d._marquee.corners_image_px() == before
    assert d._align_undo is None
    assert d._auto_align_btn.text() != "Undo auto align"


def test_an_accepted_answer_moves_the_grid_and_arms_one_step_undo(qapp, tmp_path):
    from core.i18n import tr
    from workflow.scan_auto_align import AutoAlignResult
    d = _dialog(qapp, tmp_path)
    d._marquee.set_image(Image_qimage(200, 200))
    d._marquee.set_corners([(10, 10), (100, 10), (100, 100), (10, 100)])
    d._capture_current_corners()
    before = d._marquee.corners_image_px()
    d._align_before = list(before)
    found = [(20.0, 20.0), (150.0, 20.0), (150.0, 150.0), (20.0, 150.0)]
    d._auto_align_done(AutoAlignResult(corners=found, rho=0.97, source="auto"))
    assert d._marquee.corners_image_px() == found
    assert d._auto_align_btn.text() == tr("Undo auto align")
    # one press puts it back, exactly
    d._on_auto_align()
    assert d._marquee.corners_image_px() == before
    assert d._auto_align_btn.text() == tr("Auto align")


def Image_qimage(w, h):
    from PyQt6.QtGui import QImage, qRgb
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(qRgb(255, 255, 255))
    return img


def test_moving_the_grid_by_hand_ends_the_undo(qapp, tmp_path):
    from core.i18n import tr
    from workflow.scan_auto_align import AutoAlignResult
    d = _dialog(qapp, tmp_path)
    d._marquee.set_image(Image_qimage(200, 200))
    d._marquee.set_corners([(10, 10), (100, 10), (100, 100), (10, 100)])
    d._capture_current_corners()
    d._align_before = list(d._marquee.corners_image_px())
    d._auto_align_done(AutoAlignResult(
        corners=[(20.0, 20.0), (150.0, 20.0), (150.0, 150.0), (20.0, 150.0)],
        rho=0.97, source="auto"))
    assert d._auto_align_btn.text() == tr("Undo auto align")
    # what a drag emits (set_corners is a restore, and stays silent)
    d._marquee.changed.emit()
    assert d._align_undo is None
    assert d._auto_align_btn.text() == tr("Auto align")


# ---------------------------------------------------------------------------
# end to end with the real ArgyllCMS, when it is present
# ---------------------------------------------------------------------------
from tests.argyll_env import argyll_tool  # noqa: E402
_SCANIN = argyll_tool("scanin")


@pytest.mark.skipif(_SCANIN is None, reason="ArgyllCMS scanin not present")
def test_the_real_recogniser_finds_a_real_chart(tmp_path):
    scan, text, truth, _box = _chart(tmp_path, cols=8, rows=10, box=40,
                                     margin=60)
    boxes = parse_cht(text).patches
    cie = tmp_path / "chart.cie"
    cie.write_text("\n".join(
        ["CGATS.17", "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
         "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
         f"NUMBER_OF_SETS {len(boxes)}", "BEGIN_DATA"]
        + [f"{b.name} 20 20 20" for b in boxes] + ["END_DATA", ""]),
        encoding="utf-8")
    with Image.open(scan) as im:
        size = im.size
    r = auto_align(_SCANIN, scan, tmp_path / "chart.cht", cie, boxes,
                   expected_luminance(text), size, timeout=300)
    assert r.ok, f"refused: {r.reason} / {r.log_tail}"
    worst = max(math.dist(a, b) for a, b in zip(r.corners, truth))
    assert worst < 8.0, f"corners {worst:.1f} px out: {r.corners}"
