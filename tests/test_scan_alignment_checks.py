"""Misalignment detection + the F-orientation fix (#108, Knut round 4).

Knut deliberately misaligned one page's grid and built anyway: the ΔE check
printed one ⚠ line buried in colprof's -v output, scanner mode had no check at
all, and — the real find — every engine-chart scanner read was scrambled even
when perfectly aligned: the patch-bbox ``F`` rewrite emitted a fixed corner
order (right for y-down standard charts, a vertical mirror for y-up engine
charts), reversing every strip while every box still landed on a patch.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from core.settings import DEFAULTS  # noqa: E402
from workflow.layout_engine.cht_writer import build_cht_text  # noqa: E402
from workflow.scanin_runner import cht_with_patchbox_fiducials  # noqa: E402


@pytest.fixture(scope="module")
def _app():
    return QApplication.instance() or QApplication([])


class _FakeSettings:
    def __init__(self, **overrides):
        self._store = {**DEFAULTS, **overrides}

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set(self, key, value):
        self._store[key] = value


def _f_corners(cht_text: str) -> list[tuple[float, float]]:
    import re
    m = re.search(r"(?m)^\s*F _ _ (.*)$", cht_text)
    v = [float(t) for t in m.group(1).split()]
    return [(v[i], v[i + 1]) for i in range(0, 8, 2)]


def _engine_cht(marks_outside: float = 0.0) -> str:
    """A y-up (bottom-left-origin) cht: strip A runs A1 (top, y=90) → A3
    (bottom, y=10) — the convention engine charts used before round 5
    switched the writer to y-down. Such files still exist on disk, so the
    F rewrite must keep preserving their orientation; the y-up F line is
    written explicitly here since the writer itself is y-down now."""
    import re
    boxes = [{"loc": f"A{i + 1}", "x": 10.0, "y": 90.0 - i * 40.0,
              "w": 20.0, "h": 20.0} for i in range(3)]
    txt = build_cht_text(boxes, [(b["loc"], 20.0, 20.0, 20.0) for b in boxes])
    #        TL (ymax first — y-up)   TR          BR         BL
    yup_f = "  F _ _ 10.0 110.0 30.0 110.0 30.0 10.0 10.0 10.0"
    txt = re.sub(r"(?m)^\s*F .*$", yup_f, txt, count=1)
    if marks_outside:
        c = _f_corners(txt)
        moved = [(x + (marks_outside if x > 15 else -marks_outside),
                  y + (marks_outside if y > 60 else -marks_outside))
                 for x, y in c]
        line = "  F _ _ " + " ".join(f"{x:f} {y:f}" for x, y in moved)
        import re
        txt = re.sub(r"(?m)^\s*F .*$", line, txt, count=1)
    return txt


def _downwards_cht() -> str:
    """A y-down (image-style) standard-target cht, F in TL,TR,BR,BL order the
    way rectarg/Argyll write it (first corner = ymin = physically top)."""
    return "\n".join([
        "", "", "BOXES 4",
        "  F _ _ 5 5 105 5 105 55 5 55",
        "  X P1 P1 _ _ 40 40 10 10 0 0",
        "  X P2 P2 _ _ 40 40 60 10 0 0",
        "", "BOX_SHRINK 3", "", "REF_ROTATION 0.0", "",
        "XLIST 0", "", "YLIST 0", "", "",
        "EXPECTED XYZ 2", "  P1 20 20 20", "  P2 20 20 20", ""])


def test_patchbox_rewrite_preserves_yup_orientation():
    """The #108 regression: an engine cht's F starts at the TOP corner
    (ymax in its y-up coords) — the patch-bbox rewrite must keep it there,
    not emit the y-down fixed order that mirrors the grid."""
    old = _f_corners(_engine_cht())
    new = _f_corners(cht_with_patchbox_fiducials(_engine_cht()))
    assert old[0][1] == max(c[1] for c in old)          # engine F: TL first
    assert new[0][1] == max(c[1] for c in new), \
        "F corner order flipped — every strip reads reversed (#108)"
    # x order preserved too (TL, TR, BR, BL).
    assert new[0][0] < new[1][0] and new[3][0] < new[2][0]


def test_writer_emits_ydown_fiducials():
    """Round 5: the engine writer uses Argyll's image-style y-down convention
    — F starts at (xmin, ymin) = top-left — so scanin's -F mapping carries no
    reflection and the diagnostic image renders labels upright (Knut read
    mirrored '2' as '5' and reported scrambled label order)."""
    txt = build_cht_text([{"loc": "A1", "x": 10.0, "y": 5.0, "w": 20.0, "h": 20.0}],
                         [("A1", 20.0, 20.0, 20.0)])
    assert _f_corners(txt)[0] == (10.0, 5.0)


def test_patchbox_rewrite_preserves_ydown_orientation():
    new = _f_corners(cht_with_patchbox_fiducials(_downwards_cht()))
    # Standard chart: first corner stays the ymin (top-of-image) one, and the
    # frame is now the patch bbox (10..100 / 10..50).
    assert new[0] == (10.0, 10.0) and new[2] == (100.0, 50.0)


def test_patchbox_rewrite_snaps_outside_marks_without_flip():
    """printtarg -s marks sit OUTSIDE the patch area; each must snap to the
    nearest bbox corner, keeping the frame's orientation."""
    new = _f_corners(cht_with_patchbox_fiducials(_engine_cht(marks_outside=7.0)))
    assert new[0][1] == max(c[1] for c in new)          # still top-first
    assert new[0][0] == min(c[0] for c in new)
    xs = sorted({x for x, _ in new}); ys = sorted({y for _, y in new})
    assert xs == [10.0, 30.0] and ys == [10.0, 110.0]   # exactly the bbox now


