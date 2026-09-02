"""Hardware-free registration test with self-made targets.

We generate scanner targets of our own — in ChromIQ's ``.cht`` format, across a
range of layouts — render each with KNOWN per-patch colours, run the real
ArgyllCMS ``scanin -F`` (the manual marquee path), and assert every patch is read
back from the right place. Because we control both the geometry and the image,
they are exactly consistent, so any mismatch is a genuine registration bug.

This is what caught the ``cht_writer`` ``BOXES`` off-by-one (it counted the F
line; ``scanin`` doesn't, and aborts with "More BOXes than declared"): the count
here matches ``cht_writer``'s corrected convention (patches only, F not counted).

Skipped unless ArgyllCMS ``scanin`` and Pillow are available.
"""
from __future__ import annotations

import subprocess

import pytest

from tests.argyll_env import argyll_tool  # noqa: E402
_SCANIN = argyll_tool("scanin")
PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

pytestmark = pytest.mark.skipif(
    _SCANIN is None, reason="ArgyllCMS scanin not present")

_MARGIN = 60


def _grid(rows, cols, box=40, pitch=52, ox=20, oy=20, prefix=""):
    return [{"loc": f"{prefix}{chr(65 + r)}{c + 1:02d}",
             "x": ox + c * pitch, "y": oy + r * pitch, "w": box, "h": box}
            for r in range(rows) for c in range(cols)]


def _cht(patches):
    xs = [p["x"] for p in patches] + [p["x"] + p["w"] for p in patches]
    ys = [p["y"] for p in patches] + [p["y"] + p["h"] for p in patches]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    # BOXES counts the patch (X) boxes only — the F line is NOT counted.
    o = ["", "", f"BOXES {len(patches)}",
         f"  F _ _ {minx} {miny} {maxx} {miny} {maxx} {maxy} {minx} {maxy}"]
    for p in patches:
        o.append(f"  X {p['loc']} {p['loc']} _ _ {p['w']} {p['h']} {p['x']} {p['y']} 0 0")
    smin = min(min(p["w"], p["h"]) for p in patches)
    o += ["", f"BOX_SHRINK {smin * 0.15:.3f}", "", "REF_ROTATION 0.0", ""]
    xe = sorted({p["x"] for p in patches} | {p["x"] + p["w"] for p in patches})
    ye = sorted({p["y"] for p in patches} | {p["y"] + p["h"] for p in patches})
    o.append(f"XLIST {len(xe)}"); o += [f"  {x:.1f} {maxy - miny:.1f} 1.0" for x in xe]
    o.append("")
    o.append(f"YLIST {len(ye)}"); o += [f"  {y:.1f} {maxx - minx:.1f} 1.0" for y in ye]
    o += ["", "", f"EXPECTED XYZ {len(patches)}"]
    o += [f"  {p['loc']} 20 20 20" for p in patches]
    o.append("")
    return "\n".join(o), (minx, miny, maxx, maxy)


def _cie(patches):
    return "\n".join(
        ['CGATS.17', 'NUMBER_OF_FIELDS 4', 'BEGIN_DATA_FORMAT',
         'SAMPLE_ID XYZ_X XYZ_Y XYZ_Z', 'END_DATA_FORMAT',
         f'NUMBER_OF_SETS {len(patches)}', 'BEGIN_DATA']
        + [f'{p["loc"]} 20 20 20' for p in patches] + ['END_DATA', ''])


def _rgb(i):
    return (30 + (i * 37) % 200, 30 + (i * 91) % 200, 30 + (i * 53) % 200)


