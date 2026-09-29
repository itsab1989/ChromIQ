#!/usr/bin/env python3
"""R05: (A) what a FAILED build leaves on disk, by file name (F-025 and the
exports/ question) and the run round trip afterwards; (B) F-021 through a real
project re-open after a 22-page build; (C) built-in presets F-015/F-016/F-017
and the preset reveal button (openUrl logged, not opened); (D) F-027 completed:
external .ti1 armed in R2-Engine, then Generate on R2-High with its .ti1
inspected; (E) F-029 with calibration mode on for this session only."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402
from PyQt6.QtGui import QDesktopServices  # noqa: E402

OUT = L.SHOTS / "R05-files-presets-cal"
R: dict = {}
ENGINE = "R2-Engine"
HIGH = "R2-High"


def names(d: Path) -> list:
    return sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()) if d and d.is_dir() else []


def pick_preset(tab, text: str) -> bool:
    c = tab._preset_combo
    for i in range(c.count()):
        if text.lower() in c.itemText(i).lower():
            c.setCurrentIndex(i); L.pump(100); c.activated.emit(i); L.pump(400)
            L.log(f"  picked preset #{i} {c.itemText(i)!r} (activated)")
            return True
    L.log(f"  preset {text!r} not in {[c.itemText(i) for i in range(c.count())]}")
    return False


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    L.open_project(win, settings, ENGINE)
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn); L.pump(400)
    panel = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(panel.instr, "i1"); L.set_combo_data(panel.paper, "A4"); L.set_combo_data(panel.mode, "clip")
    L.set_combo_data(panel.layout_mode, "area_first"); L.set_check(panel.use_instr_margins, True); L.set_spin(panel.pages, 1); L.pump(400)

    # ---------------- A. failed build: files by name ----------------
    s0 = L.gen(tab, watcher, "good A4 chart", extra_expect=[("already", "Continue")])
    run_dir = L.current_run_dir(win)
    before = names(run_dir)
    ti2_before = L.ti2_facts(next(run_dir.glob("*.ti2")))
    # impossible layout
    idx = next(i for i in range(panel.paper.count()) if "ustom" in str(panel.paper.itemData(i)))
    panel.paper.setCurrentIndex(idx); L.pump(200)
    L.set_spin(panel.custom_w, 20); L.set_spin(panel.custom_h, 20)
    L.set_combo_data(panel.layout_mode, "patch_first"); L.set_spin(panel.patch_x, 60.0); L.set_spin(panel.patch_y, 60.0); L.pump(500)
    n0 = len(L.APP_LINES); ns = len(watcher.seen)
    L.click(tab._generate_btn); L.wait_build(tab, 120_000); L.pump(1500)
    after = names(run_dir)
    snap = L.panel_snapshot(tab)
    R["A_failed_build"] = {"files_before": before, "files_after": after,
                           "missing_after": sorted(set(before) - set(after)), "new_after": sorted(set(after) - set(before)),
                           "ti2_before": ti2_before, "ti2_after": L.ti2_facts(next(run_dir.glob("*.ti2"), Path("/x"))),
                           "dialogs": watcher.seen[ns:], "errors": L.app_lines_since(n0, r"ERROR|WARNING.*estimate|too short"),
                           "preview_pages": snap["preview_pages"], "status_visible": snap["margin_status_visible"],
                           "tab_log_tail": L.tab_log_text(tab)[-700:]}
    L.log(f"  A: missing after failure={R['A_failed_build']['missing_after']} new={R['A_failed_build']['new_after']} preview_pages={snap['preview_pages']}")
    L.grab(win, OUT / "a01-after-failed-build.png")
    # run round trip: New run and back
    L.set_combo_data(win._target_bar._run_combo, "\x00new"); L.pump(1200)
    L.set_combo_data(win._target_bar._run_combo, "run1"); L.pump(1500)
    snap2 = L.panel_snapshot(tab)
    R["A_roundtrip"] = {"preview_pages": snap2["preview_pages"], "actual": snap2["layout_info_actual"], "status": snap2["margin_status"],
                        "panel_paper": panel.paper.currentText(), "custom": (panel.custom_w.value(), panel.custom_h.value()),
                        "patch": (panel.patch_x.value(), panel.patch_y.value()), "layout_mode": panel.layout_mode.currentData()}
    L.log(f"  A roundtrip: {R['A_roundtrip']}")
    L.grab(win, OUT / "a02-after-run-roundtrip.png")

    # ---------------- B. F-021 via re-open after a 22-page build ----------------
    L.set_combo_data(panel.paper, "A4"); L.set_combo_data(panel.layout_mode, "patch_first"); L.set_spin(panel.patch_x, 0.0); L.set_spin(panel.patch_y, 0.0)
    if auto.isChecked():
        auto.click(); L.pump(200)
    L.pw(tab, "targen", "-f").set_value(9500); L.pump(400)
    s1 = L.gen(tab, watcher, "9500 fixed, 22 pages", extra_expect=[("already", "Continue")], timeout_ms=400_000)
    R["B"] = {"built": s1["layout_info_actual"], "spins_after_build": (panel.get_pages(), tab._manual_pages_spin.value())}
    L.open_project(win, settings, "Demo-Full-RGB"); L.pump(500)
    L.open_project(win, settings, ENGINE); L.pump(800)
    tab = L.goto_chart_tab(win); L.click(tab._manual_btn); L.pump(500)
    panel = tab._manual_layout_panel; auto = tab._manual_auto_patches_check
    R["B"]["spins_after_reopen"] = (panel.get_pages(), tab._manual_pages_spin.value(), panel.pages.isEnabled(), tab._manual_pages_spin.isEnabled())
    R["B"]["auto_after_reopen"] = auto.isChecked()
    R["B"]["f_after_reopen"] = L.pw(tab, "targen", "-f").get_raw_value()
    if not auto.isChecked():
        auto.click(); L.pump(300)
    R["B"]["spins_after_auto"] = (panel.get_pages(), tab._manual_pages_spin.value())
    L.set_spin(panel.pages, 1); L.pump(600)
    R["B"]["spins_after_pages1"] = (panel.get_pages(), tab._manual_pages_spin.value())
    R["B"]["est_after_pages1"] = L.panel_snapshot(tab)["layout_info_estimate"]
    L.log(f"  B F-021: {R['B']}")
    L.grab(win, OUT / "b01-f021-after-reopen-pages1.png")
    s2 = L.gen(tab, watcher, "after reopen, pages 1", extra_expect=[("already", "Continue")], timeout_ms=400_000)
    R["B"]["built_after"] = s2["layout_info_actual"]; R["B"]["est_after"] = s2["layout_info_estimate"]
    L.log(f"  B built pages={s2['layout_info_actual'] and s2['layout_info_actual']['pages']} est pages={s2['layout_info_estimate'] and s2['layout_info_estimate']['pages']}")

    # ---------------- C. built-ins and the reveal button ----------------
    opened = []
    orig_open = QDesktopServices.openUrl
    QDesktopServices.openUrl = staticmethod(lambda url: (opened.append(url.toString()), True)[1])  # logged, not opened
    L.log(f"  presets in combo: {[tab._preset_combo.itemText(i) for i in range(tab._preset_combo.count())]}")
    R["C"] = {}
    for key, text in (("tc918eg", "TC9.18 extended greys by Pharmacist"), ("knut_i1_162", "162p-1page-Portrait-w7.5mm"),
                      ("cr30_153", "CR30 A4-153p"), ("none", "none")):
        eng_before = tab._manual_engine_check.isChecked()
        watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue")
        ok = pick_preset(tab, text)
        L.wait_build(tab, 240_000); L.pump(1200); watcher.clear()
        s = L.panel_snapshot(tab)
        R["C"][key] = {"picked": ok, "engine_before": eng_before, "engine_after": tab._manual_engine_check.isChecked(),
                       "engine_enabled": tab._manual_engine_check.isEnabled(), "info": tab._manual_info_lbl.text(),
                       "actual": s["layout_info_actual"], "est": s["layout_info_estimate"], "status": s["margin_status"],
                       "notes": s["margin_notes"], "margins": s["margin_panel_text"][:240],
                       "override_pt": (tab._override_printtarg_check.isVisible(), tab._override_printtarg_check.isChecked()) if tab._override_printtarg_check else None}
        L.log(f"  builtin {key}: engine {eng_before}->{R['C'][key]['engine_after']} status={s['margin_status']!r}\n     info={tab._manual_info_lbl.text()[:260]!r}")
        L.grab(win, OUT / f"c-builtin-{key}.png")
    L.click(tab._preset_reveal_btn); L.pump(600)
    R["C"]["reveal"] = {"opened": list(opened), "tooltip": tab._preset_reveal_btn.toolTip()[:200], "enabled": tab._preset_reveal_btn.isEnabled()}
    L.log(f"  reveal: {R['C']['reveal']}")
    QDesktopServices.openUrl = orig_open

    # ---------------- D. F-027 completed ----------------
    ext = L.ASSESS / "Evidence" / "external_patchset.ti1"
    ext_sets = L.ti1_sets(ext)
    import ui.tabs.tab_chart as TC
    orig_dlg = TC.open_file_dialog
    TC.open_file_dialog = lambda *a, **k: str(ext)
    L.log(f"  header Load patch set: native picker replaced by {ext.name} ({ext_sets} sets); logged substitution")
    watcher.expect("Where should this patch set", "Build it as a new run instead"); watcher.expect("quite fill", "OK"); watcher.expect("loaded", "OK")
    ns = len(watcher.seen)
    L.click(tab._load_ti1_btn); L.wait_build(tab, 240_000); L.pump(1500); watcher.clear()
    TC.open_file_dialog = orig_dlg
    s = L.panel_snapshot(tab)
    R["D"] = {"engine_run_after_load": win._target_bar._run_combo.currentText(), "actual": s["layout_info_actual"], "est": s["layout_info_estimate"],
              "dialogs": watcher.seen[ns:], "preset_ti1": str(getattr(tab, "_preset_ti1_path", None)),
              "override_row": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None}
    L.log(f"  D loaded into {ENGINE}: run={R['D']['engine_run_after_load']} actual={s['layout_info_actual']} armed={R['D']['preset_ti1']}")
    # now open the OTHER project
    L.open_project(win, settings, HIGH); L.pump(800)
    tab = L.goto_chart_tab(win); L.click(tab._manual_btn); L.pump(600)
    high_run = L.current_run_dir(win)
    high_before = names(high_run)
    ti1_before = L.ti1_sets(next(high_run.glob("*.ti1"), Path("/x")))
    R["D"]["high_state"] = {"run": win._target_bar._run_combo.currentText(), "preset_ti1": str(getattr(tab, "_preset_ti1_path", None)),
                            "override_row": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None,
                            "engine_enabled": tab._manual_engine_check.isEnabled(), "engine_on": tab._manual_engine_check.isChecked(),
                            "info": tab._manual_info_lbl.text(), "targen_grp_visible": tab._manual_targen_grp.isVisible(),
                            "f_value": L.pw(tab, "targen", "-f").get_raw_value(), "ti1_sets_before": ti1_before,
                            "est": L.panel_snapshot(tab)["layout_info_estimate"]}
    L.log(f"  D on {HIGH}: {R['D']['high_state']}")
    L.grab(win, OUT / "d01-other-project-armed.png")
    n0 = len(L.APP_LINES)
    s = L.gen(tab, watcher, f"Generate on {HIGH} with foreign set armed", extra_expect=[("already", "Continue")])
    high_run = L.current_run_dir(win)
    R["D"]["high_after"] = {"run": win._target_bar._run_combo.currentText(), "actual": s["layout_info_actual"],
                            "ti1_sets_after": L.ti1_sets(next(high_run.glob("*.ti1"), Path("/x"))), "ti2": L.ti2_facts(next(high_run.glob("*.ti2"), Path("/x"))),
                            "targen_ran": L.app_lines_since(n0, r"Run.*targen"), "engine_or_printtarg": L.app_lines_since(n0, r"Run.*printtarg|layout engine\]")[:3],
                            "log_tail": L.tab_log_text(tab)[-500:]}
    L.log(f"  D after Generate on {HIGH}: ti1 sets {ti1_before} -> {R['D']['high_after']['ti1_sets_after']} (foreign set has {ext_sets}); targen ran={bool(R['D']['high_after']['targen_ran'])}")
    L.grab(win, OUT / "d02-other-project-after-generate.png")

    # ---------------- E. F-029 calibration ----------------
    settings.set("calibration_mode", True); win._apply_calibration_mode(); L.pump(500)
    L.open_project(win, settings, "Demo-Full-RGB"); L.pump(800)
    tab = L.goto_chart_tab(win)
    ok = L.set_combo_data(win._target_bar._type_combo, "calibration"); L.pump(1500)
    R["E"] = {"type_set": ok, "type": win._target_bar._type_combo.currentText(), "run": win._target_bar._run_combo.currentText(),
              "loc": win._target_bar._location.text(), "generate_enabled": tab._generate_btn.isEnabled(), "stop_visible": tab._stop_btn.isVisible(),
              "cal_meta_calibration_used": [ (r, L.read_json(Path('/Users/Basti/ChromIQ-assessment/Demo-Full-RGB/runs')/r/'meta.json').get('calibration_used')) for r in ("run1","run2","run3","run4")]}
    L.grab(win, OUT / "e01-calibration-selected.png")
    n0 = len(L.APP_LINES); ns = len(watcher.seen)
    watcher.expect("already has a finished calibration", "Cancel")
    L.click(tab._generate_btn); L.pump(2500); watcher.clear()
    R["E"].update({"dialogs": watcher.seen[ns:], "trace_lines": L.app_lines_since(n0, r"could not list runs|AttributeError|Traceback")[:4],
                   "generate_after": tab._generate_btn.isEnabled()})
    L.log(f"  E F-029: dialogs={[d.get('text','')[:160] for d in watcher.seen[ns:]]} trace={R['E']['trace_lines']}")
    settings.set("calibration_mode", False); win._apply_calibration_mode(); L.pump(500)

    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r05_results.json")
    L.log(f"unexpected={[(u.get('text') or '')[:120] for u in watcher.unexpected]} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