def test_patchbox_rewrite_no_f_line_unchanged():
    txt = "\n".join(l for l in _engine_cht().splitlines()
                    if not l.strip().startswith("F "))
    assert cht_with_patchbox_fiducials(txt) == txt


def _write_cgats(path, fields, rows):
    path.write_text("\n".join(
        ["CGATS.17", f"NUMBER_OF_FIELDS {len(fields)}", "BEGIN_DATA_FORMAT",
         " ".join(fields), "END_DATA_FORMAT", f"NUMBER_OF_SETS {len(rows)}",
         "BEGIN_DATA"] + [" ".join(str(v) for v in r) for r in rows]
        + ["END_DATA", ""]), encoding="utf-8")


def test_page_reference_agreement_translates_page_locs(tmp_path, _app):
    """Printer-mode .ti3/.ti2 are keyed by numeric SAMPLE_ID with the loc in
    SAMPLE_LOC; a page's .cht gives locs — the agreement must restrict
    correctly and stay blind to honest response differences (the retired
    ΔE-vs-aims check flagged Knut's perfectly aligned REAL scans at 100 %
    on every page, because a print can't reach the chart's ideal aims)."""
    from ui.dialogs.scanin_dialog import page_reference_agreement
    ti2 = tmp_path / "c.ti2"; ti3 = tmp_path / "c.ti3"
    f2 = ["SAMPLE_ID", "SAMPLE_LOC", "RGB_R", "RGB_G", "RGB_B",
          "XYZ_X", "XYZ_Y", "XYZ_Z"]
    aims = [[i + 1, f'"{s}{n}"', 50, 50, 50, 8 * i + 1, 8 * i + 1, 8 * i + 1]
            for i, (s, n) in enumerate((s, n) for s in "AB" for n in range(1, 11))]
    _write_cgats(ti2, f2, aims)
    # Page A scrambled; page B = heavy but MONOTONE response (compressed):
    # aligned-but-compressed must stay above the floor.
    perm = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]   # fully reversed = scrambled
    got = []
    for i, r in enumerate([list(r) for r in aims]):
        if str(r[1]).startswith('"A'):
            src = aims[perm[i % 10]]
            got.append(r[:5] + list(src[5:]))
        else:
            got.append(r[:5] + [v ** 0.5 * 3 for v in r[5:]])
    _write_cgats(ti3, f2, got)
    a = page_reference_agreement(ti3, ti2, ids={f"A{i}" for i in range(1, 11)})
    b = page_reference_agreement(ti3, ti2, ids={f"B{i}" for i in range(1, 11)})
    assert a is None or a < 0.6                     # scrambled page low
    assert b is not None and b > 0.9                # compressed-but-aligned high


def test_scan_reference_correlation_separates(tmp_path, _app):
    from ui.dialogs.scanin_dialog import scan_reference_correlation
    f = ["SAMPLE_ID", "RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z"]
    n = 24
    good = [[f"P{i + 1}", 4 * i, 4 * i, 4 * i, 3 * i, 3 * i + 1, 3 * i]
            for i in range(n)]
    t = tmp_path / "good.ti3"; _write_cgats(t, f, good)
    assert scan_reference_correlation(t) > 0.9
    bad = [r[:4] + good[(i * 7 + 3) % n][4:] for i, r in enumerate(good)]
    t2 = tmp_path / "bad.ti3"; _write_cgats(t2, f, bad)
    assert scan_reference_correlation(t2) < 0.5


