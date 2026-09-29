#!/usr/bin/env python3
"""D03 (A3 + A4): layout modes, margins, alignment, strip length, and a
threshold change made through the real Preferences dialog.

Each step: set the controls, read the estimate + margin panel BEFORE Generate,
Generate, read everything AFTER, save a window shot. Project A3-LayoutModes,
Manual, engine ON, i1Pro A4 unless stated."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialogButtonBox  # noqa: E402

OUT3 = L.SHOTS / "A3-layout-modes"
OUT4 = L.SHOTS / "A4-margins"
PROJECT = "A3-LayoutModes"
RESULTS = []


def pw(tab, tool, flag):
    for w in tab._manual_widgets.get(tool, []):
        if w.flag == flag:
            return w


def set_auto(tab, on: bool, n: int | None = None):
    auto = tab._manual_auto_patches_check
    if auto.isChecked() != on:
        auto.click()
        L.pump(200)
    if not on and n is not None:
        pw(tab, "targen", "-f").set_value(n)
        L.pump(200)


def step(tag, win, tab, watcher, out, setup, note=""):
    panel = tab._manual_layout_panel
    L.log(f"--- {tag}: {note}")
    setup(panel)
    L.pump(700)
    before = L.panel_snapshot(tab)
    rec = L.recipe_of(tab)
    margins_ui = {k: (v.value(), v.isEnabled()) for k, v in panel.margins.items()}
    L.grab(win, out / f"{tag}-before.png")
    watcher.expect("quite fill", "OK")
    watcher.expect("already", "Continue this project")
    n0 = len(L.SERIOUS)
    t0 = time.time()
    L.click(tab._generate_btn)
    ok = L.wait_build(tab, 300_000)
    watcher.clear()
    after = L.panel_snapshot(tab)
    L.grab(win, out / f"{tag}-after.png")
    logtxt = L.tab_log_text(tab)
    eng = [l for l in logtxt.splitlines() if "layout engine]" in l or "[ERROR]" in l][-5:]
    rd = L.current_run_dir(win)
    inv = L.run_inventory(rd) if rd else {}
    r = {"tag": tag, "note": note, "ok": ok, "secs": round(time.time() - t0, 1),
         "estimate_before": before["layout_info_estimate"],
         "actual_after": after["layout_info_actual"],
         "estimate_after": after["layout_info_estimate"],
         "margin_before": {"status": before["margin_status"], "notes": before["margin_notes"], "text": before["margin_panel_text"][:400]},
         "margin_after": {"status": after["margin_status"], "visible": after["margin_status_visible"], "notes": after["margin_notes"], "text": after["margin_panel_text"][:400]},
         "margins_ui": margins_ui,
         "recipe": {k: rec.get(k) for k in ("layout_mode", "area_method", "area_cols", "area_rows", "area_ratio", "area_min_patch_mm",
                                            "patch_w_mm", "patch_h_mm", "pscale", "margin_top", "margin_right", "margin_bottom", "margin_left",
                                            "use_instrument_margins", "patch_area_align", "clip_border", "nolimit", "max_strip_mm", "paper")},
         "engine_log": eng, "serious": L.serious_since(n0),
         "ti2": {k: v for k, v in inv.items() if k.startswith("ti2")},
         "n_tiffs": len(inv.get("tiffs") or []),
         "dialogs": [d.get("answer") for d in watcher.seen[-2:]],
         "unexpected": list(watcher.unexpected)}
    watcher.unexpected.clear()
    RESULTS.append(r)
    L.save_json(RESULTS, L.LOGS / "d03_results.json")
    L.log(f"    est_before={r['estimate_before']}\n    actual={r['actual_after']}\n    est_after={r['estimate_after']}\n    margin_after={r['margin_after']['status']!r} notes={r['margin_after']['notes']!r}")
    return r


def drive_settings(win, fn, label):
    """Open the real Preferences dialog (modal exec) and let fn edit it, then
    press its OK button. The timer first asserts it is the Settings dialog."""
    app = QApplication.instance()
    state = {"done": False, "err": None}

    def tick():
        dlg = app.activeModalWidget()
        if dlg is None or type(dlg).__name__ != "SettingsDialog":
            QTimer.singleShot(150, tick)
            return
        try:
            L.log(f"  Preferences dialog open: title={dlg.windowTitle()!r}")
            fn(dlg)
            L.pump(400)
            L.grab(dlg, L.SHOTS / "A4-margins" / f"prefs-{label}.png")
            bb = dlg.findChild(QDialogButtonBox)
            okb = bb.button(QDialogButtonBox.StandardButton.Ok) or bb.button(QDialogButtonBox.StandardButton.Save)
            L.log(f"  clicking Preferences button {okb.text()!r}")
            okb.click()
        except Exception as e:  # noqa: BLE001
            state["err"] = repr(e)
            L.log(f"  settings drive error {e!r}")
            dlg.reject()
        state["done"] = True

    QTimer.singleShot(200, tick)
    win._open_settings()
    L.pump(800)
    return state


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn)
    L.pump(400)
    tab._manual_target_name_edit.setText(PROJECT)
    tab._manual_target_name_edit.editingFinished.emit()
    L.pump(300)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    panel = tab._manual_layout_panel
    L.set_combo_data(panel.instr, "i1")
    L.set_combo_data(panel.paper, "A4")
    L.set_combo_data(panel.mode, "clip")
    L.set_spin(panel.pages, 1)
    set_auto(tab, True)
    watcher.expect("Give this project a name", "<reject>")

    def base(p):
        L.set_combo_data(p.layout_mode, "area_first")
        L.set_combo_data(p.area_method, "by_width")
        L.set_spin(p.area_min_patch, 0.0)
        L.set_spin(p.area_ratio, 100.0)
        L.set_spin(p.area_cols, 0); L.set_spin(p.area_rows, 0)
        L.set_spin(p.patch_x, 0.0); L.set_spin(p.patch_y, 0.0)
        L.set_spin(p.pscale, 1.0)
        L.set_combo_data(p.patch_align, "top-left")
        L.set_check(p.use_instr_margins, True)
        L.set_check(p.nolimit, False)
        L.set_spin(p.max_strip, 0.0)

    # ---- A3 layout modes (Auto count) ----
    step("m01-area-bywidth-auto", win, tab, watcher, OUT3, base, "area-first, by width, min auto")
    step("m02-area-bywidth-min12", win, tab, watcher, OUT3, lambda p: (base(p), L.set_spin(p.area_min_patch, 12.0)), "area-first by width, min patch width 12 mm")
    step("m03-area-grid-cols10", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.area_method, "by_grid"), L.set_spin(p.area_cols, 10), L.set_spin(p.area_rows, 0)), "by grid, 10 columns, rows auto")
    step("m04-area-grid-rows20", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.area_method, "by_grid"), L.set_spin(p.area_cols, 0), L.set_spin(p.area_rows, 20)), "by grid, cols auto, 20 rows")
    step("m05-area-grid-12x18", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.area_method, "by_grid"), L.set_spin(p.area_cols, 12), L.set_spin(p.area_rows, 18)), "by grid, 12 cols x 18 rows pinned")
    step("m06-area-ratio150", win, tab, watcher, OUT3, lambda p: (base(p), L.set_spin(p.area_ratio, 150.0)), "area-first, height 150 % of width")
    step("m07-patchfirst-auto", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.layout_mode, "patch_first")), "patch-first, size auto")
    step("m08-patchfirst-15x15", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.layout_mode, "patch_first"), L.set_spin(p.patch_x, 15.0), L.set_spin(p.patch_y, 15.0)), "patch-first, 15 x 15 mm")
    step("m09-patchfirst-scale2", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.layout_mode, "patch_first"), L.set_spin(p.pscale, 2.0)), "patch-first, patch scale 2.0")
    step("m10-patchfirst-align-center", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.layout_mode, "patch_first"), L.set_combo_data(p.patch_align, "center")), "patch-first, align centre")
    step("m11-patchfirst-align-bottomright", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.layout_mode, "patch_first"), L.set_combo_data(p.patch_align, "bottom-right")), "patch-first, align bottom-right")
    # fixed count variants (F-001 scope)
    set_auto(tab, False, 300)
    step("m12-area-fixed300", win, tab, watcher, OUT3, base, "area-first by width, FIXED -f 300")
    step("m13-patchfirst-fixed300", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.layout_mode, "patch_first")), "patch-first, FIXED -f 300")
    step("m14-grid12x18-fixed300", win, tab, watcher, OUT3, lambda p: (base(p), L.set_combo_data(p.area_method, "by_grid"), L.set_spin(p.area_cols, 12), L.set_spin(p.area_rows, 18)), "by grid 12x18 pinned, FIXED -f 300")
    set_auto(tab, True)

    # ---- A4 margins ----
    def own(p, t, r, b, l):
        base(p)
        L.set_check(p.use_instr_margins, False)
        L.set_spin(p.margins["t"], t); L.set_spin(p.margins["r"], r)
        L.set_spin(p.margins["b"], b); L.set_spin(p.margins["l"], l)
    step("g01-own-6666", win, tab, watcher, OUT4, lambda p: own(p, 6, 6, 6, 6), "own margins 6/6/6/6, instrument margins off")
    step("g02-own-0000", win, tab, watcher, OUT4, lambda p: own(p, 0, 0, 0, 0), "own margins 0/0/0/0")
    step("g03-own-60606060", win, tab, watcher, OUT4, lambda p: own(p, 60, 60, 60, 60), "own margins 60/60/60/60 (max)")
    step("g04-own-20-clipside-5", win, tab, watcher, OUT4, lambda p: own(p, 20, 20, 20, 5), "own margins 20/20/20 and left 5 (under the clip band)")
    step("g05-instr-back-on", win, tab, watcher, OUT4, base, "instrument margins back on (restores 38/9/19/26?)")
    # strip length
    step("g06-A3-portrait-ruler", win, tab, watcher, OUT4, lambda p: (base(p), L.set_combo_data(p.paper, "A3")), "i1 A3 portrait, 43-patch strips: ruler note?")
    step("g07-A3-maxstrip200", win, tab, watcher, OUT4, lambda p: (base(p), L.set_combo_data(p.paper, "A3"), L.set_spin(p.max_strip, 200.0)), "A3 portrait, Max strip 200 mm")
    step("g08-A3-nolimit", win, tab, watcher, OUT4, lambda p: (base(p), L.set_combo_data(p.paper, "A3"), L.set_spin(p.max_strip, 0.0), L.set_check(p.nolimit, True)), "A3 portrait, Don't cap strip length")
    L.set_combo_data(panel.paper, "A4")
    L.set_check(panel.nolimit, False)

    # ---- threshold change through the real Preferences dialog ----
    before_thr = dict(settings.get_margin_thresholds().get("i1Pro|A4 Portrait", {}))
    L.log(f"thresholds i1Pro|A4 Portrait before: {before_thr}")

    def edit(dlg):
        tabs = dlg._tabs
        for i in range(tabs.count()):
            if "Instrument Limits" in tabs.tabText(i):
                tabs.setCurrentIndex(i)
        L.pump(300)
        L.set_combo_text(dlg._margin_instr, "i1Pro")
        L.set_combo_text(dlg._margin_paper, "A4 Portrait")
        L.pump(300)
        L.log(f"  dialog fields before edit: { {k: v.value() for k, v in dlg._margin_fields.items()} } ruler={dlg._margin_ruler.value()} ({dlg._margin_ruler.specialValueText()!r})")
        dlg._margin_fields["T"].setValue(50.0)
        dlg._margin_fields["T"].editingFinished.emit()
        dlg._margin_ruler.setValue(200.0)
        dlg._margin_ruler.editingFinished.emit()
        L.pump(300)

    st = drive_settings(win, edit, "i1-A4-top50-ruler200")
    L.pump(1000)
    after_thr = dict(settings.get_margin_thresholds().get("i1Pro|A4 Portrait", {}))
    L.log(f"thresholds after: {after_thr}  drive={st}")
    snap = L.panel_snapshot(tab)
    L.log(f"panel margins now: { {k: v.value() for k, v in panel.margins.items()} } use_instr={panel.use_instr_margins.isChecked()}")
    L.log(f"estimate now (no regenerate): {snap['layout_info_estimate']}  margin status: {snap['margin_status']!r} notes={snap['margin_notes']!r}")
    L.grab(win, OUT4 / "g09-after-threshold-change-before-generate.png")
    RESULTS.append({"tag": "g09-threshold-change", "before_thr": before_thr, "after_thr": after_thr,
                    "panel_margins": {k: v.value() for k, v in panel.margins.items()},
                    "estimate_no_regen": snap["layout_info_estimate"], "margin_status": snap["margin_status"],
                    "margin_notes": snap["margin_notes"], "drive": st})
    step("g10-generate-after-threshold", win, tab, watcher, OUT4, lambda p: None, "Generate with T=50 / ruler 200 thresholds")

    # restore the threshold through the dialog again
    def restore(dlg):
        tabs = dlg._tabs
        for i in range(tabs.count()):
            if "Instrument Limits" in tabs.tabText(i):
                tabs.setCurrentIndex(i)
        L.set_combo_text(dlg._margin_instr, "i1Pro")
        L.set_combo_text(dlg._margin_paper, "A4 Portrait")
        L.pump(200)
        dlg._margin_fields["T"].setValue(float(before_thr.get("T", 38)))
        dlg._margin_fields["T"].editingFinished.emit()
        dlg._margin_ruler.setValue(float(before_thr.get("ruler", 0) or 0))
        dlg._margin_ruler.editingFinished.emit()
    drive_settings(win, restore, "restore")
    L.log(f"thresholds restored: {settings.get_margin_thresholds().get('i1Pro|A4 Portrait')}")
    L.save_json(RESULTS, L.LOGS / "d03_results.json")
    L.log(f"unexpected: {watcher.unexpected}  serious: {L.serious_since(0)}")
    win.close()
    L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
