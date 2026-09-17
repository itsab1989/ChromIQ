#!/usr/bin/env python3
"""Does "Show only measured patches" hide BOTH edge spacers?

Basti: *"are edge spacers also hidden by this? they should then be i think"*,
and then, on the photographs: *"still something at the top here. sometimes it
seemed at the bottom as well"*.

The page is monochrome except for two colours: the patches are magenta and the
EDGE SPACER bands are green, so what the blanking leaves behind can be counted
apart from everything else. Anything not white in the band is a leak.

    CHROMIQ_ROOT=<tree> EDGE_SIZES=700x820,... python3 drive_edge_spacer.py <tag>
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path

ROOT = Path(os.environ.get("CHROMIQ_ROOT", "/Users/Basti/develop/ChromIQ")).resolve()
sys.path.insert(0, str(ROOT))
TAG = sys.argv[1] if len(sys.argv) > 1 else "after"
SANDBOX = Path("/Users/Basti/.claude/jobs/c4ec4e71/tmp/b21-edge")
SANDBOX.mkdir(parents=True, exist_ok=True)
os.environ["CHROMIQ_SETTINGS_FILE"] = str(SANDBOX / "driver.ini")
os.environ["CHROMIQ_PRESETS_DIR"] = str(SANDBOX / "presets")

from PIL import Image, ImageChops                       # noqa: E402
from PyQt6.QtCore import QRect                          # noqa: E402
from PyQt6.QtWidgets import (QApplication, QMainWindow,  # noqa: E402
                             QVBoxLayout, QWidget)
from scripts.onscreen_capture import capture_window     # noqa: E402
from ui.styles import WinButtonLayoutStyle              # noqa: E402
from ui.tiff_preview import TiffPreview                 # noqa: E402

OUT = Path.home() / "Desktop" / "ChromIQ-beta21-proof" / "edge-spacers"
PATCH = (255, 0, 255)
EDGE = (0, 220, 0)
SIZES = os.environ.get("EDGE_SIZES", "900x1000,1200x980,760x900").split(",")


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def shoot(app, win, path, tries=10):
    prev = path.with_name(path.stem + "__prev.png")
    why, last = "", None
    for i in range(tries):
        pump(app, 400 + 250 * i)
        ok, why = capture_window(win, path, settle=0.4 + 0.15 * i)
        if not ok:
            continue
        if last is not None:
            a = Image.open(prev).convert("RGB"); b = Image.open(path).convert("RGB")
            if a.size == b.size and ImageChops.difference(a, b).getbbox() is None:
                prev.unlink(missing_ok=True); return True, ""
        last = True; path.replace(prev)
    prev.unlink(missing_ok=True)
    return False, why or "never painted the same thing twice"


def ti1(n, path):
    L = ["CTI1", "", 'DESCRIPTOR "e"', 'ORIGINATOR "ChromIQ"',
         'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
         "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
         f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        L.append(f"{i+1} {(i*7)%101} {(i*13)%101} {(i*29)%101} 40 45 50")
    L += ["END_DATA", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L)); return path


def recipe_for(name):
    """A LayoutRecipe, which is what the app stores in `channels.json`.

    NOT a dict of `build_chart` keyword names. `LayoutRecipe(**recipe)` drops
    every key that is not one of its fields, so a sidecar written with the
    build-kwarg spelling (`spacer_width` instead of `spacer_width_mm`) loses
    the value and `edge_spacer_px_from_sidecar` answers with the instrument's
    default instead of the chart's own. This driver did exactly that: it drew a
    12 px edge spacer, told the widget it was 8, and the four rows in between
    showed as the black line Basti saw in the photograph. The code was right;
    the harness was not.
    """
    from workflow.layout_engine.presets import LayoutRecipe
    # patch_first with a real patch size. `LayoutRecipe`'s own defaults are
    # `area_first` with `area_min_patch_mm` 0.0, which makes the engine collapse
    # the sheet into ONE full-width band per row: a chart with one strip, which
    # no instrument ever reads and which cannot show a per-strip fault at all.
    kw = dict(instrument="i1", edge_spacers=True, spacer_on=True,
              spacer_width_mm=1.5, layout_mode="patch_first",
              patch_w_mm=8.0, patch_h_mm=10.0)
    if name == "nolabels":
        # No strip indicators, so the chart records no label band and the strip
        # rect starts ON the first patch. That is the class where the blank's
        # top clamp actually binds, and where there are no letters to protect.
        kw["show_strip_indicators"] = False
    return LayoutRecipe(**kw)


def build(name, n=150):
    from workflow.layout_engine import chart as le
    rc = recipe_for(name)
    work = SANDBOX / "charts" / name
    stem = work / name
    if not stem.with_suffix(".strips.json").is_file():
        kw = dict(rc.build_kwargs())
        for k in ("paper", "dpi", "randomize"):
            kw.pop(k, None)
        le.build_chart(ti1(n, work / "probe.ti1"), stem, paper="A4", dpi=200,
                       randomize=False, **kw)
    strips = json.loads(stem.with_suffix(".strips.json").read_text())
    (stem.parent / f"{stem.name}.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"],
        "layout": {"engine": "chromiq", "engine_version": 1, "dpi": 200,
                   "paper_mm": [210.0, 297.0], "patches": strips["patches"],
                   "strips": strips.get("strips") or [],
                   "label_band_bottom_px": strips.get("label_band_bottom_px"),
                   "recipe": dict(rc.__dict__)}}, indent=1))
    return stem


def main():
    from ui.tabs.tab_measure import (edge_spacer_px_from_sidecar,
                                     engine_strip_rects_from_sidecar)
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    win = QMainWindow(); win.setWindowTitle(f"ChromIQ edge spacers {TAG}")
    c = QWidget(); lay = QVBoxLayout(c); lay.setContentsMargins(0, 0, 0, 0)
    prev = TiffPreview(); lay.addWidget(prev); win.setCentralWidget(c)
    win.resize(900, 1000); win.show(); pump(app, 500)

    name = os.environ.get("EDGE_CHART", "nolabels")
    stem = build(name)
    strips = json.loads(stem.with_suffix(".strips.json").read_text())
    boxes = [QRect(int(p["x"]), int(p["y"]), int(p["w"]), int(p["h"]))
             for p in strips["patches"] if int(p["page"]) == 0]
    side = stem.parent / f"{stem.name}.channels.json"
    esp = edge_spacer_px_from_sidecar(stem.with_suffix(".ti2"))
    rects = engine_strip_rects_from_sidecar(side, 1)
    cols = list(rects[0][0]) if rects else []
    print(f"{name}: {len(boxes)} patches, {len(cols)} strips, "
          f"edge spacer {esp} px", flush=True)
    if not cols or esp <= 0:
        print("!! no strips or no edge spacer; nothing to measure"); return 2

    page = stem.parent / f"{stem.name}_01.tif"
    if not page.is_file():
        page = stem.with_suffix(".tif")
    im = Image.open(page).convert("RGB"); px = im.load(); W, H = im.size
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            px[x, y] = (255, 255, 255) if (r + g + b) > 382 else (0, 0, 0)
    for b in boxes:
        for y in range(max(0, b.y()), min(H, b.y() + b.height())):
            for x in range(max(0, b.x()), min(W, b.x() + b.width())):
                px[x, y] = PATCH
    # THE EDGE SPACER BANDS, MEASURED OFF THE PAGE, NOT ASSUMED. The band is
    # whatever ink lies directly above the first patch and below the last; the
    # number the widget is told is checked against it below.
    colx = sorted({b.x() for b in boxes})
    drawn = set()
    for x0 in colx:
        cb = [b for b in boxes if b.x() == x0]
        w = cb[0].width()
        hi = min(b.y() for b in cb); lo = max(b.y() + b.height() for b in cb)
        up = hi
        while up > 0 and px[x0 + w // 2, up - 1] != (255, 255, 255):
            up -= 1
        dn = lo
        while dn < H - 1 and px[x0 + w // 2, dn] != (255, 255, 255):
            dn += 1
        drawn.add((hi - up, dn - lo))
        for y in list(range(up, hi)) + list(range(lo, dn)):
            for x in range(x0, min(W, x0 + w)):
                px[x, y] = EDGE
    print(f"  edge spacer as DRAWN (top, bottom) px: {sorted(drawn)}; "
          f"the widget is told {esp}", flush=True)
    if any(t != esp or b != esp for t, b in drawn):
        print("!! the drawn edge spacer and the reported one disagree")
    mono = SANDBOX / f"{name}-mono-{TAG}.tif"
    im.save(mono)

    def leak(img):
        """Anything in the band that is not white, in any strength."""
        q = img.load(); n = 0
        for y in range(img.height):
            for x in range(img.width):
                r, g, bl = q[x, y]
                if g > r + 18 and g > bl + 18:
                    if 88 <= x <= 128 and 8 <= y <= 48:
                        continue                 # the window's own icon
                    n += 1
        return n

    results = {}
    for spec in SIZES:
        w, h = (int(v) for v in spec.split("x"))
        win.resize(w, h); pump(app, 600)
        folder = OUT / TAG / spec; folder.mkdir(parents=True, exist_ok=True)
        for tag, on in (("blanked", True), ("plain", False)):
            prev.clear_patch_overlay(); prev.load_tiff([mono]); pump(app, 900)
            prev.set_page_patch_boxes({0: list(boxes)})
            prev.set_edge_spacer_px(esp)
            prev.set_stripe_rects(list(cols))
            prev.set_stripe_read_map({i: False for i in range(len(cols))})
            prev.set_show_only_measured(on)
            pump(app, 800)
            ok, why = shoot(app, win, folder / f"{tag}.png")
            if not ok:
                print(f"!! {spec} {tag}: CAPTURE REFUSED: {why}"); return 2
        a = Image.open(folder / "plain.png").convert("RGB")
        b = Image.open(folder / "blanked.png").convert("RGB")
        results[spec] = {"plain": leak(a), "blanked": leak(b)}
        print(f"  {spec}: edge-spacer pixels {results[spec]['plain']} plain, "
              f"{results[spec]['blanked']} with the blanking on", flush=True)
    (OUT / TAG / "facts.json").write_text(json.dumps(
        {"tag": TAG, "edge_spacer_px": esp, "drawn": sorted(drawn),
         "results": results}, indent=1))
    win.close(); pump(app, 200)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
