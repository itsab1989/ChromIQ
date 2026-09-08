#!/usr/bin/env python3
"""D08b (resume of D08): fresh-session Calibration target check; Guided under
Verification before and after a visit to the gamut module (does the disabled
Generate leak?); header Load patch set with the five-way box armed; failed
build after a good chart (files and preview restored?); tooltip scan; window
sizes; light and dark. Saves after every block."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

R: dict = {}


def save():
    L.save_json(R, L.LOGS / "d08b_results.json")


def gen(tab, watcher, extra=()):
    for m, b in extra:
        watcher.expect(m, b)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    ns = len(watcher.seen); n0 = len(L.SERIOUS)
    en = tab._generate_btn.isEnabled()
    L.click(tab._generate_btn); ok = L.wait_build(tab, 240_000) if en else False; L.pump(1000); watcher.clear()
    s = L.panel_snapshot(tab)
    return {"generate_was_enabled": en, "ok": ok, "actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"], "status": s["margin_status"],
            "dialogs": [(d.get("title") or d.get("text", "")[:90], d.get("answer"), d.get("buttons")) for d in watcher.seen[ns:]], "serious": L.serious_since(n0),
            "log_tail": [l for l in L.tab_log_text(tab).splitlines() if l.strip()][-4:]}


def btn_state(tab):
    return {"generate_enabled": tab._generate_btn.isEnabled(), "generate_tip": tab._generate_btn.toolTip()[:160], "stop_visible": tab._stop_btn.isVisible(), "in_flight": tab._chart_build_in_flight()}


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)

    # ---------------- Calibration in a fresh session
    L.open_project(win, settings, "Demo-Full-RGB")
    settings.set("calibration_mode", True); win._apply_calibration_mode(); L.pump(800)
    L.set_combo_data(win._target_bar._type_combo, "calibration"); L.pump(1500)
    R["cal-fresh"] = {**btn_state(tab), "run": win._target_bar._run_combo.currentText(), "location": win._target_bar._location.text(), "mode_btns_visible": (tab._guided_btn.isVisible(), tab._manual_btn.isVisible()),
                      "estimate": L.panel_snapshot(tab)["layout_info_estimate"], "actual": L.panel_snapshot(tab)["layout_info_actual"], "info": tab._manual_info_lbl.text()[-200:]}
    L.log(f"calibration fresh: {R['cal-fresh']}")
    L.grab(win, L.SHOTS / "B4-calibration" / "c10-fresh-session.png")
    r = gen(tab, watcher, extra=(("calibration", "Cancel"),))
    R["cal-fresh-generate"] = r; L.log(f"calibration generate (fresh): {r}"); save()
    L.set_combo_data(win._target_bar._type_combo, "profiling"); L.pump(800)
    settings.set("calibration_mode", False); win._apply_calibration_mode(); L.pump(500)

    # ---------------- Guided under Verification: before and after visiting gamut
    L.set_combo_data(win._target_bar._run_combo, "run3"); L.pump(800)
    L.click(tab._guided_btn); L.pump(400)
    L.set_combo_data(win._target_bar._type_combo, "verification"); L.pump(1200)
    R["verif-guided-before-gamut"] = {**btn_state(tab), "noprofile_visible": tab._verify_noprofile_lbl.isVisible()}
    L.grab(win, L.SHOTS / "B3-gamut" / "g10-guided-verification-before-gamut.png")
    L.click(tab._gamut_btn); L.pump(1000)
    R["verif-gamut"] = btn_state(tab)
    L.click(tab._guided_btn); L.pump(800)
    R["verif-guided-after-gamut"] = btn_state(tab)
    L.click(tab._manual_btn); L.pump(800)
    R["verif-manual-after-gamut"] = btn_state(tab)
    L.grab(win, L.SHOTS / "B3-gamut" / "g11-manual-verification-after-gamut.png")
    L.set_combo_data(win._target_bar._type_combo, "profiling"); L.pump(800)
    R["profiling-after"] = btn_state(tab)
    L.log(f"verification leak: before={R['verif-guided-before-gamut']} gamut={R['verif-gamut']} guided_after={R['verif-guided-after-gamut']} manual_after={R['verif-manual-after-gamut']} profiling_after={R['profiling-after']}")
    save()

    # ---------------- B5 header Load patch set (five-way box armed)
    ext_ti1 = L.ASSESS / "Evidence" / "external_patchset.ti1"
    if not ext_ti1.exists():
        shutil.copy(next(Path("/Users/Basti/ChromIQ-assessment/A5-Furniture/runs/run1").glob("*.ti1")), ext_ti1)
    import ui.tabs.tab_chart as TC
    orig = TC.open_file_dialog
    TC.open_file_dialog = lambda *a, **k: str(ext_ti1)
    L.log(f"  header load .ti1: native file dialog replaced by the path {ext_ti1.name} (logged substitution)")
    watcher.expect("Build it as a new run", "Build it as a new run instead"); watcher.expect("quite fill", "OK"); watcher.expect("loaded", "OK")
    ns = len(watcher.seen)
    L.click(tab._load_ti1_btn); L.wait_build(tab, 240_000); L.pump(1500); watcher.clear()
    TC.open_file_dialog = orig
    s = L.panel_snapshot(tab)
    R["b5-load-ti1"] = {"actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"], "info": tab._manual_info_lbl.text()[-260:], "preset_ti1": str(getattr(tab, "_preset_ti1_path", None)),
                        "override_targen": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None,
                        "dialogs": [(d.get("title") or d.get("text", "")[:120], d.get("answer"), d.get("buttons")) for d in watcher.seen[ns:]], "mode": "manual" if tab._manual_btn.isChecked() else "other",
                        "run_bar": win._target_bar._run_combo.currentText(), "location": win._target_bar._location.text()[-60:], "engine": tab._manual_engine_check.isChecked()}
    L.log(f"header load ti1: {R['b5-load-ti1']}")
    L.grab(win, L.SHOTS / "B5-header" / "h01-after-load-ti1.png"); save()

    # ---------------- failed build after a good chart
    L.open_project(win, settings, "A5-Furniture"); L.click(tab._manual_btn); L.pump(500)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    p = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(p.instr, "i1"); L.set_combo_data(p.paper, "A4"); L.set_combo_data(p.mode, "clip"); L.set_combo_data(p.layout_mode, "area_first")
    L.set_check(p.use_instr_margins, True); L.set_spin(p.pages, 1); L.set_spin(p.patch_x, 0.0); L.set_spin(p.patch_y, 0.0); L.pump(400)
    good = gen(tab, watcher)
    rd = L.current_run_dir(win)
    files_before = sorted(x.name for x in rd.iterdir() if x.is_file())
    L.set_combo_data(p.layout_mode, "patch_first"); L.set_spin(p.patch_x, 60.0); L.set_spin(p.patch_y, 60.0)
    L.set_combo_data(p.paper, "__custom__"); L.set_spin(p.custom_w, 20.0); L.set_spin(p.custom_h, 20.0); L.pump(500)
    bad = gen(tab, watcher)
    files_after = sorted(x.name for x in rd.iterdir() if x.is_file())
    s = L.panel_snapshot(tab)
    R["failed-build-restore"] = {"good": good["actual"], "bad_log": bad["log_tail"], "bad_dialogs": bad["dialogs"], "files_before": files_before, "files_after": files_after,
                                 "preview_pages_after": tab._preview.page_count(), "frames_after": (s["layout_info_actual"], s["margin_status"]), **btn_state(tab),
                                 "log_visible": tab._log.isVisible(), "status_bar": tab._status_bar_lbl.text()[:200]}
    L.log(f"failed build restore: {R['failed-build-restore']}")
    L.grab(win, L.SHOTS / "A10-extremes" / "x10-after-failed-build.png"); save()
    L.set_combo_data(p.paper, "A4"); L.set_spin(p.patch_x, 0.0); L.set_spin(p.patch_y, 0.0); L.set_combo_data(p.layout_mode, "area_first")
    # does a run switch bring the chart back?
    L.set_combo_data(win._target_bar._run_combo, "run2"); L.pump(800); L.set_combo_data(win._target_bar._run_combo, "run1"); L.pump(1200)
    R["failed-build-restore"]["after_run_roundtrip"] = {"preview_pages": tab._preview.page_count(), "actual": L.panel_snapshot(tab)["layout_info_actual"]}
    L.log(f"after run round trip: {R['failed-build-restore']['after_run_roundtrip']}"); save()

    # ---------------- B8 tooltip scan
    from ui.tooltip_button import TooltipButton
    tips = []
    for w in tab.findChildren(TooltipButton):
        t = getattr(w, "_title", None) or getattr(w, "title", None) or ""
        b = getattr(w, "_body", None) or getattr(w, "body", None) or w.toolTip()
        tips.append({"title": str(t)[:80], "body": str(b)[:2000]})
    pat = re.compile(r"\b(used to|no longer|previously|formerly|in earlier versions|since version|new in)\b|\(s\)", re.I)
    flagged = [{"title": t["title"], "hits": sorted(set(m.group(0) for m in pat.finditer(t["body"])))} for t in tips if pat.search(t["body"])]
    R["b8-tooltips"] = {"count": len(tips), "flagged": flagged[:40], "empty_bodies": sum(1 for t in tips if not t["body"].strip())}
    L.save_json(tips, L.LOGS / "d08b_tooltips_dump.json")
    L.log(f"tooltips: {len(tips)} scanned, {len(flagged)} with history/plural markers: {flagged[:6]}")
    save()

    # ---------------- B9 window sizes and B11 appearance
    L.open_project(win, settings, "A1-EngineVsPrinttarg"); L.set_combo_data(win._target_bar._run_combo, "run1"); L.click(tab._manual_btn); L.pump(500)
    for w_, h_ in ((1280, 800), (1700, 1050)):
        win.resize(w_, h_); L.pump(1200)
        L.grab(win, L.SHOTS / "B9-window" / f"w-{w_}x{h_}-manual.png")
        L.click(tab._guided_btn); L.pump(500); L.grab(win, L.SHOTS / "B9-window" / f"w-{w_}x{h_}-guided.png"); L.click(tab._manual_btn); L.pump(300)
        R[f"b9-{w_}x{h_}"] = {"window": (win.width(), win.height()), "left_pane_width": tab._stack.width(), "preview_width": tab._preview.width(), "preview_height": tab._preview.height(),
                              "generate_visible": tab._generate_btn.isVisible(), "frames_visible": (tab._margin_panel.isVisible(), tab._layout_info_panel.isVisible()),
                              "frames_height": (tab._margin_panel.height(), tab._layout_info_panel.height())}
    win.showMaximized(); L.pump(1500); L.grab(win, L.SHOTS / "B9-window" / "w-maximized-manual.png"); R["b9-max"] = (win.width(), win.height()); win.showNormal(); win.resize(1700, 1050); L.pump(800)
    from ui.theme import apply_appearance
    for mode in ("light", "dark", "neutral"):
        apply_appearance(app, win, mode); L.pump(1500)
        L.grab(win, L.SHOTS / "B11-appearance" / f"a-{mode}-manual.png")
        L.click(tab._guided_btn); L.pump(500); L.grab(win, L.SHOTS / "B11-appearance" / f"a-{mode}-guided.png"); L.click(tab._manual_btn); L.pump(300)
    save()
    L.log(f"unexpected: {[(d['class'], d['title'], d['text'][:80]) for d in watcher.unexpected]} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
