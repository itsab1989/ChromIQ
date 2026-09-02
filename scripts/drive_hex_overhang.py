#!/usr/bin/env python3
"""Drive the REAL ChromIQ window over a SpectroScan HEX chart at CR30 sizes.

Two faults sat in the path of the hexagonal layout, and both get worse as the
patches get bigger — which is exactly the direction a CR30 chart goes:

* the hex overhang (hxeh/hxew) was computed from the patch SCALE and never
  revisited when the Manual patch-size boxes or the area-first grid set the size
  directly, so a 20 mm hexagon reserved the 7 mm geometry's 1.75 mm and printed
  5 mm past it;
* the margin inspector added the ±¼·w row stagger that the recorded rects
  already carry, reporting 3 mm of margin at 12 mm — and 5 mm at 20 mm — that
  does not exist on the sheet.

    python scripts/drive_hex_overhang.py

Basti's preferences are copied to a throwaway .ini; nothing of his is touched.
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
from PIL import Image                                           # noqa: E402
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_hex_"))
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
    settings.set("use_chromiq_layout_engine", True)
    print(f"Sandbox: {sandbox}\n")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 900)
    lp = tab._manual_layout_panel
    lp._expert_frame.set_collapsed(False)

    print("SCENARIO 1 — the panel offers the SpectroScan hexagonal layout")
    lp.instr.setCurrentIndex(lp.instr.findData("SS"))
    pump(app, 600)
    modes = [lp.mode.itemData(i) for i in range(lp.mode.count())]
    check("hex" in modes, "SpectroScan offers 'Hexagonal — denser'",
          f"modes: {modes}")
    lp.mode.setCurrentIndex(lp.mode.findData("hex"))
    pump(app, 600)

    print("\nSCENARIO 2 — a CR30-sized hexagon, set the way a user sets it")
    for W in (12.0, 20.0):
        # The Manual patch-size boxes: the path that lost the overhang.
        lp.patch_x.setValue(W)
        lp.patch_y.setValue(round(W * (3 ** 0.5) / 2, 2))
        pump(app, 700)
        rec = lp.get_recipe()
        from workflow.layout_engine import instruments
        g = instruments.geom_from_build_kwargs(rec.build_kwargs())
        check(abs(g.hxew - g.pwid / 4.0) < 0.01,
              f"[{W:.0f} mm] the sides reserve the real overhang",
              f"reserves {g.hxew:.2f} mm, hexagon overhangs {g.pwid / 4.0:.2f} mm")
        check(abs(g.hxeh - g.plen / 6.0) < 0.01,
              f"[{W:.0f} mm] the apex reserves the real overhang",
              f"reserves {g.hxeh:.2f} mm, hexagon overhangs {g.plen / 6.0:.2f} mm")

    print("\nSCENARIO 3 — the sheet it builds, and what the inspector says of it")
    from workflow.layout_engine import chart as le_chart
    from workflow.margin_inspector import measure_from_engine
    ti1 = next(iter(sorted((Path.home() / "ChromIQ").glob("*/*.ti1"))), None)
    if ti1 is None:
        check(False, "a .ti1 to build from")
    else:
        for W in (12.0, 20.0):
            out = sandbox / f"hex{int(W)}"
            le_chart.build_chart(ti1, out, instrument="SS", paper="A4",
                                 hflag=True, pscale=W / 7.0, border=6.0,
                                 dpi=200, randomize=False)
            strips = json.loads((sandbox / f"hex{int(W)}.strips.json").read_text(encoding="utf-8"))
            rects = [r for r in strips["patches"] if r["page"] == 0]
            sc = sandbox / f"hex{int(W)}.channels.json"
            sc.write_text(json.dumps({"layout": {
                "engine": "chromiq", "dpi": 200, "paper_mm": [210.0, 297.0],
                "patches": rects,
                "recipe": {"instrument": "SS", "hflag": True}}}), encoding="utf-8")
            rep, _ = measure_from_engine(sc, 0)
            left_mm = min(r["x"] for r in rects) * 25.4 / 200
            check(abs(rep.left_mm - left_mm) < 0.06,
                  f"[{W:.0f} mm] the reported margin is where the hexagons are",
                  f"says {rep.left_mm:.2f} mm, leftmost hexagon at {left_mm:.2f} mm")

            # A bigger patch means more pages, so the stem gains a number.
            tif = next(iter(sorted(sandbox.glob(f"hex{int(W)}*.tif"))), None)
            im = np.asarray(Image.open(tif).convert("RGB")).astype(int)
            # every hexagon's ink must stay on the page
            ink = (im.sum(axis=2) < 735)
            xs = np.where(ink.any(axis=0))[0]
            check(xs.min() > 0 and xs.max() < im.shape[1] - 1,
                  f"[{W:.0f} mm] nothing is printed off the edge of the sheet",
                  f"ink spans columns {int(xs.min())}–{int(xs.max())} of "
                  f"{im.shape[1]}")

    bad = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    win.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
