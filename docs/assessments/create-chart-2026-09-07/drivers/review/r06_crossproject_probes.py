#!/usr/bin/env python3
"""R06: (1) the cross-project armed-set case through the REAL Open Project
route (`open_project_manifest`, the act behind the header icon; the file
picker is the only thing substituted, logged); (2) the typed-name route
(type another existing project's name, press Generate); (3) keyboard focus
order in Manual and Guided; (4) first-time-user probes: Generate with an
empty name and no project, Auto off with -f 0, Pages 3 with -f 50, a double
click on Generate, preset "+" with an empty name, Escape on the last-page
hint, Delete run from the bar with a chart on screen."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402
from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QAbstractSpinBox, QLineEdit, QPushButton, QAbstractButton  # noqa: E402

OUT = L.SHOTS / "R06-crossproject-probes"
R: dict = {}
PROJ = Path("/Users/Basti/ChromIQ-assessment")


def desc(w) -> str:
    if w is None:
        return "None"
    t = type(w).__name__
    txt = ""
    for attr in ("text", "currentText", "placeholderText", "toolTip"):
        f = getattr(w, attr, None)
        if callable(f):
            try:
                v = f()
                if v:
                    txt = v.replace("\n", " ")[:50]
                    break
            except Exception:  # noqa: BLE001
                pass
    return f"{t}({w.objectName() or ''}|{txt})"


def arm_state(tab):
    return {"preset_ti1": str(getattr(tab, "_preset_ti1_path", None)),
            "override_row": (tab._override_targen_check.isVisible(), tab._override_targen_check.isChecked()) if tab._override_targen_check else None,
            "engine_on": tab._manual_engine_check.isChecked(), "engine_enabled": tab._manual_engine_check.isEnabled(),
            "f": L.pw(tab, "targen", "-f").get_raw_value(), "auto": tab._manual_auto_patches_check.isChecked(),
            "info": tab._manual_info_lbl.text()[:300], "est": L.panel_snapshot(tab)["layout_info_estimate"]}


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    bar = win._target_bar

    # ---------- (4a) fresh window, no project: Guided Generate with an empty name ----------
    L.click(tab._guided_btn); L.pump(300)
    R["p_empty_name"] = {"name_field": tab._target_name_edit.text(), "run_bar": bar._run_combo.currentText(), "loc": bar._location.text()}
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    L.click(tab._generate_btn); L.pump(2500)
    R["p_empty_name"].update({"dialogs": [(d.get("class"), d.get("title"), (d.get("text") or "")[:200], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                              "generate_enabled": tab._generate_btn.isEnabled(), "runner": tab._runner.is_running,
                              "lines": L.app_lines_since(n0, r"Run:|ERROR|WARNING")[:4], "loc_after": bar._location.text()})
    L.wait_build(tab, 120_000)
    L.log(f"  P empty-name: {R['p_empty_name']}")
    L.grab(win, OUT / "p01-empty-name-generate.png")

    # ---------- (1) cross-project via the real Open Project route ----------
    tab.open_project_manifest(PROJ / "Demo-Full-RGB" / "project.json"); L.pump(1800)
    R["x_demo"] = {"loc": bar._location.text(), "run": bar._run_combo.currentText(), **arm_state(tab)}
    L.log(f"  X Demo opened via manifest: run={R['x_demo']['run']} armed={R['x_demo']['preset_ti1']}")
    tab.open_project_manifest(PROJ / "R2-Guided" / "project.json"); L.pump(1800)
    L.click(tab._manual_btn); L.pump(600)
    if not tab._manual_engine_check.isEnabled() or not tab._manual_engine_check.isChecked():
        L.log(f"  engine toggle enabled={tab._manual_engine_check.isEnabled()} on={tab._manual_engine_check.isChecked()}")
    run_dir = L.current_run_dir(win)
    before_sets = L.ti1_sets(next(run_dir.glob("*.ti1"), Path("/x")))
    R["x_guided"] = {"loc": bar._location.text(), "run": bar._run_combo.currentText(), "name_field": tab._manual_target_name_edit.text(),
                     "ti1_before": before_sets, **arm_state(tab)}
    L.log(f"  X R2-Guided opened via manifest: {R['x_guided']}")
    L.grab(win, OUT / "x01-r2guided-after-demo.png")
    if not tab._manual_auto_patches_check.isChecked() and tab._manual_auto_patches_check.isEnabled():
        tab._manual_auto_patches_check.click(); L.pump(200)
    n0 = len(L.APP_LINES)
    s = L.gen(tab, watcher, "Generate on R2-Guided after Demo (manifest route)", extra_expect=[("already", "Continue")])
    run_dir = L.current_run_dir(win)
    R["x_guided_after"] = {"loc": bar._location.text(), "run": bar._run_combo.currentText(), "actual": s["layout_info_actual"],
                           "ti1_after": L.ti1_sets(next(run_dir.glob("*.ti1"), Path("/x"))), "targen": L.app_lines_since(n0, r"Run: .*targen"),
                           "build_lines": L.app_lines_since(n0, r"chart build \(")}
    L.log(f"  X after Generate: {R['x_guided_after']}")
    L.grab(win, OUT / "x02-r2guided-after-generate.png")

    # ---------- (2) typed-name route ----------
    tab._manual_target_name_edit.setText("R2-High"); tab._manual_target_name_edit.editingFinished.emit(); L.pump(800)
    R["t_typed"] = {"hint": tab._target_name_hint.text() if hasattr(tab, "_target_name_hint") else None, "loc": bar._location.text(),
                    "run": bar._run_combo.currentText(), "project_exists_lbl": getattr(tab, "_project_exists_lbl", None) and tab._project_exists_lbl.text()}
    high_run2_before = sorted(p.name for p in (PROJ / "R2-High" / "runs" / "run2").glob("*"))
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    s = L.gen(tab, watcher, "Generate after typing R2-High", extra_expect=[("already", "Continue"), ("Rename", "Cancel")])
    R["t_typed"].update({"loc_after": bar._location.text(), "run_after": bar._run_combo.currentText(), "name_after": tab._manual_target_name_edit.text(),
                         "dialogs": [((d.get("text") or "")[:140], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                         "actual": s["layout_info_actual"], "targen": L.app_lines_since(n0, r"Run: .*targen"), "build_lines": L.app_lines_since(n0, r"chart build \("),
                         "high_run2_changed": sorted(p.name for p in (PROJ / "R2-High" / "runs" / "run2").glob("*")) != high_run2_before,
                         "high_runs": sorted(p.name for p in (PROJ / "R2-High" / "runs").glob("run*"))})
    L.log(f"  T typed-name: {R['t_typed']}")
    L.grab(win, OUT / "t01-typed-other-name-generate.png")

    # ---------- (3) keyboard focus order ----------
    def tab_order(start, n=40):
        start.setFocus(); L.pump(200)
        seq = [desc(QApplication.focusWidget())]
        for _ in range(n):
            QTest.keyClick(QApplication.focusWidget() or win, Qt.Key.Key_Tab); L.pump(60)
            seq.append(desc(QApplication.focusWidget()))
        return seq
    L.click(tab._manual_btn); L.pump(300)
    R["focus_manual"] = tab_order(tab._manual_target_name_edit, 45)
    L.click(tab._guided_btn); L.pump(300)
    R["focus_guided"] = tab_order(tab._target_name_edit, 30)
    L.log("  FOCUS manual: " + " > ".join(R["focus_manual"][:45]))
    L.log("  FOCUS guided: " + " > ".join(R["focus_guided"][:30]))

    # ---------- (4b..g) first-time probes on R2-Guided ----------
    tab.open_project_manifest(PROJ / "R2-Guided" / "project.json"); L.pump(1500)
    L.click(tab._manual_btn); L.pump(400)
    auto = tab._manual_auto_patches_check
    if auto.isChecked():
        auto.click(); L.pump(200)
    # -f 0 with Auto off
    L.pw(tab, "targen", "-f").set_value(0); L.pump(400)
    R["p_f0"] = {"info": tab._manual_info_lbl.text()[:200], "est": L.panel_snapshot(tab)["layout_info_estimate"], "gen_enabled": tab._generate_btn.isEnabled(),
                 "f_min": L.pw(tab, "targen", "-f")._control.minimum() if hasattr(L.pw(tab, 'targen', '-f')._control, 'minimum') else None}
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    s = L.gen(tab, watcher, "-f 0, Auto off", extra_expect=[("already", "Continue")])
    R["p_f0"].update({"dialogs": [((d.get("text") or "")[:160], d.get("answer")) for d in watcher.seen[ns:]], "actual": s["layout_info_actual"], "errors": s["errors"], "targen": L.app_lines_since(n0, r"Run: .*targen")})
    L.log(f"  P -f0: {R['p_f0']}")
    # Pages 3 with -f 50
    panel = tab._manual_layout_panel
    L.pw(tab, "targen", "-f").set_value(50); L.pump(200)
    R["p_pages3_f50"] = {"pages_enabled": panel.pages.isEnabled(), "pages": panel.get_pages(), "info": tab._manual_info_lbl.text()[:160]}
    if panel.pages.isEnabled():
        L.set_spin(panel.pages, 3)
    s = L.gen(tab, watcher, "-f 50", extra_expect=[("already", "Continue")])
    R["p_pages3_f50"].update({"actual": s["layout_info_actual"], "est": s["layout_info_estimate"]})
    L.log(f"  P pages3/f50: {R['p_pages3_f50']}")
    # double click on Generate
    auto.click(); L.pump(200)
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue")
    tab._generate_btn.click(); tab._generate_btn.click(); L.pump(300)
    L.wait_build(tab, 240_000); L.pump(800); watcher.clear()
    R["p_double_click"] = {"targen_runs": len(L.app_lines_since(n0, r"Run: .*targen")), "build_lines": L.app_lines_since(n0, r"chart build \("),
                           "dialogs": [((d.get("text") or "")[:100], d.get("answer")) for d in watcher.seen[ns:]], "errors": L.app_lines_since(n0, r"ERROR|CRITICAL")}
    L.log(f"  P double-click: {R['p_double_click']}")
    # preset + with an empty name
    ns = len(watcher.seen)
    watcher.expect("preset", "<reject>")
    L.click(tab._preset_add_btn); L.pump(1200); watcher.clear()
    R["p_preset_add"] = {"dialogs": [(d.get("class"), d.get("title"), (d.get("text") or "")[:200], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]]}
    L.log(f"  P preset+: {R['p_preset_add']}")
    # Escape on the last-page hint: fixed -f 400 area-first raises it
    if auto.isChecked():
        auto.click(); L.pump(200)
    L.pw(tab, "targen", "-f").set_value(400); L.set_combo_data(panel.layout_mode, "area_first"); L.pump(300)
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    watcher.ignore.append("quite fill")
    from PyQt6.QtCore import QTimer
    esc = {"seen": None, "result": None}

    def press_escape():
        w = app.activeModalWidget()
        if w is None:
            QTimer.singleShot(150, press_escape); return
        d = L.ModalWatcher.describe(w)
        if "quite fill" not in d["text"]:
            QTimer.singleShot(150, press_escape); return
        esc["seen"] = d
        QTest.keyClick(w, Qt.Key.Key_Escape)
        L.log(f"  ESC sent to the hint dialog (buttons {d['buttons']})")
    QTimer.singleShot(300, press_escape)
    L.click(tab._generate_btn); L.wait_build(tab, 240_000); L.pump(1000)
    watcher.ignore.remove("quite fill")
    R["p_escape_hint"] = {"seen": esc["seen"] and esc["seen"]["buttons"], "editor_opened": any("patch set" in (d.get("title") or "").lower() for d in watcher.seen[ns:]),
                          "dialogs_after": [(d.get("class"), d.get("title")) for d in watcher.seen[ns:]], "actual": L.panel_snapshot(tab)["layout_info_actual"],
                          "modal_now": desc(app.activeModalWidget())}
    L.log(f"  P escape: {R['p_escape_hint']}")
    # Delete run via the bar
    ns = len(watcher.seen)
    runs_before = sorted(p.name for p in (PROJ / "R2-Guided" / "runs").glob("run*"))
    watcher.expect("Delete", "Cancel")
    L.click(bar._delete_btn); L.pump(1200); watcher.clear()
    R["p_delete_run"] = {"runs_before": runs_before, "dialogs": [((d.get("title") or ""), (d.get("text") or "")[:300], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                         "runs_after": sorted(p.name for p in (PROJ / "R2-Guided" / "runs").glob("run*")), "delete_enabled": bar._delete_btn.isEnabled()}
    L.log(f"  P delete-run (cancelled): {R['p_delete_run']}")

    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r06_results.json")
    L.log(f"unexpected={[(u.get('title'), (u.get('text') or '')[:120]) for u in watcher.unexpected]} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
