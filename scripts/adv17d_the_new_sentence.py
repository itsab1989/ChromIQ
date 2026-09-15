#!/usr/bin/env python3
"""Adversary 17d: the sentence round 3 left behind, and the box it names.

`_no_margin_clears_note` says, in thirteen languages:

    Raising "Bottom" cannot clear this one on its own: the box stops at 60 mm
    and even that leaves the text in the patches. Make the sheet text smaller
    under "Sheet text", or print the chart on a larger paper.

Three clauses, none of them asked of the sheet:

  P1  "print the chart on a larger paper" -- does a larger paper clear it at
      the same settings?
  P2  "make the sheet text smaller" -- is Size always typed (so there is
      something to make smaller), or can this fire on "auto" at the floor?
  P3  the number the message's MAIN clause names when the note fires, and
      whether it is the largest rise the box holds. At margin_b = 60 the
      ceiling arithmetic is `max(0, 60 - 60)` = 0.

And a fourth thing nobody has asked at all:

  P4  "Use instrument margins" LOCKS the four margin boxes read-only
      (`layout_options_panel` line 3162, `setEnabled(not on)`). Is the
      "Raise 'Bottom' under 'Margins (mm)'" remedy still offered there?
"""
from __future__ import annotations

import json
import os
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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17d-"))
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
    panel.chart_text.setText("test-{project}-page {page}-{paper}")
    pump(app, 300)
    print(f"    margins[b]: min={panel.margins['b'].minimum()} "
          f"max={panel.margins['b'].maximum()} "
          f"step={panel.margins['b'].singleStep()}", flush=True)
    papers = [(panel.paper.itemText(k), panel.paper.itemData(k))
              for k in range(panel.paper.count())]
    print(f"    papers: {[p[0] for p in papers]}", flush=True)

    def refresh():
        pump(app, 260); tab._update_margin_inspector(); pump(app, 380)
        return said(tab)

    results = {"window_on_screen": onscreen,
               "margin_box_max": panel.margins["b"].maximum(),
               "papers": [p[0] for p in papers]}

    # ---------------- P3 + P1 + P2 : the note, where it fires -------------
    note_key = "cannot clear this one on its own"
    rows = []
    cur_paper = panel.paper.currentText()
    for mode in ("area_first", "patch_first"):
        j = panel.layout_mode.findData(mode)
        panel.layout_mode.setCurrentIndex(j)
        for mb in (6.0, 20.0, 40.0, 55.0, 59.5, 60.0):
            panel.margins["b"].setValue(mb)
            for stamp in (False, True):
                panel.stamp_command.setChecked(stamp)
                for pt in (0.0, 48.0, 56.0, 64.0, 72.0):
                    panel.chart_text_size.setValue(pt)
                    msgs = refresh()
                    if not msgs or note_key not in msgs[0]:
                        continue
                    m = msgs[0]
                    # the number the MAIN clause names
                    import re
                    n = re.search(r"by about ([0-9.,]+) mm", m)
                    named = float(n.group(1).replace(",", ".")) if n else None
                    row = {"mode": mode, "margin_b": mb,
                           "lines": 1 + int(stamp),
                           "size_pt": ("auto" if pt == 0 else pt),
                           "named_rise_mm": named,
                           "largest_rise_the_box_holds":
                               round(max(0.0, 60.0 - mb), 1),
                           "message": m[:400]}
                    # ---- P1: does a LARGER PAPER clear it? ----
                    bigger = {}
                    for label, data in papers:
                        if label == cur_paper:
                            continue
                        panel.paper.setCurrentText(label)
                        got = refresh()
                        bigger[label] = (not got)
                        panel.paper.setCurrentText(cur_paper)
                        refresh()
                    row["a_larger_paper_clears_it"] = bigger
                    rows.append(row)
                    print(f"    NOTE {mode:11s} mb={mb:4.1f} "
                          f"lines={1+int(stamp)} size={row['size_pt']} "
                          f"-> named {named} (box holds "
                          f"{row['largest_rise_the_box_holds']}) "
                          f"papers_clearing="
                          f"{[k for k,v in bigger.items() if v]}", flush=True)
    results["note_states"] = rows

    # ---------------- P4 : the locked box ---------------------------------
    panel.margins["b"].setValue(6.0)
    panel.chart_text_size.setValue(40.0)
    panel.stamp_command.setChecked(False)
    p4 = []
    for mode in ("area_first", "patch_first"):
        j = panel.layout_mode.findData(mode)
        panel.layout_mode.setCurrentIndex(j)
        for lock in (False, True):
            panel.use_instr_margins.setChecked(lock)
            pump(app, 500)
            msgs = refresh()
            p4.append({
                "mode": mode, "use_instrument_margins": lock,
                "bottom_box_enabled": panel.margins["b"].isEnabled(),
                "bottom_box_value": panel.margins["b"].value(),
                "warning": (msgs[0][:300] if msgs else None),
                "names_raise_bottom": bool(
                    msgs and "Margins (mm)" in msgs[0]),
            })
            print(f"    P4 {mode:11s} lock={lock} "
                  f"box_enabled={panel.margins['b'].isEnabled()} "
                  f"warns={bool(msgs)} "
                  f"names_raise_bottom={bool(msgs and 'Margins (mm)' in msgs[0])}",
                  flush=True)
            if lock and msgs and "Margins (mm)" in msgs[0]:
                capture_window(win, out / f"P4-locked-{mode}.png")
    results["p4_locked_margins"] = p4
    panel.use_instr_margins.setChecked(False); pump(app, 400)

    (out / "adv17d-the-new-sentence.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("    written", flush=True)
    win.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
