#!/usr/bin/env python3
"""D08: B3 From Profile Gamut (with and without a profile), B4 Calibration run
type, legacy project migration (Demo-Legacy-v1), B9 window sizes, B11 light and
dark, B6 preview paging and overlays, B5 header load-patch-set icon, B8 tooltip
text scan. Saves after every block."""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

OUT3 = L.SHOTS / "B3-gamut"
OUT4 = L.SHOTS / "B4-calibration"
OUT12 = L.SHOTS / "B12-names-files"
OUT9 = L.SHOTS / "B9-window"
OUT11 = L.SHOTS / "B11-appearance"
OUT6 = L.SHOTS / "B6-preview"
OUT5 = L.SHOTS / "B5-header"
OUT8 = L.SHOTS / "B8-help"
R: dict = {}


def save():
    L.save_json(R, L.LOGS / "d08_results.json")


def gen(tab, watcher, extra=()):
    for m, b in extra:
        watcher.expect(m, b)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project")
    ns = len(watcher.seen); n0 = len(L.SERIOUS)
    L.click(tab._generate_btn); ok = L.wait_build(tab, 240_000); L.pump(1000); watcher.clear()
    s = L.panel_snapshot(tab)
    return {"ok": ok, "actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"], "status": s["margin_status"],
            "dialogs": [(d.get("title") or d.get("text", "")[:80], d.get("answer")) for d in watcher.seen[ns:]], "serious": L.serious_since(n0),
            "log_tail": [l for l in L.tab_log_text(tab).splitlines() if l.strip()][-4:]}


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)

    # ---------------- B3 gamut with a profile (Demo-Full-RGB run2 has an .icc)
    L.open_project(win, settings, "Demo-Full-RGB")
    L.set_combo_data(win._target_bar._run_combo, "run2"); L.pump(1000)
    L.set_combo_data(win._target_bar._type_combo, "verification"); L.pump(1000)
    R["b3-bar"] = {"type": win._target_bar._type_combo.currentText(), "verify_items": L.combo_items(win._target_bar._verify_combo), "gamut_btn_visible": tab._gamut_btn.isVisible(),
                   "location": win._target_bar._location.text(), "build_tab_enabled": win._tabs.isTabEnabled(3)}
    L.click(tab._gamut_btn); L.pump(1200)
    R["b3-with-profile"] = {"grp_visible": tab._gamut_grp.isVisible(), "count": tab._gamut_count_spin.value(), "count_bounds": L.spinbox_bounds(tab._gamut_count_spin),
                            "auto": tab._gamut_auto_check.isChecked(), "margin_items": L.combo_items(tab._gamut_margin_combo), "margin": tab._gamut_margin_combo.currentData(),
                            "intent_items": L.combo_items(tab._gamut_intent_combo), "intent": tab._gamut_intent_combo.currentData(),
                            "count_lbl": tab._gamut_count_lbl.text()[:300], "empty_lbl_visible": tab._gamut_empty_lbl.isVisible(), "empty_lbl": tab._gamut_empty_lbl.text()[:300],
                            "noprofile_visible": tab._verify_noprofile_lbl.isVisible(), "generate_enabled": tab._generate_btn.isEnabled(),
                            "engine": tab._manual_engine_check.isChecked(), "panel_instr": tab._manual_layout_panel.instr.currentData(), "panel_paper": tab._manual_layout_panel.paper.currentData(),
                            "estimate": L.panel_snapshot(tab)["layout_info_estimate"], "actual": L.panel_snapshot(tab)["layout_info_actual"], "info": tab._manual_info_lbl.text()[-260:]}
    L.log(f"gamut with profile: {R['b3-with-profile']}")
    L.grab(win, OUT3 / "g01-gamut-with-profile.png"); save()
    r = gen(tab, watcher, extra=(("verification", "Generate the new chart"), ("measured", "Generate the new chart")))
    vdir = Path("/Users/Basti/ChromIQ-assessment/Demo-Full-RGB/runs/run2/verifications")
    R["b3-generate"] = {**r, "verifications_files": sorted(str(p.relative_to(vdir)) for p in vdir.rglob("*") if p.is_file())[:40],
                        "run_bar": win._target_bar._run_combo.currentText(), "verify": win._target_bar._verify_combo.currentText(), "location": win._target_bar._location.text()}
    L.log(f"gamut generate: {R['b3-generate']}")
    L.grab(win, OUT3 / "g02-gamut-generated.png"); save()
    # count default vs on-screen count; margin combo effect on estimate
    est0 = L.panel_snapshot(tab)["layout_info_estimate"]
    L.set_combo_data(tab._gamut_margin_combo, L.combo_items(tab._gamut_margin_combo)[-1][1]); L.pump(800)
    R["b3-margin-change"] = {"estimate_before": est0, "estimate_after": L.panel_snapshot(tab)["layout_info_estimate"], "count_lbl": tab._gamut_count_lbl.text()[:200]}
    L.log(f"gamut margin change: {R['b3-margin-change']}")
    # without a profile (run3)
    L.set_combo_data(win._target_bar._run_combo, "run3"); L.pump(1200)
    R["b3-no-profile"] = {"mode_gamut": tab._gamut_btn.isChecked(), "grp_visible": tab._gamut_grp.isVisible(), "empty_lbl_visible": tab._gamut_empty_lbl.isVisible(), "empty_lbl": re.sub(r"<[^>]+>", "", tab._gamut_empty_lbl.text())[:400],
                         "noprofile_visible": tab._verify_noprofile_lbl.isVisible(), "generate_enabled": tab._generate_btn.isEnabled(), "stop_visible": tab._stop_btn.isVisible(),
                         "actual": L.panel_snapshot(tab)["layout_info_actual"], "preview_pages": tab._preview.page_count()}
    L.log(f"gamut no profile: {R['b3-no-profile']}")
    L.grab(win, OUT3 / "g03-gamut-no-profile-run3.png"); save()
    # Guided/Manual no-profile info box under Verification
    L.click(tab._guided_btn); L.pump(600)
    R["b3-guided-verification"] = {"noprofile_visible": tab._verify_noprofile_lbl.isVisible(), "text": re.sub(r"<[^>]+>", "", tab._verify_noprofile_lbl.text())[:400], "generate_enabled": tab._generate_btn.isEnabled()}
    L.grab(win, OUT3 / "g04-guided-verification-run3.png")
    L.click(tab._manual_btn); L.pump(400)
    R["b3-manual-verification"] = {"noprofile_visible": tab._verify_noprofile_lbl.isVisible(), "text": re.sub(r"<[^>]+>", "", tab._verify_noprofile_lbl.text())[:300], "notes_label": None}
    L.grab(win, OUT3 / "g05-manual-verification-run3.png"); save()
    L.set_combo_data(win._target_bar._type_combo, "profiling"); L.pump(800)

    # ---------------- B4 calibration run type
    settings.set("calibration_mode", True); win._apply_calibration_mode(); L.pump(800)
    R["b4-bar"] = {"type_items": L.combo_items(win._target_bar._type_combo), "run_items": L.combo_items(win._target_bar._run_combo)}
    L.log(f"calibration bar: {R['b4-bar']}")
    cal_item = next((d for _, d in L.combo_items(win._target_bar._run_combo) if d == "__calibration__"), None)
    cal_type = next((d for _, d in L.combo_items(win._target_bar._type_combo) if "cal" in str(d).lower()), None)
    if cal_type:
        L.set_combo_data(win._target_bar._type_combo, cal_type); L.pump(1000)
    elif cal_item:
        L.set_combo_data(win._target_bar._run_combo, cal_item); L.pump(1000)
    s = L.panel_snapshot(tab)
    R["b4-selected"] = {"type": win._target_bar._type_combo.currentText(), "run": win._target_bar._run_combo.currentText(), "location": win._target_bar._location.text(),
                        "guided_visible": tab._guided_btn.isVisible(), "manual_visible": tab._manual_btn.isVisible(), "gamut_visible": tab._gamut_btn.isVisible(),
                        "mode": "guided" if tab._guided_btn.isChecked() else "manual" if tab._manual_btn.isChecked() else "gamut",
                        "engine": tab._manual_engine_check.isChecked(), "targen_f": None, "actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"],
                        "info": tab._manual_info_lbl.text()[-300:], "preview_pages": tab._preview.page_count(), "auto_patches": tab._manual_auto_patches_check.isChecked() if tab._manual_auto_patches_check else None}
    for w in tab._manual_widgets.get("targen", []):
        if w.flag == "-f":
            R["b4-selected"]["targen_f"] = (w.get_raw_value(), w.isEnabled())
        if w.flag in ("-d", "-s", "-e", "-B", "-g", "-m", "-M", "-l"):
            R["b4-selected"][f"targen{w.flag}"] = (w.get_raw_value(), w.isEnabled(), w.isVisible())
    L.log(f"calibration selected: {R['b4-selected']}")
    L.grab(win, OUT4 / "c01-calibration-selected.png"); save()
    r = gen(tab, watcher, extra=(("calibration", "Generate"),))
    cdir = Path("/Users/Basti/ChromIQ-assessment/Demo-Full-RGB/cal")
    R["b4-generate"] = {**r, "cal_files": sorted(p.name for p in cdir.glob("*")) if cdir.exists() else None, "location": win._target_bar._location.text()}
    L.log(f"calibration generate: {R['b4-generate']}")
    L.grab(win, OUT4 / "c02-calibration-generated.png"); save()
    L.set_combo_data(win._target_bar._type_combo, "profiling"); L.pump(600)
    settings.set("calibration_mode", False); win._apply_calibration_mode(); L.pump(500)

    # ---------------- legacy project migration (Demo-Legacy-v1)
    src = Path("/Users/Basti/ChromIQ-assessment/Demo-Legacy-v1")
    before = sorted(str(p.relative_to(src)) for p in src.rglob("*") if p.is_file())
    schema_before = json.loads((src / "project.json").read_text()).get("schema_version")
    ns = len(watcher.seen); n0 = len(L.SERIOUS)
    watcher.expect("newer", "OK")
    ok = L.open_project(win, settings, "Demo-Legacy-v1"); L.pump(1500)
    after = sorted(str(p.relative_to(src)) for p in src.rglob("*") if p.is_file())
    schema_after = json.loads((src / "project.json").read_text()).get("schema_version")
    s = L.panel_snapshot(tab)
    R["legacy-v1"] = {"opened": ok, "schema": (schema_before, schema_after), "files_before": before, "files_after": after,
                      "moved": sorted(set(after) - set(before)), "gone": sorted(set(before) - set(after)),
                      "run_bar": win._target_bar._run_combo.currentText(), "run_items": L.combo_items(win._target_bar._run_combo),
                      "preview_pages": tab._preview.page_count(), "actual": s["layout_info_actual"], "status": s["margin_status"],
                      "dialogs": [(d.get("title") or d.get("text", "")[:80], d.get("answer")) for d in watcher.seen[ns:]], "serious": L.serious_since(n0)}
    watcher.clear()
    L.log(f"legacy v1: schema {schema_before}->{schema_after} moved={R['legacy-v1']['moved']} gone={R['legacy-v1']['gone']} run={R['legacy-v1']['run_bar']} pages={R['legacy-v1']['preview_pages']} dialogs={R['legacy-v1']['dialogs']}")
    L.grab(win, OUT12 / "l01-legacy-v1-opened.png"); save()

    # ---------------- B6 preview: paging, overlays, zoom
    L.open_project(win, settings, "A1-EngineVsPrinttarg"); L.set_combo_data(win._target_bar._run_combo, "run1"); L.pump(1000)
    L.click(tab._manual_btn); L.pump(300)
    mp = tab._margin_panel
    for name, setter in (("instrument-guides", mp.set_guides_checked), ("measured-guides", mp.set_measured_guides_checked), ("coords", mp.set_coords_checked)):
        setter(True); L.pump(500)
    L.grab(tab._preview, OUT6 / "v01-overlays-on.png")
    tab._preview._apply_zoom(2.0); L.pump(400); L.grab(tab._preview, OUT6 / "v02-zoom-2x.png")
    tab._preview._apply_zoom(0.5); L.pump(400)
    for name, setter in (("instrument-guides", mp.set_guides_checked), ("measured-guides", mp.set_measured_guides_checked), ("coords", mp.set_coords_checked)):
        setter(False)
    # a multi-page chart: Demo-Full-RGB run3 (4 pages)
    L.open_project(win, settings, "Demo-Full-RGB"); L.set_combo_data(win._target_bar._run_combo, "run3"); L.pump(1000)
    pages = tab._preview.page_count(); seq = []
    for i in range(pages + 1):
        seq.append((tab._preview.current_page(), tab._preview._page_label.text(), tab._preview._prev_btn.isEnabled(), tab._preview._next_btn.isEnabled(), L.panel_snapshot(tab)["layout_info_actual"]["page_patches"] if L.panel_snapshot(tab)["layout_info_actual"] else None, L.panel_snapshot(tab)["margin_panel_text"][:90]))
        if tab._preview._next_btn.isEnabled():
            L.click(tab._preview._next_btn); L.pump(500)
    R["b6-paging"] = {"pages": pages, "sequence": seq}
    L.log(f"paging: {R['b6-paging']}")
    L.grab(win, OUT6 / "v03-last-page.png"); save()

    # ---------------- B5 header icons
    hdr = {"load_ti1_tip": tab._load_ti1_btn.toolTip()[:200]}
    for name in ("_preset_reveal_btn", "_preset_add_btn", "_preset_del_btn"):
        w = getattr(tab, name, None)
        if w is not None:
            hdr[name] = (w.toolTip()[:160], w.isEnabled())
    R["b5-header"] = hdr
    # load an external .ti1 through the header icon (file dialog replaced by a path, logged)
    ext_ti1 = L.ASSESS / "Evidence" / "external_patchset.ti1"
    shutil.copy(next(Path("/Users/Basti/ChromIQ-assessment/A5-Furniture/runs/run1").glob("*.ti1")), ext_ti1)
    import ui.tabs.tab_chart as TC
    orig = TC.open_file_dialog
    TC.open_file_dialog = lambda *a, **k: str(ext_ti1)
    L.log(f"  header load .ti1: file dialog replaced by path {ext_ti1.name}")
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue this project"); watcher.expect("loaded", "OK")
    ns = len(watcher.seen)
    L.click(tab._load_ti1_btn); L.wait_build(tab, 240_000); L.pump(1500); watcher.clear()
    TC.open_file_dialog = orig
    s = L.panel_snapshot(tab)
    R["b5-load-ti1"] = {"actual": s["layout_info_actual"], "estimate": s["layout_info_estimate"], "info": tab._manual_info_lbl.text()[-260:], "preset_ti1": str(getattr(tab, "_preset_ti1_path", None)),
                        "override_targen": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None,
                        "dialogs": [(d.get("title") or d.get("text", "")[:80], d.get("answer")) for d in watcher.seen[ns:]], "mode": "manual" if tab._manual_btn.isChecked() else "other"}
    L.log(f"header load ti1: {R['b5-load-ti1']}")
    L.grab(win, OUT5 / "h01-after-load-ti1.png"); save()

    # ---------------- failed build after a good chart: are the files and the preview restored?
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
    R["failed-build-restore"] = {"good": good["actual"], "bad_errors": bad["log_tail"], "bad_dialogs": bad["dialogs"], "files_before": files_before, "files_after": files_after,
                                 "preview_pages_after": tab._preview.page_count(), "frames_after": (s["layout_info_actual"], s["margin_status"]), "generate_enabled": tab._generate_btn.isEnabled(),
                                 "log_visible": tab._log.isVisible(), "status_bar": tab._status_bar_lbl.text()[:200]}
    L.log(f"failed build restore: {R['failed-build-restore']}")
    L.grab(win, L.SHOTS / "A10-extremes" / "x10-after-failed-build.png"); save()
    L.set_combo_data(p.paper, "A4"); L.set_spin(p.patch_x, 0.0); L.set_spin(p.patch_y, 0.0); L.set_combo_data(p.layout_mode, "area_first")

    # ---------------- B8 tooltip scan (Manual panel + layout panel)
    from ui.tooltip_button import TooltipButton
    tips = []
    for w in tab.findChildren(TooltipButton):
        t = getattr(w, "_title", None) or getattr(w, "title", None) or ""
        b = getattr(w, "_body", None) or getattr(w, "body", None) or w.toolTip()
        tips.append({"title": str(t)[:80], "body": str(b)[:2000]})
    pat = re.compile(r"\b(used to|no longer|previously|formerly|in earlier versions|since version|new in)\b|\(s\)", re.I)
    flagged = [{"title": t["title"], "hits": sorted(set(m.group(0) for m in pat.finditer(t["body"])))} for t in tips if pat.search(t["body"])]
    R["b8-tooltips"] = {"count": len(tips), "flagged": flagged[:40], "empty_bodies": sum(1 for t in tips if not t["body"].strip())}
    L.save_json(tips, L.LOGS / "d08_tooltips_dump.json")
    L.log(f"tooltips: {len(tips)} scanned, {len(flagged)} with history/plural markers")
    save()

    # ---------------- B9 window sizes and B11 appearance
    L.open_project(win, settings, "A1-EngineVsPrinttarg"); L.click(tab._manual_btn); L.pump(500)
    for w_, h_ in ((1280, 800), (1728, 1050)):
        win.resize(w_, h_); L.pump(1200)
        L.grab(win, OUT9 / f"w-{w_}x{h_}-manual.png")
        L.click(tab._guided_btn); L.pump(500); L.grab(win, OUT9 / f"w-{w_}x{h_}-guided.png"); L.click(tab._manual_btn); L.pump(300)
        # overlap check: any visible widget in the left pane extending past the pane?
        left = tab._manual_panel
        over = []
        for c in left.findChildren(type(tab._generate_btn)):
            pass
        R[f"b9-{w_}x{h_}"] = {"window": (win.width(), win.height()), "left_pane_width": tab._stack.width(), "preview_width": tab._preview.width(),
                              "generate_visible": tab._generate_btn.isVisible(), "info_row_visible": tab._margin_panel.isVisible() and tab._layout_info_panel.isVisible()}
    win.showMaximized(); L.pump(1500); L.grab(win, OUT9 / "w-maximized-manual.png"); R["b9-max"] = (win.width(), win.height()); win.showNormal(); win.resize(1700, 1050); L.pump(800)
    from ui.theme import apply_appearance
    for mode in ("light", "dark", "neutral"):
        apply_appearance(app, win, mode); L.pump(1500)
        L.grab(win, OUT11 / f"a-{mode}-manual.png")
        L.click(tab._guided_btn); L.pump(500); L.grab(win, OUT11 / f"a-{mode}-guided.png"); L.click(tab._manual_btn); L.pump(300)
    save()
    L.log(f"unexpected: {[(d['class'], d['title'], d['text'][:80]) for d in watcher.unexpected]} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
