#!/usr/bin/env python3
"""R08: quick re-tests of low findings and two baselines. F-004 (engine toggle
flips the Stamp box), F-009 (SpectroScan: instrument-margin box ticked and
locked with no table), F-011 (example-table question with only OK), F-026
(row labels clipped at 1280 x 800, measured with font metrics), Guided -L/-P
boxes move the headline. Project R2-Engine."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import r_lib as L  # noqa: E402
from PyQt6.QtWidgets import QLabel  # noqa: E402

OUT = L.SHOTS / "R08-lows"
R: dict = {}
PROJ = Path("/Users/Basti/ChromIQ-assessment")


def clipped_labels(w):
    out = []
    for l in w.findChildren(QLabel):
        if not l.isVisible() or not l.text().strip() or l.wordWrap():
            continue
        need = l.fontMetrics().horizontalAdvance(l.text())
        if need > l.width() + 1:
            out.append((l.text()[:50], need, l.width()))
    return out


def main() -> int:
    app, settings = L.build_app()
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    tab = L.goto_chart_tab(win)
    tab.open_project_manifest(PROJ / "R2-Engine" / "project.json"); L.pump(1500)
    L.click(tab._manual_btn); L.pump(400)
    panel = tab._manual_layout_panel
    stamp = tab._manual_stamp_cmd_check

    # F-004
    L.set_check(tab._manual_engine_check, True); L.pump(300)
    L.set_check(stamp, True); L.pump(200)
    s0 = stamp.isChecked()
    L.set_check(tab._manual_engine_check, False); L.pump(500)
    s1 = stamp.isChecked()
    L.set_check(tab._manual_engine_check, True); L.pump(500)
    s2 = stamp.isChecked()
    R["f004"] = {"stamp_before": s0, "after_engine_off": s1, "after_engine_on": s2}
    L.log(f"  F-004 stamp: {R['f004']}")

    # F-009
    L.set_combo_data(panel.instr, "SS"); L.set_combo_data(panel.paper, "A4"); L.set_combo_data(panel.mode, "flat"); L.pump(600)
    R["f009"] = {"use_instr_visible": panel.use_instr_margins.isVisible(), "checked": panel.use_instr_margins.isChecked(),
                 "margins": {k: (v.value(), v.isEnabled()) for k, v in panel.margins.items()}, "tip": panel.use_instr_margins.toolTip()[:200]}
    L.log(f"  F-009 SS: {R['f009']}")
    L.grab(panel.use_instr_margins.parentWidget(), OUT / "f009-SS-margins-group.png")
    L.set_combo_data(panel.instr, "i1"); L.set_combo_data(panel.mode, "clip"); L.pump(500)

    # F-011
    L.set_combo_data(panel.clip_content_mode, "text"); L.pump(200)
    panel.clip_text.setPlainText("my own clip text"); L.pump(300)
    ns = len(watcher.seen)
    watcher.expect("example table", "OK")
    L.set_combo_data(panel.clip_content_mode, "example"); L.pump(800); watcher.clear()
    R["f011"] = {"dialogs": [(d.get("class"), (d.get("text") or "")[:120], d.get("buttons"), d.get("answer")) for d in watcher.seen[ns:]],
                 "text_after": panel.clip_text.toPlainText()[:80], "mode_after": panel.clip_content_mode.currentData()}
    L.log(f"  F-011: {R['f011']}")
    L.set_combo_data(panel.clip_content_mode, "notes"); L.pump(200)

    # F-026 at 1280x800
    win.resize(1280, 800); L.pump(1500)
    R["f026"] = {"size": (win.width(), win.height()), "clipped_margin_panel": clipped_labels(tab._margin_panel), "clipped_info_panel": clipped_labels(tab._layout_info_panel),
                 "clipped_left_pane": clipped_labels(tab._manual_panel)[:8] if hasattr(tab, "_manual_panel") else None}
    L.log(f"  F-026 1280x800: {R['f026']}")
    L.grab(win, OUT / "f026-1280x800.png")
    win.resize(1700, 1050); L.pump(1000)

    # Guided -L / -P
    L.click(tab._guided_btn); L.pump(400)
    L.set_combo_data(tab._instr_combo, "i1"); L.set_combo_data(tab._paper_combo, "A4"); L.set_spin(tab._pages_spin, 1); L.pump(400)
    import re
    def head():
        return re.sub(r"<[^>]+>", "", tab._patch_count_lbl.text())
    h0 = head()
    L.set_check(tab._lb_check, True); L.pump(500); h1 = head()
    L.set_check(tab._lb_check, False); L.set_check(tab._nsl_check, True); L.pump(500); h2 = head()
    L.set_check(tab._nsl_check, False); L.pump(300)
    R["guided_boxes"] = {"base": h0, "L_on": h1, "P_on": h2, "lb_text": tab._lb_check.text(), "nsl_text": tab._nsl_check.text(), "guided_info": tab._guided_info_lbl.text()[:200]}
    L.log(f"  GUIDED boxes: {R['guided_boxes']}")

    R["unexpected"] = watcher.unexpected; R["serious"] = L.serious_since(0)
    L.save_json(R, L.LOGS / "r08_results.json")
    L.log(f"unexpected={[(u.get('title'), (u.get('text') or '')[:120]) for u in watcher.unexpected]} serious={L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
