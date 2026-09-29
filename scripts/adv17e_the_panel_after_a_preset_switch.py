#!/usr/bin/env python3
"""Adversary 17e / P7: the bottom-text notice across a preset switch.

An angle no round has used. Put the panel into a state where the bottom-text
warning is up, switch to another preset (which replaces paper, margins, the
layout mode and the Sheet text frame in one go), and ask whether what is on
screen afterwards describes the chart that is now loaded: is the message the
old one, is it consistent with the new recipe's own numbers, and does it come
back correctly when the first preset is chosen again?
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window                      # noqa: E402

A = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
     "_w11_0mm_hexagonal_straight__")


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents(); time.sleep(0.01)


def said(tab):
    panel = getattr(tab, "_margin_panel", None)
    last = getattr(panel, "_last_status", None) if panel is not None else None
    msgs = [m for m in ((last[1].get("overlap_warnings") or []) if last else [])
            if "along the bottom" in m]
    return [m for m in msgs if "into the patches" in m]


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17e7-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("margin_violation_notify", True)):
        settings.set(k, v)
    assert settings.get("custom_output_path", "") == str(work)
    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings); win.resize(1620, 1060)
    win.show(); win.raise_(); pump(app, 2500)
    print(f"    window on screen: {bool(win.isVisible())}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    combo = tab._preset_combo

    def load(key):
        i = combo.findData(key); assert i >= 0, key
        combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
        for _ in range(300):
            pump(app, 100)
            if getattr(tab, "_margin_ti2", None):
                break
        pump(app, 600)

    load(A)
    panel = tab._manual_layout_panel
    panel.use_instr_margins.setChecked(False); pump(app, 400)
    panel.chart_text.setText("test"); panel.stamp_command.setChecked(True)
    panel.chart_text_size.setValue(72.0); panel.margins["b"].setValue(20.0)
    pump(app, 300); tab._update_margin_inspector(); pump(app, 500)
    before = said(tab)
    print(f"    warning up on {A[-30:]}: {bool(before)}", flush=True)
    capture_window(win, out / "P7-before-the-switch.png")

    # every other preset the pulldown offers, one at a time
    rows = []
    keys = [combo.itemData(i) for i in range(combo.count())
            if isinstance(combo.itemData(i), str)
            and combo.itemData(i).startswith("__chromiq_")]
    for k in keys[:10]:
        if k == A:
            continue
        load(k)
        after = said(tab)
        r = tab._current_layout_recipe()
        # what the message says against what the recipe now IS
        m = after[0] if after else ""
        edge = re.search(r"printed ([0-9.]+) mm up", m)
        row = {"preset": k, "warns": bool(after),
               "paper_now": r.paper, "size_pt_now": panel.chart_text_size.value(),
               "message_edge_mm": (float(edge.group(1)) if edge else None),
               "same_text_as_before": bool(after and before
                                           and after[0] == before[0])}
        rows.append(row)
        print(f"    {k[-34:]:34s} paper={r.paper:9s} "
              f"size={panel.chart_text_size.value():5.1f} warns={bool(after)} "
              f"identical_to_the_old_message={row['same_text_as_before']}",
              flush=True)
    load(A)
    panel.use_instr_margins.setChecked(False); pump(app, 300)
    panel.chart_text.setText("test"); panel.stamp_command.setChecked(True)
    panel.chart_text_size.setValue(72.0); panel.margins["b"].setValue(20.0)
    pump(app, 300); tab._update_margin_inspector(); pump(app, 500)
    back = said(tab)
    same = bool(back and before and back[0] == before[0])
    print(f"    back on the first preset, the same message returns: {same}",
          flush=True)
    capture_window(win, out / "P7-back-again.png")
    (out / "adv17e-preset-switch.json").write_text(json.dumps(
        {"before": before, "rows": rows, "returns_identical": same},
        indent=2, ensure_ascii=False), encoding="utf-8")
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
