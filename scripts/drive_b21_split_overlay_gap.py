#!/usr/bin/env python3
"""Photograph the split-patch overlay against the chart it is drawn on.

A tester photographed the Measure tab (issue thread, 2026-09-17) and found two
faults in the expected/measured split:

  * the 6th patch of the first strip shows a thin light line along its BOTTOM
    edge, where the chart underneath is still visible past the overlay;
  * on some patches the diagonal is clean and on others it makes a STEP.

This drives the REAL `TiffPreview` in a REAL window with a REAL engine chart and
photographs it with `scripts/onscreen_capture.py` (the window's own buffer, at
device resolution). Nothing is re-implemented: the overlay goes in through the
widget's public `set_patch_overlay`, exactly as `ui/tabs/tab_measure.py` feeds
it.

Per window size, three photographs:

  A   overlay OFF               -> where the CHART's patch is, in screen pixels
  B1  overlay ON, marker pairs  -> where the OVERLAY is
  B2  overlay ON, pairs SWAPPED -> so a chart colour that happens to match one
                                   marker cannot hide a leak

Neighbouring patches get DIFFERENT marker pairs (a checkerboard), so a walk out
from a patch's centre stops at its own painted edge instead of running on into
the next patch's overlay.

The window is swept over several sizes because the fault is geometry
dependent: the preview scales the page to fit, and how the two edges of a patch
round is what decides whether a chart pixel is left showing.

    python scripts/drive_b21_split_overlay_gap.py [--sizes 560x1000,720x900]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SANDBOX = Path(os.environ.get(
    "B21_SANDBOX", "/Users/Basti/.claude/jobs/c4ec4e71/tmp/b21-overlay"))
SANDBOX.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "chromiq-driver.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

import traceback  # noqa: E402

from core.logger import configure_logging, get_logger  # noqa: E402

configure_logging()
log = get_logger("chromiq")


def _log_excepthook(exc_type, exc, tb):            # the hook main.py installs
    log.critical("Uncaught exception:\n%s",
                 "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _log_excepthook

from PyQt6.QtCore import QPoint, QRect            # noqa: E402
from PyQt6.QtGui import QColor                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMainWindow,  # noqa: E402
                             QVBoxLayout, QWidget)

from scripts.onscreen_capture import capture_window  # noqa: E402
from ui.styles import WinButtonLayoutStyle           # noqa: E402
from ui.tiff_preview import TiffPreview              # noqa: E402

CHART = Path("/Users/Basti/ChromIQ/Canon-Pro300-CanonSG-i1Pro/runs/run1")
PAGE = CHART / "engine-preview_01.tif"
GEOM = CHART / "engine-preview.strips.json"
OUT = Path.home() / "Desktop" / "ChromIQ-beta21-proof" / "split-overlay-gap"

# Two marker pairs, laid out as a checkerboard so a patch never touches a patch
# with the same pair. None of the four colours is one of the chart's own
# strip-guide colours (pure white, blue, yellow, red, black).
PAIRS = [((255, 0, 255), (0, 200, 0)),          # expected, measured
         ((0, 220, 220), (255, 130, 0))]
MARKED = MONO = None
SIZES = ["560x1000", "620x1000", "700x980", "560x820", "900x1000", "480x760"]


def say(*a):
    print(*a, flush=True)


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shoot(app, win, path: Path, tries: int = 5) -> "tuple[bool, str]":
    """Photograph the window, giving it time to have painted.

    `set_patch_overlay` schedules a refresh, and a capture taken before that
    refresh lands comes back as an empty buffer -- `capture_window` correctly
    refuses it as one flat colour. That is the helper doing its job, not a
    failure of the window server, so the answer is to wait and ask again
    rather than to accept a blank picture. A refusal that survives every try
    is reported by the caller, never papered over.
    """
    why = ""
    for i in range(tries):
        pump(app, 400 + 300 * i)
        ok, why = capture_window(win, path, settle=0.4 + 0.2 * i)
        if ok:
            if i:
                say(f"    (the window had not painted yet; capture {i + 1} "
                    f"of {tries} succeeded)")
            return True, ""
    return False, why


def boxes_for_page(page: int) -> "dict[str, QRect]":
    data = json.loads(GEOM.read_text(encoding="utf-8"))
    return {str(p["loc"]): QRect(int(p["x"]), int(p["y"]),
                                 int(p["w"]), int(p["h"]))
            for p in data["patches"] if int(p["page"]) == page}


def checkerboard(boxes: "dict[str, QRect]") -> "dict[str, int]":
    """Pair index per patch, alternating along both axes of the patch grid."""
    cols = sorted({r.x() for r in boxes.values()})
    rows = sorted({r.y() for r in boxes.values()})
    ci = {v: i for i, v in enumerate(cols)}
    ri = {v: i for i, v in enumerate(rows)}
    return {loc: (ci[r.x()] + ri[r.y()]) % 2 for loc, r in boxes.items()}


def monochrome_page(src: Path, boxes, dst: Path) -> Path:
    """A copy of the page where the only colour left is the patches.

    Basti's idea, and it is the better detector: paint every patch a saturated
    colour, drive everything else on the sheet to pure black or pure white, and
    draw the overlay in two greys. Then a single question answers the whole
    thing, with no geometry, no offsets and no classification: is there a
    coloured pixel left when the overlay is on? Every one that is, is chart
    showing through a split that was supposed to cover it.
    """
    from PIL import Image as _I
    im = _I.open(src).convert("RGB")
    px = im.load()
    W, H = im.size
    for y in range(H):                       # everything to black or white
        for x in range(W):
            r, g_, b_ = px[x, y]
            px[x, y] = (255, 255, 255) if (r + g_ + b_) > 382 else (0, 0, 0)
    for i, r in enumerate(boxes.values()):   # then the patches, in colour
        col = (255, 0, 255) if i % 2 == 0 else (0, 255, 255)
        for y in range(r.y(), r.y() + r.height()):
            for x in range(r.x(), r.x() + r.width()):
                if 0 <= x < W and 0 <= y < H:
                    px[x, y] = col
    im.save(dst)
    return dst


def run_size(app, win, prev, boxes, parity, w: int, h: int) -> "dict | None":
    tag = f"{w}x{h}"
    folder = OUT / tag
    folder.mkdir(parents=True, exist_ok=True)
    win.resize(w, h)
    pump(app, 700)
    prev.clear_patch_overlay()
    pump(app, 500)

    ok, why = shoot(app, win, folder / "A-no-overlay.png")
    if not ok:
        say(f"!! {tag}: CAPTURE REFUSED (overlay off): {why}")
        return None

    shots = []
    for swap in (0, 1):
        items = []
        for loc, r in boxes.items():
            cexp, cmeas = PAIRS[(parity[loc] + swap) % 2]
            items.append((r, QColor(*cexp), QColor(*cmeas), False))
        prev.set_patch_overlay(0, items, replace_page=True)
        pump(app, 600)
        name = f"B{swap + 1}-overlay.png"
        ok, why = shoot(app, win, folder / name)
        if not ok:
            say(f"!! {tag}: CAPTURE REFUSED (overlay pass {swap}): {why}")
            return None
        shots.append(name)

    # Basti's monochrome pass: the page with colour ONLY in the patches, the
    # overlay in two greys. Anything coloured in this photograph is a leak.
    prev.load_tiff([MONO])
    pump(app, 900)
    grey = [(r, QColor(96, 96, 96), QColor(176, 176, 176), False)
            for r in boxes.values()]
    prev.set_patch_overlay(0, grey, replace_page=True)
    pump(app, 700)
    ok, why = shoot(app, win, folder / "C-grey-on-monochrome.png")
    if not ok:
        say(f"!! {tag}: CAPTURE REFUSED (monochrome pass): {why}")
        return None
    prev.clear_patch_overlay()
    pump(app, 400)
    ok, why = shoot(app, win, folder / "C0-monochrome-no-overlay.png")
    if not ok:
        say(f"!! {tag}: CAPTURE REFUSED (monochrome, overlay off): {why}")
        return None
    # A pass that LOOKS like the real thing: expected = the patch's own colour
    # off the page, measured = the same colour a little darker, which is what a
    # print that came out heavy reads like. Nothing is measured from this one;
    # it is there so the proof can be looked at rather than only counted.
    prev.load_tiff([MARKED])
    pump(app, 900)
    from PIL import Image as _I2
    _src = _I2.open(PAGE).convert("RGB").load()
    real = []
    for r in boxes.values():
        c = _src[r.x() + r.width() // 2, r.y() + r.height() // 2]
        real.append((r, QColor(*c),
                     QColor(*[max(0, int(v * 0.72)) for v in c]), False))
    prev.set_patch_overlay(0, real, replace_page=True)
    ok, why = shoot(app, win, folder / "D-realistic-split.png")
    if not ok:
        say(f"!! {tag}: CAPTURE REFUSED (realistic pass): {why}")
        return None

    lbl = prev._img_label
    pm = lbl.pixmap()
    org = lbl.mapTo(win, QPoint(0, 0))
    facts = {
        "window": [w, h],
        "corner_colours": {"origin": [255, 0, 255], "far": [0, 255, 255]},
        "dpr": float(prev.devicePixelRatioF()),
        "page_px": [prev._pixmap.width(), prev._pixmap.height()],
        "border_B": prev._paint_border,
        "paint_geom": list(prev._paint_geom),
        "canvas_px": [pm.width(), pm.height()],
        "label_origin_in_window": [org.x(), org.y()],
        "label_size": [lbl.width(), lbl.height()],
        "shots": shots,
        "mono_shots": ["C0-monochrome-no-overlay.png", "C-grey-on-monochrome.png"],
        "realistic_shot": "D-realistic-split.png",
        "pairs": PAIRS,
        "parity": parity,
        "boxes": {k: [r.x(), r.y(), r.width(), r.height()]
                  for k, r in boxes.items()},
    }
    (folder / "geometry.json").write_text(json.dumps(facts, indent=1),
                                          encoding="utf-8")
    say(f"    {tag}: canvas {facts['canvas_px']} "
        f"border {facts['border_B']} s {facts['paint_geom'][0]:.9f}")
    return facts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default=",".join(SIZES))
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    win = QMainWindow()
    win.setWindowTitle("ChromIQ split-overlay geometry")
    central = QWidget()
    lay = QVBoxLayout(central)
    lay.setContentsMargins(0, 0, 0, 0)
    prev = TiffPreview()
    lay.addWidget(prev)
    win.setCentralWidget(central)
    win.resize(560, 1000)
    win.show()
    pump(app, 400)

    # A COPY OF THE PAGE WITH ITS CORNERS STAMPED. Where the drawn image
    # begins and ends on screen has to be MEASURED, not derived: the label
    # centres the canvas, the canvas carries a border, the photograph carries
    # a title bar, and every one of those can land on a half pixel -- which is
    # the size of the fault being measured. Two 6 px corner blocks in the page
    # itself pin the image's first and last device row and column in the
    # photograph exactly. Both corners sit in the sheet's white margin, well
    # clear of every patch.
    global MARKED, MONO
    marked = MARKED = SANDBOX / "page-with-corners.tif"
    from PIL import Image as _I
    _im = _I.open(PAGE).convert("RGB")
    _pw, _ph = _im.size
    for box, col in (((0, 0, 6, 6), (255, 0, 255)),
                     ((_pw - 6, _ph - 6, _pw, _ph), (0, 255, 255))):
        _im.paste(col, box)
    _im.save(marked)
    prev.load_tiff([marked])
    pump(app, 1200)

    MONO = monochrome_page(PAGE, boxes_for_page(0), SANDBOX / "page-mono.tif")

    boxes = boxes_for_page(0)
    parity = checkerboard(boxes)
    prev.set_page_patch_boxes({0: list(boxes.values())})
    pump(app, 300)
    say(f"chart: {len(boxes)} patches on page 1, dpr "
        f"{prev.devicePixelRatioF()}")

    done = []
    for spec in args.sizes.split(","):
        w, h = (int(v) for v in spec.lower().split("x"))
        globals()["OUT"] = out
        if run_size(app, win, prev, boxes, parity, w, h):
            done.append(spec)
    win.close()
    pump(app, 200)
    say(f"photographed {len(done)} window sizes into {out}")
    return 0 if done else 2


if __name__ == "__main__":
    raise SystemExit(main())
