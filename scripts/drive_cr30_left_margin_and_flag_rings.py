#!/usr/bin/env python3
"""Drive the REAL ChromIQ window for two CR30 faults Basti found on screen.

He named both in the filenames of his screenshots:

  "margins left was set to 1mm but measured from preview sections says 8,6mm"
  "red overlays for flagged patches are partly covered by other patches"

FAULT A — the left margin. A CR30 chart reserves a row-label band down the left
(`rlwi = 7.5 mm`, instruments.py), which carries the row numbers that make the
sheet a 2-D A1/B2 grid — the thing that makes finding one patch among hundreds
by hand possible at all. It is reserved OUTSIDE the user's margin, so a 1 mm
left margin puts the first patch at 8.5 mm. This drives the real Manual tab,
generates a real chart, and reads the margin back through the app's OWN
`measure_from_engine`, on the app's OWN generated file.

FAULT B — the flagged-patch rings. `TiffPreview` paints the overlay in ONE pass:
`for rect, c_exp, c_meas, warn in items:` fills the patch and then, if warn,
draws its red ring. So the NEXT item's fill lands on top of the previous item's
ring. This drives the real widget with two interlocking hexagons and counts red
pixels with the flagged patch drawn first and drawn last. If draw order changes
the count, the ring is being overpainted — which one pass can never avoid.

Basti's preferences are copied to a throwaway .ini and his ChromIQ root is
replaced by a sandbox. Nothing of his is touched.

    python scripts/drive_cr30_left_margin_and_flag_rings.py
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QRect, QSettings                       # noqa: E402
from PyQt6.QtGui import QColor, QFontDatabase                   # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "cr30-margin-and-rings"
LEFT_MM, TOP_MM, RIGHT_MM, BOTTOM_MM = 1.0, 6.0, 2.0, 1.0


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(w, name):
    SHOTS.mkdir(parents=True, exist_ok=True)
    p = SHOTS / f"{name}.png"
    w.grab().save(str(p))
    print(f"    saved {p}")
    return p


# ---------------------------------------------------------------- fault B
def fault_b(app, payload) -> None:
    """Two interlocking hexagons, one flagged. Does draw ORDER change the ring?

    Loaded through the widget's OWN `load_tiff`, on the REAL CR30 hexagonal
    chart fault A just generated -- faking `_pages` with a bare QPixmap is not
    the page shape the widget keeps, and a stand-in that cannot even be
    displayed proves nothing about what the displayed thing does.
    """
    from ui.tiff_preview import TiffPreview
    print("\nFAULT B — flagged rings, on the real TiffPreview widget")
    tiffs, boxes = payload
    if not tiffs or len(boxes) < 2:
        print("    no chart to draw on; skipped.")
        return
    (loc_a, ax, ay, aw, ah), (loc_b, bx, by, bw, bh) = boxes
    print(f"    {loc_a} at y={ay}..{ay+ah}, {loc_b} at y={by}..{by+bh} — "
          f"touching, and a hexagon overshoots its slot by h/6 = {ah//6} px, "
          "so they interlock")

    # COUNT THE DIFFERENCE, NOT THE COLOUR. A first attempt counted red pixels
    # in the whole widget -- and the CHART is full of red patches, so 142 real
    # pixels of ring sat inside 37,000 of artwork and could not be attributed.
    # The two renders differ in NOTHING except the order the two items are
    # drawn in, so any pixel that differs IS the covering.
    def render(flag_first: bool):
        pv = TiffPreview()
        pv.resize(1100, 900)
        pv.load_tiff([Path(tiffs[0])])
        pump(app, 900)
        pv._hex_zigzag = True
        a = QRect(ax, ay, aw, ah)
        b = QRect(bx, by, bw, bh)
        flagged = (a, QColor("#3050ff"), QColor("#3050ff"), True)
        plain = (b, QColor("#20c060"), QColor("#20c060"), False)
        items = [flagged, plain] if flag_first else [plain, flagged]
        pv.set_patch_overlay(0, items, replace_page=True)
        pv.show()
        pump(app, 800)
        shot(pv, f"faultB_flagged_{'first' if flag_first else 'last'}")
        im = pv.grab().toImage()
        pv.close()
        return im

    im_first = render(True)
    im_last = render(False)
    assert im_first.size() == im_last.size(), "the two renders differ in size"
    RED = QColor("#ff2b2b")
    diff = red_lost = 0
    for y in range(im_first.height()):
        for x in range(im_first.width()):
            c1, c2 = im_first.pixelColor(x, y), im_last.pixelColor(x, y)
            if c1 != c2:
                diff += 1
                # a pixel that is ring-red when the flagged patch is drawn LAST
                # and something else when it is drawn FIRST = ring lost
                if (abs(c2.red() - RED.red()) < 45 and c2.green() < 100
                        and c2.blue() < 100):
                    red_lost += 1
    print(f"    pixels differing between the two draw orders : {diff}")
    print(f"    ... of those, ring-red only when drawn LAST  : {red_lost}")
    if red_lost > 0:
        print("    -> PROVEN: the ring is painted over by a patch drawn after it. "
              "One pass cannot avoid this, whatever the ring width.")
    else:
        print("    -> NOT reproduced. Report the numbers; do not conclude.")
    return


def _unused_red_pixels():
    return


# ---------------------------------------------------------------- fault A
def fault_a(app) -> int:
    from PyQt6.QtGui import QFontDatabase as _f  # noqa: F401
    print("\nFAULT A — the left margin, in the real window")

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_cr30_margin_"))
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    print(f"    sandbox: {sandbox}")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    TabChart._prompt_target_name = lambda self, *a, **k: "cr30-margin"

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)

    tab._user_switch_mode("manual")
    pump(app, 800)
    pnl = tab._manual_layout_panel

    i = pnl.instr.findData("CR30")
    assert i >= 0, "the CR30 is not offered"
    pnl.instr.setCurrentIndex(i)
    pump(app, 800)
    for key, val in (("t", TOP_MM), ("r", RIGHT_MM),
                     ("b", BOTTOM_MM), ("l", LEFT_MM)):
        pnl.margins[key].setValue(val)
    pump(app, 500)
    print(f"    set on screen: left={pnl.margins['l'].value()} "
          f"top={pnl.margins['t'].value()} right={pnl.margins['r'].value()} "
          f"bottom={pnl.margins['b'].value()}")
    shot(win, "faultA_settings_on_screen")

    tab._target_name_edit.setText("cr30-margin")
    pump(app, 300)
    tab._on_generate()
    for _ in range(120):
        pump(app, 500)
        if getattr(tab, "_margin_ti2", None):
            break
    ti2 = getattr(tab, "_margin_ti2", None)
    print(f"    generated: {ti2}")
    if not ti2:
        print("    -> the chart did not build; nothing to measure. STOP.")
        win.close()
        return 1, ([], [])
    pump(app, 2500)
    shot(win, "faultA_after_generate")

    from workflow.margin_inspector import measure_from_engine
    ch = Path(ti2).with_suffix(".channels.json")
    eng = measure_from_engine(ch, 0) if ch.is_file() else None
    if eng is None:
        print("    -> no engine report; the app would fall back to the image.")
        win.close()
        return 1, ([], [])
    rep, _ = eng
    print(f"    MEASURED left   : {rep.left_mm:.2f} mm   (set {LEFT_MM})")
    print(f"    MEASURED right  : {rep.right_mm:.2f} mm   (set {RIGHT_MM})")
    print(f"    MEASURED top    : {rep.top_mm:.2f} mm   (set {TOP_MM})")
    print(f"    MEASURED bottom : {rep.bottom_mm:.2f} mm   (set {BOTTOM_MM})")
    gap = rep.left_mm - LEFT_MM
    print(f"    left overshoot  : {gap:.2f} mm   (rlwi is 7.5 mm)")
    print("    -> PROVEN: the row-label band sits OUTSIDE the margin"
          if gap > 5.0 else "    -> not reproduced; report the numbers.")
    tiffs = list(getattr(tab, "_margin_tiffs", []) or [])
    import json as _json
    _lay = _json.loads(ch.read_text())["layout"]["patches"]
    boxes = [(p["loc"], p["x"], p["y"], p["w"], p["h"])
             for p in _lay if p.get("page") == 0][:2]
    print(f"    two REAL neighbours from the chart: {boxes}")
    win.close()
    pump(app, 400)
    return 0, (tiffs, boxes)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    rc, tiffs = fault_a(app)
    fault_b(app, tiffs)
    print(f"\nscreenshots in {SHOTS}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