def _worst_read_error(patches, tmp_path):
    cht, (minx, miny, maxx, maxy) = _cht(patches)
    off = (_MARGIN - minx, _MARGIN - miny)
    img = Image.new("RGB", (int(maxx + off[0] + _MARGIN),
                            int(maxy + off[1] + _MARGIN)), "white")
    px = img.load(); rgb_by = {}
    for i, p in enumerate(patches):
        col = _rgb(i); rgb_by[p["loc"]] = col
        for yy in range(int(p["y"] + off[1]), int(p["y"] + off[1] + p["h"])):
            for xx in range(int(p["x"] + off[0]), int(p["x"] + off[0] + p["w"])):
                px[xx, yy] = col
    fids = [(minx + off[0], miny + off[1]), (maxx + off[0], miny + off[1]),
            (maxx + off[0], maxy + off[1]), (minx + off[0], maxy + off[1])]
    fstr = ",".join(f"{v:.1f}" for xy in fids for v in xy)
    img.save(tmp_path / "s.tif")
    (tmp_path / "r.cht").write_text(cht)
    (tmp_path / "ref.cie").write_text(_cie(patches))
    r = subprocess.run([_SCANIN, "-v", "-p", "-F", fstr,
                        "s.tif", "r.cht", "ref.cie"],
                       cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    ti3 = tmp_path / "s.ti3"
    assert ti3.is_file(), f"scanin produced no .ti3:\n{r.stderr[-400:]}"
    lines = ti3.read_text().splitlines()
    fb = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA_FORMAT")
    fields = lines[fb + 1].split()
    li = fields.index("SAMPLE_ID"); ri = [fields.index(f"RGB_{c}") for c in "RGB"]
    db = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    de = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    worst = 0.0
    for l in lines[db + 1:de]:
        t = l.split()
        if len(t) != len(fields):
            continue
        want = [v / 255 * 100 for v in rgb_by[t[li].strip('"')]]
        read = [float(t[k]) for k in ri]
        worst = max(worst, max(abs(a - b) for a, b in zip(read, want)))
    return worst


def _worst_from_cht(cht_text, tmp_path):
    """Render a target from its OWN parsed .cht geometry, then scanin -F against
    that .cht (self-consistency). A consistent .cht reads back exactly; an
    inconsistent one (boxes not where the fiducials say) misregisters. Naming-
    independent: each patch is a unique solid colour, so a good read matches some
    rendered colour exactly and a blend/background read matches none."""
    from workflow.cht_parser import parse_cht
    g = parse_cht(cht_text)
    boxes = g.patches
    xs = [b.x1 for b in boxes] + [b.x2 for b in boxes] + [f[0] for f in g.fiducials]
    ys = [b.y1 for b in boxes] + [b.y2 for b in boxes] + [f[1] for f in g.fiducials]
    off = (_MARGIN - min(xs), _MARGIN - min(ys))
    W = int(max(xs) + off[0] + _MARGIN); H = int(max(ys) + off[1] + _MARGIN)
    img = Image.new("RGB", (W, H), "white"); px = img.load(); rendered = []
    for i, b in enumerate(boxes):
        col = (30 + (i * 37) % 200, 30 + (i * 91) % 200, 30 + (i * 53) % 200)
        rendered.append([v / 255 * 100 for v in col])
        s = g.box_shrink
        for yy in range(int(b.y1 + s + off[1]), int(b.y2 - s + off[1])):
            for xx in range(int(b.x1 + s + off[0]), int(b.x2 - s + off[0])):
                if 0 <= xx < W and 0 <= yy < H:
                    px[xx, yy] = col
    fids = [(f[0] + off[0], f[1] + off[1]) for f in g.fiducials]
    fstr = ",".join(f"{v:.1f}" for xy in fids for v in xy)
    img.save(tmp_path / "s.tif")
    (tmp_path / "r.cht").write_text(cht_text)
    cie = (["CGATS.17", "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
            f"NUMBER_OF_SETS {len(boxes)}", "BEGIN_DATA"]
           + [f"{b.name} 20 20 20" for b in boxes] + ["END_DATA", ""])
    (tmp_path / "ref.cie").write_text("\n".join(cie))
    r = subprocess.run([_SCANIN, "-v", "-p", "-F", fstr,
                        "s.tif", "r.cht", "ref.cie"], cwd=tmp_path,
                       capture_output=True, text=True, encoding="utf-8")
    assert (tmp_path / "s.ti3").is_file(), \
        f"scanin -F produced no .ti3:\n{r.stderr[-400:]}"
    lines = (tmp_path / "s.ti3").read_text().splitlines()
    fb = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA_FORMAT")
    fields = lines[fb + 1].split(); ri = [fields.index(f"RGB_{c}") for c in "RGB"]
    db = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    de = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    worst = 0.0
    for l in lines[db + 1:de]:
        t = l.split()
        if len(t) != len(fields):
            continue
        read = [float(t[k]) for k in ri]
        worst = max(worst, min(max(abs(a - b) for a, b in zip(read, r_))
                               for r_ in rendered))
    return worst


from tests.argyll_env import argyll_ref_dir  # noqa: E402
_REF = argyll_ref_dir()


@pytest.mark.skipif(_REF is None, reason="Argyll ref/ not present")
@pytest.mark.parametrize("name", [
    "QPcard_202", "SpyderChecker", "SpyderChecker24", "CMP_Digital_Target-4"])
def test_argyll_ref_target_is_self_consistent(name, tmp_path):
    """The targets ChromIQ falls back to Argyll's ref/ for (Knut's rectarg copies
    were broken) register perfectly from their own geometry."""
    cht = _REF / f"{name}.cht"
    if not cht.is_file():
        pytest.skip(f"{name} not in ref/")
    worst = _worst_from_cht(cht.read_text(errors="ignore"), tmp_path)
    assert worst < 6.0, f"{name}: Argyll ref/ geometry misregisters ({worst:.1f})"


def test_engine_cht_reads_correct_labels_through_rewrite(tmp_path):
    """#108 round 4 (Knut): the dialog's patch-bbox F rewrite used a fixed
    corner order that vertically mirrored engine charts — every box still
    landed ON a patch, so the registration-only checks passed while every
    strip's labels were reversed. This is the label-AWARE end-to-end guard:
    render an engine-style chart, push its .cht (round 5: now written in
    Argyll's y-down image convention) through the dialog's rewrite, scanin
    -F it, and require every patch to read its OWN colour."""
    from workflow.layout_engine.cht_writer import boxes_from_patch_rects, build_cht_text
    from workflow.scanin_runner import cht_with_patchbox_fiducials
    dpi, paper_h_mm = 100, 120.0
    s = dpi / 25.4
    rects, colors = [], {}
    for c in range(4):                      # 4 strips × 5 patches, top-left px
        for r in range(5):
            loc = f"{chr(65 + c)}{r + 1}"
            rects.append({"loc": loc, "page": 0, "x": 40 + c * 90,
                          "y": 40 + r * 70, "w": 70, "h": 50})
            colors[loc] = (25 + c * 55, 25 + r * 45, 200 - c * 40)
    W, H = int(160 * s), int(paper_h_mm * s)
    img = Image.new("RGB", (int(420 * dpi / 100), int(paper_h_mm * s)), "white")
    px = img.load()
    for r in rects:
        for yy in range(r["y"], r["y"] + r["h"]):
            for xx in range(r["x"], r["x"] + r["w"]):
                px[xx, yy] = colors[r["loc"]]
    img.save(tmp_path / "s.tif")
    boxes = boxes_from_patch_rects(rects, paper_h_mm, dpi)
    cht = build_cht_text(boxes, [(b["loc"], 20.0, 20.0, 20.0) for b in boxes])
    rewritten = cht_with_patchbox_fiducials(cht)     # what scanin actually gets
    (tmp_path / "r.cht").write_text(rewritten)
    (tmp_path / "ref.cie").write_text("\n".join(
        ["CGATS.17", "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
         "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
         f"NUMBER_OF_SETS {len(boxes)}", "BEGIN_DATA"]
        + [f"{b['loc']} 20 20 20" for b in boxes] + ["END_DATA", ""]))
    # Marquee corners: patch-area bbox, image px, TL TR BR BL.
    x0 = min(r["x"] for r in rects); x1 = max(r["x"] + r["w"] for r in rects)
    y0 = min(r["y"] for r in rects); y1 = max(r["y"] + r["h"] for r in rects)
    fstr = f"{x0},{y0},{x1},{y0},{x1},{y1},{x0},{y1}"
    r = subprocess.run([_SCANIN, "-v", "-p", "-F", fstr,
                        "s.tif", "r.cht", "ref.cie"], cwd=tmp_path,
                       capture_output=True, text=True, encoding="utf-8")
    assert (tmp_path / "s.ti3").is_file(), \
        f"scanin -F produced no .ti3:\n{r.stderr[-400:]}"
    lines = (tmp_path / "s.ti3").read_text().splitlines()
    fb = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA_FORMAT")
    fields = lines[fb + 1].split()
    ri = [fields.index(f"RGB_{c}") for c in "RGB"]
    li = fields.index("SAMPLE_ID")
    db = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    de = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    import re as _re
    checked = 0
    for l in lines[db + 1:de]:
        t = l.split()
        if len(t) != len(fields):
            continue
        sid = t[li].strip('"')
        m = _re.match(r"([A-Za-z]+)0*(\d+)$", sid)
        want = [v / 255 * 100 for v in colors[m.group(1) + m.group(2)]]
        read = [float(t[k]) for k in ri]
        err = max(abs(a - b) for a, b in zip(read, want))
        assert err < 3.0, f"{sid} read another patch's colour (err {err:.1f})"
        checked += 1
    assert checked == len(rects)


@pytest.mark.parametrize("name, patches", [
    ("6x7 grid",        _grid(6, 7)),
    ("10x10 grid",      _grid(10, 10, box=30, pitch=40)),
    ("2x24 wide strip", _grid(2, 24, box=30, pitch=40)),
    ("tight pitch",     _grid(8, 8, box=50, pitch=50)),
    ("big gaps",        _grid(5, 5, box=30, pitch=90)),
    ("two areas",       _grid(6, 8, box=40, pitch=52)
                        + _grid(1, 12, box=40, pitch=52, oy=400, prefix="GS")),
])
def test_self_made_target_registers(name, patches, tmp_path):
    worst = _worst_read_error(patches, tmp_path)
    # Solid patches read exactly; a misregistration reads a neighbour's very
    # different colour → error in the tens. 6/100 is a generous ceiling.
    assert worst < 6.0, f"{name}: worst read error {worst:.1f}/100 — misregistered"
