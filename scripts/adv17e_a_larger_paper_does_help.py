#!/usr/bin/env python3
"""Adversary 17e / P1: "A larger paper does not help" — driven on screen.

The message that round 4's fix introduced says, in twelve languages:

    No bottom margin this sheet allows will clear it: "Bottom" under
    "Margins (mm)" stops at 60 mm and even that leaves the text in the
    patches. Make the sheet text smaller under "Sheet text". A larger paper
    does not help: the text is printed from the paper edge, so it stays
    where it is.

The last clause is a claim about the PATCHES, not the text, and nothing asked
the sheet about it. A headless sweep over the panel's own functions found four
states where a larger paper clears the collision the message says it cannot.
This drives them in a real window.
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

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
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
    return [m for m in msgs if "runs into the patches" in m
            or "run into the patches" in m]


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17e-"))
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
    onscreen = bool(win.isVisible())
    print(f"    window on screen: {onscreen}", flush=True)
    win._tabs.setCurrentWidget(win._tab_chart); tab = win._tab_chart
    pump(app, 800); tab._user_switch_mode("manual"); pump(app, 1500)
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    panel = tab._manual_layout_panel
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    panel.chart_text.setText("test")
    pump(app, 300)

    def refresh():
        pump(app, 240); tab._update_margin_inspector(); pump(app, 360)
        return said(tab)

    box_max = panel.margins["b"].maximum()
    papers = [(panel.paper.itemText(k), panel.paper.itemData(k))
              for k in range(panel.paper.count())]
    print(f"    margin box max = {box_max}", flush=True)
    print(f"    papers = {[p[1] for p in papers]}", flush=True)
    res = {"window_on_screen": onscreen, "margin_box_max": box_max,
           "papers": [p[1] for p in papers], "cases": []}

    NOTE = "No bottom margin this sheet allows will clear it"
    # the four states the headless sweep named, plus a control
    # (layout mode, bottom margin, Size pt, base paper) — the states the
    # headless sweep named, driven here in the real window.
    CASES = [("area_first", 59.5, 72.0, "A4"),
             ("area_first", 60.0, 72.0, "Letter"),
             ("patch_first", 60.0, 72.0, "Letter"),
             ("area_first", 45.0, 72.0, "A4"),
             # …and states where the sentence is expected to STAND, which is
             # where the gate costs the most: every larger paper is tried.
             ("area_first", 30.0, 72.0, "127x178"),
             ("area_first", 20.0, 72.0, "4x6"),
             ("patch_first", 30.0, 72.0, "4x6")]
    panel.stamp_command.setChecked(True)   # the second line
    j = panel.layout_mode.findData("area_first")
    panel.layout_mode.setCurrentIndex(j); pump(app, 400)
    for mode, mb, size, base in CASES:
        panel.paper.setCurrentIndex(panel.paper.findData(base))
        panel.layout_mode.setCurrentIndex(panel.layout_mode.findData(mode))
        panel.margins["b"].setValue(mb)
        panel.chart_text_size.setValue(size)
        msgs = refresh()
        m0 = msgs[0] if msgs else None
        row = {"mode": mode, "margin_b": mb, "size_pt": size, "base_paper": base,
               "paper": panel.paper.currentData(),
               "warns": bool(msgs), "note_fires": bool(m0 and NOTE in m0),
               "message": m0, "unfilled_placeholder": bool(m0 and "{" in m0)}
        row["denies_a_larger_paper"] = bool(
            m0 and "larger paper does not help" in m0)
        named = re.search(r"stops at ([0-9.,]+) mm", m0 or "")
        row["named_ceiling_mm"] = (float(named.group(1).replace(",", "."))
                                   if named else None)
        if row["note_fires"]:
            # WHAT THE NOTICE PASS COSTS IN THIS BRANCH, which is the only one
            # that asks the papers.
            t0 = time.monotonic()
            for _ in range(5):
                tab._engine_text_notes()
            row["notice_pass_ms"] = round(
                (time.monotonic() - t0) * 1000.0 / 5.0, 1)
            print(f"    notice pass here: {row['notice_pass_ms']} ms",
                  flush=True)
            capture_window(win, out / f"note-{base}-{mode}-mb{mb}-{size:.0f}pt.png")
            clears = {}
            here = panel.paper.currentData()
            for _lab, code in papers:
                if code == here:
                    continue
                k = panel.paper.findData(code)
                panel.paper.setCurrentIndex(k)
                got = refresh()
                clears[code] = (not got)
                if not got:
                    capture_window(
                        win, out / f"CLEARED-{base}-{mode}-mb{mb}-{size:.0f}pt-{code}.png")
            panel.paper.setCurrentIndex(panel.paper.findData(here))
            refresh()
            row["papers_that_clear_it"] = sorted(
                c for c, ok in clears.items() if ok)
            print(f"    NOTE base={base} mode={mode} mb={mb} size={size} -> "
                  f"papers that CLEAR it: {row['papers_that_clear_it']}; "
                  f"the message denies a larger paper: "
                  f"{row['denies_a_larger_paper']}", flush=True)
        res["cases"].append(row)

    (out / "adv17e-a-larger-paper.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    written", flush=True)
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
