"""The marquee's coordinate maths: unit-square→quad homography and the grid
normalisation from engine geometry (#98). Pure — no real scan needed."""
import numpy as np

from ui.scan_grid_marquee import GridSpec, apply_h, unit_quad_homography


def test_homography_axis_aligned_rect():
    # Quad = a plain rectangle → the homography is a simple affine scale/offset.
    quad = [(10, 20), (110, 20), (110, 220), (10, 220)]   # TL, TR, BR, BL
    h = unit_quad_homography(quad)
    for (u, v), corner in zip([(0, 0), (1, 0), (1, 1), (0, 1)], quad):
        x, y = apply_h(h, u, v)
        assert abs(x - corner[0]) < 1e-6 and abs(y - corner[1]) < 1e-6
    cx, cy = apply_h(h, 0.5, 0.5)                # centre
    assert abs(cx - 60) < 1e-6 and abs(cy - 120) < 1e-6


def test_homography_perspective_quad_maps_corners_exactly():
    quad = [(30, 12), (210, 40), (198, 300), (8, 262)]    # skewed (perspective)
    h = unit_quad_homography(quad)
    for (u, v), corner in zip([(0, 0), (1, 0), (1, 1), (0, 1)], quad):
        x, y = apply_h(h, u, v)
        assert abs(x - corner[0]) < 1e-6 and abs(y - corner[1]) < 1e-6


def test_grid_from_patches_normalises_to_unit_square():
    # Two patches spanning x∈[0,300], y∈[0,220] (top-left px, already flipped).
    patches = [{"x": 0, "y": 0, "w": 100, "h": 100},
               {"x": 200, "y": 120, "w": 100, "h": 100}]
    g = GridSpec.from_patches(patches)
    assert len(g.rects) == 2
    u0, v0, w0, h0 = g.rects[0]
    assert (u0, v0) == (0.0, 0.0)
    assert abs(w0 - 100 / 300) < 1e-9 and abs(h0 - 100 / 220) < 1e-9
    # last patch's far corner touches (1,1)
    u1, v1, w1, h1 = g.rects[1]
    assert abs((u1 + w1) - 1.0) < 1e-9 and abs((v1 + h1) - 1.0) < 1e-9


def test_grid_empty_is_safe():
    assert GridSpec.from_patches([]).rects == []


def test_ink_rect_extends_one_spacer_beyond_the_patches():
    """#119 (Knut): an engine chart prints spacer strips above the first and
    below the last patch row, so the visible ink block is bigger than the
    patch grid the corners belong on. The ink guide is derived from the patch
    gaps themselves — any spacer size works, and a gap-less chart gets none."""
    # 2×3 grid, 100×100 patches, 10 px row spacers, columns touching.
    patches = [{"x": c * 100, "y": r * 110, "w": 100, "h": 100}
               for r in range(3) for c in range(2)]
    g = GridSpec.from_patches(patches)
    assert g.ink_rect is not None
    u0, v0, u1, v1 = g.ink_rect
    assert u0 == 0.0 and u1 == 1.0            # columns touch → no x extension
    assert abs(v0 + 10 / 320) < 1e-9          # one spacer above…
    assert abs(v1 - (1 + 10 / 320)) < 1e-9    # …and below
    # no gaps at all → no guide
    tight = [{"x": c * 100, "y": r * 100, "w": 100, "h": 100}
             for r in range(3) for c in range(2)]
    assert GridSpec.from_patches(tight).ink_rect is None


def test_grid_is_derived_from_cht_boxes_for_every_bundled_target(qapp):
    """Knut's demand (#108): the selection grid must be built dynamically from
    the .cht box data — every bundled standard target's on-screen rects must
    match its parsed .cht boxes one for one (position, width, height), with no
    hard-wired shapes anywhere."""
    from pathlib import Path
    from core.resource_path import resource_path
    from ui.scan_grid_marquee import GridSpec
    from workflow.cht_parser import parse_cht

    cht_dir = resource_path("data/scanner_targets")
    chts = sorted(Path(cht_dir).glob("*.cht"))
    assert len(chts) >= 8, f"expected the bundled targets, found {len(chts)}"
    for f in chts:
        text = f.read_text(errors="ignore", encoding="utf-8")
        geom = parse_cht(text)
        g = GridSpec.from_cht(text)
        assert len(g.rects) == len(geom.patches), f.name
        xs = [b.x1 for b in geom.patches] + [b.x2 for b in geom.patches]
        ys = [b.y1 for b in geom.patches] + [b.y2 for b in geom.patches]
        x0, y0 = min(xs), min(ys)
        sw, sh = (max(xs) - x0) or 1.0, (max(ys) - y0) or 1.0
        for rect, box in zip(g.rects, geom.patches):
            assert abs(rect[0] - (box.x1 - x0) / sw) < 1e-9, f.name
            assert abs(rect[1] - (box.y1 - y0) / sh) < 1e-9, f.name
            assert abs(rect[2] - (box.x2 - box.x1) / sw) < 1e-9, f.name
            assert abs(rect[3] - (box.y2 - box.y1) / sh) < 1e-9, f.name
