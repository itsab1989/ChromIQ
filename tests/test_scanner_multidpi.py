"""Every bundled scanner/camera target registers with scanin -F using the
PATCH-AREA CORNERS as the reference (Knut's approach — no fiducial marks needed),
and does so independently of the scan's resolution.

For each bundled ``.cht`` we render the patches from the file's own geometry at
several pixel scales (≈100/200/300 dpi), then drive the real ``scanin -F`` with
the four patch-area corners and check every patch reads back from the right place.
Guarded on ArgyllCMS ``scanin`` + Pillow.
"""
from __future__ import annotations

import subprocess

import pytest

from workflow.standard_targets import bundled_targets_dir
from workflow.cht_parser import parse_cht

from tests.argyll_env import argyll_tool  # noqa: E402
_SCANIN = argyll_tool("scanin")
PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

pytestmark = pytest.mark.skipif(
    _SCANIN is None, reason="ArgyllCMS scanin not present")

_TARGETS = sorted(p.name for p in bundled_targets_dir().glob("*.cht"))
_M = 40


def _patchbox_cht(text):
    """Rewrite the cht's F line to the patch bounding box — the OFF / patch-frame
    mode the demo scan and patch-corner placement use (the bundled F line is the
    real fiducial marks, which sit outside the rendered patch area)."""
    import re
    g = parse_cht(text)
    xs = [b.x1 for b in g.patches] + [b.x2 for b in g.patches]
    ys = [b.y1 for b in g.patches] + [b.y2 for b in g.patches]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    fl = ("  F _ _ %.2f %.2f %.2f %.2f %.2f %.2f %.2f %.2f"
          % (x0, y0, x1, y0, x1, y1, x0, y1))
    return re.sub(r"(?m)^\s*F .*$", fl, text, count=1)


def _worst(cht_text, scale, tmp_path):
    g = parse_cht(cht_text)
    boxes = [(b.name, b.x1, b.y1, b.x2, b.y2) for b in g.patches]
    minx = min(b[1] for b in boxes); maxx = max(b[3] for b in boxes)
    miny = min(b[2] for b in boxes); maxy = max(b[4] for b in boxes)
    off = (_M - minx * scale, _M - miny * scale)
    W = int(maxx * scale + off[0] + _M); H = int(maxy * scale + off[1] + _M)
    img = Image.new("RGB", (W, H), "white"); px = img.load(); rendered = []
    s = g.box_shrink * scale
    for i, (nm, x1, y1, x2, y2) in enumerate(boxes):
        col = (30 + (i * 37) % 200, 30 + (i * 91) % 200, 30 + (i * 53) % 200)
        rendered.append([v / 255 * 100 for v in col])
        for yy in range(int(y1 * scale + s + off[1]), int(y2 * scale - s + off[1])):
            for xx in range(int(x1 * scale + s + off[0]), int(x2 * scale - s + off[0])):
                if 0 <= xx < W and 0 <= yy < H:
                    px[xx, yy] = col
    corners = [(minx*scale+off[0], miny*scale+off[1]), (maxx*scale+off[0], miny*scale+off[1]),
               (maxx*scale+off[0], maxy*scale+off[1]), (minx*scale+off[0], maxy*scale+off[1])]
    fstr = ",".join(f"{v:.1f}" for xy in corners for v in xy)
    img.save(tmp_path / "s.tif")
    (tmp_path / "r.cht").write_text(_patchbox_cht(cht_text), encoding="utf-8")
    cie = (["CGATS.17", "NUMBER_OF_FIELDS 4", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
            f"NUMBER_OF_SETS {len(boxes)}", "BEGIN_DATA"]
           + [f"{b[0]} 40 40 40" for b in boxes] + ["END_DATA", ""])
    (tmp_path / "ref.cie").write_text("\n".join(cie), encoding="utf-8")
    r = subprocess.run([_SCANIN, "-v", "-p", "-F", fstr,
                        "s.tif", "r.cht", "ref.cie"], cwd=tmp_path,
                       capture_output=True, text=True, encoding="utf-8")
    assert (tmp_path / "s.ti3").is_file(), f"scanin failed:\n{r.stderr[-300:]}"
    lines = (tmp_path / "s.ti3").read_text(encoding="utf-8").splitlines()
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
        worst = max(worst, min(max(abs(a - b) for a, b in zip(read, rr))
                               for rr in rendered))
    return worst


@pytest.mark.parametrize("name", _TARGETS)
@pytest.mark.parametrize("scale", [1.0, 2.0, 3.0])   # ≈100 / 200 / 300 dpi
def test_bundled_target_registers_at_scale(name, scale, tmp_path):
    cht = (bundled_targets_dir() / name).read_text(errors="ignore", encoding="utf-8")
    worst = _worst(cht, scale, tmp_path)
    assert worst < 6.0, f"{name} @ {scale}×: misregistered (worst {worst:.1f}/100)"


