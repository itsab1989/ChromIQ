#!/usr/bin/env python3
"""Does the split overlay follow a HEXAGON, on a real honeycomb chart?

Basti, 2026-09-17: *"is it working for hexagonal patches as well (normal and
rotated honeycomb)? … it seemed that there was something still wrong with
hexagonal patches getting a rectangular overlay or maybe vice versa."*

The detector is the monochrome one, made hex-aware. A page is painted so that
the only colour on it lies INSIDE each patch's hexagon; the slot's corners,
which a hexagon does not reach, are painted a second colour; everything else is
black or white. The split is drawn in two greys. Two questions then answer
themselves from one photograph:

  * a pixel of the HEXAGON colour left showing  -> the split missed part of
    its own patch;
  * a GREY pixel on a slot CORNER               -> the split painted a
    rectangle over a hexagon.

Both directions, in one picture, with nothing to interpret.

Charts are built by ChromIQ's own layout engine from Create Chart options:
pointy-top honeycomb, flat-top (the rotated one), and a CR30 chart, whose
patches are SQUARE and must NOT borrow the honeycomb.

    python scripts/drive_b21_hex_overlay_shape.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SANDBOX = Path(os.environ.get(
    "B21_HEX_SANDBOX", "/Users/Basti/.claude/jobs/c4ec4e71/tmp/b21-hex"))
SANDBOX.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "chromiq-hex-driver.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

import traceback  # noqa: E402

from core.logger import configure_logging, get_logger  # noqa: E402

configure_logging()
log = get_logger("chromiq")


def _log_excepthook(exc_type, exc, tb):
    log.critical("Uncaught exception:\n%s",
                 "".join(traceback.format_exception(exc_type, exc, tb)))
    sys.__excepthook__(exc_type, exc, tb)


sys.excepthook = _log_excepthook

from PyQt6.QtCore import QRect                      # noqa: E402
from PyQt6.QtGui import QColor                      # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMainWindow,  # noqa: E402
                             QVBoxLayout, QWidget)

from scripts.onscreen_capture import capture_window  # noqa: E402
from ui.styles import WinButtonLayoutStyle           # noqa: E402
from ui.tiff_preview import TiffPreview              # noqa: E402
from workflow.layout_engine import hexagon           # noqa: E402

OUT = Path.home() / "Desktop" / "ChromIQ-beta21-proof" / "hex-overlay-shape"

HEX_COLOUR = (255, 0, 255)        # inside the hexagon
CORNER_COLOUR = (0, 255, 255)     # the slot corners a hexagon never reaches
GREY_EXPECTED = QColor(96, 96, 96)
GREY_MEASURED = QColor(176, 176, 176)

# THE ROTATED HONEYCOMB IS A CR30 THING, NOT A SPECTROSCAN ONE.
# `_build_base` writes `hex_flat_top` only inside its `key == "CR30" and hflag`
# branch, and `recipe_is_flat_top` resolves it the same way, so a SpectroScan
# honeycomb is always pointy-top however the flag is set. Asking for
# `instrument="SS", hex_flat_top=True` does not build a rotated chart; it
# builds a pointy one, and a driver that did not check would have reported the
# rotated case as tested when it never ran.
CASES = [
    ("ss-honeycomb", dict(instrument="SS", hflag=True)),
    ("cr30-honeycomb", dict(instrument="CR30", hflag=True)),
    ("cr30-honeycomb-rotated",
     dict(instrument="CR30", hflag=True, hex_flat_top=True)),
    ("cr30-square", dict(instrument="CR30")),
]
SIZES = ["900x1000", "1200x980", "700x900"]


def say(*a):
    print(*a, flush=True)


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shoot(app, win, path: Path, tries: int = 6):
    """Settled: photograph until two consecutive frames are identical."""
    from PIL import Image, ImageChops
    prev = path.with_name(path.stem + "__prev.png")
    why, last = "", None
    for i in range(tries):
        pump(app, 400 + 250 * i)
        ok, why = capture_window(win, path, settle=0.4 + 0.15 * i)
        if not ok:
            continue
        if last is not None:
            a = Image.open(prev).convert("RGB")
            b = Image.open(path).convert("RGB")
            if a.size == b.size and ImageChops.difference(a, b).getbbox() is None:
                prev.unlink(missing_ok=True)
                return True, ""
        last = True
        path.replace(prev)
    prev.unlink(missing_ok=True)
    return False, why or "never painted the same thing twice"


def ti1(n: int, path: Path) -> Path:
    lines = ["CTI1", "", 'DESCRIPTOR "hex probe"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i + 1} {(i * 7) % 101} {(i * 13) % 101} "
                     f"{(i * 29) % 101} 40 45 50")
    lines += ["END_DATA", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build(name: str, n: int = 150, **kw) -> Path:
    """Build the chart AND the sidecar the app reads its shape from.

    `build_chart` writes the pages and `<stem>.strips.json`; the
    `channels.json` that carries the layout RECIPE is written by the Create
    Chart tab, and `chart_is_hexagonal` reads the recipe, not the geometry.
    Without it a real honeycomb chart answers "not hexagonal" and every driver
    built on top quietly photographs the rectangular branch. That is how round
    3 cleared hexagonal charts for draw order without ever drawing one, and it
    is how this driver's first run reported `hexagonal=False` for a
    SpectroScan honeycomb.
    """
    from workflow.layout_engine import chart as le
    work = SANDBOX / "charts" / name
    stem = work / name
    if not stem.with_suffix(".strips.json").is_file():
        le.build_chart(ti1(n, work / "probe.ti1"), stem, paper="A4", dpi=200,
                       randomize=False, **kw)
    sidecar = stem.parent / f"{stem.name}.channels.json"
    if not sidecar.is_file():
        strips = json.loads(
            stem.with_suffix(".strips.json").read_text(encoding="utf-8"))
        sidecar.write_text(json.dumps({
            "ink_channels": ["r", "g", "b"],
            "layout": {"engine": "chromiq", "engine_version": 1, "dpi": 200,
                       "paper_mm": [210.0, 297.0],
                       "patches": strips["patches"],
                       "recipe": dict(kw)},
        }, indent=1), encoding="utf-8")
    return stem


def mono_page(src: Path, boxes, flat_top: bool, hexed: bool, dst: Path) -> Path:
    """Colour ONLY inside the hexagon, a second colour on the slot's corners."""
    from PIL import Image, ImageDraw
    im = Image.open(src).convert("RGB")
    px = im.load()
    W, H = im.size
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            px[x, y] = (255, 255, 255) if (r + g + b) > 382 else (0, 0, 0)
    d = ImageDraw.Draw(im)
    for r in boxes:
        d.rectangle([r.x(), r.y(), r.x() + r.width() - 1,
                     r.y() + r.height() - 1], fill=CORNER_COLOUR)
        if hexed:
            pts = hexagon.vertices(r.x(), r.y(), r.width(), r.height(),
                                   flat_top=flat_top)
            d.polygon([(float(vx), float(vy)) for vx, vy in pts],
                      fill=HEX_COLOUR)
        else:
            d.rectangle([r.x(), r.y(), r.x() + r.width() - 1,
                         r.y() + r.height() - 1], fill=HEX_COLOUR)
    im.save(dst)
    return dst