def test_page_ids_from_cht_strips_padding(tmp_path, _app):
    from ui.dialogs.scanin_dialog import page_ids_from_cht
    p = tmp_path / "p.cht"
    p.write_text(_engine_cht().replace("A1 A1", "A01 A01"), encoding="utf-8")
    assert page_ids_from_cht(p) == {"A1", "A2", "A3"}


def _dense_cht_text(boxes) -> str:
    """A minimal Argyll .cht: one X line per box + the patch-bbox F line."""
    minx = min(b.x1 for b in boxes); maxx = max(b.x2 for b in boxes)
    miny = min(b.y1 for b in boxes); maxy = max(b.y2 for b in boxes)
    lines = [f"BOXES {len(boxes) + 1}",
             f"  F _ _ {minx} {miny} {maxx} {miny} {maxx} {maxy} {minx} {maxy}"]
    for b in boxes:
        lines.append(f"  X {b.name} {b.name} _ _ "
                     f"{b.x2 - b.x1} {b.y2 - b.y1} {b.x1} {b.y1} 0 0")
    return "\n".join(lines) + "\n"


def test_check_page_alignment_flags_and_logs(tmp_path, _app):
    """Drive the real per-page hook with a MISPLACED grid over a real image:
    the dense placement check must log a ⚠ AND collect the finding for the
    pre-colprof modal (Knut: the Build button runs the same check as the
    Check alignment button)."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    from workflow.scanin_runner import ScaninParams
    scan, boxes, corners, exp = _dense_fixture(tmp_path, 0.40)
    # Production always hands the probe a sample-area-shrunk cht (the
    # prepare pipeline); the dialog's box grow-back assumes it. Mirror that.
    from workflow.scanin_runner import cht_with_sample_area
    (tmp_path / "x.cht").write_text(
        cht_with_sample_area(_dense_cht_text(boxes), 0.6), encoding="utf-8")
    f = ["SAMPLE_ID", "RGB_R", "RGB_G", "RGB_B", "XYZ_X", "XYZ_Y", "XYZ_Z"]
    rows = [[n, v, v, v, v, v, v] for n, v in exp.items()]
    _write_cgats(scan.parent / f"{scan.stem}-scanner.ti3", f, rows)
    # tmp_path, not tempfile.mkdtemp(): nothing ever removes an mkdtemp tree,
    # and these had grown to thousands of folders on disk (see the note in
    # tests/test_scanin_dialog.py).
    dlg = ScannerProfileDialog(object(), _FakeSettings(
        custom_output_path=str(tmp_path / "out")))
    try:
        params = ScaninParams(scan, tmp_path / "x.cht", corners=corners)
        dlg._check_page_alignment({"params": params, "page": 2})
        assert len(dlg._align_warnings) == 1
        assert "lacement agreement" in dlg._align_warnings[0]
        assert "⚠" in dlg._log.toPlainText()
        # an ALIGNED grid must stay quiet
        scan2, boxes2, corners2, _exp2 = _dense_fixture(tmp_path, 0.0)
        dlg._align_warnings.clear()
        params2 = ScaninParams(scan2, tmp_path / "x.cht", corners=corners2)
        dlg._check_page_alignment({"params": params2, "page": 1})
        assert dlg._align_warnings == []
    finally:
        dlg.deleteLater()


@pytest.mark.parametrize("press_stop", [True, False])
def test_confirm_despite_misalignment(press_stop, _app, monkeypatch, tmp_path):
    """The modal gate: Stop (the default) aborts the build; Build anyway
    continues. Only the blocking exec edge is stubbed — the real handler,
    buttons and _finish path run."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    # tmp_path, not tempfile.mkdtemp(): nothing ever removes an mkdtemp tree,
    # and these had grown to thousands of folders on disk (see the note in
    # tests/test_scanin_dialog.py).
    dlg = ScannerProfileDialog(object(), _FakeSettings(
        custom_output_path=str(tmp_path / "out")))
    try:
        dlg._align_warnings = ["Page 1: scrambled"]
        finished = []
        monkeypatch.setattr(dlg, "_finish", lambda ok: finished.append(ok))

        def _exec(box):
            (box.defaultButton() if press_stop
             else next(b for b in box.buttons()
                       if b is not box.defaultButton())).click()
            return 0

        monkeypatch.setattr(QMessageBox, "exec", _exec)
        proceed = dlg._confirm_despite_misalignment()
        assert proceed is (not press_stop)
        assert finished == ([False] if press_stop else [])
    finally:
        dlg.deleteLater()