@pytest.mark.parametrize("name", _TARGETS)   # every supported target
def test_make_test_scan_reads_back(name, tmp_path):
    """The "Try with a demo scan" generator (make_test_scan) — the exact files the
    button loads — reads back its known colours through the real scanin, for EVERY
    bundled target (contiguous and gapped). Knut's end-to-end check: the demo
    doubles as a scanin self-check. Its colours span dark→light in a scrambled
    order (demo_patch_color), so a grid that slipped onto a neighbour cell would
    read a very different colour and fail — a real misalignment detector."""
    from workflow.standard_targets import make_test_scan, demo_patch_color

    cht_path = bundled_targets_dir() / name
    tif, cie = make_test_scan(cht_path, tmp_path)
    g = parse_cht(cht_path.read_text(errors="ignore", encoding="utf-8"))
    n = len(g.patches)
    expected = {b.name: [c / 2.55 for c in demo_patch_color(i, n)]  # 0..255 → 0..100
                for i, b in enumerate(g.patches)}
    minx = min(b.x1 for b in g.patches); maxx = max(b.x2 for b in g.patches)
    miny = min(b.y1 for b in g.patches); maxy = max(b.y2 for b in g.patches)
    scale = 1500.0 / max(maxx - minx, maxy - miny, 1.0); m = 80
    W, H = (maxx - minx) * scale, (maxy - miny) * scale
    corners = [(m, m), (m + W, m), (m + W, m + H), (m, m + H)]
    fstr = ",".join(f"{v:.1f}" for xy in corners for v in xy)
    # make_test_scan draws patches at their true (gapped) positions, so read with
    # the same cht — contiguous re-placement would MISread a gapped demo.
    (tmp_path / "r.cht").write_text(_patchbox_cht(cht_path.read_text(errors="ignore", encoding="utf-8")), encoding="utf-8")
    subprocess.run([_SCANIN, "-v", "-p", "-F", fstr,
                    tif.name, "r.cht", cie.name], cwd=tmp_path,
                   capture_output=True, text=True, encoding="utf-8")
    ti3 = tif.with_suffix(".ti3")
    assert ti3.is_file(), "scanin produced no .ti3 for the demo scan"
    lines = ti3.read_text(encoding="utf-8").splitlines()
    fb = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA_FORMAT")
    fields = lines[fb + 1].split()
    ri = [fields.index(f"RGB_{c}") for c in "RGB"]; ni = fields.index("SAMPLE_ID")
    db = next(i for i, l in enumerate(lines) if l.strip() == "BEGIN_DATA")
    de = next(i for i, l in enumerate(lines) if l.strip() == "END_DATA")
    worst = 0.0
    for l in lines[db + 1:de]:
        t = l.split()
        if len(t) != len(fields) or t[ni].strip('"') not in expected:
            continue
        read = [float(t[k]) for k in ri]
        worst = max(worst, max(abs(a - b) for a, b in zip(read, expected[t[ni].strip('"')])))
    assert worst < 3.0, f"{name}: demo scan misread (worst {worst:.1f}/100)"


def test_sanitized_ti3_builds_a_profile(tmp_path):
    """End-to-end (Nelson's Windows crash): a scanner .ti3 with an injected bad
    value + bad STDEV makes colprof fail raw, but sanitize_ti3 drops the bad-read
    patch + zeros the STDEV, and colprof then builds a valid profile."""
    from workflow.standard_targets import make_test_scan
    from workflow.scanin_runner import sanitize_ti3
    colprof = argyll_tool("colprof")
    if colprof is None:
        pytest.skip("colprof not present")
    cht = bundled_targets_dir() / "it8Wolf.cht"
    tif, cie = make_test_scan(cht, tmp_path)
    g = parse_cht(cht.read_text(encoding="utf-8"))
    xs = [b.x1 for b in g.patches] + [b.x2 for b in g.patches]
    ys = [b.y1 for b in g.patches] + [b.y2 for b in g.patches]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    sc = 1500.0 / max(maxx - minx, maxy - miny, 1.0); m = 80
    W, H = (maxx - minx) * sc, (maxy - miny) * sc
    fstr = ",".join(f"{v:.1f}" for xy in
                    [(m, m), (m + W, m), (m + W, m + H), (m, m + H)] for v in xy)
    (tmp_path / "r.cht").write_text(cht.read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run([_SCANIN, "-p", "-dipn", "-F", fstr,
                    tif.name, "r.cht", cie.name], cwd=tmp_path,
                   capture_output=True, text=True, encoding="utf-8")
    ti3 = tif.with_suffix(".ti3")
    assert ti3.is_file(), "scanin produced no .ti3"
    lines = ti3.read_text(encoding="utf-8").splitlines()
    db = next(i for i, ln in enumerate(lines) if ln.strip() == "BEGIN_DATA")
    r = lines[db + 3].split(); r[4] = "1.#IND00"; lines[db + 3] = " ".join(r)   # RGB_R
    r = lines[db + 6].split(); r[-1] = "nan"; lines[db + 6] = " ".join(r)       # STDEV_B
    (tmp_path / "bad.ti3").write_text("\n".join(lines) + "\n", encoding="utf-8")
    subprocess.run([str(colprof), "-as", "bad"], cwd=tmp_path,
                   capture_output=True, text=True, encoding="utf-8")
    # colprof writes .icc, or .icm on Windows — check both so the assertion is
    # real on every platform (the app resolves it the same robust way).
    def _profile(stem: str):
        return next((p for p in (tmp_path / f"{stem}.icc", tmp_path / f"{stem}.icm")
                     if p.is_file()), None)
    assert _profile("bad") is None, "colprof should reject the raw nan .ti3"
    clean, zeroed, dropped = sanitize_ti3("\n".join(lines) + "\n")
    assert dropped == 1 and zeroed == 1
    (tmp_path / "clean.ti3").write_text(clean, encoding="utf-8")
    subprocess.run([str(colprof), "-as", "clean"], cwd=tmp_path,
                   capture_output=True, text=True, encoding="utf-8")
    icc = _profile("clean")
    assert icc is not None and icc.stat().st_size > 1000, \
        "sanitized .ti3 should build a profile"
