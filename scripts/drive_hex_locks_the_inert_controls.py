#!/usr/bin/env python3
"""Drive the REAL ChromIQ window for Knut's hexagon report (4.1.5-beta.10).

    *"When I try to make hexagonal patches on a chart for CR30, and setting in
    the layout engine Calculation method 'By columns / rows…', then changing the
    patches per strip has no function or effect. When 15 strips the patch width
    is 10.9 mm, and there is 28 rows, no matter what I set on patches per
    strip."*

Two things are shown on screen, in the app, not in a harness:

  1. THE REPORT IS TRUE. Create Chart > Manual, CR30, Hexagonal, area-first,
     "By columns / rows", 15 strips: the app's own patch-count readout does not
     move as "Patches per strip" is swept, and neither does the patch size the
     app's own layout panel would hand the engine.
  2. THE FIX IS VISIBLE. The row is greyed, and the reason is on an info button
     that still works, because a disabled QWidget receives no hover events and a
     tooltip parked on the greyed spin box may never be shown at all.

The "before" shot is taken with `_update_area_hex_locks` neutered, which is
exactly the state of the code before this change: that method IS the change, and
nothing else in the panel was touched. Said plainly rather than pretending the
screenshot came off another checkout.

SETTINGS ARE SANDBOXED BEFORE ANYTHING IS IMPORTED. `CHROMIQ_SETTINGS_FILE` is
set at the top of this file, so `AppSettings` physically cannot reach the real
preference store (`core/settings.py`). Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

    python scripts/drive_hex_locks_the_inert_controls.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# BEFORE any ChromIQ import: the settings store this run may touch.
_SANDBOX = Path(tempfile.mkdtemp(prefix="chromiq_hexlock_"))
os.environ["CHROMIQ_SETTINGS_FILE"] = str(_SANDBOX / "settings.ini")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

SHOTS = Path.home() / "Desktop" / "beta 9" / "hex-layout-controls"
ROWS_SWEEP = (10, 20, 28, 40)


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


def _derived(panel):
    """What the panel's OWN recipe makes the engine do: (w, h, strips, rows)."""
    from workflow.layout_engine import area_fit, geometry, instruments, papers
    r = panel.get_recipe()
    kw = r.build_kwargs()
    size = area_fit.derive_area_patch_size(kw)
    if size is None:
        return None
    pw, ph = size
    g = instruments.geom_from_build_kwargs({**kw, "patch_w": pw, "patch_h": ph})
    w_mm, h_mm = papers.dimensions_mm(r.paper)
    lay = geometry.compute(g, w_mm, h_mm, 100_000)
    cols = lay.patches_per_page // lay.steps_in_pass if lay.steps_in_pass else 0
    return (round(pw, 2), round(ph, 2), cols, lay.steps_in_pass,
            lay.patches_per_page)


def run(app) -> int:
    from core.settings import AppSettings
    settings = AppSettings()
    work = _SANDBOX / "ChromIQ"
    work.mkdir()
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    print(f"    sandbox: {_SANDBOX}")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.dialogs.layout_options_panel import LayoutOptionsPanel
    from ui.main_window import MainWindow
    from ui.tooltip_button import TooltipButton

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 600)
    tab._user_switch_mode("manual")
    pump(app, 900)
    pnl = tab._manual_layout_panel

    # ---- Knut's selection, made through the real widgets ------------------
    pnl.instr.setCurrentIndex(pnl.instr.findData("CR30"))
    pump(app, 700)
    pnl.mode.setCurrentIndex(pnl.mode.findData("hex"))
    pump(app, 500)
    pnl.layout_mode.setCurrentIndex(pnl.layout_mode.findData("area_first"))
    pump(app, 400)
    pnl.area_method.setCurrentIndex(pnl.area_method.findData("by_grid"))
    pump(app, 400)
    pnl.area_cols.setValue(15)
    pump(app, 500)
    print(f"    on screen: {pnl.instr.currentText()} / "
          f"{pnl.mode.currentText()} / {pnl.area_method.currentText()} / "
          f"{pnl.area_cols.value()} strips")

    # ---- 1. the report, swept in the running app --------------------------
    print("\n1. IS 'Patches per strip' INERT? (real panel, real recipe)")
    seen = set()
    for rows in ROWS_SWEEP:
        pnl.area_rows.setValue(rows)
        pump(app, 400)
        d = _derived(pnl)
        count = tab._patch_count_lbl.text()
        seen.add(d)
        print(f"    patches per strip = {rows:3d} -> patch {d[0]} x {d[1]} mm, "
              f"{d[2]} strips of {d[3]} = {d[4]}   (app readout: {count!r})")
    verdict = "INERT, Knut is right" if len(seen) == 1 else "it moves"
    print(f"    -> {verdict}")

    # ---- 2. before / after, on screen -------------------------------------
    print("\n2. THE PANEL, BEFORE AND AFTER")
    real = LayoutOptionsPanel._update_area_hex_locks
    LayoutOptionsPanel._update_area_hex_locks = lambda self, *a: None
    try:
        pnl.area_rows.setEnabled(True)
        for w in pnl._area_row_rows:
            w.setEnabled(True)
            if isinstance(w, TooltipButton):
                w.set_live_note("")
        pump(app, 500)
        shot(win, "before_window")
        shot(pnl._area_fields_w, "before_area_fields")
        print(f"    before: 'Patches per strip' enabled = "
              f"{pnl.area_rows.isEnabled()}")
    finally:
        LayoutOptionsPanel._update_area_hex_locks = real
    pnl._update_area_hex_locks()
    pump(app, 500)
    shot(win, "after_window")
    shot(pnl._area_fields_w, "after_area_fields")
    tip = [w for w in pnl._area_row_rows if isinstance(w, TooltipButton)][0]
    print(f"    after : 'Patches per strip' enabled = "
          f"{pnl.area_rows.isEnabled()}, info button enabled = "
          f"{tip.isEnabled()}")
    print(f"    hover tip: {tip.toolTip()!r}")

    # …and the dialog behind it, which is the thing a greyed spin box could
    # never have popped: click the info button and photograph what opens.
    grabbed = {}

    def _exec_and_grab(self):
        self.show()
        pump(app, 500)
        grabbed["d"] = shot(self, "after_rows_info_dialog")
        self.close()
        return 1

    QDialog.exec = _exec_and_grab                      # type: ignore[assignment]
    tip.click()
    pump(app, 400)
    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    print(f"    info dialog captured: {bool(grabbed)}")

    # ---- 3. the other half: the height % in 'By patch width' --------------
    print("\n3. 'Minimum patch height (% of width)' IN 'By patch width'")
    pnl.area_method.setCurrentIndex(pnl.area_method.findData("by_width"))
    pump(app, 600)
    rtip = [w for w in pnl._area_row_ratio if isinstance(w, TooltipButton)][0]
    print(f"    hexagonal: enabled = {pnl.area_ratio.isEnabled()}, "
          f"info button enabled = {rtip.isEnabled()}")
    shot(pnl._area_fields_w, "after_by_width_hex")
    pnl.mode.setCurrentIndex(pnl.mode.findData("flat"))
    pump(app, 600)
    print(f"    rectangular: enabled = {pnl.area_ratio.isEnabled()} "
          f"(must be True), note = {rtip.live_note()!r}")
    shot(pnl._area_fields_w, "after_by_width_rectangular")

    win.close()
    pump(app, 400)
    return 0 if len(seen) == 1 else 1


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    rc = run(app)
    print(f"\nscreenshots in {SHOTS}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