def test_locally_misaligned_groups_flags_shifted_row(_app):
    """Knut's mid-handle squeeze: only the top row reads the row below it.
    The rank-displacement cluster check names exactly that row and stays
    quiet on an aligned page (his literal per-row pattern matching false-
    alarmed at 98.5 % on randomised charts — see the helper's docstring)."""
    import random
    from ui.dialogs.scanin_dialog import locally_misaligned_groups
    rng = random.Random(42)
    strips = "ABCDEFG"
    exp = {f"{s}{i}": rng.random() * 100
           for s in strips for i in range(1, 16)}
    read_ok = {k: v * 0.9 + 2 for k, v in exp.items()}     # monotone response
    assert locally_misaligned_groups(read_ok, exp) == []
    read_bad = dict(read_ok)
    for s in strips:                                       # row 1 reads row 2
        read_bad[f"{s}1"] = read_ok[f"{s}2"]
    flags = locally_misaligned_groups(read_bad, exp)
    assert any("1" in f and "row" in f for f in flags), flags


def test_locally_misaligned_groups_needs_enough_structure(_app):
    from ui.dialogs.scanin_dialog import locally_misaligned_groups
    # Tiny pages (or unparsable ids) are never judged.
    assert locally_misaligned_groups({"P1": 1.0}, {"P1": 1.0}) == []


def test_locally_misaligned_groups_ignores_colour_family_response(_app):
    """Knut's Wolf Faust / LaserSoft false alarms: structured targets group
    colour FAMILIES into rows/columns, and a scanner's hue-dependent response
    displaces a whole family coherently — which mimics a shifted line in rank
    space. The confirmation gate only flags a line whose reads land ON a
    neighbouring line's expected values; a response-shifted family lands
    between lines and stays quiet, while a genuinely shifted line is still
    caught (validated on his actual IT8 reference: FP 0 %, detection 99 %+)."""
    import random
    from ui.dialogs.scanin_dialog import locally_misaligned_groups
    rng = random.Random(11)
    letters = "ABCDEFGHIJKL"                   # IT8-like: 12 rows × 22 columns,
    cols = range(1, 23)                        # lightness by row, hue by column
    exp = {f"{s_}{d}": 8 + 7 * i + 2.1 * d   # hue swings ACROSS row steps
           for i, s_ in enumerate(letters) for d in cols}
    # Aligned + per-family (per-column) response deviation → must stay quiet.
    fam = {d: rng.uniform(0.99, 1.01) for d in cols}   # deviation < line step
    read = {k: v * fam[int(k[1:])] * rng.uniform(0.998, 1.002)
            for k, v in exp.items()}
    assert locally_misaligned_groups(read, exp) == []
    # Row C genuinely reading row D → flagged.
    shifted = dict(read)
    for d in cols:
        shifted[f"C{d}"] = exp[f"D{d}"] * rng.uniform(0.998, 1.002)
    flags = locally_misaligned_groups(shifted, exp)
    assert any(f.endswith(" C") for f in flags), flags


# ---------------------------------------------------------------- placement
# score (Knut #108 round 12 — probe objective for the Check-alignment star)

def test_placement_score_clean_monotone_is_low():
    from ui.dialogs.scanin_dialog import placement_score
    # read = smooth monotone response of expected (a gamma curve): the score
    # sees ONE consistent response → residuals ≈ 0.
    exp = {f"P{i}": i / 99 * 100 for i in range(100)}
    read = {k: (v / 100) ** 2.2 * 90 + 3 for k, v in exp.items()}
    s = placement_score(read, exp)
    assert s is not None and s < 0.01


def test_placement_score_blends_raise_it():
    from ui.dialogs.scanin_dialog import placement_score
    import random
    rng = random.Random(7)
    order = list(range(100))
    rng.shuffle(order)                       # scrambled neighbours, like a chart
    exp = {f"P{i}": order[i] / 99 * 100 for i in range(100)}
    clean = {k: (v / 100) ** 2.2 * 90 + 3 for k, v in exp.items()}
    # 30 % contamination from the (spatially) next patch's colour
    keys = [f"P{i}" for i in range(100)]
    blended = {k: 0.7 * clean[k] + 0.3 * clean[keys[(i + 1) % 100]]
               for i, k in enumerate(keys)}
    s_clean = placement_score(clean, exp)
    s_blend = placement_score(blended, exp)
    assert s_blend > s_clean * 3            # sharply separable


