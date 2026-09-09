#!/usr/bin/env python3
"""D05b: corrected presets test (prefix box off, presets picked through the
combo's activated signal), the patch-set editor Apply/Overwrite round trip,
the F-003 re-check with raw printtarg widget values, and the auto-update
debounce counted from engine log lines. Results are saved after every block."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QCheckBox, QLineEdit, QPushButton  # noqa: E402

OUT8 = L.SHOTS / "A8-presets"
OUT9 = L.SHOTS / "A9-patch-editor"
OUT7 = L.SHOTS / "A7-auto-preview"
PRESET_DIR = Path(os.environ["CHROMIQ_PRESETS_DIR"]) / "Create Chart"
R: dict = {}


def save():
    L.save_json(R, L.LOGS / "d05b_results.json")


def pw(tab, tool, flag):
    for w in tab._manual_widgets.get(tool, []):
        if w.flag == flag:
            return w


KEYS = ("instrument", "paper", "layout_mode", "area_method", "patch_w_mm", "patch_h_mm", "margin_top", "margin_right",
        "margin_bottom", "margin_left", "use_instrument_margins", "clip_border", "clip_content_mode", "chart_text",
        "helper_markers", "show_row_indicators", "pscale", "spacer_mode", "indicator_size_mm", "randomize", "dpi", "hflag")


def kr(rec):
    return {k: rec.get(k) for k in KEYS}


def drive_dialog(cls_name, title_sub, fn, watcher, label, timeout_ms=8000):
    app = QApplication.instance()
    state = {"seen": False, "err": None}
    watcher.ignore.append(cls_name)
    deadline = time.time() + timeout_ms / 1000

    def done():
        try:
            watcher.ignore.remove(cls_name)
        except ValueError:
            pass

    def tick():
        dlg = app.activeModalWidget()
        if dlg is None or type(dlg).__name__ != cls_name or (title_sub and title_sub.lower() not in dlg.windowTitle().lower()):
            if time.time() < deadline:
                QTimer.singleShot(120, tick)
            else:
                L.log(f"  [{label}] no {cls_name} '{title_sub}' within {timeout_ms} ms"); done()
            return
        state["seen"] = True
        L.log(f"  [{label}] dialog {cls_name} title={dlg.windowTitle()!r}")
        try:
            fn(dlg)
        except Exception as e:  # noqa: BLE001
            state["err"] = repr(e); L.log(f"  [{label}] error {e!r}; rejecting"); dlg.reject()
        done()

    QTimer.singleShot(150, tick)
    return state


def click_named(dlg, text):
    for b in dlg.findChildren(QPushButton):
        if b.text().replace("&", "").strip().lower().startswith(text.lower()):
            L.log(f"    clicking '{b.text()}'"); b.click(); return True
    L.log(f"    NO button '{text}' among {[b.text() for b in dlg.findChildren(QPushButton)]}"); return False


def pick_preset(tab, data_or_text):
    c = tab._preset_combo
    for i in range(c.count()):
        if c.itemData(i) == data_or_text or c.itemText(i).strip() == data_or_text or (isinstance(data_or_text, str) and data_or_text in c.itemText(i)):
            c.setCurrentIndex(i); L.pump(100); c.activated.emit(i); L.pump(300)
            L.log(f"  picked preset #{i} {c.itemText(i)!r} (activated)")
            return True
    L.log(f"  preset {data_or_text!r} not found"); return False


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    L.open_project(win, settings, "A5-Furniture")
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn); L.pump(400)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    p = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)

    def distinctive():
        L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4R"); L.set_combo_data(p.mode, "noclip")
        L.set_combo_data(p.layout_mode, "patch_first"); L.set_spin(p.patch_x, 12.0); L.set_spin(p.patch_y, 12.0)
        L.set_check(p.use_instr_margins, False)
        for k in ("t", "r", "b", "l"):
            L.set_spin(p.margins[k], 15.0)
        p.chart_text.setText("Preset {project}"); p.chart_text.editingFinished.emit()
        L.set_check(p.helper_markers_cb, True); L.set_check(p.show_row_indicators, True); L.set_spin(p.indicator_size, 4.0)
        L.pump(400)
    distinctive()
    saved = kr(L.recipe_of(tab))
    R["a8-saved-recipe"] = saved

    def fill(name, dlg, *, gen=False):
        boxes = {b.text(): b for b in dlg.findChildren(QCheckBox)}
        R.setdefault("a8-save-dialog-defaults", {t: b.isChecked() for t, b in boxes.items()})
        for t, b in boxes.items():
            if "prefix" in t.lower() and b.isChecked():
                b.click()
            if "immediately" in t.lower() and b.isChecked() != gen:
                b.click()
        [e for e in dlg.findChildren(QLineEdit) if e.isVisible()][0].setText(name)
        L.pump(200); L.grab(dlg, OUT8 / f"q10-save-{name}.png"); click_named(dlg, "Save")

    st = drive_dialog("QDialog", "Save Preset", lambda d: fill("AssessPresetA", d), watcher, "save A")
    L.click(tab._preset_add_btn); L.pump(1500)
    names = [tab._preset_combo.itemText(i) for i in range(tab._preset_combo.count())]
    R["a8-save"] = {"seen": st["seen"], "err": st["err"], "in_combo": any(n.strip().endswith("AssessPresetA") for n in names),
                    "combo_current": tab._preset_combo.currentText(), "files": sorted(f.name for f in PRESET_DIR.glob("*AssessPreset*"))}
    L.log(f"save A: {R['a8-save']}  dialog defaults={R.get('a8-save-dialog-defaults')}")
    L.grab(win, OUT8 / "q11-after-save.png"); save()

    # change, then reload through activated
    L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.layout_mode, "area_first"); L.set_spin(p.patch_x, 0.0)
    for k in ("t", "r", "b", "l"):
        L.set_spin(p.margins[k], 8.0)
    p.chart_text.setText("changed"); p.chart_text.editingFinished.emit(); L.set_check(p.helper_markers_cb, False); L.pump(300)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    pick_preset(tab, "AssessPresetA"); L.wait_build(tab, 240_000); L.pump(1500); watcher.clear()
    reloaded = kr(L.recipe_of(tab))
    R["a8-reload"] = {"diff_vs_saved": {k: (saved[k], reloaded[k]) for k in KEYS if saved[k] != reloaded[k]}, "engine": tab._manual_engine_check.isChecked(),
                      "panel_enabled": p.isEnabled(), "generate_enabled": tab._generate_btn.isEnabled(), "combo": tab._preset_combo.currentText(),
                      "override_printtarg": (tab._override_printtarg_check.isVisible(), tab._override_printtarg_check.isChecked()) if tab._override_printtarg_check else None,
                      "info": tab._manual_info_lbl.text()[-220:], "built": L.panel_snapshot(tab)["layout_info_actual"]}
    L.log(f"reload A: {R['a8-reload']}"); L.grab(win, OUT8 / "q12-after-reload.png"); save()
    # modify a locked value? (does the panel lock after a preset?) then overwrite same name
    L.set_spin(p.indicator_size, 5.0); L.pump(300)
    R["a8-edit-after-load"] = {"indicator_size_now": p.indicator_size.value(), "combo": tab._preset_combo.currentText(), "modified_marker": tab._manual_info_lbl.text()[-60:]}
    st2 = drive_dialog("QDialog", "Save Preset", lambda d: fill("AssessPresetA", d), watcher, "save A again")
    watcher.expect("Preset already exists", "Overwrite")
    L.click(tab._preset_add_btn); L.pump(1500)
    R["a8-overwrite"] = {"seen": st2["seen"], "dialogs": [(d.get("title"), d.get("answer")) for d in watcher.seen[-2:]], "files": sorted(f.name for f in PRESET_DIR.glob("*AssessPreset*"))}
    watcher.clear(); L.log(f"overwrite: {R['a8-overwrite']}"); save()
    # delete
    st3 = drive_dialog("QDialog", "Delete Preset", lambda d: (L.grab(d, OUT8 / "q13-delete-dialog.png"), click_named(d, "Delete")), watcher, "delete A")
    L.click(tab._preset_del_btn); L.pump(1200)
    names = [tab._preset_combo.itemText(i) for i in range(tab._preset_combo.count())]
    R["a8-delete"] = {"seen": st3["seen"], "in_combo": any(n.strip().endswith("AssessPresetA") for n in names), "files": sorted(f.name for f in PRESET_DIR.glob("*AssessPreset*")),
                      "combo_after": tab._preset_combo.currentText(), "recipe_after_delete": kr(L.recipe_of(tab))}
    L.log(f"delete: {R['a8-delete']}"); save()
    # save B for the restart test
    distinctive()
    st4 = drive_dialog("QDialog", "Save Preset", lambda d: fill("AssessPresetB", d), watcher, "save B")
    L.click(tab._preset_add_btn); L.pump(1500)
    L.save_json(L.recipe_of(tab), L.LOGS / "d05b_presetB_recipe_saved.json")
    R["a8-saveB"] = {"seen": st4["seen"], "files": sorted(f.name for f in PRESET_DIR.glob("*AssessPreset*"))}
    save()

    # built-ins through activated
    for key, label in (("__chromiq_tc918eg_a4_builtin__", "tc918eg-a4-printtarg-kind"),
                       ("__chromiq_knut_i1_w75_a4_162p_1page_portrait_w7_5mm__", "knut-i1-w75-162p-fulllayout"),
                       ("__chromiq_knut_cr30_a4_153p_1page_portrait_w18_0mm_hexagonal__", "knut-cr30-153p-hex"),
                       ("__chromiq_knut_scanner_a4_3430p_1page_landscape__", "knut-scanner-a4-3430p")):
        watcher.expect("quite fill", "OK"); watcher.expect("scanner", "OK"); watcher.expect("already", "Continue this project")
        eng_before = tab._manual_engine_check.isChecked(); n_dlg = len(watcher.seen)
        pick_preset(tab, key)
        L.wait_build(tab, 300_000); L.pump(2000); watcher.clear()
        s = L.panel_snapshot(tab)
        L.grab(win, OUT8 / f"q14-builtin-{label}.png")
        R[f"a8-builtin-{label}"] = {"engine_before": eng_before, "engine_after": tab._manual_engine_check.isChecked(), "engine_enabled": tab._manual_engine_check.isEnabled(),
                                    "info": tab._manual_info_lbl.text()[-320:], "actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"],
                                    "recipe": kr(L.recipe_of(tab)), "panel_enabled": p.isEnabled(), "targen_grp_enabled": tab._manual_targen_grp.isEnabled(),
                                    "generate_enabled": tab._generate_btn.isEnabled(),
                                    "override_targen": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None,
                                    "override_printtarg": (tab._override_printtarg_check.isVisible(), tab._override_printtarg_check.isChecked()) if tab._override_printtarg_check else None,
                                    "margin_status": s["margin_status"], "margin_notes": s["margin_notes"],
                                    "log_tail": [l for l in L.tab_log_text(tab).splitlines() if "engine]" in l or l.lower().startswith("printtarg") or "ChromIQ" in l][-4:],
                                    "dialogs": [(d.get("title") or d.get("text", "")[:50], d.get("answer")) for d in watcher.seen[n_dlg:]],
                                    "files": [f for f, _ in L.run_inventory(L.current_run_dir(win)).get("files", []) if not f.startswith(("cache", "exports"))]}
        L.log(f"[builtin {label}] engine {eng_before}->{tab._manual_engine_check.isChecked()} enabled={tab._manual_engine_check.isEnabled()} actual={s['layout_info_actual']} est={s['layout_info_estimate']} info={tab._manual_info_lbl.text()[-200:]!r} dialogs={R[f'a8-builtin-{label}']['dialogs']}")
        save()
    pick_preset(tab, "none"); L.pump(1000)
    R["a8-after-none"] = {"engine": tab._manual_engine_check.isChecked(), "recipe": kr(L.recipe_of(tab)), "panel_enabled": p.isEnabled(), "info": tab._manual_info_lbl.text()[-200:]}
    L.log(f"after none: {R['a8-after-none']}"); save()

    # ---------------- A9: editor Apply / Overwrite round trip
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.mode, "clip")
    L.set_combo_data(p.layout_mode, "area_first"); L.set_check(p.use_instr_margins, True); L.set_check(p.helper_markers_cb, False)
    if auto.isChecked():
        auto.click(); L.pump(200)
    pw(tab, "targen", "-f").set_value(300); L.pump(300)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    L.click(tab._generate_btn); L.wait_build(tab, 240_000); L.pump(800); watcher.clear()
    before = kr(L.recipe_of(tab)); s0 = L.panel_snapshot(tab)
    ed = {}

    def in_editor(dlg):
        L.pump(3000)
        L.grab(dlg, OUT9 / "e10-editor-via-tools.png")
        try:
            er = kr(dlg._engine_panel.get_recipe().to_dict())
            ed["diff_editor_vs_tab"] = {k: (before[k], er[k]) for k in KEYS if before[k] != er[k]}
        except Exception as e:  # noqa: BLE001
            ed["diff_editor_vs_tab"] = repr(e)
        ed["apply_enabled"] = dlg._apply_btn.isEnabled()
        # Apply -> "Apply or save this patch set" -> Overwrite
        def in_apply(d2):
            L.grab(d2, OUT9 / "e11-apply-or-save.png")
            ed["apply_dialog_buttons"] = [b.text() for b in d2.findChildren(QPushButton) if b.text()]
            click_named(d2, "Overwrite")
        drive_dialog("QDialog", "Apply or save", in_apply, watcher, "apply-or-save", timeout_ms=8000)
        dlg._apply_btn.click()
    st5 = drive_dialog("Ti2RelayoutDialog", "", in_editor, watcher, "editor", timeout_ms=30000)
    watcher.expect("already", "Continue this project"); watcher.expect("quite fill", "OK")
    win._launch_tool("ti2_relayout")
    L.pump(1500); L.wait_build(tab, 240_000); L.pump(2500); watcher.clear()
    after = kr(L.recipe_of(tab)); s1 = L.panel_snapshot(tab)
    L.grab(win, OUT9 / "e12-after-overwrite.png")
    R["a9-editor"] = {"seen": st5["seen"], "err": st5["err"], **ed, "tab_recipe_diff_after_apply": {k: (before[k], after[k]) for k in KEYS if before[k] != after[k]},
                      "applied_active": getattr(tab, "_applied_active", None), "actual_before": s0["layout_info_actual"], "actual_after": s1["layout_info_actual"],
                      "estimate_after": s1["layout_info_estimate"], "info": tab._manual_info_lbl.text()[-260:],
                      "override_targen": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None,
                      "override_printtarg": (tab._override_printtarg_check.isVisible(), tab._override_printtarg_check.isChecked()) if tab._override_printtarg_check else None,
                      "panel_enabled": p.isEnabled(), "generate_enabled": tab._generate_btn.isEnabled(),
                      "log_tail": [l for l in L.tab_log_text(tab).splitlines() if "engine]" in l or "editor" in l.lower()][-4:]}
    L.log(f"[editor] {R['a9-editor']}"); save()
    # Generate again after the editor apply: does the layout survive?
    watcher.expect("already", "Continue this project"); watcher.expect("quite fill", "OK")
    L.click(tab._generate_btn); L.wait_build(tab, 240_000); L.pump(1000); watcher.clear()
    s2 = L.panel_snapshot(tab)
    R["a9-generate-after-apply"] = {"actual": s2["layout_info_actual"], "recipe": kr(L.recipe_of(tab)), "applied_active": getattr(tab, "_applied_active", None), "info": tab._manual_info_lbl.text()[-200:]}
    L.log(f"[after apply generate] {R['a9-generate-after-apply']}"); save()

    # ---------------- F-003 re-check
    L.set_combo_data(win._target_bar._run_combo, "\x00new"); L.pump(1000)
    L.set_check(tab._manual_engine_check, False); L.pump(800)
    def raw():
        return {f: (pw(tab, "printtarg", f).get_raw_value() if pw(tab, "printtarg", f) else None) for f in ("-i", "-p", "-L", "-a", "-m")}
    r0 = raw(); cmd0 = tab._manual_info_lbl.text().splitlines()[-1]
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    L.click(tab._generate_btn); r_during = raw()
    L.wait_build(tab, 240_000); r1 = raw(); L.pump(3000); r2 = raw(); watcher.clear()
    rd = L.current_run_dir(win)
    meta = json.loads((rd / "meta.json").read_text()) if (rd / "meta.json").is_file() else {}
    cs = meta.get("create_chart_settings", {})
    ch = next(rd.glob("*.channels.json"), None)
    side = json.loads(ch.read_text()) if ch else {}
    R["f003"] = {"before": r0, "cmd_before": cmd0, "during": r_during, "right_after": r1, "after_3s": r2,
                 "meta": {k: cs.get(k) for k in ("printtarg-L", "printtarg-a", "printtarg-m")},
                 "sidecar_create_chart_settings": {k: side.get("create_chart_settings", {}).get(k) for k in ("printtarg-L", "printtarg-a")},
                 "sidecar_printtarg_fields": [f for f in side.get("printtarg_fields", []) if f.get("flag") in ("-L", "-a")],
                 "run": str(rd), "log_cmd": [l for l in L.tab_log_text(tab).splitlines() if "printtarg -" in l][-1:]}
    L.log(f"F-003 re-check: {R['f003']}"); L.grab(win, L.SHOTS / "A6-info-panels" / "f003-after-printtarg-build.png"); save()
    L.set_check(tab._manual_engine_check, True); L.pump(600)

    # ---------------- A7 debounce redo
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(p.layout_mode, "area_first"); L.set_check(p.use_instr_margins, True); L.set_spin(p.area_min_patch, 0.0)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    L.click(tab._generate_btn); L.wait_build(tab, 240_000); watcher.clear(); L.pump(500)
    settings.set("auto_update_preview", True)
    tab._auto_preview_check.blockSignals(True); tab._auto_preview_check.setChecked(True); tab._auto_preview_check.blockSignals(False)
    builds = lambda: L.tab_log_text(tab).count("random start")  # noqa: E731
    n0 = builds(); t0 = time.time()
    L.set_spin(p.area_min_patch, 10.0); L.pump(150); L.set_spin(p.area_min_patch, 11.0)
    L.wait_until(lambda: builds() > n0, 5000, "first auto build"); t_first = round(time.time() - t0, 2)
    L.pump(6000)
    R["a7-debounce"] = {"builds_for_two_nudges_150ms_apart": builds() - n0, "first_build_after_s": t_first}
    n1 = builds(); tab._manual_chart_notes_edit.setText("notes only edit"); tab._manual_chart_notes_edit.editingFinished.emit(); L.pump(4000)
    R["a7-notes"] = {"builds_for_notes_edit": builds() - n1}
    n2 = builds(); L.set_check(p.helper_markers_cb, True); L.pump(4000)
    R["a7-helper-markers"] = {"builds_for_helper_marker_toggle": builds() - n2}
    n3 = builds(); L.set_combo_data(p.spacer_mode, "bw"); L.pump(4000)
    R["a7-spacer-colour"] = {"builds_for_spacer_bw": builds() - n3}
    L.log(f"A7: {R['a7-debounce']} {R['a7-notes']} {R['a7-helper-markers']} {R['a7-spacer-colour']}")
    L.grab(win, OUT7 / "a10-after-debounce-tests.png")
    settings.set("auto_update_preview", False)
    tab._auto_preview_check.blockSignals(True); tab._auto_preview_check.setChecked(False); tab._auto_preview_check.blockSignals(False)
    save()
    L.log(f"unexpected: {[(d['class'], d['title'], d['text'][:80]) for d in watcher.unexpected]} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
