#!/usr/bin/env python3
"""R06b: the probes R06 did not reach. Typed-name route again (to catch the
dialog that blocked R06), keyboard focus order, -f 0 with Auto off, Pages 3
with -f 50, a double click on Generate, preset "+" with an empty name, Escape
on the last-page hint, Delete run from the bar (cancelled)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402
from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

OUT = L.SHOTS / "R06-crossproject-probes"
R: dict = {}
PROJ = Path("/Users/Basti/ChromIQ-assessment")


def desc(w) -> str:
    if w is None:
        return "None"
    t = type(w).__name__
    txt = ""
    for attr in ("text", "currentText", "placeholderText"):
        f = getattr(w, attr, None)
        if callable(f):
            try:
                v = f()
                if v:
                    txt = v.replace("\n", " ")[:40]
                    break
            except Exception:  # noqa: BLE001
                pass
    return f"{t}({w.objectName() or ''}|{txt})"


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    bar = win._target_bar
    tab.open_project_manifest(PROJ / "R2-Guided" / "project.json"); L.pump(1500)
    L.click(tab._manual_btn); L.pump(500)

    # ---------- typed-name route again ----------
    tab._manual_target_name_edit.setText("R2-High"); tab._manual_target_name_edit.editingFinished.emit(); L.pump(800)
    R["t_typed"] = {"hint": tab._target_name_hint.text() if hasattr(tab, "_target_name_hint") else None, "loc": bar._location.text()}
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    watcher.expect("quite fill", "OK"); watcher.expect("already", "Continue")
    L.click(tab._generate_btn)
    ok = L.wait_build(tab, 180_000); L.pump(2500); watcher.clear()
    R["t_typed"].update({"built_ok": ok, "loc_after": bar._location.text(), "run_after": bar._run_combo.currentText(),
                         "dialogs": [(d.get("class"), d.get("title"), (d.get("text") or "")[:300], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                         "actual": L.panel_snapshot(tab)["layout_info_actual"], "watchdog": L.app_lines_since(n0, r"watchdog|chart_finished"),
                         "targen": L.app_lines_since(n0, r"Run: .*targen")})
    L.log(f"  T typed-name: {R['t_typed']}")
    L.grab(win, OUT / "t01-typed-other-name-generate.png")

    # ---------- keyboard focus order ----------
    def tab_order(start, n):
        start.setFocus(); L.pump(200)
        seq = [desc(QApplication.focusWidget())]
        for _ in range(n):
            QTest.keyClick(QApplication.focusWidget() or win, Qt.Key.Key_Tab); L.pump(50)
            seq.append(desc(QApplication.focusWidget()))
        return seq
    R["focus_manual"] = tab_order(tab._manual_target_name_edit, 45)
    L.click(tab._guided_btn); L.pump(300)
    R["focus_guided"] = tab_order(tab._target_name_edit, 30)
    L.log("  FOCUS manual: " + " > ".join(R["focus_manual"]))
    L.log("  FOCUS guided: " + " > ".join(R["focus_guided"]))

    # ---------- probes on R2-Guided ----------
    tab.open_project_manifest(PROJ / "R2-Guided" / "project.json"); L.pump(1500)
    L.click(tab._manual_btn); L.pump(400)
    auto = tab._manual_auto_patches_check
    panel = tab._manual_layout_panel
    if auto.isChecked():
        auto.click(); L.pump(200)
    fpw = L.pw(tab, "targen", "-f")
    fpw.set_value(0); L.pump(400)
    R["p_f0"] = {"raw": fpw.get_raw_value(), "info": tab._manual_info_lbl.text()[:200], "est": L.panel_snapshot(tab)["layout_info_estimate"],
                 "gen_enabled": tab._generate_btn.isEnabled(), "auto_now": auto.isChecked()}
    ns = len(watcher.seen); n0 = len(L.APP_LINES)
    s = L.gen(tab, watcher, "-f 0, Auto off", extra_expect=[("already", "Continue")])
    R["p_f0"].update({"dialogs": [((d.get("text") or "")[:160], d.get("answer")) for d in watcher.seen[ns:]], "actual": s["layout_info_actual"], "errors": s["errors"], "targen": L.app_lines_since(n0, r"Run: .*targen")})
    L.log(f"  P -f0: {R['p_f0']}")
    fpw.set_value(50); L.pump(300)
    R["p_pages3_f50"] = {"pages_enabled": panel.pages.isEnabled(), "pages": panel.get_pages(), "info": tab._manual_info_lbl.text()[:160]}
    if panel.pages.isEnabled():
        L.set_spin(panel.pages, 3)
    s = L.gen(tab, watcher, "-f 50", extra_expect=[("already", "Continue")])
    R["p_pages3_f50"].update({"actual": s["layout_info_actual"], "est": s["layout_info_estimate"]})
    L.log(f"  P pages3/f50: {R['p_pages3_f50']}")
    # double click
    if not auto.isChecked():
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
    L.click(tab._preset_add_btn); L.pump(1500); watcher.clear()
    R["p_preset_add"] = {"dialogs": [(d.get("class"), d.get("title"), (d.get("text") or "")[:240], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]]}
    L.log(f"  P preset+: {R['p_preset_add']}")
    # Escape on the hint
    if auto.isChecked():
        auto.click(); L.pump(200)
    fpw.set_value(400); L.set_combo_data(panel.layout_mode, "area_first"); L.pump(300)
    ns = len(watcher.seen)
    watcher.ignore.append("quite fill")
    esc = {"seen": None}

    def press_escape():
        w = watcher._find_modal()
        if w is None:
            QTimer.singleShot(150, press_escape); return
        d = L.ModalWatcher.describe(w)
        if "quite fill" not in d["text"]:
            QTimer.singleShot(150, press_escape); return
        esc["seen"] = d["buttons"]
        QTest.keyClick(w, Qt.Key.Key_Escape)
        L.log(f"  ESC sent to the hint dialog (buttons {d['buttons']})")
    QTimer.singleShot(300, press_escape)
    watcher.expect("already", "Continue")
    L.click(tab._generate_btn); L.wait_build(tab, 240_000); L.pump(1500)
    watcher.ignore.remove("quite fill"); watcher.clear()
    R["p_escape_hint"] = {"seen": esc["seen"], "dialogs_after": [(d.get("class"), d.get("title"), (d.get("text") or "")[:80]) for d in watcher.seen[ns:]],
                          "actual": L.panel_snapshot(tab)["layout_info_actual"], "modal_now": desc(watcher._find_modal())}
    L.log(f"  P escape: {R['p_escape_hint']}")
    if watcher._find_modal() is not None:
        watcher._find_modal().reject(); L.pump(300)
    # Delete run via the bar (cancelled)
    ns = len(watcher.seen)
    runs_before = sorted(p.name for p in (PROJ / "R2-Guided" / "runs").glob("run*"))
    watcher.expect("Delete", "Cancel")
    L.click(bar._delete_btn); L.pump(1500); watcher.clear()
    R["p_delete_run"] = {"runs_before": runs_before, "dialogs": [((d.get("title") or ""), (d.get("text") or "")[:400], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                         "runs_after": sorted(p.name for p in (PROJ / "R2-Guided" / "runs").glob("run*")), "delete_enabled": bar._delete_btn.isEnabled()}
    L.log(f"  P delete-run (cancelled): {R['p_delete_run']}")

    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r06b_results.json")
    L.log(f"unexpected={[(u.get('title'), (u.get('text') or '')[:120]) for u in watcher.unexpected]} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
