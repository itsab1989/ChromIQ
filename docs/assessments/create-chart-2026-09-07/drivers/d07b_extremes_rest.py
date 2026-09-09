#!/usr/bin/env python3
"""D07b (resume of D07 after the 10,000-patch step): fresh-session Chart Layout default; clean auto-update order (build,
tick, nudge; preset load; nudge); A10 extremes; B12 names; B7 run bar
(switch mid-edit, deleted project folder). Results saved after every block."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402

OUT10 = L.SHOTS / "A10-extremes"
OUT12 = L.SHOTS / "B12-names-files"
OUT7b = L.SHOTS / "B7-runbar"
OUT7 = L.SHOTS / "A7-auto-preview"
OUT8 = L.SHOTS / "A8-presets"
R: dict = {}


def save():
    L.save_json(R, L.LOGS / "d07b_results.json")


def pw(tab, tool, flag):
    for w in tab._manual_widgets.get(tool, []):
        if w.flag == flag:
            return w


def build(tab, watcher, timeout=240_000, extra_expect=()):
    for m, b in extra_expect:
        watcher.expect(m, b)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    n0 = len(L.SERIOUS); ns = len(watcher.seen)
    t0 = time.time()
    L.click(tab._generate_btn)
    ok = L.wait_build(tab, timeout)
    stopped = False
    if not ok and tab._runner.is_running:
        L.log("    build still running at timeout -> pressing Stop"); L.click(tab._stop_btn); L.wait_build(tab, 60_000); stopped = True
    L.pump(600); watcher.clear()
    s = L.panel_snapshot(tab)
    logtxt = L.tab_log_text(tab)
    return {"ok": ok, "stopped": stopped, "secs": round(time.time() - t0, 1), "actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"],
            "status": s["margin_status"], "notes": s["margin_notes"], "margin_text": s["margin_panel_text"][:260],
            "dialogs": [(d.get("title") or d.get("text", "")[:70], d.get("answer")) for d in watcher.seen[ns:]],
            "serious": L.serious_since(n0), "errors": [l for l in logtxt.splitlines() if "[ERROR]" in l or "CRITICAL" in l or "Traceback" in l][-3:],
            "engine": [l for l in logtxt.splitlines() if "engine]" in l][-2:]}


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    L.open_project(win, settings, "A10-Extremes")
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn); L.pump(500)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    p = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.mode, "clip"); L.set_combo_data(p.layout_mode, "area_first")
    L.set_check(p.use_instr_margins, True); L.set_spin(p.area_min_patch, 0.0); L.set_spin(p.pages, 1); L.set_spin(p.patch_x, 0.0); L.set_spin(p.patch_y, 0.0)
    R["x-10000-from-disk"] = {"note": "built in D07 at 09:07:01-09:07:33: targen 27 s, engine 4 s, 36 pages of 20x14 = 280, 10000 sets, 34 MB of TIFF; the driver then stalled on a modal its own watcher missed (id reuse), see checkpoint-07"}
    # patch larger than the page
    L.set_combo_data(p.paper, "__custom__"); L.set_spin(p.custom_w, 20.0); L.set_spin(p.custom_h, 20.0)
    L.set_combo_data(p.layout_mode, "patch_first"); L.set_spin(p.patch_x, 60.0); L.set_spin(p.patch_y, 60.0); L.pump(600)
    R["x-patch-bigger-than-page"] = {"estimate": L.panel_snapshot(tab)["layout_info_estimate"], "info": tab._manual_info_lbl.text()[-200:], "generate_enabled": tab._generate_btn.isEnabled(), **build(tab, watcher, timeout=120_000)}
    L.log(f"60 mm patch on 20x20: {R['x-patch-bigger-than-page']}"); L.grab(win, OUT10 / "x03-patch-bigger-than-page.png"); save()
    # margins leaving no room
    L.set_spin(p.custom_w, 100.0); L.set_spin(p.custom_h, 100.0); L.set_spin(p.patch_x, 0.0); L.set_spin(p.patch_y, 0.0)
    L.set_check(p.use_instr_margins, False)
    for k in ("t", "r", "b", "l"):
        L.set_spin(p.margins[k], 50.0)
    L.pump(600)
    R["x-margins-no-room"] = {"estimate": L.panel_snapshot(tab)["layout_info_estimate"], "info": tab._manual_info_lbl.text()[-200:], **build(tab, watcher, timeout=120_000)}
    L.log(f"margins 50 on 100x100: {R['x-margins-no-room']}"); L.grab(win, OUT10 / "x04-margins-no-room.png"); save()
    for k in ("t", "r", "b", "l"):
        L.set_spin(p.margins[k], 6.0)
    # grid 200 x 500 on A4
    L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.layout_mode, "area_first"); L.set_combo_data(p.area_method, "by_grid")
    L.set_spin(p.area_cols, 200); L.set_spin(p.area_rows, 500); L.pump(600)
    R["x-grid-200x500"] = {"estimate": L.panel_snapshot(tab)["layout_info_estimate"], "info": tab._manual_info_lbl.text()[-200:], **build(tab, watcher, timeout=240_000)}
    L.log(f"grid 200x500: {R['x-grid-200x500']}"); L.grab(win, OUT10 / "x05-grid-200x500.png"); save()
    L.set_spin(p.area_cols, 0); L.set_spin(p.area_rows, 0); L.set_combo_data(p.area_method, "by_width")
    # dpi 72 and 1200 on 100x100 custom
    L.set_combo_data(p.paper, "__custom__"); L.set_spin(p.custom_w, 100.0); L.set_spin(p.custom_h, 100.0)
    for dpi in (72, 1200):
        L.set_spin(p.dpi, dpi); L.pump(400)
        r = build(tab, watcher, timeout=240_000)
        rd = L.current_run_dir(win); inv = L.run_inventory(rd)
        R[f"x-dpi-{dpi}"] = {**r, "tiffs": inv.get("tiffs")}
        L.log(f"dpi {dpi}: ok={r['ok']} secs={r['secs']} tiffs={inv.get('tiffs')} actual={r['actual']}")
        save()
    L.set_spin(p.dpi, 300); L.set_combo_data(p.paper, "A4"); L.set_check(p.use_instr_margins, True)
    # pages 20 with CM hand-held
    L.set_combo_data(p.instr, "CM"); L.set_combo_data(p.mode, "freehand"); L.set_spin(p.pages, 20); L.pump(600)
    R["x-pages-20-CM"] = {"estimate": L.panel_snapshot(tab)["layout_info_estimate"], **build(tab, watcher, timeout=300_000)}
    L.log(f"20 pages CM: {R['x-pages-20-CM']}"); L.grab(win, OUT10 / "x06-20-pages-CM.png"); save()
    L.set_spin(p.pages, 1); L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.mode, "clip")
    # custom paper at its limits
    for w_, h_ in ((20.0, 20.0), (2000.0, 2000.0)):
        L.set_combo_data(p.paper, "__custom__"); L.set_spin(p.custom_w, w_); L.set_spin(p.custom_h, h_); L.pump(600)
        R[f"x-custom-{int(w_)}"] = {"estimate": L.panel_snapshot(tab)["layout_info_estimate"], "info": tab._manual_info_lbl.text()[-160:]}
        if w_ == 20.0:
            R[f"x-custom-{int(w_)}"].update(build(tab, watcher, timeout=120_000))
        L.log(f"custom {w_}x{h_}: {R[f'x-custom-{int(w_)}']}")
    save()
    L.set_combo_data(p.paper, "A4")

    # ---------------- B12 names
    names = [("", "empty"), ("A10-Extremes", "duplicate-open"), ("A1-EngineVsPrinttarg", "duplicate-other"), ("Ümläut Äpfel Øre", "umlauts"),
             ("x" * 250, "long250"), ("a/b:c", "slash-colon"), ("  trailing  ", "trailing-spaces"), ("CON", "windows-reserved"), (".dot", "leading-dot")]
    for name, tag in names:
        tab._manual_target_name_edit.setText(name); L.pump(300)
        hint = tab._project_exists_lbl.text() if hasattr(tab, "_project_exists_lbl") else ""
        ns = len(watcher.seen)
        watcher.expect("Give this project a name", "<reject>")
        watcher.expect("Rename Printer Profile", "Cancel")
        watcher.expect("already", "Cancel")
        L.click(tab._generate_btn); L.pump(1500)
        # if a build started, wait for it
        if tab._runner.is_running or not tab._generate_btn.isEnabled():
            L.wait_build(tab, 120_000)
        watcher.clear()
        seen = [(d.get("class"), d.get("title"), d.get("text", "")[:260], d.get("answer")) for d in watcher.seen[ns:]]
        R[f"name-{tag}"] = {"typed": name, "hint_line": hint, "dialogs": seen, "field_after": tab._manual_target_name_edit.text(),
                            "location": win._target_bar._location.text()[-80:], "built": L.panel_snapshot(tab)["layout_info_actual"]}
        L.log(f"name {tag}: dialogs={[(s[1] or s[2][:60], s[3]) for s in seen]} field_after={tab._manual_target_name_edit.text()!r} loc={win._target_bar._location.text()[-60:]!r}")
        L.grab(win, OUT12 / f"n-{tag}.png")
        save()
    # projects created by the names test?
    R["projects-on-disk"] = sorted(d.name for d in Path("/Users/Basti/ChromIQ-assessment").iterdir() if d.is_dir())
    L.log(f"projects on disk now: {R['projects-on-disk']}")

    # ---------------- B7 run bar: switch mid-edit, deleted folder
    L.open_project(win, settings, "A1-EngineVsPrinttarg"); L.click(tab._manual_btn); L.pump(500)
    L.set_combo_data(win._target_bar._run_combo, "run1"); L.pump(1000)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    before = {"margin_t": p.margins["t"].value(), "use_instr": p.use_instr_margins.isChecked(), "text": p.chart_text.text()}
    L.set_check(p.use_instr_margins, False); L.set_spin(p.margins["t"], 44.0); p.chart_text.setText("mid-edit"); p.chart_text.editingFinished.emit(); L.pump(400)
    L.set_combo_data(win._target_bar._run_combo, "run2"); L.pump(1200)
    on_run2 = {"margin_t": p.margins["t"].value(), "text": p.chart_text.text(), "engine": tab._manual_engine_check.isChecked()}
    L.set_combo_data(win._target_bar._run_combo, "run1"); L.pump(1200)
    back = {"margin_t": p.margins["t"].value(), "use_instr": p.use_instr_margins.isChecked(), "text": p.chart_text.text(), "engine": tab._manual_engine_check.isChecked()}
    meta = json.loads((Path("/Users/Basti/ChromIQ-assessment/A1-EngineVsPrinttarg/runs/run1/meta.json")).read_text())
    rec = ((meta.get("create_chart_ui") or {}).get("engine_recipe") or {})
    R["runbar-mid-edit"] = {"before": before, "on_run2": on_run2, "back_on_run1": back, "stored_run1": {"margin_top": rec.get("margin_top"), "chart_text": rec.get("chart_text"), "use_instr": rec.get("use_instrument_margins")}}
    L.log(f"run bar mid-edit: {R['runbar-mid-edit']}"); L.grab(win, OUT7b / "r01-back-on-run1.png"); save()
    # deleted project folder while open
    tab._manual_target_name_edit.setText("B7-Delete"); L.pump(200)
    r = build(tab, watcher, extra_expect=(("Rename Printer Profile", "Create \"B7-Delete\" and keep"),))
    proj = Path("/Users/Basti/ChromIQ-assessment/B7-Delete")
    R["deleted-folder"] = {"built": r["actual"], "existed": proj.exists()}
    if proj.exists():
        shutil.rmtree(proj)
        L.log("  removed project folder B7-Delete while it is open")
        L.pump(1500)
        R["deleted-folder"]["run_bar_after_rm"] = win._target_bar._run_combo.currentText()
        R["deleted-folder"]["location_after_rm"] = win._target_bar._location.text()
        ns = len(watcher.seen)
        watcher.expect("Give this project a name", "<reject>"); watcher.expect("already", "Cancel"); watcher.expect("Rename", "Cancel")
        L.click(tab._generate_btn); L.wait_build(tab, 120_000); L.pump(1000); watcher.clear()
        R["deleted-folder"]["generate_after_rm"] = {"dialogs": [(d.get("title") or d.get("text", "")[:80], d.get("answer")) for d in watcher.seen[ns:]], "folder_recreated": proj.exists(),
                                                    "files": sorted(str(x.relative_to(proj)) for x in proj.rglob("*") if x.is_file()) if proj.exists() else [],
                                                    "log_tail": L.tab_log_text(tab)[-500:], "serious": L.serious_since(0)[-3:]}
        L.grab(win, OUT7b / "r02-after-folder-deleted-and-generate.png")
        # run switch after deletion
        L.set_combo_data(win._target_bar._run_combo, "\x00new"); L.pump(1200)
        R["deleted-folder"]["new_run_after_rm"] = {"run_bar": win._target_bar._run_combo.currentText(), "location": win._target_bar._location.text(), "serious": L.serious_since(0)[-3:]}
        L.grab(win, OUT7b / "r03-new-run-after-folder-deleted.png")
    L.log(f"deleted folder: {R['deleted-folder']}"); save()
    L.log(f"unexpected: {[(d['class'], d['title'], d['text'][:80]) for d in watcher.unexpected]} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
