#!/usr/bin/env python3
"""R04: the layout engine on my own sample. Estimate vs render (Auto count) on
six instrument x paper combos; furniture capacity accounting (strip labels
off, clip Off/On with and without instrument margins: F-005); F-006 (verdict
hidden by a note); F-008 (Max strip in area-first); F-012 (tokens: valid only,
and one bad); F-021 (two Pages spins after a >20-page build); F-019/F-025
(impossible layout after a good chart, files before/after); Save as Defaults.
Own project R2-Engine. Unattended."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402

OUT = L.SHOTS / "R04-engine"
PROJECT = "R2-Engine"
R: dict = {}


def crop_tiff(tiff: Path, box_frac, out: Path):
    from PIL import Image
    with Image.open(tiff) as im:
        w, h = im.size
        l, t, r, b = box_frac
        im.crop((int(w * l), int(h * t), int(w * r), int(h * b))).convert("RGB").save(out)
    L.log(f"  crop {out.relative_to(L.ASSESS)}")


def setup(tab, panel, instr, paper, mode, custom=None):
    L.set_combo_data(panel.instr, instr); L.pump(300)
    if paper == "custom":
        idx = next((i for i in range(panel.paper.count()) if "ustom" in str(panel.paper.itemData(i)) or "ustom" in panel.paper.itemText(i)), -1)
        panel.paper.setCurrentIndex(idx); L.pump(200)
        L.set_spin(panel.custom_w, custom[0]); L.set_spin(panel.custom_h, custom[1])
    else:
        L.set_combo_data(panel.paper, paper)
    if mode:
        L.set_combo_data(panel.mode, mode)
    L.pump(500)


def est(tab):
    return L.panel_snapshot(tab)["layout_info_estimate"]


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn); L.pump(400)
    tab._manual_target_name_edit.setText(PROJECT); tab._manual_target_name_edit.editingFinished.emit(); L.pump(600)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    panel = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_spin(panel.pages, 1)
    L.log(f"paper items: {[(t, d) for t, d in L.combo_items(panel.paper)]}")

    # ---------------- A. estimate vs render, Auto count ----------------
    R["matrix"] = []
    for instr, paper, mode, custom, hexdlg in (
            ("i1", "A4", "clip", None, False), ("p3", "420x297", "clip", None, False),
            ("CM", "A4R", "high", None, False), ("SS", "A4", "hex", None, True),
            ("CR30", "custom", "flat", (200, 200), False), ("i1", "Letter", "clip", None, False)):
        if hexdlg:
            watcher.expect("hexagon", "OK", note="(hex heads-up)")
        setup(tab, panel, instr, paper, mode, custom)
        watcher.clear()
        e = est(tab)
        s = L.gen(tab, watcher, f"{instr} {paper} {mode}", extra_expect=[("already", "Continue")])
        a = s["layout_info_actual"]
        same = bool(a and e and all(a.get(k) == e.get(k) for k in ("total", "rows", "cols", "pages")))
        R["matrix"].append({"instr": instr, "paper": paper, "mode": mode, "est": e, "actual": a, "same": same,
                            "status": s["margin_status"], "notes": s["margin_notes"], "errors": s["errors"]})
        L.log(f"  MATRIX {instr}/{paper}/{mode}: same={same} est={e and (e['total'], e['rows'], e['cols'], e['pages'], e['patch'])} actual={a and (a['total'], a['rows'], a['cols'], a['pages'], a['patch'])}")
        L.grab(win, OUT / f"m-{instr}-{paper}-{mode}.png")

    # ---------------- B. furniture accounting on i1 A4 clip ----------------
    setup(tab, panel, "i1", "A4", "clip")
    L.set_combo_data(panel.layout_mode, "area_first"); L.set_combo_data(panel.area_method, "by_width")
    L.set_check(panel.use_instr_margins, True); L.pump(400)
    base_e = est(tab)
    sb = L.gen(tab, watcher, "i1 A4 baseline", extra_expect=[("already", "Continue")])
    R["furn_base"] = {"est": base_e, "actual": sb["layout_info_actual"], "margins": sb["margin_panel_text"][:200]}
    # strip indicators off
    L.set_check(panel.show_indicators, False); L.pump(400)
    e1 = est(tab)
    s1 = L.gen(tab, watcher, "strip indicators OFF", extra_expect=[("already", "Continue")])
    R["furn_labels_off"] = {"est": e1, "actual": s1["layout_info_actual"], "margins": s1["margin_panel_text"][:220], "notes": s1["margin_notes"]}
    L.grab(win, OUT / "f-labels-off.png")
    L.set_check(panel.show_indicators, True); L.pump(300)
    # F-005: clip Off with instrument margins ON
    L.set_combo_data(panel.mode, "noclip"); L.pump(400)
    e2 = est(tab)
    s2 = L.gen(tab, watcher, "clip OFF, instr margins ON", extra_expect=[("already", "Continue")])
    R["f005_instr_on"] = {"est": e2, "actual": s2["layout_info_actual"], "margins": s2["margin_panel_text"][:220],
                          "panel_margins": {k: v.value() for k, v in panel.margins.items()}}
    L.grab(win, OUT / "f005-noclip-instr-on.png")
    # F-005: clip Off with OWN margins 10 mm
    L.set_check(panel.use_instr_margins, False); L.pump(200)
    for k in ("t", "r", "b", "l"):
        L.set_spin(panel.margins[k], 10.0)
    L.pump(400)
    e3 = est(tab)
    s3 = L.gen(tab, watcher, "clip OFF, own 10 mm", extra_expect=[("already", "Continue")])
    L.set_combo_data(panel.mode, "clip"); L.pump(400)
    e4 = est(tab)
    s4 = L.gen(tab, watcher, "clip ON, own 10 mm", extra_expect=[("already", "Continue")])
    R["f005_own10"] = {"noclip": {"est": e3, "actual": s3["layout_info_actual"], "margins": s3["margin_panel_text"][:220]},
                       "clip": {"est": e4, "actual": s4["layout_info_actual"], "margins": s4["margin_panel_text"][:220]}}
    L.grab(win, OUT / "f005-clip-own10.png")
    L.set_check(panel.use_instr_margins, True); L.pump(300)

    # ---------------- C. F-006 verdict hidden by a note; D. F-008 ----------------
    L.set_combo_data(panel.paper, "A3"); L.pump(400)
    s5 = L.gen(tab, watcher, "i1 A3 portrait instr margins", extra_expect=[("already", "Continue")])
    R["f006_A3"] = {"status": s5["margin_status"], "status_visible": s5["margin_status_visible"], "notes": s5["margin_notes"],
                    "actual": s5["layout_info_actual"], "tip_hover": tab._margin_panel._panel_tip.toolTip()[:300] if hasattr(tab._margin_panel, "_panel_tip") else None}
    L.grab(win, OUT / "f006-A3-note-no-verdict.png")
    L.grab(tab._margin_panel, OUT / "f006-A3-margin-panel.png")
    L.set_spin(panel.max_strip, 200.0); L.pump(400)
    e6 = est(tab)
    s6 = L.gen(tab, watcher, "A3 area-first max strip 200", extra_expect=[("already", "Continue")])
    L.set_check(panel.nolimit, True); L.pump(300)
    e7 = est(tab)
    L.set_combo_data(panel.layout_mode, "patch_first"); L.pump(400)
    e8 = est(tab)
    s8 = L.gen(tab, watcher, "A3 patch-first max strip 200 + nolimit", extra_expect=[("already", "Continue")])
    L.set_check(panel.nolimit, False); L.pump(200)
    e9 = est(tab)
    R["f008"] = {"area_cap200_est": e6, "area_cap200_actual": s6["layout_info_actual"], "area_cap200_notes": s6["margin_notes"],
                 "area_cap200_nolimit_est": e7, "patch_cap200_nolimit_est": e8, "patch_cap200_nolimit_actual": s8["layout_info_actual"],
                 "patch_cap200_est": e9, "max_strip_tip": panel.max_strip.toolTip()[:200], "nolimit_tip": panel.nolimit.toolTip()[:300]}
    L.log(f"  F-008: area cap200 est/act cols={e6 and e6['rows']}/{s6['layout_info_actual'] and s6['layout_info_actual']['rows']} ; patch-first cap200+nolimit est rows={e8 and e8['rows']} act={s8['layout_info_actual'] and s8['layout_info_actual']['rows']} ; patch-first cap200 rows={e9 and e9['rows']}")
    L.set_spin(panel.max_strip, 0.0); L.set_combo_data(panel.layout_mode, "area_first")
    L.set_combo_data(panel.paper, "A4"); L.pump(400)

    # ---------------- E. F-012 tokens ----------------
    panel.chart_text.setText("Sheet {project} {date} {patchcount}"); panel.chart_text.editingFinished.emit(); L.pump(300)
    s10 = L.gen(tab, watcher, "sheet text valid tokens", extra_expect=[("already", "Continue")])
    run_dir = L.current_run_dir(win)
    tif = sorted(run_dir.glob("*.tif"))[0]
    crop_tiff(tif, (0.0, 0.90, 1.0, 1.0), OUT / "f012-valid-tokens-bottom.png")
    panel.chart_text.setText("Sheet {project} {patches}"); panel.chart_text.editingFinished.emit(); L.pump(300)
    s11 = L.gen(tab, watcher, "sheet text one bad token", extra_expect=[("already", "Continue")])
    tif = sorted(run_dir.glob("*.tif"))[0]
    crop_tiff(tif, (0.0, 0.90, 1.0, 1.0), OUT / "f012-bad-token-bottom.png")
    R["f012"] = {"valid_errors": s10["errors"], "bad_errors": s11["errors"], "text_preview": panel.text_preview.text()}
    panel.chart_text.setText(""); panel.chart_text.editingFinished.emit(); L.pump(200)

    # ---------------- F. F-021 two Pages spins ----------------
    L.set_combo_data(panel.layout_mode, "patch_first"); L.pump(300)
    if auto.isChecked():
        auto.click(); L.pump(200)
    L.pw(tab, "targen", "-f").set_value(9500); L.pump(400)
    R["f021"] = {"before": {"panel_pages": panel.get_pages(), "printtarg_spin": tab._manual_pages_spin.value(), "spin_max": tab._manual_pages_spin.maximum(), "panel_max": panel.pages.maximum()}}
    s12 = L.gen(tab, watcher, "9500 patches", extra_expect=[("already", "Continue")], timeout_ms=400_000)
    R["f021"]["built_9500"] = s12["layout_info_actual"]
    R["f021"]["after_build"] = {"panel_pages": panel.get_pages(), "printtarg_spin": tab._manual_pages_spin.value()}
    auto.click(); L.pump(300)
    L.set_spin(panel.pages, 1); L.pump(600)
    R["f021"]["after_auto_pages1"] = {"panel_pages": panel.get_pages(), "printtarg_spin": tab._manual_pages_spin.value(), "est": est(tab)}
    L.log(f"  F-021: {R['f021']}")
    L.grab(win, OUT / "f021-after-pages1.png")
    s13 = L.gen(tab, watcher, "after pages 1", extra_expect=[("already", "Continue")], timeout_ms=400_000)
    R["f021"]["built_after"] = s13["layout_info_actual"]
    R["f021"]["est_after"] = s13["layout_info_estimate"]
    L.log(f"  F-021 built pages={s13['layout_info_actual'] and s13['layout_info_actual']['pages']} est pages={s13['layout_info_estimate'] and s13['layout_info_estimate']['pages']}")

    # ---------------- G. F-019 / F-025 ----------------
    files_before = L.listing(run_dir)
    setup(tab, panel, "i1", "custom", "clip", (20, 20))
    L.set_combo_data(panel.layout_mode, "patch_first"); L.set_spin(panel.patch_x, 60.0); L.set_spin(panel.patch_y, 60.0)
    L.pump(500)
    R["f019"] = {"est_before": est(tab), "generate_enabled": tab._generate_btn.isEnabled()}
    n0 = len(L.APP_LINES)
    L.click(tab._generate_btn)
    L.wait_build(tab, 120_000)
    L.pump(1200)
    files_after = L.listing(run_dir)
    snap = L.panel_snapshot(tab)
    R["f019"].update({"dialogs": watcher.seen[-2:], "errors": L.app_lines_since(n0, r"ERROR|too short|failed"),
                      "files_same": {k: v[0] for k, v in files_before.items()} == {k: v[0] for k, v in files_after.items()},
                      "files_before": len(files_before), "files_after": len(files_after),
                      "preview_pages": snap["preview_pages"], "status": snap["margin_status"], "status_visible": snap["margin_status_visible"],
                      "info_actual": snap["layout_info_actual"], "tab_log_tail": L.tab_log_text(tab)[-500:]})
    L.log(f"  F-019/025: {R['f019']}")
    L.grab(win, OUT / "f019-after-failed-build.png")

    # ---------------- H. Save as Defaults ----------------
    setup(tab, panel, "i1", "A4", "clip")
    before_key = settings.get("manual_engine_recipe", None)
    n0 = len(L.APP_LINES)
    watcher.expect("default", "OK")
    L.click(tab._save_defaults_btn); L.pump(1200)
    watcher.clear()
    after_key = settings.get("manual_engine_recipe", None)
    R["save_defaults"] = {"had_before": before_key is not None, "after_keys": sorted(after_key.keys())[:12] if isinstance(after_key, dict) else after_key,
                          "after_paper": after_key.get("paper") if isinstance(after_key, dict) else None,
                          "dialogs": watcher.seen[-1:], "lines": L.app_lines_since(n0)[-5:]}
    L.log(f"  Save as Defaults: {R['save_defaults']}")

    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r04_results.json")
    L.log(f"unexpected={watcher.unexpected} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
