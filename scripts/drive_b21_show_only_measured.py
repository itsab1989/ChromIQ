#!/usr/bin/env python3
"""Does "Show only measured patches" blank exactly the unread strips?

Basti, 2026-09-17: *"does this also affect the option to only show measured
patches in the measure tab … in a positive way?"*

It does, because the blanking is drawn by the same function as the split and
it mapped y with the page's HORIZONTAL scale until this change set. This
measures it rather than asserting it.

The detector: a page whose patches are a saturated colour and whose paper is
black or white. "Show only measured" paints the UNREAD columns paper-white and
leaves the read ones alone, so two numbers say whether the blanking lands:

  * coloured pixels left inside an UNREAD column  -> the blanking fell short
    and a sliver of chart the user was told is hidden is still showing;
  * white painted over a READ column's patches    -> it blanked too far and
    ate a measurement.

Both are counted against the CHART's own grid, taken from the sidecar, not
against the overlay's arithmetic.

    python scripts/drive_b21_show_only_measured.py
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
    "B21_SOM_SANDBOX", "/Users/Basti/.claude/jobs/c4ec4e71/tmp/b21-som"))
SANDBOX.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "chromiq-som-driver.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

import traceback  # noqa: E402

from core.logger import configure_logging, get_logger  # noqa: E402

configure_logging()
log = get_logger("chromiq")


def _hook(t, e, tb):
    log.critical("Uncaught exception:\n%s",
                 "".join(traceback.format_exception(t, e, tb)))
    sys.__excepthook__(t, e, tb)


sys.excepthook = _hook

from PyQt6.QtCore import QRect                    # noqa: E402
from PyQt6.QtGui import QColor                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMainWindow,  # noqa: E402
                             QVBoxLayout, QWidget)

from scripts.onscreen_capture import capture_window  # noqa: E402
from ui.styles import WinButtonLayoutStyle           # noqa: E402
from ui.tiff_preview import TiffPreview              # noqa: E402

OUT = Path.home() / "Desktop" / "ChromIQ-beta21-proof" / "show-only-measured"
PATCH = (255, 0, 255)
CASES = [
    ("i1-default", dict(instrument="i1")),
    ("cm-stagger", dict(instrument="CM", cm_stagger=True)),
    ("ss-honeycomb", dict(instrument="SS", hflag=True)),
]
SIZES = ["900x1000", "1200x980", "620x900"]


def say(*a):
    print(*a, flush=True)


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shoot(app, win, path: Path, tries: int = 6):
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
    L = ["CTI1", "", 'DESCRIPTOR "som"', 'ORIGINATOR "ChromIQ"',
         'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
         "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
         f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        L.append(f"{i + 1} {(i * 7) % 101} {(i * 13) % 101} {(i * 29) % 101} 40 45 50")
    L += ["END_DATA", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L), encoding="utf-8")
    return path


def build(name: str, n: int = 150, **kw) -> Path:
    from workflow.layout_engine import chart as le
    work = SANDBOX / "charts" / name
    stem = work / name
    if not stem.with_suffix(".strips.json").is_file():
        le.build_chart(ti1(n, work / "probe.ti1"), stem, paper="A4", dpi=200,
                       randomize=False, **kw)
    side = stem.parent / f"{stem.name}.channels.json"
    if not side.is_file():
        strips = json.loads(
            stem.with_suffix(".strips.json").read_text(encoding="utf-8"))
        # THE STRIPS BLOCK TOO. `engine_strip_rects_from_sidecar` returns None
        # without it, and "Show only measured patches" blanks by STRIP, so a
        # sidecar with only `patches` makes the whole feature a no-op and a
        # driver built on it photographs nothing.
        side.write_text(json.dumps({
            "ink_channels": ["r", "g", "b"],
            "layout": {"engine": "chromiq", "engine_version": 1, "dpi": 200,
                       "paper_mm": [210.0, 297.0],
                       "patches": strips["patches"],
                       "strips": strips.get("strips") or [],
                       "label_band_bottom_px":
                           strips.get("label_band_bottom_px"),
                       "recipe": dict(kw)},
        }, indent=1), encoding="utf-8")
    return stem


def mono(src: Path, boxes, dst: Path) -> Path:
    from PIL import Image
    im = Image.open(src).convert("RGB")
    px = im.load()
    W, H = im.size
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            px[x, y] = (255, 255, 255) if (r + g + b) > 382 else (0, 0, 0)
    for r in boxes:
        for y in range(max(0, r.y()), min(H, r.y() + r.height())):
            for x in range(max(0, r.x()), min(W, r.x() + r.width())):
                px[x, y] = PATCH
    im.save(dst)
    return dst


def main() -> int:
    from ui.tabs.tab_measure import engine_strip_rects_from_sidecar
    from workflow.hex_support import chart_is_flat_top, chart_is_hexagonal
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    win = QMainWindow()
    win.setWindowTitle("ChromIQ show only measured")
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
        except Exception as exc:                        # noqa: BLE001
            say(f"!! {name}: {type(exc).__name__}: {exc}")
            bad += 1
            continue
        strips = json.loads(
            stem.with_suffix(".strips.json").read_text(encoding="utf-8"))
        boxes = [QRect(int(p["x"]), int(p["y"]), int(p["w"]), int(p["h"]))
                 for p in strips["patches"] if int(p["page"]) == 0]
        page = stem.parent / f"{stem.name}_01.tif"
        if not page.is_file():
            page = stem.with_suffix(".tif")
        side = stem.parent / f"{stem.name}.channels.json"
        rects = engine_strip_rects_from_sidecar(side, 1)
        cols = list(rects[0][0]) if rects else []
        if not cols:
            say(f"!! {name}: no strip rects from the sidecar")
            bad += 1
            continue
        mono_page = mono(page, boxes, SANDBOX / f"{name}-mono.tif")
        is_hex = chart_is_hexagonal(stem.with_suffix(".ti2"))
        read = {i: (i % 2 == 0) for i in range(len(cols))}
        say(f"{name}: {len(boxes)} patches, {len(cols)} strips, "
            f"hex={is_hex}, {sum(read.values())} marked read")

        for spec in SIZES:
            w, h = (int(v) for v in spec.split("x"))
            win.resize(w, h)
            pump(app, 600)
            folder = OUT / name / spec
            folder.mkdir(parents=True, exist_ok=True)
            # BOTH PAGES. The monochrome one is the detector; the REAL one is
            # what a person actually sees, and a driver that only keeps the
            # first hands its reader a picture of patch BOXES -- rectangles,
            # even on a honeycomb -- under a hexagonal grid, which looks like a
            # fault in the app and is a fault in the test page. Basti looked at
            # exactly that and asked whether it was real.
            for tag, src in (("blanked", mono_page), ("blanked-real", page)):
                prev.clear_patch_overlay()
                prev.load_tiff([src])
                pump(app, 900)
                prev.set_hex_zigzag(is_hex,
                                    flat_top=chart_is_flat_top(
                                        stem.with_suffix(".ti2")))
                prev.set_page_patch_boxes({0: list(boxes)})
                prev.set_stripe_rects(list(cols))
                prev.set_stripe_read_map(read)
                # NO split overlay on purpose. The blanking is what is under
                # test, and a grey overlay on the read strips would hide the
                # very pixels that say where the page is.
                prev.set_show_only_measured(True)
                pump(app, 800)
                ok, why = shoot(app, win, folder / f"{tag}.png")
                if not ok:
                    say(f"!! {name} {spec} {tag}: CAPTURE REFUSED: {why}")
                    bad += 1
            (folder / "facts.json").write_text(json.dumps({
                "chart": name, "window": [w, h], "hex": is_hex,
                "dpr": float(prev.devicePixelRatioF()),
                "read_map": {str(k): v for k, v in read.items()},
                "strips": [[r.x(), r.y(), r.width(), r.height()] for r in cols],
                "boxes": [[b.x(), b.y(), b.width(), b.height()] for b in boxes],
            }, indent=1), encoding="utf-8")
            say(f"   {spec}: photographed")
    win.close()
    pump(app, 200)
    say(f"photographed into {OUT}")
    return 2 if bad else 0


def _strip_of(box: QRect, cols) -> int:
    cx = box.x() + box.width() / 2
    for i, r in enumerate(cols):
        if r.left() <= cx <= r.right():
            return i
    return -1


if __name__ == "__main__":
    raise SystemExit(main())