def main() -> int:
    from workflow.hex_support import chart_is_flat_top, chart_is_hexagonal
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    win = QMainWindow()
    win.setWindowTitle("ChromIQ hexagon overlay shape")
    central = QWidget()
    lay = QVBoxLayout(central)
    lay.setContentsMargins(0, 0, 0, 0)
    prev = TiffPreview()
    lay.addWidget(prev)
    win.setCentralWidget(central)
    win.resize(900, 1000)
    win.show()
    pump(app, 400)

    bad = 0
    for name, kw in CASES:
        try:
            stem = build(name, **kw)
        except Exception as exc:                   # noqa: BLE001
            say(f"!! {name}: could not build: {type(exc).__name__}: {exc}")
            bad += 1
            continue
        strips = json.loads(
            stem.with_suffix(".strips.json").read_text(encoding="utf-8"))
        boxes = [QRect(int(p["x"]), int(p["y"]), int(p["w"]), int(p["h"]))
                 for p in strips["patches"] if int(p["page"]) == 0]
        page = stem.parent / f"{stem.name}_01.tif"
        if not page.is_file():
            page = stem.with_suffix(".tif")
        # THE CHART DECIDES, exactly as ui/tabs/tab_measure.py does.
        is_hex = chart_is_hexagonal(stem.with_suffix(".ti2"))
        flat = chart_is_flat_top(stem.with_suffix(".ti2"))
        mono = mono_page(page, boxes, flat, is_hex,
                         SANDBOX / f"{name}-mono.tif")
        say(f"{name}: {len(boxes)} patches on page 1, "
            f"hexagonal={is_hex} flat_top={flat}")

        for spec in SIZES:
            w, h = (int(v) for v in spec.split("x"))
            win.resize(w, h)
            pump(app, 600)
            folder = OUT / name / spec
            folder.mkdir(parents=True, exist_ok=True)
            for tag, src in (("plain", page), ("mono", mono)):
                prev.clear_patch_overlay()
                prev.load_tiff([src])
                pump(app, 900)
                prev.set_hex_zigzag(is_hex, flat_top=flat)
                prev.set_page_patch_boxes({0: list(boxes)})
                prev.set_patch_overlay(
                    0, [(b, GREY_EXPECTED, GREY_MEASURED, False)
                        for b in boxes], replace_page=True)
                pump(app, 700)
                ok, why = shoot(app, win, folder / f"{tag}.png")
                if not ok:
                    say(f"!! {name} {spec} {tag}: CAPTURE REFUSED: {why}")
                    bad += 1
            (folder / "facts.json").write_text(json.dumps({
                "chart": name, "hexagonal": is_hex, "flat_top": flat,
                "window": [w, h], "dpr": float(prev.devicePixelRatioF()),
                "patches": len(boxes),
                "boxes": [[b.x(), b.y(), b.width(), b.height()]
                          for b in boxes],
            }, indent=1), encoding="utf-8")
    win.close()
    pump(app, 200)
    say(f"photographed into {OUT}")
    return 2 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