def test_placement_score_needs_enough_patches():
    from ui.dialogs.scanin_dialog import placement_score
    exp = {f"P{i}": float(i) for i in range(10)}
    assert placement_score(exp, exp) is None


# ------------------------------------------------------------- dense ladder
# (Knut #108 round 12 — dense_placement_agreement)

def _dense_fixture(tmp_path, offset_frac=0.0):
    """Synthetic 12×8 chart image with scrambled patch colours + boxes."""
    import random
    from PIL import Image, ImageDraw
    rng = random.Random(3)
    ncols, nrows, cell, margin = 12, 8, 40, 60
    W = ncols * cell + 2 * margin
    H = nrows * cell + 2 * margin
    img = Image.new("L", (W, H), 230)
    d = ImageDraw.Draw(img)

    class Box:
        pass

    boxes, exp = [], {}
    vals = list(range(ncols * nrows))
    rng.shuffle(vals)
    for r in range(nrows):
        for c in range(ncols):
            v = int(vals[r * ncols + c] / (ncols * nrows - 1) * 235) + 10
            d.rectangle([margin + c * cell, margin + r * cell,
                         margin + (c + 1) * cell - 1,
                         margin + (r + 1) * cell - 1], fill=v)
            b = Box()
            b.x1, b.y1 = c * 10.0, r * 10.0
            b.x2, b.y2 = c * 10.0 + 10.0, r * 10.0 + 10.0
            b.name = f"P{r}_{c}"
            boxes.append(b)
            exp[b.name] = v
    from PIL import ImageFilter
    # σ1 matches real scans (Knut measured 3–4 px transitions at 300 dpi);
    # softer blur starves the gradient and no detector should be tuned to it
    img = img.filter(ImageFilter.GaussianBlur(1))
    path = tmp_path / "chart.png"
    img.save(path)
    dx = offset_frac * cell
    corners = [(margin + dx, margin), (W - margin + dx, margin),
               (W - margin + dx, H - margin), (margin + dx, H - margin)]
    return path, boxes, corners, exp


def test_dense_ladder_aligned_scores_high(tmp_path):
    from workflow.placement_probe import dense_placement_agreement
    path, boxes, corners, exp = _dense_fixture(tmp_path, 0.0)
    rep = dense_placement_agreement(path, boxes, corners, exp)
    assert rep is not None and rep.agreement_pct > 95.0


def test_dense_ladder_offset_flags_and_is_monotone(tmp_path):
    from workflow.placement_probe import dense_placement_agreement

    def agree(off):
        path, boxes, corners, exp = _dense_fixture(tmp_path, off)
        rep = dense_placement_agreement(path, boxes, corners, exp)
        assert rep is not None
        return rep
    a0, a25, a40 = agree(0.0), agree(0.25), agree(0.40)
    # Per-patch semantics (#119): at 25 % offset the 50 % sample box only
    # TOUCHES the border — each patch still reads clean, so the agreement
    # may stay high (the flank check is what covers a touch); once the box
    # CROSSES (40 %), the worst patch collapses well below the default
    # floor (85 %). The calibration to Knut's spec lives on his real scans.
    assert a0.agreement_pct >= a25.agreement_pct >= a40.agreement_pct
    assert a40.agreement_pct < 85.0
    assert a40.offenders                     # worst patches are named


def test_dense_ladder_uniformity_objective(tmp_path):
    from workflow.placement_probe import dense_placement_agreement
    path, boxes, corners, exp = _dense_fixture(tmp_path, 0.0)
    ok = dense_placement_agreement(path, boxes, corners, exp,
                                   objective="uniformity")
    path2, boxes2, corners2, exp2 = _dense_fixture(tmp_path, 0.35)
    off = dense_placement_agreement(path2, boxes2, corners2, exp2,
                                    objective="uniformity")
    assert ok is not None and off is not None
    assert ok.agreement_pct > 95.0 > off.agreement_pct


