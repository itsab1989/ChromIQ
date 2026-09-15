#!/usr/bin/env python3
"""Adversary 17b: is the lifted patch-first height check ever WRONG?

Round 1 measured three silent collisions in patch-first and the gate on
`_labels_can_overflow` was lifted in response. This hunts the other direction,
which is the risky half: a sheet the panel WARNS about that has real clear
paper under the text.

The check measures the line's BOX (`sheet_text_line_mm`, the larger of the
4.2 mm pitch and the face's ascent + descent), so a little ink clearance can
still warn and that is accepted. The axes below are the ones that make the box
and the ink differ MOST, and the arbiter is the ink on the app's own rendered
TIFFs:

* text with no descenders and no tall ascenders ("access the scanner") against
  text full of them ("Jpqgy |ÄÖÜ typography"), at the same typed size;
* the ruler helper markers on and off, which move the anchor the block hangs
  from;
* the clip border on and off;
* one bottom line and two;
* two instruments and two papers.

Everything on screen, in a real window, with the panel read from what the
window is SHOWING.
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
from onscreen_capture import capture_window, session_is_locked   # noqa: E402
from drive_182_knut_bottom_text_height import (on_screen, pump,  # noqa: E402
                                               text_ink_mm)

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")
FLAT = "access the scanner acme"          # no descenders, no tall ascenders
TALL = "Jpqgy typography ÄÖÜ"             # ascenders and descenders


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17bpf-"))
    settings = AppSettings()
    for k, v in (("custom_output_path", str(work)),
                 ("use_chromiq_layout_engine", True),
                 ("restore_last_session", False), ("appearance", "dark"),
                 ("margin_inspector_show", True),
                 ("margin_violation_notify", True)):
        settings.set(k, v)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

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
    print(f"    window on screen: {win.isVisible()} locked={session_is_locked()}",
          flush=True)
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
    j = panel.layout_mode.findData("patch_first")
    panel.layout_mode.setCurrentIndex(j)
    panel.margins["b"].setValue(11.0)
    pump(app, 600)

    ti1 = None
    for attr in ("_preset_ti1_path", "_builtin_ti1_path"):
        v = getattr(tab, attr, None)
        if v and Path(v).is_file():
            ti1 = Path(v); break
    assert ti1 is not None, "no .ti1 to render from"

    rows = []
    n = 0
    for text_label, text in (("flat", FLAT), ("tall", TALL)):
        for markers in (False, True):
            for stamp in (False, True):
                for pt in (14.0, 24.0, 40.0):
                    n += 1
                    panel.chart_text.setText(text)
                    panel.helper_markers_cb.setChecked(markers)
                    if markers:
                        panel.helper_marker_edge.setValue(4.0)
                        panel.helper_marker_len.setValue(2.0)
                        panel.helper_markers_top_bottom.setChecked(True)
                    panel.stamp_command.setChecked(stamp)
                    panel.chart_text_size.setValue(pt)
                    pump(app, 500)
                    tab._update_margin_inspector(); pump(app, 700)
                    r = panel.get_recipe()
                    said = on_screen(tab)
                    ink = text_ink_mm(r, ti1,
                                      f"pf-{text_label}-{int(markers)}-{int(stamp)}-{pt:g}")
                    gap = ink.get("gap_patches_to_text_mm")
                    row = {"layout_mode": r.layout_mode, "text": text_label,
                           "markers": markers, "two_lines": stamp,
                           "typed_size_pt": pt,
                           "gap_patches_to_text_mm": gap,
                           "text_top_up_mm": ink.get("text_top_up_mm"),
                           "text_bottom_up_mm": ink.get("text_bottom_up_mm"),
                           "patch_bottom_up_mm": ink.get("patch_bottom_up_mm"),
                           "height_warnings": said["height"]}
                    rows.append(row)
                    print(f"    [{n:2d}] {text_label:4s} mk={int(markers)} "
                          f"lines={1+int(stamp)} {pt:4.0f}pt  "
                          f"patches->{ink.get('patch_bottom_up_mm')} "
                          f"text {ink.get('text_top_up_mm')}.."
                          f"{ink.get('text_bottom_up_mm')}  gap={gap}  "
                          f"warn={len(said['height'])}", flush=True)

    ok, why = capture_window(win, out / "03-patch-first-sweep.png")
    print(f"    photo: {'ok' if ok else 'REFUSED ' + str(why)}", flush=True)

    def collides(x):
        g = x["gap_patches_to_text_mm"]
        return g is not None and g < 0
    quiet_and_colliding = [x for x in rows if collides(x) and not x["height_warnings"]]
    # a warning with MORE than 2 mm of real ink clearance is beyond the slack
    # the box model is allowed
    loud_and_clear = [x for x in rows
                      if x["height_warnings"]
                      and (x["gap_patches_to_text_mm"] or -1) > 2.0]
    verdicts = {
        "no patch-first sheet collides while the panel is quiet":
            not quiet_and_colliding,
        "no patch-first sheet is warned about with more than 2 mm of ink clear":
            not loud_and_clear,
        "at least one state really collides": any(collides(x) for x in rows),
    }
    (out / "patch-first-false-warning.json").write_text(json.dumps(
        {"rows": rows, "verdicts": verdicts,
         "quiet_and_colliding": quiet_and_colliding,
         "loud_and_clear": loud_and_clear,
         "photo": "03-patch-first-sweep.png" if ok else f"REFUSED {why}",
         "locked": session_is_locked()}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps(verdicts, indent=2), flush=True)
    for x in loud_and_clear:
        print("   LOUD AND CLEAR:", {k: x[k] for k in
                                     ("text", "markers", "two_lines",
                                      "typed_size_pt",
                                      "gap_patches_to_text_mm")}, flush=True)
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
