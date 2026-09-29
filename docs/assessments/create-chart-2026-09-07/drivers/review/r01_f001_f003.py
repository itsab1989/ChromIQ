#!/usr/bin/env python3
"""R01: re-test F-001 (estimate vs area-first build with a fixed -f) and F-003
(printtarg panel / store diverge after Generate), with instrumentation that
names every writer of the -L / -a / -m widgets and the ChartParams the
creator actually received. Own project R2-High, own steps. Unattended."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402

OUT = L.SHOTS / "R01-f001-f003"
PROJECT = "R2-High"
R: dict = {}


def widgets(tab):
    d = {}
    for flag in ("-i", "-p", "-L", "-a", "-m", "-r", "-t", "-P"):
        w = L.pw(tab, "printtarg", flag)
        d[flag] = (w.get_raw_value() if w else None, bool(w.isVisible()) if w else None)
    d["engine"] = tab._manual_engine_check.isChecked()
    d["stamp"] = tab._manual_stamp_cmd_check.isChecked()
    return d


def sidecar_facts(run_dir: Path, stem: str):
    doc = L.read_json(run_dir / f"{stem}.channels.json")
    meta = L.read_json(run_dir / "meta.json")
    ccs = (doc or {}).get("create_chart_settings") or {}
    mcs = (meta or {}).get("create_chart_settings") or {}
    pf = {f.get("flag"): f.get("value") for f in (doc or {}).get("printtarg_fields") or []}
    pick = lambda d: {k: d.get(k) for k in ("printtarg--L", "printtarg-L", "printtarg-a", "printtarg--a", "printtarg-m", "printtarg--m") if k in d}  # noqa: E731
    keys_L = [k for k in ccs if k.endswith("-L")]
    return {"sidecar_ccs": {k: ccs.get(k) for k in ccs if k.split("-", 1)[-1] in ("L", "a", "m", "r")},
            "meta_ccs": {k: mcs.get(k) for k in mcs if k.split("-", 1)[-1] in ("L", "a", "m", "r")},
            "printtarg_fields": {k: pf.get(k) for k in ("-L", "-a", "-m", "-r")},
            "ccs_keys_sample": sorted(ccs)[:6], "keys_L": keys_L,
            "ti2": L.ti2_facts(next(run_dir.glob("*.ti2"), Path("/nonexistent"))),
            "ti1_sets": L.ti1_sets(next(run_dir.glob("*.ti1"), Path("/nonexistent")))}


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    L.click(tab._manual_btn); L.pump(400)
    tab._manual_target_name_edit.setText(PROJECT)
    tab._manual_target_name_edit.editingFinished.emit(); L.pump(600)
    L.log(f"name typed; run bar {win._target_bar._run_combo.currentText()!r} loc {win._target_bar._location.text()!r}")
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    panel = tab._manual_layout_panel
    L.set_combo_data(panel.instr, "i1"); L.set_combo_data(panel.paper, "A4"); L.set_combo_data(panel.mode, "clip")
    L.set_combo_data(panel.layout_mode, "area_first"); L.set_combo_data(panel.area_method, "by_width")
    L.set_check(panel.use_instr_margins, True); L.set_spin(panel.pages, 1)
    auto = tab._manual_auto_patches_check
    if auto.isChecked():
        auto.click(); L.pump(200)
    L.pw(tab, "targen", "-f").set_value(400); L.pump(400)
    R["f001_before"] = {"est": L.panel_snapshot(tab)["layout_info_estimate"], "recipe": L.recipe_of(tab),
                        "info": tab._manual_info_lbl.text()}
    L.log(f"F-001 before Generate: est={R['f001_before']['est']} info={R['f001_before']['info'][:200]!r}")

    # capture the hint text if it comes
    hint = {}
    orig_describe = watcher.describe

    s = L.gen(tab, watcher, "F-001 i1 A4 area-first -f400")
    for d in watcher.seen:
        if "quite fill" in (d.get("text") or ""):
            hint = d
    run_dir = L.current_run_dir(win)
    stem = run_dir.parent.parent.name if run_dir else PROJECT
    R["f001_after"] = {"snap": s, "hint": hint, "run_dir": str(run_dir), "files": sidecar_facts(run_dir, PROJECT),
                       "tab_log_tail": L.tab_log_text(tab)[-1200:]}
    L.grab(win, OUT / "01-f001-after-generate.png")
    L.log(f"F-001: built={s['layout_info_actual']} est={s['layout_info_estimate']} hint={hint.get('text', '')[:200]!r} "
          f"ti1={R['f001_after']['files']['ti1_sets']} ti2={R['f001_after']['files']['ti2'].get('sets')}")

    # F-001 variant: patch-first, fixed -f 300 (fill-up disagreement claimed)
    L.set_combo_data(panel.layout_mode, "patch_first"); L.pump(300)
    L.pw(tab, "targen", "-f").set_value(300); L.pump(500)
    est = L.panel_snapshot(tab)["layout_info_estimate"]
    s2 = L.gen(tab, watcher, "F-001 patch-first -f300", extra_expect=[("already", "Continue")])
    R["f001_patchfirst"] = {"est_before": est, "after": s2, "files": sidecar_facts(run_dir, PROJECT)}
    L.grab(win, OUT / "02-f001-patchfirst-f300.png")

    # ------------------------------------------------------------------ F-003
    # New run through the bar, engine OFF, -L off, -a 1.0; trace every writer.
    L.set_combo_data(win._target_bar._run_combo, "\x00new"); L.pump(1500)
    L.log(f"bar: {win._target_bar._run_combo.currentText()!r} loc={win._target_bar._location.text()!r}")
    L.set_check(tab._manual_engine_check, False); L.pump(600)
    for flag, name in (("-L", "pw[-L]"), ("-a", "pw[-a]"), ("-m", "pw[-m]"), ("-r", "pw[-r]")):
        w = L.pw(tab, "printtarg", flag)
        if w is not None:
            L.trace_pw(w, name)
    for meth in ("_open_this_target_on_its_defaults", "_on_target_changed", "_restore_printtarg_fields",
                 "_apply_instrument_default_margin", "_restore_chart_settings", "_apply_ui_state",
                 "load_target_settings", "save_target_settings", "_align_current_run_to_target",
                 "_convert_engine_to_printtarg", "_reset_knut_overrides", "_leave_applied"):
        if hasattr(tab, meth):
            L.trace_method(tab, meth, "tab")
    L.trace_method(tab._creator, "generate", "creator",
                   show=lambda a, k: (f"disable_left_border={a[0].disable_left_border} patch_scale={a[0].patch_scale} "
                                      f"margin_mm={a[0].margin_mm} no_randomise={a[0].no_randomise} "
                                      f"chromiq_clip_style={a[0].chromiq_clip_style} instr={a[0].instrument} paper={a[0].paper}"))
    # user's explicit choices
    L.pw(tab, "printtarg", "-L").set_value(False); L.pump(200)
    L.pw(tab, "printtarg", "-a").set_value(1.0); L.pump(200)
    L.pump(600)
    R["f003_before"] = {"widgets": widgets(tab), "info": tab._manual_info_lbl.text(),
                        "clip_style_setting": settings.get("i1pro_chromiq_clip_style", None)}
    L.log(f"F-003 before: {R['f003_before']['widgets']} \n   preview: {R['f003_before']['info']!r}")
    L.grab(win, OUT / "03-f003-before-generate.png")
    n_tr = len(L.TRACES); n_app = len(L.APP_LINES)
    watcher.expect("quite fill", "OK")
    L.click(tab._generate_btn)
    L.pump(300)
    R["f003_at_click"] = widgets(tab)
    L.log(f"F-003 300 ms after click: {R['f003_at_click']}")
    L.wait_build(tab, 240_000); watcher.clear()
    L.pump(1500)
    run_dir = L.current_run_dir(win)
    R["f003_after"] = {"widgets": widgets(tab), "run_dir": str(run_dir), "files": sidecar_facts(run_dir, PROJECT),
                       "executed": L.app_lines_since(n_app, r"Run.*printtarg"),
                       "snap": L.panel_snapshot(tab),
                       "traces": [t for t in L.TRACES[n_tr:]]}
    L.grab(win, OUT / "04-f003-after-generate.png")
    L.log(f"F-003 after: widgets={R['f003_after']['widgets']}\n   executed={R['f003_after']['executed']}\n"
          f"   files={R['f003_after']['files']}")

    # Variant B: overwrite the SAME run (no target change) with -L off again
    L.pw(tab, "printtarg", "-L").set_value(False); L.pump(300)
    R["f003b_before"] = widgets(tab)
    n_tr = len(L.TRACES); n_app = len(L.APP_LINES)
    s3 = L.gen(tab, watcher, "F-003 variant B overwrite same run", extra_expect=[("already", "Continue")])
    R["f003b_after"] = {"widgets": widgets(tab), "files": sidecar_facts(run_dir, PROJECT),
                        "executed": L.app_lines_since(n_app, r"Run.*printtarg"), "traces": L.TRACES[n_tr:],
                        "dialogs": [d for d in watcher.seen[-3:]]}
    L.log(f"F-003 B after: widgets={R['f003b_after']['widgets']} executed={R['f003b_after']['executed']}")
    L.grab(win, OUT / "05-f003b-after-overwrite.png")

    R["unexpected"] = watcher.unexpected
    R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r01_results.json")
    L.log(f"unexpected={watcher.unexpected} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
