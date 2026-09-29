#!/usr/bin/env python3
"""D00: launch the real app, capture the empty state, open Demo-Full-RGB,
walk Guided / Manual, and dump an inventory of every layout-panel control
(items, bounds, visibility) so later drivers and the functional inventory
have a ground truth."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtWidgets import (QAbstractSpinBox, QCheckBox, QComboBox,  # noqa: E402
                             QLineEdit, QPushButton, QRadioButton)

OUT = L.SHOTS / "00-launch"


def control_inventory(panel) -> dict:
    inv = {}
    for name in dir(panel):
        if name.startswith("__"):
            continue
        try:
            w = getattr(panel, name)
        except Exception:
            continue
        if isinstance(w, QComboBox):
            inv[name] = {"type": "combo", "items": L.combo_items(w),
                         "current": w.currentData(), "visible": w.isVisible(),
                         "enabled": w.isEnabled()}
        elif isinstance(w, QAbstractSpinBox):
            inv[name] = {"type": type(w).__name__, **L.spinbox_bounds(w)}
        elif isinstance(w, (QCheckBox, QRadioButton)):
            inv[name] = {"type": "check", "checked": w.isChecked(),
                         "text": w.text(), "visible": w.isVisible(),
                         "enabled": w.isEnabled()}
        elif isinstance(w, QLineEdit):
            inv[name] = {"type": "line", "text": w.text(), "visible": w.isVisible()}
        elif isinstance(w, QPushButton):
            inv[name] = {"type": "button", "text": w.text(), "visible": w.isVisible(),
                         "enabled": w.isEnabled()}
        elif isinstance(w, dict) and name == "margins":
            inv[name] = {k: L.spinbox_bounds(v) for k, v in w.items()}
    return inv


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    L.grab(win, OUT / "01-startup-window.png")
    tab = L.goto_chart_tab(win)
    L.grab(win, OUT / "02-create-chart-no-project.png")
    log = L.log
    log(f"mode buttons: guided={tab._guided_btn.isChecked()} manual={tab._manual_btn.isChecked()} "
        f"gamut visible={tab._gamut_btn.isVisible()}")
    log(f"run bar: run={win._target_bar._run_combo.currentText()!r} "
        f"type={win._target_bar._type_combo.currentText()!r} "
        f"type items={L.combo_items(win._target_bar._type_combo)}")
    log(f"generate enabled={tab._generate_btn.isEnabled()} text={tab._generate_btn.text()!r}")
    log(f"engine setting={settings.get('use_chromiq_layout_engine')} auto_update={settings.get('auto_update_preview')}")

    # empty-state panels
    L.save_json(L.panel_snapshot(tab), L.LOGS / "d00_panels_no_project.json")

    # open the demo project
    ok = L.open_project(win, settings, "Demo-Full-RGB")
    L.grab(win, OUT / "03-demo-full-rgb-opened.png")
    log(f"opened={ok} run items={L.combo_items(win._target_bar._run_combo)}")
    L.save_json(L.panel_snapshot(tab), L.LOGS / "d00_panels_demo_full_rgb.json")

    # Guided
    L.click(tab._guided_btn)
    L.pump(600)
    L.grab(win, OUT / "04-guided.png")
    g = {
        "instr_items": L.combo_items(tab._instr_combo),
        "paper_items": L.combo_items(tab._paper_combo),
        "pages": L.spinbox_bounds(tab._pages_spin),
        "dd_visible": tab._dd_check.isVisible(), "td_visible": tab._td_check.isVisible(),
        "lb_visible": tab._lb_check.isVisible(), "lb_checked": tab._lb_check.isChecked(),
        "nsl_visible": tab._nsl_check.isVisible(),
        "patch_count_lbl": tab._patch_count_lbl.text(),
        "patch_detail_lbl": tab._patch_detail_lbl.text(),
        "guided_info": tab._guided_info_lbl.text()[:500],
        "name": tab._target_name_edit.text(),
        "name_hint": tab._target_name_hint.text(),
    }
    L.save_json(g, L.LOGS / "d00_guided_inventory.json")
    # paper list per instrument in Guided
    per = {}
    for i in range(tab._instr_combo.count()):
        tab._instr_combo.setCurrentIndex(i)
        L.pump(300)
        per[str(tab._instr_combo.itemData(i))] = {
            "papers": [d for _, d in L.combo_items(tab._paper_combo)],
            "count_lbl": tab._patch_count_lbl.text(),
            "detail": tab._patch_detail_lbl.text(),
            "dd": tab._dd_check.isVisible(), "td": tab._td_check.isVisible(),
            "lb": tab._lb_check.isVisible(), "nsl": tab._nsl_check.isVisible()}
        L.grab(win, OUT / f"05-guided-instr-{tab._instr_combo.itemData(i)}.png")
    L.save_json(per, L.LOGS / "d00_guided_per_instrument.json")
    tab._instr_combo.setCurrentIndex(0)
    L.pump(200)

    # Manual
    L.click(tab._manual_btn)
    L.pump(800)
    L.grab(win, OUT / "06-manual.png")
    chk = tab._manual_engine_check
    log(f"manual engine check: visible={chk.isVisible()} checked={chk.isChecked()} text={chk.text()!r}")
    log(f"auto preview row visible={tab._auto_preview_row_w.isVisible()} checked={tab._auto_preview_check.isChecked()}")
    log(f"preset combo items={L.combo_items(tab._preset_combo)}")
    if not chk.isChecked():
        watcher.expect("layout", "OK", note="engine toggle may inform")
        L.set_check(chk, True)
        L.pump(800)
        watcher.clear()
    L.grab(win, OUT / "07-manual-engine-on.png")
    panel = tab._manual_layout_panel
    grp = tab._manual_layout_grp
    log(f"layout group collapsed={grp.is_collapsed()} visible={grp.isVisible()}")
    if grp.is_collapsed():
        grp.set_collapsed(False)
        L.pump(400)
    inv = control_inventory(panel)
    L.save_json(inv, L.LOGS / "d00_layout_panel_inventory.json")
    # instrument x mode x paper lists
    combos = {}
    for i in range(panel.instr.count()):
        panel.instr.setCurrentIndex(i)
        L.pump(300)
        key = str(panel.instr.itemData(i))
        combos[key] = {"label": panel.instr.itemText(i),
                       "modes": L.combo_items(panel.mode),
                       "mode_label": getattr(panel, "_mode_lbl", None) and panel._mode_lbl.text(),
                       "papers": [d for _, d in L.combo_items(panel.paper)],
                       "layout_mode": panel.layout_mode.currentData(),
                       "area_method": panel.area_method.currentData(),
                       "helper_markers_enabled": panel.helper_markers_cb.isEnabled(),
                       "clip_group_visible": panel._clip_content_grp.isVisible(),
                       "use_instr_margins": (panel.use_instr_margins.isVisible(), panel.use_instr_margins.isChecked()),
                       "margins": {k: v.value() for k, v in panel.margins.items()},
                       "patch_xy": (panel.patch_x.value(), panel.patch_y.value()),
                       "pscale": panel.pscale.value(), "sscale": panel.sscale.value(),
                       "spacer_mode": panel.spacer_mode.currentData(),
                       "spacer_width": panel.spacer_width.value(),
                       "max_strip": panel.max_strip.value(), "nolimit": panel.nolimit.isChecked(),
                       "dpi": panel.dpi.value(), "pages": panel.pages.value(),
                       }
        L.grab(win, OUT / f"08-manual-engine-instr-{key}.png")
    L.save_json(combos, L.LOGS / "d00_engine_instr_matrix.json")
    panel.instr.setCurrentIndex(0)
    L.pump(300)

    # Run type = Verification shows the gamut button?
    L.set_combo_data(win._target_bar._type_combo, "verification")
    L.pump(800)
    log(f"after run type verification: gamut btn visible={tab._gamut_btn.isVisible()} "
        f"type={win._target_bar._type_combo.currentText()!r}")
    L.grab(win, OUT / "09-run-type-verification.png")
    if tab._gamut_btn.isVisible():
        L.click(tab._gamut_btn)
        L.pump(800)
        L.grab(win, OUT / "10-gamut-module.png")
        log(f"gamut: noprofile lbl visible={tab._verify_noprofile_lbl.isVisible()} text={tab._verify_noprofile_lbl.text()[:300]!r}")
    L.set_combo_data(win._target_bar._type_combo, "profiling")
    L.pump(600)
    L.click(tab._manual_btn)
    L.pump(400)

    log(f"serious log records: {L.serious_since(0)}")
    log(f"dialogs seen: {watcher.seen}")
    log(f"unexpected dialogs: {watcher.unexpected}")
    win.close()
    L.pump(400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
