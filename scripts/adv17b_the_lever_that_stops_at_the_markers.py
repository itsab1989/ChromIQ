#!/usr/bin/env python3
"""Adversary 17b: "lowering B buys the same room" is false above the markers.

`_bottom_lever_note` picks its sentence from ONE comparison::

    if anchor_mm > typed_b_mm + 0.05:   -> "it will not help"
    else:                               -> "it buys the same room"

The docstring's own measurement only ever typed "B" at or BELOW the ruler
helper markers' reach (7, 5, 4, 3, 2, 1, 0 against a 7.0 mm reach), which is
the branch that is right. Type "B" ABOVE the reach and the anchor equals the
typed value, so the second sentence is chosen -- and lowering "B" then buys
exactly ``B - reach`` millimetres and stops dead, however much room is short.

This sweeps "B" down one step at a time in a real window, on a sheet whose
bottom text really does run into the patches, and records the anchor, the
overlap the panel reports, and whether the warning is still up.
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
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PRESET = ("__chromiq_knut_cr30_letter_792p_2pages_portrait"
          "_w11_0mm_hexagonal_straight__")
TEXT = "test-{project}-page {page}-{date}-{paper}-{patchcount} patches"
LEAVES = re.compile(r"leaving ([0-9.]+) mm")
RISE = re.compile(r"“Bottom”[^.]*?by about ([0-9.]+) mm")


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
    out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17b2-"))
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
    panel.chart_text.setText(TEXT)
    j = panel.layout_mode.findData("area_first")
    panel.layout_mode.setCurrentIndex(j)
    panel.stamp_command.setChecked(False)
    panel.chart_text_size.setValue(24.0)
    panel.helper_markers_cb.setChecked(True)
    panel.helper_marker_edge.setValue(4.0)
    panel.helper_marker_len.setValue(2.0)
    panel.helper_markers_top_bottom.setChecked(True)
    panel.helper_markers_sides.setChecked(True)
    panel.margins["b"].setValue(8.0)
    pump(app, 600)

    from workflow import text_edge_fit as tef
    rows = []
    for b in (12.0, 11.0, 10.0, 9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0, 0.0):
        panel.text_edge.setValue(b)
        pump(app, 400)
        tab._update_margin_inspector()
        pump(app, 600)
        r = panel.get_recipe()
        anchor = tef.sheet_text_bottom_mm(
            r.effective_text_edge_mm, r.helper_markers, r.helper_marker_edge_mm,
            r.helper_marker_len_mm, r.helper_markers_top_bottom)
        msgs = said(tab)
        m = msgs[0] if msgs else ""
        rows.append({"B_typed": b,
                     "effective_B": r.effective_text_edge_mm,
                     "anchor_mm": round(anchor, 2),
                     "warns": bool(msgs),
                     "leaves_mm": (float(LEAVES.search(m).group(1))
                                   if LEAVES.search(m) else None),
                     "rise_named_mm": (float(RISE.search(m).group(1))
                                       if RISE.search(m) else None),
                     "sentence": ("will not help here" if "will not help here" in m
                                  else "buys the same room" if "moves the text down" in m
                                  else None)})
        print(f"    B={b:4.1f} anchor={anchor:5.2f} warns={bool(msgs)} "
              f"leaves={rows[-1]['leaves_mm']} sentence={rows[-1]['sentence']}",
              flush=True)

    ok, why = capture_window(win, out / "02-the-lever-stops-at-the-markers.png")
    print(f"    photo: {'ok' if ok else 'REFUSED ' + str(why)}", flush=True)
    # The verdict: on every row whose sentence is "buys the same room", pulling
    # the lever all the way down must remove the warning.
    offered = [r for r in rows if r["sentence"] == "buys the same room"]
    bottom = rows[-1]
    verdict = {
        "the lever was offered at": [r["B_typed"] for r in offered],
        "with the lever pulled all the way down (B = 0) the warning is":
            ("still up" if bottom["warns"] else "gone"),
        "the offer is honest": not (offered and bottom["warns"]),
    }
    (out / "the-lever-stops-at-the-markers.json").write_text(json.dumps(
        {"rows": rows, "verdict": verdict,
         "photo": "02-the-lever-stops-at-the-markers.png" if ok else f"REFUSED {why}",
         "locked": session_is_locked()}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps(verdict, indent=2, ensure_ascii=False), flush=True)
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
