#!/usr/bin/env python3
"""D05: A6 info frames on a printtarg run / an empty run / a reflected external
chart; A8 named presets (save, change, reload, overwrite, delete, built-ins);
A9 patch-set editor round trip from the last-page hint; F-003 re-check with raw
widget values; A7 debounce redo by counting engine log lines.

Native file dialogs cannot be driven, so where the app would open one, the
driver substitutes the path and LOGS that it did (open_file_dialog only)."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QLineEdit, QPushButton  # noqa: E402

OUT6 = L.SHOTS / "A6-info-panels"
OUT8 = L.SHOTS / "A8-presets"
OUT9 = L.SHOTS / "A9-patch-editor"
OUT7 = L.SHOTS / "A7-auto-preview"
R: dict = {}


def pw(tab, tool, flag):
    for w in tab._manual_widgets.get(tool, []):
        if w.flag == flag:
            return w


def key_recipe(rec):
    return {k: rec.get(k) for k in ("instrument", "paper", "layout_mode", "area_method", "patch_w_mm", "patch_h_mm",
                                    "margin_top", "margin_right", "margin_bottom", "margin_left", "use_instrument_margins",
                                    "clip_border", "clip_content_mode", "chart_text", "helper_markers", "show_row_indicators",
                                    "pscale", "spacer_mode", "indicator_size_mm", "randomize")}


def drive_dialog(cls_name: str, title_sub: str, fn, watcher, label, timeout_ms=6000):
    """Arm a timer that waits for a modal of class cls_name whose title contains
    title_sub, runs fn(dlg), and records what happened."""
    app = QApplication.instance()
    state = {"seen": False, "err": None, "title": None}
    watcher.ignore.append(cls_name)
    deadline = time.time() + timeout_ms / 1000

    def tick():
        dlg = app.activeModalWidget()
        if dlg is None or type(dlg).__name__ != cls_name:
            if time.time() < deadline:
                QTimer.singleShot(120, tick)
            else:
                L.log(f"  [{label}] no {cls_name} appeared within {timeout_ms} ms")
                try:
                    watcher.ignore.remove(cls_name)
                except ValueError:
                    pass
            return
        state["seen"] = True
        state["title"] = dlg.windowTitle()
        try:
            assert title_sub.lower() in dlg.windowTitle().lower() or title_sub == "", dlg.windowTitle()
            L.log(f"  [{label}] dialog {cls_name} title={dlg.windowTitle()!r}")
            fn(dlg)
        except Exception as e:  # noqa: BLE001
            state["err"] = repr(e)
            L.log(f"  [{label}] drive error {e!r}; rejecting")
            dlg.reject()
        try:
            watcher.ignore.remove(cls_name)
        except ValueError:
            pass

    QTimer.singleShot(150, tick)
    return state


def click_named(dlg, text):
    for b in dlg.findChildren(QPushButton):
        if b.text().replace("&", "").strip().lower() == text.lower():
            L.log(f"    clicking '{b.text()}'")
            b.click()
            return True
    L.log(f"    NO button '{text}' among {[b.text() for b in dlg.findChildren(QPushButton)]}")
    return False


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)

    # ---------------- A6: info frames on printtarg run / empty run / reflected chart
    L.open_project(win, settings, "A1-EngineVsPrinttarg")
    L.click(tab._manual_btn); L.pump(400)
    for run_id in ("run1", "run2", "run3"):
        L.set_combo_data(win._target_bar._run_combo, run_id); L.pump(1200)
        s = L.panel_snapshot(tab)
        L.grab(win, OUT6 / f"p01-{run_id}.png")
        R[f"a6-{run_id}"] = {"run_bar": win._target_bar._run_combo.currentText(), "engine_check": tab._manual_engine_check.isChecked(),
                             "actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"], "margin_text": s["margin_panel_text"][:260],
                             "status": s["margin_status"], "layout_info_text": s["layout_info_text"][:200]}
        L.log(f"[{run_id}] engine={tab._manual_engine_check.isChecked()} actual={s['layout_info_actual']} est={s['layout_info_estimate']} status={s['margin_status']!r}")
    # reflected external chart (what Load .ti2 in Print/Measure emits)
    ext = Path("/Users/Basti/ChromIQ-assessment/A2-Instruments/runs/run1")
    ti2 = next(ext.glob("*.ti2")); tiffs = sorted(ext.glob("*.tif"))
    L.log(f"reflecting external chart {ti2.name} ({len(tiffs)} tiff) via reflect_loaded_chart (the Measure tab's Load .ti2 signal)")
    tab.reflect_loaded_chart(ti2, tiffs); L.pump(1500)
    s = L.panel_snapshot(tab)
    L.grab(win, OUT6 / "p02-reflected-external.png")
    R["a6-reflected"] = {"actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"], "status": s["margin_status"], "margin_text": s["margin_panel_text"][:260],
                         "generate_enabled": tab._generate_btn.isEnabled(), "engine_panel_enabled": tab._manual_layout_panel.isEnabled(),
                         "override_targen": tab._override_targen_check is not None and tab._override_targen_check.isVisible(),
                         "run_bar": win._target_bar._run_combo.currentText(), "location": win._target_bar._location.text()}
    L.log(f"[reflected] {R['a6-reflected']}")
    # Generate while reflected -> the info dialog
    watcher.expect("loaded from elsewhere", "Close", note="reflected-chart info")
    L.click(tab._generate_btn); L.pump(1200); watcher.clear()
    R["a6-reflected-generate"] = [d.get("answer") for d in watcher.seen[-1:]]

    # ---------------- A8: named presets in a fresh project
    settings.set("session_target_name", ""); L.open_project(win, settings, "A5-Furniture")   # leave reflection via a real project open
    L.click(tab._manual_btn); L.pump(400)
    tab._manual_target_name_edit.setText("A8-Presets"); tab._manual_target_name_edit.editingFinished.emit(); L.pump(300)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    p = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4R"); L.set_combo_data(p.mode, "noclip")
    L.set_combo_data(p.layout_mode, "patch_first"); L.set_spin(p.patch_x, 12.0); L.set_spin(p.patch_y, 12.0)
    L.set_check(p.use_instr_margins, False)
    for k in ("t", "r", "b", "l"):
        L.set_spin(p.margins[k], 15.0)
    p.chart_text.setText("Preset {project}"); p.chart_text.editingFinished.emit()
    L.set_check(p.helper_markers_cb, True); L.set_check(p.show_row_indicators, True)
    L.set_spin(p.indicator_size, 4.0)
    L.pump(500)
    saved_recipe = key_recipe(L.recipe_of(tab))
    L.log(f"recipe to save: {saved_recipe}")
    L.grab(win, OUT8 / "q01-before-save.png")

    def fill_save(dlg):
        edits = [e for e in dlg.findChildren(QLineEdit) if e.isVisible()]
        edits[0].setText("AssessPresetA"); L.pump(200)
        L.grab(dlg, OUT8 / "q02-save-dialog.png")
        click_named(dlg, "Save")
    st = drive_dialog("QDialog", "Save Preset", fill_save, watcher, "save A")
    watcher.expect("Give this project a name", "<reject>")
    L.click(tab._preset_add_btn); L.pump(1500)
    items = [d for _, d in L.combo_items(tab._preset_combo)]
    on_disk = sorted(f.name for f in (Path(L.os.environ["CHROMIQ_PRESETS_DIR"]) / "Create Chart").glob("AssessPreset*"))
    L.log(f"after save: dialog seen={st['seen']} err={st['err']} combo has A={'AssessPresetA' in items} current={tab._preset_combo.currentText()!r} files={on_disk}")
    R["a8-save"] = {"seen": st["seen"], "in_combo": "AssessPresetA" in items, "files": on_disk, "current": tab._preset_combo.currentText()}
    # change several values, then reload the preset
    L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.layout_mode, "area_first"); L.set_spin(p.patch_x, 0.0)
    for k in ("t", "r", "b", "l"):
        L.set_spin(p.margins[k], 8.0)
    p.chart_text.setText("changed"); p.chart_text.editingFinished.emit(); L.set_check(p.helper_markers_cb, False)
    L.pump(400)
    changed = key_recipe(L.recipe_of(tab))
    watcher.expect("quite fill", "OK")
    L.set_combo_data(tab._preset_combo, "AssessPresetA"); L.pump(2500)
    reloaded = key_recipe(L.recipe_of(tab))
    diff = {k: (saved_recipe[k], reloaded[k]) for k in saved_recipe if saved_recipe[k] != reloaded[k]}
    L.log(f"reload: engine={tab._manual_engine_check.isChecked()} diff vs saved={diff}  override_targen_visible={tab._override_targen_check.isVisible() if tab._override_targen_check else None} generate_enabled={tab._generate_btn.isEnabled()} panel_enabled={p.isEnabled()}")
    L.grab(win, OUT8 / "q03-after-reload.png")
    R["a8-reload"] = {"diff": diff, "changed_before_reload": changed, "engine": tab._manual_engine_check.isChecked(), "panel_enabled": p.isEnabled(), "generate_enabled": tab._generate_btn.isEnabled()}
    # overwrite with same name
    L.set_spin(p.indicator_size, 5.0); L.pump(200)
    st2 = drive_dialog("QDialog", "Save Preset", lambda d: ([e for e in d.findChildren(QLineEdit) if e.isVisible()][0].setText("AssessPresetA"), click_named(d, "Save")), watcher, "save A again")
    watcher.expect("Preset already exists", "Overwrite")
    L.click(tab._preset_add_btn); L.pump(1500); watcher.clear()
    R["a8-overwrite"] = {"seen": st2["seen"], "dialogs": [d.get("answer") for d in watcher.seen[-2:]]}
    L.log(f"overwrite: {R['a8-overwrite']}")
    # delete
    st3 = drive_dialog("QDialog", "Delete Preset", lambda d: click_named(d, "Delete"), watcher, "delete A")
    L.click(tab._preset_del_btn); L.pump(1200)
    items = [d for _, d in L.combo_items(tab._preset_combo)]
    on_disk = sorted(f.name for f in (Path(L.os.environ["CHROMIQ_PRESETS_DIR"]) / "Create Chart").glob("AssessPreset*"))
    L.log(f"delete: seen={st3['seen']} still in combo={'AssessPresetA' in items} files={on_disk} current={tab._preset_combo.currentText()!r}")
    R["a8-delete"] = {"seen": st3["seen"], "in_combo": "AssessPresetA" in items, "files": on_disk}
    # save B for the restart test (d05b compares)
    L.set_combo_data(p.paper, "A4R"); L.set_combo_data(p.layout_mode, "patch_first"); L.set_spin(p.patch_x, 12.0); L.set_spin(p.patch_y, 12.0)
    for k in ("t", "r", "b", "l"):
        L.set_spin(p.margins[k], 15.0)
    p.chart_text.setText("Preset {project}"); p.chart_text.editingFinished.emit(); L.set_check(p.helper_markers_cb, True); L.set_spin(p.indicator_size, 4.0)
    L.pump(300)
    full_b = L.recipe_of(tab)
    st4 = drive_dialog("QDialog", "Save Preset", lambda d: ([e for e in d.findChildren(QLineEdit) if e.isVisible()][0].setText("AssessPresetB"), click_named(d, "Save")), watcher, "save B")
    L.click(tab._preset_add_btn); L.pump(1500)
    L.save_json(full_b, L.LOGS / "d05_presetB_recipe_saved.json")
    R["a8-saveB"] = {"seen": st4["seen"], "on_disk": sorted(f.name for f in (Path(L.os.environ["CHROMIQ_PRESETS_DIR"]) / "Create Chart").glob("AssessPreset*"))}

    # built-in presets: printtarg-kind TC9.18, full-layout i1, CR30 hex
    for key, label in (("__chromiq_tc918eg_a4_builtin__", "tc918eg-a4-printtarg-kind"),
                       ("__chromiq_knut_i1_w75_a4_162p_1page_portrait_w7_5mm__", "knut-i1-w75-162p-fulllayout"),
                       ("__chromiq_knut_cr30_a4_153p_1page_portrait_w18_0mm_hexagonal__", "knut-cr30-153p-hex")):
        watcher.expect("quite fill", "OK"); watcher.expect("scanner", "OK"); watcher.expect("already", "Continue this project")
        eng_before = tab._manual_engine_check.isChecked()
        L.set_combo_data(tab._preset_combo, key)
        L.wait_build(tab, 240_000); L.pump(1500); watcher.clear()
        s = L.panel_snapshot(tab)
        info = tab._manual_info_lbl.text()
        L.grab(win, OUT8 / f"q04-builtin-{label}.png")
        rec = key_recipe(L.recipe_of(tab))
        R[f"a8-builtin-{label}"] = {"engine_before": eng_before, "engine_after": tab._manual_engine_check.isChecked(), "engine_check_enabled": tab._manual_engine_check.isEnabled(),
                                    "info": info[-300:], "actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"], "recipe": rec,
                                    "panel_enabled": p.isEnabled(), "targen_grp_enabled": tab._manual_targen_grp.isEnabled(), "generate_enabled": tab._generate_btn.isEnabled(),
                                    "override_targen": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None,
                                    "override_printtarg": (tab._override_printtarg_check.isVisible(), tab._override_printtarg_check.isChecked()) if tab._override_printtarg_check else None,
                                    "log_tail": [l for l in L.tab_log_text(tab).splitlines() if "engine]" in l or "printtarg" in l.lower()][-3:],
                                    "dialogs": [d.get("answer") for d in watcher.seen[-2:]]}
        L.log(f"[builtin {label}] engine {eng_before}->{tab._manual_engine_check.isChecked()} (enabled={tab._manual_engine_check.isEnabled()}) actual={s['layout_info_actual']} est={s['layout_info_estimate']} info={info[-160:]!r}")
    L.set_combo_data(tab._preset_combo, "none"); L.pump(800)
    L.log(f"after 'none': engine={tab._manual_engine_check.isChecked()} recipe={key_recipe(L.recipe_of(tab))}")
    R["a8-after-none"] = {"engine": tab._manual_engine_check.isChecked(), "recipe": key_recipe(L.recipe_of(tab))}

    # ---------------- A9: patch-set editor from the hint
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.mode, "clip")
    L.set_combo_data(p.layout_mode, "area_first"); L.set_check(p.use_instr_margins, True); L.set_check(p.helper_markers_cb, False)
    if auto.isChecked():
        auto.click(); L.pump(200)
    pw(tab, "targen", "-f").set_value(300); L.pump(300)
    before_editor = key_recipe(L.recipe_of(tab))
    ed = {}

    def in_editor(dlg):
        L.pump(2500)                    # let the pre-load timer run
        L.grab(dlg, OUT9 / "e01-editor-opened-from-hint.png")
        try:
            erec = key_recipe(dlg._engine_panel.get_recipe().to_dict())
        except Exception as e:  # noqa: BLE001
            erec = {"error": repr(e)}
        ed["editor_recipe"] = erec
        ed["diff_vs_tab"] = {k: (before_editor.get(k), erec.get(k)) for k in before_editor if erec.get(k) != before_editor.get(k)} if "error" not in erec else erec
        L.log(f"  editor recipe vs tab: {ed['diff_vs_tab']}")
        ed["apply_enabled"] = dlg._apply_btn.isEnabled(); ed["apply_text"] = dlg._apply_btn.text()
        dlg._close_btn.click()
    watcher.expect("already", "Continue this project")
    st5 = drive_dialog("Ti2RelayoutDialog", "", in_editor, watcher, "editor from hint", timeout_ms=60000)
    # the hint's second button opens the editor; our generic watcher must click it
    watcher.expect("quite fill", "Edit patch set")
    L.click(tab._generate_btn)
    L.wait_build(tab, 240_000); L.pump(1000)
    L.wait_until(lambda: st5["seen"] or app.activeModalWidget() is None, 20000, "editor")
    L.pump(1500); watcher.clear()
    after_editor = key_recipe(L.recipe_of(tab))
    R["a9-editor"] = {"seen": st5["seen"], "err": st5["err"], **ed, "tab_recipe_changed_by_open_close": {k: (before_editor[k], after_editor[k]) for k in before_editor if before_editor[k] != after_editor[k]}}
    L.log(f"[editor] {R['a9-editor']}")
    # open again via Tools and Apply unchanged
    ed2 = {}

    def apply_in_editor(dlg):
        L.pump(2500)
        ed2["apply_enabled"] = dlg._apply_btn.isEnabled()
        L.grab(dlg, OUT9 / "e02-editor-before-apply.png")
        if dlg._apply_btn.isEnabled():
            dlg._apply_btn.click()
        else:
            dlg._close_btn.click()
    st6 = drive_dialog("Ti2RelayoutDialog", "", apply_in_editor, watcher, "editor apply", timeout_ms=30000)
    watcher.expect("already", "Continue this project"); watcher.expect("quite fill", "OK")
    win._launch_tool("ti2_relayout")
    L.pump(1500); L.wait_build(tab, 240_000); L.pump(1500); watcher.clear()
    s = L.panel_snapshot(tab)
    L.grab(win, OUT9 / "e03-after-apply.png")
    R["a9-apply"] = {"seen": st6["seen"], **ed2, "applied_active": getattr(tab, "_applied_active", None), "recipe_after": key_recipe(L.recipe_of(tab)),
                     "actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"], "info": tab._manual_info_lbl.text()[-200:],
                     "override_targen": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None}
    L.log(f"[editor apply] {R['a9-apply']}")

    # ---------------- F-003 re-check: raw printtarg widget values around a printtarg build
    L.set_combo_data(win._target_bar._run_combo, "\x00new"); L.pump(1000)
    L.set_check(tab._manual_engine_check, False); L.pump(800)
    def raw():
        return {f: (pw(tab, "printtarg", f).get_raw_value() if pw(tab, "printtarg", f) else None) for f in ("-i", "-p", "-L", "-a", "-m")}
    r0 = raw(); L.log(f"F-003 before generate: {r0} cmd={tab._manual_info_lbl.text().splitlines()[-1]!r}")
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    L.click(tab._generate_btn); r_during = raw()
    L.wait_build(tab, 240_000); r1 = raw(); L.pump(2500); r2 = raw(); watcher.clear()
    rd = L.current_run_dir(win)
    meta = json.loads((rd / "meta.json").read_text()) if (rd / "meta.json").is_file() else {}
    cs = meta.get("create_chart_settings", {})
    R["f003"] = {"before": r0, "during": r_during, "right_after": r1, "after_2s": r2, "cmd_before": tab._manual_info_lbl.text()[-200:],
                 "meta": {k: cs.get(k) for k in ("printtarg-L", "printtarg-a", "printtarg-m")},
                 "log_cmd": [l for l in L.tab_log_text(tab).splitlines() if l.startswith("printtarg") or "printtarg -" in l][-2:]}
    L.log(f"F-003 re-check: {R['f003']}")
    L.grab(win, OUT6 / "f003-after-printtarg-build.png")
    L.set_check(tab._manual_engine_check, True); L.pump(600)

    # ---------------- A7 debounce redo
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(p.layout_mode, "area_first"); L.set_check(p.use_instr_margins, True)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    L.click(tab._generate_btn); L.wait_build(tab, 240_000); watcher.clear(); L.pump(500)
    settings.set("auto_update_preview", True)
    tab._auto_preview_check.blockSignals(True); tab._auto_preview_check.setChecked(True); tab._auto_preview_check.blockSignals(False)
    def builds():
        return L.tab_log_text(tab).count("random start")
    n0 = builds()
    L.set_spin(p.area_min_patch, 10.0); L.pump(150); L.set_spin(p.area_min_patch, 11.0)
    t0 = time.time(); L.pump(7000)
    R["a7-debounce"] = {"builds_for_two_nudges_150ms": builds() - n0}
    n1 = builds()
    tab._manual_chart_notes_edit.setText("notes only edit"); tab._manual_chart_notes_edit.editingFinished.emit(); L.pump(4000)
    R["a7-notes"] = {"builds_for_notes_edit": builds() - n1}
    n2 = builds()
    tab._manual_target_name_edit.setText("A8-Presets"); L.pump(3000)
    R["a7-name"] = {"builds_for_name_edit": builds() - n2}
    L.log(f"A7: {R['a7-debounce']} {R['a7-notes']} {R['a7-name']}")
    settings.set("auto_update_preview", False)
    tab._auto_preview_check.blockSignals(True); tab._auto_preview_check.setChecked(False); tab._auto_preview_check.blockSignals(False)
    L.save_json(R, L.LOGS / "d05_results.json")
    L.log(f"unexpected: {[ (d['class'], d['title'], d['text'][:80]) for d in watcher.unexpected]} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
