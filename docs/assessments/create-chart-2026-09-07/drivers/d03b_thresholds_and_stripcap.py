#!/usr/bin/env python3
"""D03b: (1) change the i1Pro A4 Portrait threshold (Top 38 -> 50, ruler
instrument default -> 200 mm) through the REAL Preferences dialog, and see
whether the panel margins, the estimate and the built chart follow; restore
it the same way. (2) Max strip length on A3 portrait in patch-first vs
area-first. (3) SS flat A4: the margins group with "Use instrument margins"
ticked while no thresholds exist (screenshot)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialogButtonBox  # noqa: E402

OUT = L.SHOTS / "A4-margins"
PROJECT = "A3-LayoutModes"
R = []


def gen(tab, watcher, label):
    watcher.expect("quite fill", "OK")
    watcher.expect("already", "Continue this project")
    L.click(tab._generate_btn)
    ok = L.wait_build(tab, 300_000)
    watcher.clear()
    s = L.panel_snapshot(tab)
    L.log(f"  [{label}] built ok={ok} actual={s['layout_info_actual']} est={s['layout_info_estimate']}\n      margins={s['margin_panel_text'][:260]}\n      status={s['margin_status']!r} notes={s['margin_notes']!r}")
    return s


def drive_settings(win, watcher, fn, label):
    app = QApplication.instance()
    state = {"done": False, "err": None, "pressed": None}
    watcher.ignore.append("SettingsDialog")

    def tick():
        dlg = app.activeModalWidget()
        if dlg is None or type(dlg).__name__ != "SettingsDialog":
            QTimer.singleShot(150, tick)
            return
        try:
            assert "Preferences" in dlg.windowTitle(), dlg.windowTitle()
            L.log(f"  Preferences dialog open: {dlg.windowTitle()!r}")
            fn(dlg)
            L.pump(500)
            L.grab(dlg, OUT / f"prefs-{label}.png")
            bb = dlg.findChild(QDialogButtonBox)
            okb = bb.button(QDialogButtonBox.StandardButton.Ok)
            state["pressed"] = okb.text()
            okb.click()
        except Exception as e:  # noqa: BLE001
            state["err"] = repr(e)
            L.log(f"  settings drive error {e!r}")
            dlg.reject()
        state["done"] = True

    QTimer.singleShot(250, tick)
    win._open_settings()
    L.pump(1000)
    watcher.ignore.remove("SettingsDialog")
    L.log(f"  Preferences closed via {state['pressed']!r} err={state['err']}")
    return state


def goto_limits(dlg, instr, paper):
    tabs = dlg._tabs
    for i in range(tabs.count()):
        if "Instrument Limits" in tabs.tabText(i):
            tabs.setCurrentIndex(i)
    L.pump(300)
    L.set_combo_text(dlg._margin_instr, instr)
    L.set_combo_text(dlg._margin_paper, paper)
    L.pump(300)
    L.log(f"  limits {instr} / {paper}: fields={ {k: v.value() for k, v in dlg._margin_fields.items()} } ruler={dlg._margin_ruler.value()} special={dlg._margin_ruler.specialValueText()!r} desc={dlg._margin_desc.text()!r}")


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    ok = L.open_project(win, settings, PROJECT)
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn)
    L.pump(500)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    panel = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(panel.instr, "i1"); L.set_combo_data(panel.paper, "A4"); L.set_combo_data(panel.mode, "clip")
    L.set_combo_data(panel.layout_mode, "area_first"); L.set_combo_data(panel.area_method, "by_width")
    L.set_spin(panel.max_strip, 0.0); L.set_check(panel.nolimit, False)
    L.set_check(panel.use_instr_margins, True)
    L.set_spin(panel.pages, 1)
    L.pump(500)
    s0 = L.panel_snapshot(tab)
    L.log(f"start: panel margins={ {k: v.value() for k, v in panel.margins.items()} } est={s0['layout_info_estimate']}")
    gen(tab, watcher, "baseline A4 T38")

    # ---- (1) threshold change through the real dialog ----
    before = dict(settings.get_margin_thresholds().get("i1Pro|A4 Portrait", {}))
    L.log(f"thresholds before: {before}")

    def edit(dlg):
        goto_limits(dlg, "i1Pro", "A4 Portrait")
        dlg._margin_fields["T"].setValue(50.0); dlg._margin_fields["T"].editingFinished.emit()
        dlg._margin_ruler.setValue(200.0); dlg._margin_ruler.editingFinished.emit()
        L.pump(300)
        L.log(f"  edited: fields={ {k: v.value() for k, v in dlg._margin_fields.items()} } ruler={dlg._margin_ruler.value()}")
    st = drive_settings(win, watcher, edit, "i1-A4-T50-ruler200")
    after = dict(settings.get_margin_thresholds().get("i1Pro|A4 Portrait", {}))
    L.log(f"thresholds after: {after}")
    L.pump(800)
    s1 = L.panel_snapshot(tab)
    L.log(f"after prefs, no regenerate: panel margins={ {k: v.value() for k, v in panel.margins.items()} } use_instr={panel.use_instr_margins.isChecked()}\n   est={s1['layout_info_estimate']}\n   margin text={s1['margin_panel_text'][:300]}\n   status={s1['margin_status']!r} notes={s1['margin_notes']!r}")
    L.grab(win, OUT / "t01-after-prefs-T50-before-generate.png")
    s2 = gen(tab, watcher, "after prefs T50 ruler200")
    L.grab(win, OUT / "t02-after-prefs-T50-generated.png")
    R.append({"before": before, "after": after, "panel_margins_after_prefs": {k: v.value() for k, v in panel.margins.items()},
              "est_after_prefs": s1["layout_info_estimate"], "built": s2["layout_info_actual"],
              "margin_text_built": s2["margin_panel_text"][:400], "notes_built": s2["margin_notes"], "status_built": s2["margin_status"]})

    # a strip longer than 200 should now be flagged: own margins 6 mm top/bottom
    L.set_check(panel.use_instr_margins, False)
    for k in ("t", "b"):
        L.set_spin(panel.margins[k], 6.0)
    s3 = gen(tab, watcher, "own T/B 6 mm with ruler 200 set")
    L.grab(win, OUT / "t03-ruler200-long-strip.png")
    R.append({"ruler200_longstrip_notes": s3["margin_notes"], "status": s3["margin_status"], "text": s3["margin_panel_text"][:300]})
    L.set_check(panel.use_instr_margins, True)

    # restore
    def restore(dlg):
        goto_limits(dlg, "i1Pro", "A4 Portrait")
        dlg._margin_fields["T"].setValue(float(before.get("T", 38))); dlg._margin_fields["T"].editingFinished.emit()
        dlg._margin_ruler.setValue(float(before.get("ruler", 0) or 0)); dlg._margin_ruler.editingFinished.emit()
    drive_settings(win, watcher, restore, "restore")
    L.log(f"thresholds restored: {settings.get_margin_thresholds().get('i1Pro|A4 Portrait')}")
    L.pump(600)
    L.log(f"panel margins after restore: { {k: v.value() for k, v in panel.margins.items()} }")

    # ---- (2) max strip on A3 portrait: patch-first vs area-first ----
    L.set_combo_data(panel.paper, "A3")
    L.log(f"max_strip tooltip: {panel.max_strip.toolTip()[:300]!r}")
    for mode in ("patch_first", "area_first"):
        L.set_combo_data(panel.layout_mode, mode)
        for cap in (0.0, 200.0):
            L.set_spin(panel.max_strip, cap)
            L.pump(500)
            s = L.panel_snapshot(tab)
            L.log(f"  A3 {mode} max_strip={cap}: est={s['layout_info_estimate']}")
            sb = gen(tab, watcher, f"A3 {mode} max_strip={cap}")
            R.append({"a3": mode, "cap": cap, "est": s["layout_info_estimate"], "actual": sb["layout_info_actual"],
                      "notes": sb["margin_notes"], "text": sb["margin_panel_text"][:300]})
            if mode == "patch_first" and cap == 200.0:
                L.grab(win, OUT / "s01-A3-patchfirst-maxstrip200.png")
            if mode == "area_first" and cap == 200.0:
                L.grab(win, OUT / "s02-A3-areafirst-maxstrip200.png")
    L.set_spin(panel.max_strip, 0.0)
    L.set_combo_data(panel.paper, "A4")

    # ---- (3) SS flat A4: the margins group ----
    L.set_combo_data(panel.instr, "SS"); L.set_combo_data(panel.mode, "flat"); L.pump(600)
    L.log(f"SS: use_instr visible={panel.use_instr_margins.isVisible()} checked={panel.use_instr_margins.isChecked()} margins={ {k: (v.value(), v.isEnabled()) for k, v in panel.margins.items()} } tip={panel.use_instr_margins.toolTip()[:200]!r}")
    grp = panel.use_instr_margins.parentWidget()
    L.grab(grp, OUT / "u01-SS-margins-group.png")
    gen(tab, watcher, "SS flat A4")
    L.grab(win, OUT / "u02-SS-flat-A4-window.png")
    L.save_json(R, L.LOGS / "d03b_results.json")
    L.log(f"unexpected: {watcher.unexpected} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
