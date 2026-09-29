#!/usr/bin/env python3
"""D06 (B1 Guided, A1 parity, preset restart, A7 real click, Chart Layout
defaults): Guided builds for i1 A4, CM A4, p3 A4R (1 page): headline count vs
built count, info line, the transfer to MANUAL, and printtarg run by hand with
the creator's own argument builder on the Guided .ti1 (parity). Then the
AssessPresetB compare after a real process restart, auto-update via a real
checkbox click, and a Chart Layout default set through Preferences."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialogButtonBox  # noqa: E402

OUT = L.SHOTS / "B1-guided"
OUT7 = L.SHOTS / "A7-auto-preview"
OUT8 = L.SHOTS / "A8-presets"
PROJECT = "B1-Guided"
SCRATCH = Path("/private/tmp/claude-502/-Users-Basti-develop-ChromIQ/43fe026d-47c0-4e05-aad3-52c64d8d9eca/scratchpad/parity")
R: dict = {}


def save():
    L.save_json(R, L.LOGS / "d06_results.json")


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "")


def ti2_facts(p: Path):
    t = p.read_text(errors="replace")
    g = lambda pat: (re.search(pat, t).group(1) if re.search(pat, t) else None)  # noqa: E731
    return {"sets": g(r"NUMBER_OF_SETS\s+(\d+)"), "steps": g(r'STEPS_IN_PASS\s+"?(\d+)"?'), "passes": g(r'PASSES_IN_STRIPS2\s+"?([\d,]+)"?'),
            "instr": g(r'TARGET_INSTRUMENT\s+"([^"]+)"'), "paper": g(r'PAPER_SIZE\s+"?([^"\n]+)"?')}


def parity(tab, ti1: Path, tag: str):
    p = tab._collect_guided()
    args = tab._creator._build_printtarg_args(p)
    d = SCRATCH / tag
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    shutil.copy(ti1, d / f"{args[-1]}.ti1")
    cmd = ["/Applications/Argyll/bin/printtarg"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(d))
        rc, out = r.returncode, r.stdout[-600:]
    except subprocess.TimeoutExpired:
        rc, out = None, "timeout 180 s"
    ti2 = next(d.glob("*.ti2"), None)
    tiffs = sorted(d.glob("*.tif"))
    facts = ti2_facts(ti2) if ti2 else None
    from PIL import Image
    px = None
    if tiffs:
        with Image.open(tiffs[0]) as im:
            px = im.size
    return {"cmd": " ".join(cmd), "rc": rc, "ti2": facts, "pages": len(tiffs), "tiff_px": px, "stdout_tail": out[-300:]}


def guided_build(win, tab, watcher, instr, paper, pages, tag):
    L.click(tab._guided_btn); L.pump(400)
    L.set_combo_data(tab._instr_combo, instr); L.pump(300)
    L.set_combo_data(tab._paper_combo, paper); L.pump(300)
    L.set_spin(tab._pages_spin, pages); L.pump(600)
    headline = strip_html(tab._patch_count_lbl.text())
    detail = tab._patch_detail_lbl.text()
    info = strip_html(tab._guided_info_lbl.text())
    est = L.panel_snapshot(tab)["layout_info_estimate"]
    L.grab(win, OUT / f"{tag}-before.png")
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    n0 = len(L.SERIOUS)
    L.click(tab._generate_btn); ok = L.wait_build(tab, 300_000); L.pump(800); watcher.clear()
    s = L.panel_snapshot(tab)
    rd = L.current_run_dir(win); inv = L.run_inventory(rd) if rd else {}
    L.grab(win, OUT / f"{tag}-after.png")
    eng = [l for l in L.tab_log_text(tab).splitlines() if "layout engine]" in l][-4:]
    r = {"tag": tag, "ok": ok, "headline": headline, "detail": detail, "info": info[-260:], "estimate_before": est,
         "actual": s["layout_info_actual"], "estimate_after": s["layout_info_estimate"], "margin_text": s["margin_panel_text"][:300],
         "status": s["margin_status"], "notes": s["margin_notes"], "ti2": {k: v for k, v in inv.items() if k.startswith("ti2")},
         "channels": inv.get("channels"), "n_tiffs": len(inv.get("tiffs") or []), "serious": L.serious_since(n0), "engine_log": eng,
         "headline_number": int(re.sub(r"\D", "", headline) or 0)}
    ti1 = next(rd.glob("*.ti1"), None)
    if ti1:
        r["parity"] = parity(tab, ti1, tag)
    R[tag] = r; save()
    L.log(f"[{tag}] headline={headline!r} built={r['actual'] and (r['actual']['total'], r['actual']['rows'], r['actual']['cols'], r['actual']['pages'])} est_before={est and (est['total'], est['rows'], est['cols'])} parity={r.get('parity', {}).get('ti2')} pages={r.get('parity', {}).get('pages')} cmd={r.get('parity', {}).get('cmd', '')[-70:]}")
    return r


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    L.click(tab._guided_btn); L.pump(300)
    tab._target_name_edit.setText(PROJECT); tab._target_name_edit.editingFinished.emit(); L.pump(300)
    watcher.expect("Give this project a name", "<reject>")
    # Guided controls inventory
    R["guided-controls"] = {"lb_text": tab._lb_check.text(), "nsl_text": tab._nsl_check.text(), "dd_text": tab._dd_check.text(), "td_text": tab._td_check.text(),
                            "precond_visible": tab._guided_precond_check.isVisible(), "name_hint": tab._target_name_hint.text()}
    g1 = guided_build(win, tab, watcher, "i1", "A4", 1, "g-i1-A4-1p")
    g2 = guided_build(win, tab, watcher, "CM", "A4", 1, "g-CM-A4-1p")
    g3 = guided_build(win, tab, watcher, "p3", "A4R", 1, "g-p3-A4R-1p")
    g4 = guided_build(win, tab, watcher, "i1", "A4", 2, "g-i1-A4-2p")
    # Guided estimate vs headline consistency when toggling the two boxes
    L.set_combo_data(tab._instr_combo, "i1"); L.set_combo_data(tab._paper_combo, "A4"); L.set_spin(tab._pages_spin, 1); L.pump(400)
    base_head = strip_html(tab._patch_count_lbl.text())
    L.set_check(tab._lb_check, not tab._lb_check.isChecked()); L.pump(500)
    lb_head = strip_html(tab._patch_count_lbl.text()); lb_est = L.panel_snapshot(tab)["layout_info_estimate"]
    L.set_check(tab._lb_check, not tab._lb_check.isChecked()); L.pump(300)
    L.set_check(tab._nsl_check, True); L.pump(500)
    nsl_head = strip_html(tab._patch_count_lbl.text()); nsl_est = L.panel_snapshot(tab)["layout_info_estimate"]
    L.set_check(tab._nsl_check, False); L.pump(300)
    R["guided-toggles"] = {"base": base_head, "clip_toggled": lb_head, "clip_est": lb_est, "nsl": nsl_head, "nsl_est": nsl_est,
                           "lb_label": tab._lb_check.text(), "nsl_label": tab._nsl_check.text()}
    L.log(f"guided toggles: {R['guided-toggles']}"); save()

    # transfer to Manual right after a Guided build (#79 exact seed)
    g5 = guided_build(win, tab, watcher, "CM", "A4", 1, "g-CM-A4-1p-b")
    L.click(tab._manual_btn); L.pump(1200)
    p = tab._manual_layout_panel
    rec = L.recipe_of(tab)
    s = L.panel_snapshot(tab)
    R["transfer"] = {"engine_check": tab._manual_engine_check.isChecked(), "instr": p.instr.currentData(), "paper": p.paper.currentData(), "mode": p.mode.currentData(),
                     "recipe": {k: rec.get(k) for k in ("instrument", "paper", "cm_density", "layout_mode", "margin_top", "margin_right", "margin_bottom", "margin_left", "use_instrument_margins", "pscale", "patch_area_align", "spacer_mode")},
                     "estimate": s["layout_info_estimate"], "actual": s["layout_info_actual"], "info": tab._manual_info_lbl.text()[-240:],
                     "auto_patches": tab._manual_auto_patches_check.isChecked(), "pages": p.pages.value(), "f": None}
    for w in tab._manual_widgets.get("targen", []):
        if w.flag == "-f":
            R["transfer"]["f"] = w.get_raw_value()
    L.grab(win, OUT / "t01-manual-after-guided-build.png")
    L.log(f"transfer: {R['transfer']}"); save()
    # Generate in Manual without touching anything: same chart?
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    L.click(tab._generate_btn); L.wait_build(tab, 240_000); L.pump(800); watcher.clear()
    s2 = L.panel_snapshot(tab)
    R["transfer-generate"] = {"actual": s2["layout_info_actual"], "estimate": s2["layout_info_estimate"], "guided_built": g5["actual"]}
    L.log(f"manual generate after transfer: {R['transfer-generate']}"); save()
    L.grab(win, OUT / "t02-manual-generate-after-transfer.png")

    # ---------------- preset B after a real restart
    c = tab._preset_combo
    idx = next((i for i in range(c.count()) if c.itemData(i) == "AssessPresetB"), -1)
    saved = json.loads((L.LOGS / "d05b_presetB_recipe_saved.json").read_text())
    if idx >= 0:
        watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
        c.setCurrentIndex(idx); c.activated.emit(idx); L.wait_build(tab, 240_000); L.pump(1500); watcher.clear()
        now = L.recipe_of(tab)
        diff = {k: (saved.get(k), now.get(k)) for k in set(saved) | set(now) if saved.get(k) != now.get(k) and k not in ("seed",)}
        R["presetB-restart"] = {"found": True, "diff": diff, "combo": c.currentText(), "engine": tab._manual_engine_check.isChecked()}
    else:
        R["presetB-restart"] = {"found": False, "items": [c.itemData(i) for i in range(c.count()) if c.itemData(i) and "Assess" in str(c.itemData(i))]}
    L.log(f"presetB after restart: {R['presetB-restart']}"); save()
    L.grab(win, OUT8 / "q20-presetB-after-restart.png")
    c.setCurrentIndex(0); c.activated.emit(0); L.pump(600)

    # ---------------- A7 with a real checkbox click
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.mode, "clip")
    L.set_combo_data(p.layout_mode, "area_first"); L.set_check(p.use_instr_margins, True); L.set_spin(p.area_min_patch, 0.0); L.set_spin(p.pages, 1)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    L.click(tab._generate_btn); L.wait_build(tab, 240_000); watcher.clear(); L.pump(500)
    builds = lambda: L.tab_log_text(tab).count("random start")  # noqa: E731
    if tab._auto_preview_check.isChecked():
        L.set_check(tab._auto_preview_check, False); L.pump(300)
    watcher.expect("Auto-update preview is on", "Close")
    L.set_check(tab._auto_preview_check, True); L.pump(800); watcher.clear()
    n0 = builds(); t0 = time.time()
    L.set_spin(p.area_min_patch, 10.0); L.pump(150); L.set_spin(p.area_min_patch, 11.0)
    L.wait_until(lambda: builds() > n0, 6000, "first auto build"); t_first = round(time.time() - t0, 2)
    L.pump(6000)
    R["a7-debounce"] = {"builds_for_two_nudges_150ms_apart": builds() - n0, "first_build_after_s": t_first, "actual": L.panel_snapshot(tab)["layout_info_actual"], "estimate": L.panel_snapshot(tab)["layout_info_estimate"]}
    n1 = builds(); tab._manual_chart_notes_edit.setText("notes only edit"); tab._manual_chart_notes_edit.editingFinished.emit(); L.pump(4000)
    R["a7-notes"] = builds() - n1
    n2 = builds(); L.set_check(p.helper_markers_cb, True); L.pump(4500)
    R["a7-helper-markers"] = builds() - n2
    n3 = builds(); L.set_combo_data(p.spacer_mode, "bw"); L.pump(4500)
    R["a7-spacer-bw"] = builds() - n3
    n4 = builds(); p.chart_text.setText("sheet text edit"); p.chart_text.editingFinished.emit(); L.pump(4500)
    R["a7-sheet-text"] = builds() - n4
    n5 = builds(); L.set_combo_data(p.paper, "A4R"); L.pump(6000); L.wait_build(tab, 120_000)
    R["a7-paper"] = builds() - n5
    L.log(f"A7 real click: {R['a7-debounce']} notes={R['a7-notes']} helper={R['a7-helper-markers']} spacer={R['a7-spacer-bw']} sheettext={R['a7-sheet-text']} paper={R['a7-paper']}")
    L.grab(win, OUT7 / "a20-real-click-tests.png")
    L.set_check(tab._auto_preview_check, False); L.pump(300); save()
    L.set_combo_data(p.paper, "A4"); L.set_check(p.helper_markers_cb, False); L.set_combo_data(p.spacer_mode, "colored"); p.chart_text.setText(""); p.chart_text.editingFinished.emit()

    # ---------------- Chart Layout default via Preferences (i1 / A4 / clip: align centre, patch area align)
    state = {"seen": False, "err": None}
    watcher.ignore.append("SettingsDialog")

    def tick():
        dlg = app.activeModalWidget()
        if dlg is None or type(dlg).__name__ != "SettingsDialog":
            QTimer.singleShot(150, tick); return
        state["seen"] = True
        try:
            tabs = dlg._tabs
            for i in range(tabs.count()):
                if tabs.tabText(i) == "Chart Layout":
                    tabs.setCurrentIndex(i)
            L.pump(400)
            L.set_combo_data(dlg._layout_instr, "i1"); L.set_combo_data(dlg._layout_paper, "A4")
            L.pump(300)
            state["mode_items"] = L.combo_items(dlg._layout_mode); state["clip_items"] = L.combo_items(dlg._layout_clip_enable) if dlg._layout_clip_enable.isVisible() else None
            lp = dlg._layout_panel
            state["before"] = {"align": lp.patch_align.currentData(), "layout_mode": lp.layout_mode.currentData(), "margins": {k: v.value() for k, v in lp.margins.items()}, "use_instr": lp.use_instr_margins.isChecked() if hasattr(lp, "use_instr_margins") else None}
            L.set_combo_data(lp.patch_align, "center"); L.set_combo_data(lp.layout_mode, "patch_first"); L.pump(400)
            state["saved_hint"] = dlg._layout_saved_hint.text(); state["calc"] = dlg._layout_calc.text()[:200]
            L.grab(dlg, OUT8 / "q30-prefs-chart-layout-i1-A4.png")
            bb = dlg.findChild(QDialogButtonBox); bb.button(QDialogButtonBox.StandardButton.Ok).click()
        except Exception as e:  # noqa: BLE001
            state["err"] = repr(e); dlg.reject()
    QTimer.singleShot(200, tick)
    win._open_settings(); L.pump(1000)
    watcher.ignore.remove("SettingsDialog")
    R["chart-layout-default"] = {"drive": state, "store_file": sorted(f.name for f in (Path(L.os.environ["CHROMIQ_PRESETS_DIR"]) / "Chart Layout").glob("*.json"))}
    # does a fresh i1/A4/clip pick in Manual take the default?
    L.set_combo_data(p.instr, "CM"); L.pump(300); L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.mode, "clip"); L.pump(600)
    R["chart-layout-default"]["manual_after"] = {"align": p.patch_align.currentData(), "layout_mode": p.layout_mode.currentData(), "info": tab._manual_info_lbl.text()[-120:]}
    L.log(f"chart layout default: {R['chart-layout-default']}")
    L.grab(win, OUT8 / "q31-manual-after-chart-layout-default.png")
    # and a brand new project?  (fresh panel)  -> new window later in D08
    save()
    L.log(f"unexpected: {[(d['class'], d['title'], d['text'][:80]) for d in watcher.unexpected]} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
