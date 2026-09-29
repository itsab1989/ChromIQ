#!/usr/bin/env python3
"""D09 (B10): one German pass, screenshots only plus an automatic check for
labels, check boxes and buttons whose text needs more width than they have
(clipped or elided). 1280x800 and 1700x1050, Guided and Manual (engine on,
groups expanded), plus the Preferences Chart Layout and Instrument Limits tabs."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cc_lib as L  # noqa: E402
from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDialogButtonBox, QLabel,  # noqa: E402
                             QPushButton, QRadioButton)

OUT = L.SHOTS / "B10-lang-de"
R: dict = {}


def clipped(root) -> list:
    out = []
    for w in root.findChildren((QLabel, QCheckBox, QPushButton, QRadioButton)):
        if not w.isVisible() or not w.text().strip() or "<" in w.text():
            continue
        if isinstance(w, QLabel) and w.wordWrap():
            continue
        need = w.fontMetrics().horizontalAdvance(w.text().replace("&", "")) + (24 if not isinstance(w, QLabel) else 2)
        if need > w.width() + 2:
            out.append((type(w).__name__, w.text()[:70], need, w.width()))
    return out


def main() -> int:
    app, settings = L.build_app(lang="de")
    watcher = L.ModalWatcher(app)
    win = L.build_window(app, settings)
    L.open_project(win, settings, "A1-EngineVsPrinttarg")
    tab = L.goto_chart_tab(win)
    for w_, h_ in ((1280, 800), (1700, 1050)):
        win.resize(w_, h_); L.pump(1000)
        L.click(tab._guided_btn); L.pump(600)
        L.grab(win, OUT / f"de-{w_}-guided.png")
        R[f"clipped-guided-{w_}"] = clipped(tab._guided_panel)
        L.click(tab._manual_btn); L.pump(600)
        if not tab._manual_engine_check.isChecked():
            L.set_check(tab._manual_engine_check, True)
        L.grab(win, OUT / f"de-{w_}-manual-top.png")
        R[f"clipped-manual-{w_}"] = clipped(tab._manual_panel)
        R[f"clipped-frames-{w_}"] = clipped(tab._margin_panel) + clipped(tab._layout_info_panel)
        # scroll the left pane down to the layout panel and shoot again
        sa = tab._manual_panel.parentWidget()
        while sa is not None and not hasattr(sa, "verticalScrollBar"):
            sa = sa.parentWidget()
        if sa is not None:
            sb = sa.verticalScrollBar()
            for i, frac in enumerate((0.35, 0.7, 1.0)):
                sb.setValue(int(sb.maximum() * frac)); L.pump(400)
                L.grab(win, OUT / f"de-{w_}-manual-scroll{i + 1}.png")
        L.log(f"{w_}: clipped guided={len(R[f'clipped-guided-{w_}'])} manual={len(R[f'clipped-manual-{w_}'])} frames={len(R[f'clipped-frames-{w_}'])}")
    # Preferences tabs in German
    state = {}
    watcher.ignore.append("SettingsDialog")

    def tick():
        dlg = app.activeModalWidget()
        if dlg is None or type(dlg).__name__ != "SettingsDialog":
            QTimer.singleShot(150, tick); return
        try:
            tabs = dlg._tabs
            state["tab_names"] = [tabs.tabText(i) for i in range(tabs.count())]
            for i in range(tabs.count()):
                tabs.setCurrentIndex(i); L.pump(500)
                name = tabs.tabText(i).replace("/", "-").replace(" ", "_")
                L.grab(dlg, OUT / f"de-prefs-{i:02d}-{name}.png")
                state[f"clipped-prefs-{name}"] = clipped(dlg)[:30]
            bb = dlg.findChild(QDialogButtonBox); bb.button(QDialogButtonBox.StandardButton.Cancel).click()
        except Exception as e:  # noqa: BLE001
            state["err"] = repr(e); dlg.reject()
    QTimer.singleShot(200, tick)
    win._open_settings(); L.pump(800)
    watcher.ignore.remove("SettingsDialog")
    R["prefs"] = state
    L.save_json(R, L.LOGS / "d09_results.json")
    L.log(f"prefs tabs: {state.get('tab_names')} clipped per tab: { {k: len(v) for k, v in state.items() if k.startswith('clipped')} }")
    L.log(f"unexpected: {[(d['class'], d['title']) for d in watcher.unexpected]} serious: {L.serious_since(0)}")
    win.close(); L.pump(300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