def test_flat_direction_is_ignored_not_floored(tmp_path):
    """Knut's #119 verification, deterministic: a patch whose surroundings in
    one direction never change colour finds no worst case there — that
    direction must be IGNORED and the roof taken from the directions that do
    find one, never collapsing onto the floor (which would zero the patch)."""
    import random
    from PIL import Image, ImageDraw, ImageFilter
    from workflow.placement_probe import dense_placement_agreement
    rng = random.Random(7)
    ncols, nrows, cell, margin = 8, 6, 40, 120
    W, H = ncols * cell + 2 * margin, nrows * cell + 2 * margin
    flat = 140                       # the rightmost column + right margin
    img = Image.new("L", (W, H), 230)
    d = ImageDraw.Draw(img)
    d.rectangle([margin + (ncols - 1) * cell, 0, W, H], fill=flat)

    class Box:
        pass

    boxes, exp = [], {}
    for r in range(nrows):
        for c in range(ncols):
            v = flat if c == ncols - 1 else rng.randrange(10, 220)
            d.rectangle([margin + c * cell, margin + r * cell,
                         margin + (c + 1) * cell - 1,
                         margin + (r + 1) * cell - 1], fill=v)
            b = Box()
            b.x1, b.y1 = c * 10.0, r * 10.0
            b.x2, b.y2 = c * 10.0 + 10.0, r * 10.0 + 10.0
            b.name = f"P{r}_{c}"
            boxes.append(b)
            exp[b.name] = v
    img = img.filter(ImageFilter.GaussianBlur(1))
    path = tmp_path / "flat.png"
    img.save(path)
    corners = [(margin, margin), (W - margin, margin),
               (W - margin, H - margin), (margin, H - margin)]
    rep = dense_placement_agreement(path, boxes, corners, exp,
                                    objective="uniformity")
    assert rep is not None
    # dirs order: (1,0) +x, (-1,0) -x, (0,1) +y, (0,-1) -y, diagonals…
    flat_boxes = [f"P{r}_{ncols - 1}" for r in range(1, nrows - 1)]
    ignored_px = [n for n in flat_boxes
                  if 0 in rep.ignored_dirs_by_patch.get(n, set())]
    assert ignored_px, "no rightmost patch ignored its flat +x direction"
    for n in flat_boxes:
        d0 = rep.roof_dir_by_patch.get(n)
        if d0 is not None:
            assert d0 not in rep.ignored_dirs_by_patch.get(n, set())
        # the flat direction must not have zeroed the patch
        assert rep.per_patch[n] > 50.0, (
            f"{n} scored {rep.per_patch[n]:.1f} % on an aligned grid")


def test_flank_detection_fires_on_edges_only(tmp_path):
    from workflow.placement_probe import dense_placement_agreement
    path, boxes, corners, exp = _dense_fixture(tmp_path, 0.0)
    rep = dense_placement_agreement(path, boxes, corners, exp)
    aligned_hits = [n for n, v in rep.flank_by_patch.items() if v > 0.16]
    # 0.25 of a cell: the sample box's edge has just crossed the border —
    # the regime the detector must catch (deeper offsets are caught by the
    # placement-agreement floor long before the edge rule matters)
    path2, boxes2, corners2, exp2 = _dense_fixture(tmp_path, 0.25)
    rep2 = dense_placement_agreement(path2, boxes2, corners2, exp2)
    crossing_hits = [n for n, v in rep2.flank_by_patch.items() if v > 0.16]
    # default scanner_flank_min_boxes = 3 (#119)
    assert len(aligned_hits) < 3
    assert len(crossing_hits) >= 3        # boxes on edges are named


def test_flank_activation_reach_caps_on_aligned_contiguous_grid(tmp_path):
    """#119 (Knut's activation-box design): the edge check's active sensing
    follows the sample box's rim, but never past the sensing grid's own
    85 % equal-margin boundary, and never into the page's measured border
    blur — on a zero-gap chart the borders' blur tails would otherwise read
    "edge" on a PERFECTLY aligned grid at a large sample area. So raising
    the sample area must never raise the edge count on an aligned grid, and
    the aligned grid stays below the warning threshold throughout."""
    from workflow.placement_probe import dense_placement_agreement

    path, boxes, corners, exp = _dense_fixture(tmp_path, 0.0)

    def hits(frac):
        rep = dense_placement_agreement(path, boxes, corners, exp,
                                        sample_frac=frac)
        return sum(1 for v in rep.flank_by_patch.values() if v > 0.20)

    counts = [hits(f) for f in (0.4, 0.6, 0.7, 0.8, 0.9)]
    assert max(counts) <= min(counts[0], 2), (
        f"aligned contiguous grid edge counts rose with sample area: {counts}")


