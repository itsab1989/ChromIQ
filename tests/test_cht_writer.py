"""The engine can emit an ArgyllCMS .cht recognition template from its exact
geometry (#93, Knut)."""
import random

from workflow.layout_engine import cht_writer, chart as le_chart
import workflow.ti2_relayout as R


def test_build_cht_text_structure():
    boxes = [
        {"loc": "A1", "x": 10.0, "y": 200.0, "w": 8.0, "h": 8.0},
        {"loc": "A2", "x": 10.0, "y": 190.0, "w": 8.0, "h": 8.0},
        {"loc": "B1", "x": 18.0, "y": 200.0, "w": 8.0, "h": 8.0},
    ]
    expected = [("A1", 95.0, 100.0, 108.0), ("A2", 0.0, 0.0, 0.0),
                ("B1", 41.0, 21.0, 1.9)]
    txt = cht_writer.build_cht_text(boxes, expected)
    # 3 patch boxes → BOXES 3. The F line is emitted but NOT counted: scanin
    # skips the fiducial line without counting it, and an over-count makes it
    # abort with "More BOXes than declared" (verified against a real scanin read).
    assert "BOXES 3" in txt
    assert sum(1 for l in txt.splitlines() if l.strip().startswith("F ")) == 1
    assert "  X A1 A1 _ _ 8.000000 8.000000 10.000000 200.000000 0 0" in txt
    assert "BOX_SHRINK" in txt and "REF_ROTATION 0.0" in txt
    # fiducial line: patch-area corners TL,TR,BR,BL over x∈[10,26], y∈[190,208]
    # in the y-DOWN image convention (#108 round 5) — TL is the ymin corner.
    assert ("  F _ _ 10.000000 190.000000 26.000000 190.000000 "
            "26.000000 208.000000 10.000000 208.000000") in txt
    # count is unchanged without fiducials (F was never counted); the F line goes.
    no_f = cht_writer.build_cht_text(boxes, expected, emit_fiducials=False)
    assert "BOXES 3" in no_f
    assert not any(l.strip().startswith("F ") for l in no_f.splitlines())
    assert "EXPECTED XYZ 3" in txt
    assert "  A1 95.000000 100.000000 108.000000" in txt
    # XLIST: vertical edges at x = 10, 18, 26 → 3 unique positions
    assert [l for l in txt.splitlines() if l.startswith("XLIST")][0] == "XLIST 3"
    # YLIST: horizontal edges at y = 190, 198, 200, 208 → 4 unique
    assert [l for l in txt.splitlines() if l.startswith("YLIST")][0] == "YLIST 4"


def test_boxes_from_patch_rects_keeps_ydown_origin():
    """#108 round 5: the cht stays in the image's own top-left/y-down
    convention — no origin flip. A y-up file read correctly (the -F mapping
    absorbs any affine) but the reflection it forced made scanin's diagnostic
    render every label glyph mirrored."""
    rects = [{"page": 0, "slot": 0, "loc": "A1", "x": 0, "y": 0, "w": 100, "h": 100},
             {"page": 1, "slot": 1, "loc": "A1", "x": 0, "y": 0, "w": 100, "h": 100}]
    boxes = cht_writer.boxes_from_patch_rects(rects, 297.0, 100, page=0)  # 1px=0.254mm
    assert len(boxes) == 1                       # only page 0
    b = boxes[0]
    assert abs(b["w"] - 25.4) < 1e-6 and abs(b["h"] - 25.4) < 1e-6
    assert abs(b["x"] - 0.0) < 1e-6
    assert abs(b["y"] - 0.0) < 1e-6              # top-left px → top-left mm


def test_build_chart_emits_cht(tmp_path):
    random.seed(3)
    prog = [(random.random() * 100, random.random() * 100, random.random() * 100)
            for _ in range(90)]
    R.write_ti1(R.ChartSpec.new("i1", "A4"), prog, tmp_path / "s.ti1")
    res = le_chart.build_chart(str(tmp_path / "s.ti1"), tmp_path / "chart",
                               instrument="i1", paper="A4", dpi=120,
                               randomize=False, emit_cht=True)
    assert res.cht_paths and res.cht_paths[0].is_file()
    txt = res.cht_paths[0].read_text(encoding="utf-8")
    # one X box and one EXPECTED row per printed patch slot (incl. grid padding)
    n_slots = res.layout.total_patches
    assert n_slots >= 90
    n_x = sum(1 for l in txt.splitlines() if l.strip().startswith("X "))
    n_exp = int([l for l in txt.splitlines() if l.startswith("EXPECTED")][0].split()[-1])
    assert n_x == n_exp == n_slots
    # one fiducial (F) line is prepended, but scanin does NOT count it in BOXES
    assert sum(1 for l in txt.splitlines() if l.strip().startswith("F ")) == 1
    assert f"BOXES {n_slots}" in txt

    # Boxes must sit inside the paper (bottom-left origin, A4 = 210×297).
    for line in (l for l in txt.splitlines() if l.strip().startswith("X ")):
        _, _, _, _, _, w, h, x, y, _, _ = line.split()
        assert 0 <= float(x) <= 210 and 0 <= float(y) <= 297


def test_cht_boxes_track_colormunki_offset_stagger(tmp_path):
    """#35 (Knut): a ColorMunki 'offset every second strip' chart must produce a
    .cht whose boxes follow the vertical stagger — so the scanner selection grid
    fits the printed patches exactly. Verified against the rendered TIFF: every
    box centre lands on a coloured (non-white) patch, and adjacent strips are
    y-offset (the boxes are staggered, not a flat regular grid)."""
    import numpy as np
    from PIL import Image
    random.seed(9)
    prog = [(random.random() * 100, random.random() * 100, random.random() * 100)
            for _ in range(240)]
    R.write_ti1(R.ChartSpec.new("CM", "A4"), prog, tmp_path / "s.ti1")
    res = le_chart.build_chart(
        str(tmp_path / "s.ti1"), tmp_path / "chart",
        instrument="CM", paper="A4", dpi=150, randomize=False,
        cm_stagger=True, layout_mode="patch_first")

    from workflow.layout_engine import geometry, instruments, papers
    kw = {"instrument": "CM", "paper": "A4", "cm_stagger": True,
          "layout_mode": "patch_first",
          "area_target_count": res.layout.total_patches}
    geom = instruments.geom_from_build_kwargs(kw)
    w_mm, h_mm = papers.dimensions_mm("A4")
    rects = geometry.patch_rects_px(geom, w_mm, h_mm, res.layout, 150)
    page0 = [r for r in rects if r["page"] == 0]

    # Adjacent strips (columns) start at different y — the stagger.
    from collections import defaultdict
    first_y_by_col = {}
    for r in page0:
        first_y_by_col.setdefault(r["x"], r["y"])
        first_y_by_col[r["x"]] = min(first_y_by_col[r["x"]], r["y"])
    assert len(set(first_y_by_col.values())) > 1, "strips are not staggered"

    boxes = cht_writer.boxes_from_patch_rects(page0, h_mm, 150, page=0)
    img = np.asarray(Image.open(res.tiff_paths[0]).convert("RGB"))
    H, W, _ = img.shape
    s = 150 / 25.4
    misses = 0
    for b in boxes:
        cx = int((b["x"] + b["w"] / 2) * s)
        cy = int((b["y"] + b["h"] / 2) * s)
        if not (0 <= cy < H and 0 <= cx < W and bool(np.any(img[cy, cx] < 235))):
            misses += 1
    assert misses == 0, f"{misses} CHT boxes missed their patch"
