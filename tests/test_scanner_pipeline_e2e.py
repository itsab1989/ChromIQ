"""Hardware-free end-to-end validation of the scanner/camera pipeline (issue #5).

Drives the *actual* ArgyllCMS ``scanin -F`` → ``colprof`` chain — the same manual
marquee registration ChromIQ ships — against the rectarg example targets (a real
Argyll ``.cht`` + reference + a geometrically-exact rendered chart image), so the
whole flow is validated with no printer or scanner.

For each target we compute the four fiducial pixels the marquee would produce,
by parsing the ``.cht`` with ChromIQ's own :func:`workflow.cht_parser.parse_cht`
and solving rectarg's render affine from the image's own dimensions
(``W = 2·margin + rangeₓ·S``, ``H = 2·margin + rangeᵧ·S + footer``), feed them to
``scanin`` through ChromIQ's own :func:`workflow.scanin_runner.scanin_args`, so
this cannot drift from what the dialog runs, then profile and assert a healthy
ΔE. A gross misregistration blows ΔE into the tens, so the thresholds catch it.

Skipped unless ArgyllCMS binaries and the example targets are both present
($CHROMIQ_ARGYLL_BIN, $CHROMIQ_SCANNER_EXAMPLES, or their defaults).

Covered: the IT8-family scanner targets people actually use (Wolf Faust,
HutchColor, LaserSoft ISO 12641-2 and DCPro). The small ColorChecker-style
targets are rendered with label margins that defeat the auto-corner solver used
*here* (not the app, where the user places corners), so they're out of scope.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from workflow.cht_parser import parse_cht
from workflow.scanin_runner import scanin_args

from tests.argyll_env import argyll_tool  # noqa: E402
_SCANIN = argyll_tool("scanin")
_COLPROF = argyll_tool("colprof")
_EXAMPLES = Path(os.environ.get(
    "CHROMIQ_SCANNER_EXAMPLES", "/tmp/rectarg_src/Example cht and cie files"))

# folder name → comfortable avg-ΔE ceiling (observed values are well below).
_TARGETS = {
    "Wolf Faust IT.7:2":            3.0,
    "Hutchcolor HCT":               3.5,
    "LaserSoft Advanced Target":    2.0,
    "LaserSoft DCPro Studio Target": 3.0,
}

pytestmark = pytest.mark.skipif(
    not (_SCANIN and _COLPROF and _EXAMPLES.is_dir()),
    reason="ArgyllCMS binaries or rectarg example targets not present")


def _pick(folder: Path, *exts: str) -> Path | None:
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() in exts and "absolute" not in p.name.lower():
            return p
    return None


def _fiducial_corners(cht_text: str, W: int, H: int, dpi: int):
    """The four fiducial pixels (TL,TR,BR,BL) the marquee would place, solved
    from rectarg's render affine."""
    g = parse_cht(cht_text)
    xs = ([b.x1 for b in g.patches] + [b.x2 for b in g.patches]
          + [f[0] for f in g.fiducials])
    ys = ([b.y1 for b in g.patches] + [b.y2 for b in g.patches]
          + [f[1] for f in g.fiducials])
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    rx, ry = maxx - minx, maxy - miny
    footer = round(12.0 * dpi / 25.4)
    if abs(rx - ry) > 1e-6:
        S = (W - H + footer) / (rx - ry)
        m = (W - rx * S) / 2.0
    else:
        m = round(15.0 * dpi / 25.4)
        S = (W - 2 * m) / rx
    return [(m + (fx - minx) * S, m + (fy - miny) * S) for fx, fy in g.fiducials]


@pytest.mark.parametrize("folder_name, max_avg_de", list(_TARGETS.items()),
                         ids=lambda v: v if isinstance(v, str) else "")
def test_target_marquee_scanin_colprof_e2e(folder_name, max_avg_de, tmp_path):
    if not isinstance(folder_name, str):        # the ΔE param of the pair
        return
    folder = _EXAMPLES / folder_name
    if not folder.is_dir():
        pytest.skip(f"{folder_name} example not present")
    cht = _pick(folder, ".cht")
    ref = _pick(folder, ".cie", ".txt")
    img = next((p for p in folder.iterdir() if "display" in p.name.lower()
                and p.suffix.lower() in (".tif", ".tiff")), None)
    if cht is None or ref is None or img is None:
        # the /tmp example fixtures decay under macOS's periodic clean-up —
        # an incomplete folder is "fixture absent", not a failure
        pytest.skip(f"{folder_name} example incomplete")

    from PyQt6.QtGui import QImage
    from PyQt6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    qi = QImage(str(img))
    dm = re.search(r"(\d+)dpi", img.name)
    dpi = int(dm.group(1)) if dm else 100
    corners = _fiducial_corners(cht.read_text(errors="ignore"),
                                qi.width(), qi.height(), dpi)

    shutil.copy(img, tmp_path / "s.tif")
    shutil.copy(cht, tmp_path / "r.cht")
    shutil.copy(ref, tmp_path / ref.name)
    argv = scanin_args(Path("s.tif"), Path("r.cht"), Path(ref.name),
                       corners=corners, diag=Path("d.tif"))
    assert "-F" in argv and "-p" not in argv   # corners replace the search
    r = subprocess.run([_SCANIN, *argv],
                       cwd=tmp_path, capture_output=True, text=True)
    assert (tmp_path / "s.ti3").is_file(), \
        f"{folder_name}: scanin -F produced no .ti3:\n{r.stderr[-400:]}"

    c = subprocess.run(
        [_COLPROF, "-v", "-D", "t", "-as", "s"],
        cwd=tmp_path, capture_output=True, text=True)
    assert (tmp_path / "s.icc").is_file(), \
        f"{folder_name}: colprof made no profile:\n{c.stderr[-400:]}"
    m = re.search(r"avg err = ([0-9.]+)", c.stdout + c.stderr)
    assert m, f"{folder_name}: colprof printed no ΔE report"
    avg = float(m.group(1))
    assert avg < max_avg_de, (
        f"{folder_name}: avg ΔE {avg} ≥ {max_avg_de} — marquee registration off")
