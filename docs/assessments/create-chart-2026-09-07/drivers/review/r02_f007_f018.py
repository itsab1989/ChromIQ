#!/usr/bin/env python3
"""R02: re-test F-007 (Instrument Limits edit through the real Preferences
dialog: does the panel / estimate / build follow?) and F-018 (Guided i1Pro 3
Plus A4 landscape red out of the box), plus the question F-018 raises: does
the Guided path clamp margins at all (log notes), and do Guided i1 / CM pass
their tables because of a clamp or by coincidence. Own project R2-Guided."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialogButtonBox  # noqa: E402

OUT = L.SHOTS / "R02-f007-f018"
PROJECT = "R2-Guided"
R: dict = {}


def drive_settings(win, watcher, fn, label):
    app = QApplication.instance()
    state = {"done": False, "err": None, "pressed": None}
    watcher.ignore.append("SettingsDialog")

    def tick():
        dlg = app.activeModalWidget()
        if dlg is None or type(dlg).__name__ != "SettingsDialog":
            QTimer.singleShot(150, tick)
            return
        try:
            assert "Preferences" in dlg.windowTitle(), dlg.windowTitle()
            L.log(f"  Preferences dialog open: {dlg.windowTitle()!r}")
            fn(dlg)
            L.pump(400)
            L.grab(dlg, OUT / f"prefs-{label}.png")
            bb = dlg.findChild(QDialogButtonBox)
            okb = bb.button(QDialogButtonBox.StandardButton.Ok)
            state["pressed"] = okb.text()
            okb.click()
        except Exception as e:  # noqa: BLE001
            state["err"] = repr(e)
            L.log(f"  settings drive error {e!r}")
            dlg.reject()
        state["done"] = True

    QTimer.singleShot(250, tick)
    win._open_settings()
    L.pump(1000)
    watcher.ignore.remove("SettingsDialog")
    L.log(f"  Preferences closed via {state['pressed']!r} err={state['err']}")
    return state


def goto_limits(dlg, instr, paper):
    tabs = dlg._tabs
    names = [tabs.tabText(i) for i in range(tabs.count())]
    for i in range(tabs.count()):
        if "Instrument Limits" in tabs.tabText(i):
            tabs.setCurrentIndex(i)
    L.pump(300)
    L.set_combo_text(dlg._margin_instr, instr)
    L.set_combo_text(dlg._margin_paper, paper)
    L.pump(300)
    L.log(f"  prefs tabs={names}\n  limits {instr}/{paper}: fields={ {k: v.value() for k, v in dlg._margin_fields.items()} } ruler={dlg._margin_ruler.value()}")


def guided(tab, win, watcher, instr_text, paper_text, pages, label):
    L.click(tab._guided_btn); L.pump(400)
    L.set_combo_text(tab._instr_combo, instr_text)
    L.set_combo_text(tab._paper_combo, paper_text)
    L.set_spin(tab._pages_spin, pages)
    L.pump(600)
    head = tab._patch_count_lbl.text()
    n0 = len(L.APP_LINES)
    s = L.gen(tab, watcher, label, extra_expect=[("already", "Continue")])
    run_dir = L.current_run_dir(win)
    ch = L.read_json(next(run_dir.glob("*.channels.json"), Path("/nonexistent")))
    rec = ((ch or {}).get("layout") or {}).get("recipe") or {}
    notes = L.app_lines_since(n0, r"raised|threshold|clamp|minimum")
    out = {"headline": head, "snap": s, "recipe_margins": [rec.get(k) for k in ("margin_top", "margin_right", "margin_bottom", "margin_left")],
           "use_instr": rec.get("use_instrument_margins"), "margins_chosen_by_user": (ch or {}).get("margins_chosen_by_user"),
           "clamp_lines": notes, "guided_info": tab._guided_info_lbl.text() if hasattr(tab, "_guided_info_lbl") else None,
           "tab_log_tail": L.tab_log_text(tab)[-900:]}
    L.log(f"  GUIDED {label}: head={head!r} status={s['margin_status']!r} notes={s['margin_notes']!r} recipe_margins={out['recipe_margins']} clamp_lines={notes}")
    return out


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    L.click(tab._guided_btn); L.pump(300)
    tab._target_name_edit.setText(PROJECT); tab._target_name_edit.editingFinished.emit(); L.pump(600)
    L.log(f"guided instr items={L.combo_items(tab._instr_combo)}")
    L.log(f"guided paper items (current instr)={[t for t, d in L.combo_items(tab._paper_combo)]}")

    # ---------------- F-018 and the clamp question ----------------
    R["g_p3_A4R"] = guided(tab, win, watcher, "i1Pro 3", "297 × 210", 1, "p3 A4 landscape")
    L.grab(win, OUT / "01-guided-p3-A4R.png")
    R["g_i1_A4"] = guided(tab, win, watcher, "i1Pro /", "A4 (210", 1, "i1 A4 portrait")
    L.grab(win, OUT / "02-guided-i1-A4.png")
    R["g_CM_A4"] = guided(tab, win, watcher, "ColorMunki", "A4 (210", 1, "CM A4 portrait")
    L.grab(win, OUT / "03-guided-CM-A4.png")
    # i1 A4 LANDSCAPE: table says L26 T38; Guided landscape run-up is L/R
    R["g_i1_A4R"] = guided(tab, win, watcher, "i1Pro /", "297 × 210", 1, "i1 A4 landscape")
    L.grab(win, OUT / "04-guided-i1-A4R.png")
    # p3 A4 portrait
    R["g_p3_A4"] = guided(tab, win, watcher, "i1Pro 3", "A4 (210", 1, "p3 A4 portrait")
    L.grab(win, OUT / "05-guided-p3-A4.png")

    # ---------------- F-007 ----------------
    L.click(tab._manual_btn); L.pump(500)
    if not tab._manual_engine_check.isChecked():
        L.set_check(tab._manual_engine_check, True)
    panel = tab._manual_layout_panel
    auto = tab._manual_auto_patches_check
    if not auto.isChecked():
        auto.click(); L.pump(200)
    L.set_combo_data(panel.instr, "i1"); L.set_combo_data(panel.paper, "A4"); L.set_combo_data(panel.mode, "clip")
    L.set_combo_data(panel.layout_mode, "area_first"); L.set_combo_data(panel.area_method, "by_width")
    L.set_check(panel.use_instr_margins, True); L.set_spin(panel.pages, 1); L.pump(500)
    before = dict(settings.get_margin_thresholds().get("i1Pro|A4 Portrait", {}))
    R["f007_start"] = {"thresholds": before, "panel_margins": {k: v.value() for k, v in panel.margins.items()},
                       "est": L.panel_snapshot(tab)["layout_info_estimate"]}
    L.log(f"F-007 start: {R['f007_start']}")

    def edit(dlg):
        goto_limits(dlg, "i1Pro", "A4 Portrait")
        dlg._margin_fields["T"].setValue(50.0); dlg._margin_fields["T"].editingFinished.emit()
        L.pump(200)
    st = drive_settings(win, watcher, edit, "T50")
    after = dict(settings.get_margin_thresholds().get("i1Pro|A4 Portrait", {}))
    L.pump(800)
    R["f007_after_prefs"] = {"thresholds": after, "panel_margins": {k: v.value() for k, v in panel.margins.items()},
                             "use_instr": panel.use_instr_margins.isChecked(),
                             "est": L.panel_snapshot(tab)["layout_info_estimate"], "prefs": st}
    L.log(f"F-007 after prefs OK: {R['f007_after_prefs']}")
    L.grab(win, OUT / "10-f007-after-prefs-before-generate.png")
    s = L.gen(tab, watcher, "F-007 build after T50", extra_expect=[("already", "Continue")])
    R["f007_built"] = {"snap": s, "panel_margins": {k: v.value() for k, v in panel.margins.items()}}
    L.grab(win, OUT / "11-f007-built-after-T50.png")
    # does re-ticking the box pick the 50 up?
    L.set_check(panel.use_instr_margins, False); L.pump(200); L.set_check(panel.use_instr_margins, True); L.pump(500)
    R["f007_retick"] = {"panel_margins": {k: v.value() for k, v in panel.margins.items()},
                        "est": L.panel_snapshot(tab)["layout_info_estimate"]}
    L.log(f"F-007 after re-tick: {R['f007_retick']}")
    # restore 38
    def restore(dlg):
        goto_limits(dlg, "i1Pro", "A4 Portrait")
        dlg._margin_fields["T"].setValue(float(before.get("T", 38))); dlg._margin_fields["T"].editingFinished.emit()
    drive_settings(win, watcher, restore, "restore")
    L.pump(600)
    R["f007_restored"] = {"thresholds": dict(settings.get_margin_thresholds().get("i1Pro|A4 Portrait", {})),
                          "panel_margins": {k: v.value() for k, v in panel.margins.items()}}
    L.log(f"F-007 restored: {R['f007_restored']}")

    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r02_results.json")
    L.log(f"unexpected={watcher.unexpected} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
