#!/usr/bin/env python3
"""Drive the REAL ChromIQ window over a hexagonal chart and photograph the
overlay, so the geometry can be judged by eye as well as by number.

A hexagonal chart is built into a throwaway project, opened in the Measure tab,
and the preview is grabbed three ways: plain, with the patch-by-patch highlight
on a known patch, and zoomed on that patch. If the recorded geometry and the
drawn ink ever drifted apart, the highlight would sit off its hexagon and it
would be obvious in the picture.

    python scripts/drive_hex_overlay.py [patch_mm]

Basti's preferences are copied to a throwaway .ini; nothing of his is touched.
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

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    W = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_hexoverlay_"))
    shots = sandbox / "shots"
    shots.mkdir()
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    (work / "HexChart").mkdir(parents=True)
    settings.set("custom_output_path", str(work))

    # A real hexagonal chart, built by the engine into the project folder.
    from workflow.layout_engine import chart as le_chart
    # A CHART BUILT TO BE JUDGED BY EYE.
    #
    # Every patch a flat pale grey except one, which is pure magenta. Then the
    # highlight is either on the magenta hexagon or it is not, and no colour
    # arithmetic is needed to tell — mine said the ring was on E10 while it sat
    # on G9, and only an exact colour match caught it.
    n = 210
    lines = ["CTI1", "", 'DESCRIPTOR "hex overlay probe"', 'ORIGINATOR "ChromIQ"',
             "KEYWORD \"SAMPLE_LOC\"", f"NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    MARK = 104                      # the one patch we will look for
    for i in range(n):
        r, g, b = (100.0, 0.0, 100.0) if i == MARK else (78.0, 78.0, 78.0)
        lines.append(f"{i+1} {r} {g} {b} 40.0 45.0 50.0")
    lines += ["END_DATA", ""]
    ti1 = work / "HexChart" / "probe.ti1"
    ti1.write_text("\n".join(lines))
    stem = work / "HexChart" / "HexChart"
    res = le_chart.build_chart(ti1, stem, instrument="SS", paper="A4",
                               hflag=True, pscale=W / 7.0, border=6.0,
                               dpi=200, randomize=False)
    print(f"built {res.layout.total_patches} hexagons of {W:.0f} mm, "
          f"{res.layout.passes} x {res.layout.steps_in_pass}")
    # THE SIDECAR THE APP WRITES.
    #
    # `build_chart` alone leaves only <stem>.strips.json; the chart creator also
    # folds that geometry and the recipe into <stem>.channels.json, and that is
    # the file `hex_support.chart_is_hexagonal` reads. Without it the preview
    # cannot know the chart is hexagonal, every hex feature stays off, and this
    # script would quietly test the rectangular path instead — which is exactly
    # what it did until the before/after screenshots came out byte-identical.
    import json
    strips = json.loads(stem.with_suffix(".strips.json").read_text())
    (stem.parent / f"{stem.name}.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"],
        "layout": {"engine": "chromiq", "engine_version": 1, "dpi": 200,
                   "paper_mm": [210.0, 297.0], "patches": strips["patches"],
                   "recipe": {"instrument": "SS", "hflag": True}}}))
    from workflow.hex_support import chart_is_hexagonal
    print(f"chart_is_hexagonal -> {chart_is_hexagonal(stem.with_suffix('.ti2'))}\n")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_measure)
    tab = win._tab_measure
    tab.set_ti1_path(stem.with_suffix(".ti2"))
    pump(app, 2500)

    print(f"pages loaded: {len(tab._tiff_pages)}   "
          f"patch boxes: {sum(len(d) for d in tab._patch_boxes)}   "
          f"hex mode: {tab._preview._hex_zigzag}")
    tab._preview.grab().save(str(shots / "1_chart.png"))

    # The patch-by-patch highlight, on a patch chosen from the RECORDED geometry.
    # Find the magenta patch on the SHEET, then highlight the loc the app
    # believes it is — if those disagree, the picture shows it at once.
    import numpy as np
    from PIL import Image
    page = np.asarray(Image.open(stem.with_suffix(".tif")).convert("RGB")).astype(int)
    boxes = tab._patch_boxes[0] if tab._patch_boxes else {}
    loc = ""
    for k, b in boxes.items():
        c = page[b.y() + b.height() // 2, b.x() + b.width() // 2]
        if c[0] > 180 and c[1] < 90 and c[2] > 180:
            loc = k
            break
    print(f"the magenta hexagon is the box the app labels {loc!r}")
    if loc:
        tab._preview.set_patch_click_enabled(True, tab._patch_boxes)
        tab._preview.highlight_patch(0, boxes[loc])
        pump(app, 1200)
        tab._preview.grab().save(str(shots / f"2_highlight_{loc}.png"))
        print(f"highlighted patch {loc} at {boxes[loc]}")
        # …and zoomed in, so the fit can be judged rather than guessed.
        for z in ("zoom_in",) * 3:
            if hasattr(tab._preview, z):
                getattr(tab._preview, z)()
        pump(app, 1200)
        tab._preview.grab().save(str(shots / f"3_zoom_{loc}.png"))

    print(f"\nscreenshots: {shots}")
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