def test_pulled_corner_is_detected(tmp_path):
    """Knut's #119 case: only ONE corner of the reading grid is dragged
    inwards, until a few patches in that corner have their sample-box edge on
    top of a patch edge. The rest of the page stays perfectly placed, so the
    page-wide ladder barely moves — the edge detector has to catch it, and
    with the shipped default of 3 boxes it must."""
    from workflow.placement_probe import dense_placement_agreement
    path, boxes, corners, exp = _dense_fixture(tmp_path, 0.0)

    base = dense_placement_agreement(path, boxes, corners, exp)
    aligned = [n for n, v in base.flank_by_patch.items() if v > 0.20]
    assert len(aligned) < 3, f"aligned grid already flags {aligned}"

    # cell = 40 px, sample box = 50 % of it, so a box rim reaches its border
    # at 25 % = 10 px. Drag the top-left corner exactly that far in both axes:
    # the handful of patches beside it now have box edge on patch edge, the
    # opposite corner is untouched.
    pulled = [(corners[0][0] + 10, corners[0][1] + 10)] + list(corners[1:])
    rep = dense_placement_agreement(path, boxes, pulled, exp)
    on_edge = [n for n, v in rep.flank_by_patch.items() if v > 0.20]
    assert len(on_edge) >= 3, (
        f"pulled corner left only {len(on_edge)} edge-carrying boxes "
        f"({on_edge})")

    # The point of the whole feature: the ladder cannot see this — the page is
    # correctly placed everywhere except one corner, so its agreement stays at
    # the ceiling and the placement floor never fires. Only the edge detector
    # catches it. (The 7-box rule shipped before #119 left this page silent;
    # the rim-following sensor now flags the pulled corner even more
    # decisively, so only the essential contract is asserted.)
    assert rep.agreement_pct > 99.0


def test_flank_min_boxes_setting_gates_the_warning():
    """OFF disables edge detection; N requires N boxes over the limit."""
    from ui.dialogs.scanin_dialog import ScannerProfileDialog

    class _Rep:
        flank_by_patch = {"A1": 0.9, "A2": 0.8, "A3": 0.7, "A4": 0.1}

    class _S(dict):
        def get(self, k, d=None):          # AppSettings-like
            return dict.get(self, k, d)

    def offenders(min_boxes, limit=0.20):
        dlg = ScannerProfileDialog.__new__(ScannerProfileDialog)
        dlg._settings = _S({"scanner_flank_min_boxes": min_boxes,
                            "scanner_flank_limit": limit})
        return ScannerProfileDialog._flank_offenders(dlg, _Rep())

    assert offenders(0) == []                    # Off
    assert len(offenders(1)) == 3
    assert len(offenders(3)) == 3                # exactly at the threshold
    assert offenders(4) == []                    # one short → silent


def test_report_carries_average_alongside_worst(tmp_path):
    """Knut (#119): the verdict is the worst-patch score; the page average is
    shown next to it on the same ladder scale. An aligned grid averages at
    least as well as its worst patch."""
    from workflow.placement_probe import dense_placement_agreement
    path, boxes, corners, exp = _dense_fixture(tmp_path, 0.0)
    rep = dense_placement_agreement(path, boxes, corners, exp)
    assert rep is not None
    assert 0.0 <= rep.average_pct <= 100.0
    assert rep.average_pct >= rep.agreement_pct - 1e-9


def test_clean_nearby_ring_tracks_step_frac(tmp_path):
    """The clean-nearby ring is a physical 20 % of the pitch. Before #119 it
    was hard-coded to ladder rung 2, so a 24x5 % ladder silently probed at
    ±10 % and a 60x2 % one at ±4 %. Same geometry ⇒ same flank verdicts,
    whatever the rung size."""
    from workflow.placement_probe import dense_placement_agreement
    path, boxes, corners, exp = _dense_fixture(tmp_path, 0.25)

    def hits(steps, step_frac):
        rep = dense_placement_agreement(path, boxes, corners, exp,
                                        steps=steps, step_frac=step_frac)
        return {n for n, v in rep.flank_by_patch.items() if v > 0.16}

    coarse, fine = hits(12, 0.10), hits(24, 0.05)
    # the ring lands on the same physical offset, so the same boxes are named
    assert coarse and fine
    overlap = len(coarse & fine) / len(coarse | fine)
    assert overlap > 0.8, f"ring moved with the rung size (overlap {overlap:.2f})"


