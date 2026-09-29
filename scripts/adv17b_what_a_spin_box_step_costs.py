#!/usr/bin/env python3
"""Adversary 17b: what ONE step of the bottom-margin spin box really costs.

**A PROBE THAT ASKS THE SAME QUESTION TWICE MEASURES A CACHE.** My first
attempt called `_engine_text_notes` fifteen times on an UNCHANGED panel and
reported 9.7 ms. Measured again with the margin DIFFERENT every time, one
geometry rebuild costs 16 ms cold against 0.7 ms warm, and
`margin_rise_that_clears_mm` does about a dozen of them -- so the number that
matters is the one a person turning the box actually pays, and every candidate
margin it tries is new on every step.

Two layouts, because they are not the same machine:

* Knut's CR30 preset, which PINS the patch size, so `area_fit` is skipped;
* a plain area-first chart with the patch size on auto, which is
  `LayoutRecipe`'s own default and where `area_fit.derive_area_patch_size`
  runs for every candidate.

Each is timed with the warning up and with it down, stepping the real spin box.
"""
from __future__ import annotations

import json
import os
import statistics
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
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17bspin-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("margin_violation_notify", True)):
        settings.set(k, v)
    assert settings.get("custom_output_path", "") == str(work)
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1060)
    win.show(); win.raise_(); pump(app, 2500)
    print(f"    window on screen: {win.isVisible()}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    panel = tab._manual_layout_panel
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    panel.chart_text.setText("a bottom line of sheet text")
    pump(app, 400)

    rows = {}

    def step_and_time(label, n=12, start=9.0):
        """Turn the box one 0.5 mm step at a time and time the notes each time."""
        ts, warned = [], []
        for k in range(n):
            panel.margins["b"].setValue(start + 0.5 * k)   # a DIFFERENT margin
            pump(app, 250)
            t0 = time.perf_counter()
            _w, over = TabChart._engine_text_notes(tab)
            ts.append((time.perf_counter() - t0) * 1000.0)
            warned.append(any("into the patches" in m for m in over))
        rows[label] = {"warning_up_on": sum(warned), "of": n,
                       "median_ms": round(statistics.median(ts), 1),
                       "max_ms": round(max(ts), 1),
                       "each_ms": [round(t, 1) for t in ts]}
        print(f"    {label:46s} warned {sum(warned)}/{n}  "
              f"median {rows[label]['median_ms']} ms  "
              f"max {rows[label]['max_ms']} ms", flush=True)

    j = panel.layout_mode.findData("area_first")
    panel.layout_mode.setCurrentIndex(j); pump(app, 500)
    panel.chart_text_size.setValue(0.0); pump(app, 400)
    step_and_time("his preset (patch size pinned), quiet")
    panel.chart_text_size.setValue(40.0); pump(app, 400)
    step_and_time("his preset (patch size pinned), WARNING")

    # …and the same with the patch size on auto, which is the recipe default
    # and the one `area_fit` has to solve for every candidate margin.
    panel.patch_x.setValue(0.0)
    panel.patch_y.setValue(0.0)
    jm = panel.area_method.findData("by_width")
    if jm >= 0:
        panel.area_method.setCurrentIndex(jm)
    panel.area_cols.setValue(0); panel.area_rows.setValue(0)
    pump(app, 600)
    r = panel.get_recipe()
    print(f"    patch size now: w={r.patch_w_mm} h={r.patch_h_mm} "
          f"method={r.area_method} cols={r.area_cols} rows={r.area_rows}",
          flush=True)
    panel.chart_text_size.setValue(0.0); pump(app, 400)
    step_and_time("patch size on AUTO (area_fit solves), quiet")
    panel.chart_text_size.setValue(40.0); pump(app, 400)
    step_and_time("patch size on AUTO (area_fit solves), WARNING")

    ok, why = capture_window(win, out / "06-what-a-spin-box-step-costs.png")
    (out / "what-a-spin-box-step-costs.json").write_text(json.dumps(
        {"rows": rows,
         "photo": "06-what-a-spin-box-step-costs.png" if ok else f"REFUSED {why}",
         "locked": session_is_locked()}, indent=2), encoding="utf-8")
    print(f"    photo: {'ok' if ok else 'REFUSED ' + str(why)}", flush=True)
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
