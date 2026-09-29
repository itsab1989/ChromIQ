#!/usr/bin/env python3
"""R03: re-test F-024 / F-023 (a visit to FROM PROFILE GAMUT on a run without
a profile disables Generate everywhere and shows Stop) and the F-002 frame
staleness under Verification. Then find what, if anything, gives Generate
back (run switch, project switch, a Guided build attempt). Demo-Full-RGB run3
(no .icc), own ordered steps, screenshots at every state."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402

OUT = L.SHOTS / "R03-f024-gamut"
R: dict = {}


def state(tab, win, label):
    s = L.panel_snapshot(tab)
    d = {"generate_enabled": s["generate_enabled"], "stop_visible": s["stop_visible"],
         "in_flight": tab._chart_build_in_flight(), "runner_running": tab._runner.is_running,
         "run_bar": win._target_bar._run_combo.currentText(), "type": win._target_bar._type_combo.currentText(),
         "noprofile_box_visible": tab._verify_noprofile_lbl.isVisible() if hasattr(tab, "_verify_noprofile_lbl") else None,
         "preview_notice": getattr(tab._preview, "_notice", None) if hasattr(tab._preview, "_notice") else None,
         "margin_status": s["margin_status"], "margin_text": s["margin_panel_text"][:160],
         "info_actual": s["layout_info_actual"], "info_est": s["layout_info_estimate"]}
    L.log(f"  STATE {label}: gen={d['generate_enabled']} stop={d['stop_visible']} inflight={d['in_flight']} "
          f"bar={d['run_bar']!r}/{d['type']!r} status={d['margin_status']!r} actual={d['info_actual'] and d['info_actual'].get('total')} est={d['info_est'] and d['info_est'].get('total')}")
    return d


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    L.open_project(win, settings, "Demo-Full-RGB")
    tab = L.goto_chart_tab(win)
    bar = win._target_bar
    L.log(f"runs={L.combo_items(bar._run_combo)} types={L.combo_items(bar._type_combo)}")
    icc = {r: sorted(p.name for p in (Path('/Users/Basti/ChromIQ-assessment/Demo-Full-RGB/runs') / r).glob('*.icc')) for r in ("run1", "run2", "run3", "run4") if (Path('/Users/Basti/ChromIQ-assessment/Demo-Full-RGB/runs') / r).is_dir()}
    L.log(f"icc per run: {icc}")
    L.set_combo_data(bar._run_combo, "run3"); L.pump(1200)
    L.click(tab._guided_btn); L.pump(300)
    R["s0_profiling_guided"] = state(tab, win, "run3 Profiling Guided")
    L.grab(win, OUT / "00-run3-profiling-guided.png")
    # Verification
    L.set_combo_data(bar._type_combo, "verification"); L.pump(1500)
    R["s1_verif_guided"] = state(tab, win, "run3 Verification Guided (before gamut)")
    L.grab(win, OUT / "01-verif-guided-before-gamut.png")
    L.click(tab._gamut_btn); L.pump(1200)
    R["s2_gamut"] = state(tab, win, "run3 Verification GAMUT (no profile)")
    R["s2_gamut"]["empty_text"] = tab._gamut_empty_lbl.text()[:300] if hasattr(tab, "_gamut_empty_lbl") else None
    L.grab(win, OUT / "02-gamut-no-profile.png")
    L.click(tab._guided_btn); L.pump(800)
    R["s3_guided_after"] = state(tab, win, "Guided after gamut")
    L.grab(win, OUT / "03-guided-after-gamut.png")
    L.click(tab._manual_btn); L.pump(800)
    R["s4_manual_after"] = state(tab, win, "Manual after gamut")
    L.grab(win, OUT / "04-manual-after-gamut.png")
    L.set_combo_data(bar._type_combo, "profiling"); L.pump(1500)
    R["s5_profiling_after"] = state(tab, win, "Profiling after gamut")
    L.grab(win, OUT / "05-profiling-after-gamut.png")
    # what gives it back? try a run switch
    L.set_combo_data(bar._run_combo, "run2"); L.pump(1500)
    R["s6_run2"] = state(tab, win, "run2 Profiling after gamut leak")
    L.set_combo_data(bar._run_combo, "run3"); L.pump(1500)
    R["s7_run3_again"] = state(tab, win, "run3 again")
    # try the keyboard shortcut / click on the disabled button
    L.click(tab._generate_btn); L.pump(500)
    R["s8_click_disabled"] = state(tab, win, "after clicking the greyed Generate")
    # try switching project
    L.open_project(win, settings, "A1-EngineVsPrinttarg"); L.pump(800)
    tab = L.goto_chart_tab(win)
    R["s9_other_project"] = state(tab, win, "A1-EngineVsPrinttarg opened")
    L.grab(win, OUT / "06-other-project-after-leak.png")
    # Verification + gamut on a run WITH a profile: does Generate return there?
    L.open_project(win, settings, "Demo-Full-RGB"); L.pump(800)
    tab = L.goto_chart_tab(win)
    L.set_combo_data(bar._run_combo, "run2"); L.pump(1000)
    L.set_combo_data(bar._type_combo, "verification"); L.pump(1500)
    L.click(tab._gamut_btn); L.pump(1500)
    R["s10_gamut_with_profile"] = state(tab, win, "run2 Verification GAMUT (has profile)")
    L.grab(win, OUT / "07-gamut-with-profile-run2.png")
    L.click(tab._guided_btn); L.pump(800)
    R["s11_guided_after_profile_gamut"] = state(tab, win, "Guided after gamut on run2")
    L.set_combo_data(bar._type_combo, "profiling"); L.pump(1200)
    R["s12_profiling_run2"] = state(tab, win, "run2 Profiling")
    # F-002 instance: New run under Profiling -> frames?
    L.set_combo_data(bar._run_combo, "\x00new"); L.pump(1500)
    R["s13_new_run"] = state(tab, win, "New run (empty)")
    R["s13_new_run"]["margin_visible"] = tab._margin_panel.isVisible()
    R["s13_new_run"]["info_visible"] = tab._layout_info_panel.isVisible()
    L.grab(win, OUT / "08-new-run-frames.png")

    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r03_results.json")
    L.log(f"unexpected={watcher.unexpected} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