def test_migrate_frees_users_pinned_to_the_old_flank_limit(tmp_path):
    """#119: Settings → Save writes every key, so anyone who had ever opened
    Settings had scanner_flank_limit=0.30 persisted. Combined with the new
    3-box count that STILL misses a pulled corner, so the stored echo of the
    old default has to be dropped once — but a value the user chose on purpose
    must survive."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings, SETTINGS_SCHEMA

    def _fresh(stored=None):
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / f"m{stored}.ini"),
                          QSettings.Format.IniFormat)
        s._qs.clear()
        if stored is not None:
            s._qs.setValue("scanner_flank_limit", stored)
        return s

    s = _fresh(0.30)                       # the old default, echoed
    assert s.migrate() == ["scanner_flank_limit"]
    assert float(s.get("scanner_flank_limit")) == 0.20
    assert int(s.get("settings_schema")) == SETTINGS_SCHEMA
    assert s.migrate() == []               # idempotent — runs once

    s = _fresh(0.42)                       # a deliberate choice
    assert s.migrate() == []
    assert float(s.get("scanner_flank_limit")) == 0.42

    s = _fresh(None)                       # never saved
    assert s.migrate() == []
    assert float(s.get("scanner_flank_limit")) == 0.20


def test_migrate_schema2_moves_beta3_defaults(tmp_path):
    """#119, Knut's beta.3 test: min-cells 3 lets a grey streak flag an
    aligned grid (6 is the new default) and the agreement floor moves to
    0.87 — stored echoes of the old defaults must fall through, deliberate
    choices must survive."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings

    def _fresh(name, **stored):
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / f"{name}.ini"),
                          QSettings.Format.IniFormat)
        s._qs.clear()
        for k, v in stored.items():
            s._qs.setValue(k, v)
        return s

    s = _fresh("echo", scanner_flank_min_cells=3, scanner_check_agreement=0.87)
    assert sorted(s.migrate()) == ["scanner_check_agreement",
                                   "scanner_flank_min_cells"]
    assert int(s.get("scanner_flank_min_cells")) == 8
    # schema 5 (Knut's GA number): the agreement floor settles at 0.85 —
    # stored echoes of EITHER shipped default (0.85 pre-schema-2, 0.87
    # since) fall through to it.
    assert float(s.get("scanner_check_agreement")) == 0.85

    s = _fresh("chosen", scanner_flank_min_cells=5, scanner_check_agreement=0.9)
    assert s.migrate() == []
    assert int(s.get("scanner_flank_min_cells")) == 5
    assert float(s.get("scanner_check_agreement")) == 0.9

    # schema 3: min-boxes default 3 → 2 (Knut's beta.4 preference)
    s = _fresh("boxes_echo", scanner_flank_min_boxes=3)
    assert s.migrate() == ["scanner_flank_min_boxes"]
    assert int(s.get("scanner_flank_min_boxes")) == 2
    s = _fresh("boxes_chosen", scanner_flank_min_boxes=5)
    assert s.migrate() == []
    assert int(s.get("scanner_flank_min_boxes")) == 5

    # schema 4 (Knut's beta.9 round): min-cells default 6 → 8 — BOTH old
    # defaults (3 from the original ship, 6 from schema 2) must fall
    # through, because a user may have last pressed Save under either.
    s = _fresh("cells_echo6", scanner_flank_min_cells=6)
    assert s.migrate() == ["scanner_flank_min_cells"]
    assert int(s.get("scanner_flank_min_cells")) == 8
    s = _fresh("cells_chosen", scanner_flank_min_cells=12)
    assert s.migrate() == []
    assert int(s.get("scanner_flank_min_cells")) == 12


def test_migrate_makes_the_layout_engine_the_manual_default(tmp_path):
    """schema 18 (Knut, 2026-08-13): the ChromIQ layout engine is the Manual
    default now. A stored echo of the old False — native bool or the INI
    string spelling — is dropped once; an explicit True (or anything the
    user re-chooses later) survives; never-saved resolves to the new True."""
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings

    def _fresh(tag, stored=None):
        s = AppSettings()
        s._qs = QSettings(str(tmp_path / f"eng-{tag}.ini"),
                          QSettings.Format.IniFormat)
        s._qs.clear()
        if stored is not None:
            s._qs.setValue("use_chromiq_layout_engine", stored)
        return s

    s = _fresh("echo", False)              # the old default, echoed by Save
    assert "use_chromiq_layout_engine (ChromIQ layout engine " \
           "now the Manual default)" in s.migrate()
    assert bool(s.get("use_chromiq_layout_engine")) is True
    assert s.migrate() == []               # idempotent

    s = _fresh("str-echo", "false")        # the INI backend's spelling
    assert any("use_chromiq_layout_engine" in d for d in s.migrate())
    assert bool(s.get("use_chromiq_layout_engine")) is True

    s = _fresh("chosen", True)             # already on — untouched
    assert not any("use_chromiq_layout_engine" in d for d in s.migrate())
    assert bool(s.get("use_chromiq_layout_engine")) is True

    s = _fresh("never", None)              # never saved → new default
    assert not any("use_chromiq_layout_engine" in d for d in s.migrate())
    assert bool(s.get("use_chromiq_layout_engine")) is True
