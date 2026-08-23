#!/usr/bin/env python3
"""Prove what Knut counted: the preview draws TWO combs at once.

A sheet is generated with "Markers per patch" = 3, so the TIFF carries three
printed dashes per patch. The spin box is then raised to 4, 5 and 6 without
pressing Generate Chart again — which is what a user does while judging the
setting. The live overlay draws the NEW comb on top of the PRINTED one, and the
sheet on screen shows the union of the two:

    set 3  ->  3 dashes per patch          (they coincide)
    set 4  ->  5 dashes, 3 of them inside the patch, unevenly spaced
    set 5  ->  5 dashes, evenly spaced
    set 6  ->  7 dashes, unevenly spaced

which is his report word for word. The dashes are counted off the REAL preview
widget's pixels, not off the geometry.

    python scripts/drive_marker_overlay_union.py [--out DIR]
"""
from __future__ import annotations

import json
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

import numpy as np                                              # noqa: E402
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
TI1 = ROOT / "tests/fixtures/charts/cm_a4_480p_2pages.ti1"
PRINTED_COUNT = 3          # what the sheet is generated with


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def dashes_down_the_left_edge(widget) -> list[float]:
    """Y positions (widget pixels) of the dashes along the sheet's left edge."""
    img = widget.grab().toImage()
    w, h = img.width(), img.height()
    arr = np.frombuffer(img.constBits().asstring(img.sizeInBytes()), np.uint8)
    arr = arr.reshape(h, img.bytesPerLine() // 4, 4)[:, :w, :3].astype(int)
    # The page sits inside the widget; find the sheet's white body first.
    white = (arr.min(axis=2) > 200).sum(axis=0)
    cols = np.where(white > h * 0.5)[0]
    if len(cols) < 20:
        return []
    x0 = cols.min()
    # A narrow band just inside the left paper edge, where the dashes live.
    band = arr[:, x0 + 2:x0 + int((cols.max() - x0) * 0.06) + 3]
    dark = np.where(band.min(axis=2).min(axis=1) < 110)[0]
    runs: list[list[int]] = []
    for y in dark:
        if runs and y - runs[-1][-1] <= 2:
            runs[-1].append(y)
        else:
            runs.append([y])
    return [sum(r) / len(r) for r in runs]


def main() -> int:
    out = Path.home() / "Desktop" / "chromiq-knut-repro"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_union_"))
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

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    # ---- the sheet the user is looking at: built WITH markers, count = 3 ----
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine.presets import default_recipe
    rec = default_recipe("CM", "A4", mode="freehand")
    rec.helper_markers = True
    rec.helper_marker_edge_mm = 2.0
    rec.helper_marker_len_mm = 4.0
    rec.helper_marker_per_patch = PRINTED_COUNT
    res = le_chart.build_chart(TI1, sandbox / "sheet", **rec.build_kwargs())
    ti2 = Path(res.ti2_path)
    ti2.with_suffix(".channels.json").write_text(json.dumps({
        "layout": {"engine": "chromiq", "seed": res.seed, "recipe": rec.to_dict()},
    }, indent=2), encoding="utf-8")
    tif = Path(res.tiff_paths[0])
    print(f"Sheet built with {PRINTED_COUNT} markers per patch: {tif.name}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1600, 1000)
    win.show()
    pump(app, 2500)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 900)
    lp = tab._manual_layout_panel
    lp._expert_frame.set_collapsed(False)
    lp.instr.setCurrentIndex(lp.instr.findData("CM"))
    pump(app, 500)

    tab._preview.set_notice(None)
    tab._preview.load_tiff([tif])
    tab._set_margin_chart([tif], ti2)
    lp.helper_markers_cb.setChecked(True)
    lp.helper_marker_edge.setValue(2.0)
    lp.helper_marker_len.setValue(4.0)
    pump(app, 1200)

    print("\nWhat the user counts on the sheet in front of them:")
    print("(the printed comb is fixed at 3; only the spin box moves)\n")
    for n in (3, 4, 5, 6):
        lp.helper_marker_per_patch.setValue(n)
        tab._refresh_helper_marker_overlay()
        pump(app, 900)
        ys = dashes_down_the_left_edge(tab._preview)
        gaps = [round(b - a, 1) for a, b in zip(ys, ys[1:])]
        mid = gaps[len(gaps) // 3: len(gaps) // 3 + 8]
        print(f"  spin box = {n}:  {len(ys)} dashes down the page, "
              f"gaps (px) {mid}")
        tab._preview.grab().save(str(out / f"overlay_union_{n}.png"))

    print(f"\nScreenshots: {out}")
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
