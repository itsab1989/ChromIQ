#!/usr/bin/env python3
"""Adversary 17: hunt the DANGEROUS direction of the new bottom-text check.

The fix of 2026-09-14 made the height warning ask where the patches really
stop. This looks for the other error: a sheet where the panel is QUIET and the
ink collides anyway.

States swept, all on Knut's own CR30 Letter preset with a real window:

* layout mode: "Prioritise chart area" (area_first) and "Prioritise patch size"
  (patch-first) -- the check is gated on ``r.layout_mode == "area_first"``;
* one bottom line and two (Sheet text + the stamp line);
* typed text sizes that do not shrink (Knut: *"Manually defined size value does
  not shrink"*).

The arbiter is the INK on the app's own rendered TIFF, read with the two-render
difference from `drive_182_knut_bottom_text_height`.
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

PRESET = "__chromiq_knut_cr30_letter_792p_2pages_portrait_w11_0mm_hexagonal_straight__"
TEXT = "test-{project}-page {page}-{date}-{paper}-{patchcount} patches"


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17bt-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    QDialog.exec = lambda self: 1                 # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show(); win.raise_()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window on screen: {win.isVisible()}", flush=True)

    combo = tab._preset_combo
    i = combo.findData(PRESET)
    assert i >= 0, "his preset is not in the dropdown"
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    panel = tab._manual_layout_panel
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False)
        pump(app, 400)
    panel.chart_text.setText(TEXT)
    panel.margins["b"].setValue(11.0)
    pump(app, 500)

    ti1 = None
    for attr in ("_preset_ti1_path", "_builtin_ti1_path"):
        v = getattr(tab, attr, None)
        if v and Path(v).is_file():
            ti1 = Path(v); break
    assert ti1 is not None, "no .ti1 to render from"

    rows = []
    for mode_label, mode_is_area in (("area_first", True), ("patch_first", False)):
        # THE CONTROL ON SCREEN, not the dataclass field: the panel owns it.
        want = "area_first" if mode_is_area else "patch_first"
        j = panel.layout_mode.findData(want)
        assert j >= 0, want
        panel.layout_mode.setCurrentIndex(j)
        pump(app, 700)
        for stamp in (False, True):
            panel.stamp_command.setChecked(stamp)
            pump(app, 400)
            for pt in (0.0, 7.0, 14.0, 28.0, 48.0):
                panel.chart_text_size.setValue(float(pt))
                pump(app, 600)
                tab._update_margin_inspector()
                pump(app, 800)
                r = panel.get_recipe()
                if r.layout_mode != ("area_first" if mode_is_area else r.layout_mode):
                    pass
                said = on_screen(tab)
                ink = text_ink_mm(r, ti1, f"{mode_label}-{int(stamp)}-{pt:g}")
                gap = ink.get("gap_patches_to_text_mm")
                row = {"layout_mode": r.layout_mode, "asked": mode_label,
                       "two_lines": stamp, "typed_size_pt": pt,
                       "gap_patches_to_text_mm": gap,
                       "text_top_up_mm": ink.get("text_top_up_mm"),
                       "text_bottom_up_mm": ink.get("text_bottom_up_mm"),
                       "patch_bottom_up_mm": ink.get("patch_bottom_up_mm"),
                       "paper_h_mm": ink.get("paper_h_mm"),
                       "height_warnings": said["height"],
                       "width_warnings": said["width"]}
                rows.append(row)
                print(f"    {r.layout_mode:11s} lines={1 + int(stamp)} "
                      f"pt={pt:5.1f}  patches->{ink.get('patch_bottom_up_mm')} "
                      f"text {ink.get('text_top_up_mm')}.."
                      f"{ink.get('text_bottom_up_mm')}  gap={gap}  "
                      f"warn={len(said['height'])}", flush=True)

    ok, why = capture_window(win, out / "01-create-chart-sweep.png")
    print(f"    photo: {'ok' if ok else 'REFUSED ' + str(why)}", flush=True)

    def collides(r):
        g = r["gap_patches_to_text_mm"]
        return g is not None and g < 0

    quiet_and_colliding = [r for r in rows
                           if collides(r) and not r["height_warnings"]]
    loud_and_clear = [r for r in rows
                      if r["height_warnings"] and not collides(r)]
    verdicts = {
        "no sheet collides while the panel is quiet": not quiet_and_colliding,
        "no sheet is warned about while it has a clear gap": not loud_and_clear,
        "at least one state really collides": any(collides(r) for r in rows),
    }
    (out / "quiet-and-colliding.json").write_text(json.dumps(
        {"rows": rows, "verdicts": verdicts,
         "quiet_and_colliding": quiet_and_colliding,
         "loud_and_clear": loud_and_clear,
         "photo": "01-create-chart-sweep.png" if ok else f"REFUSED {why}",
         "locked": session_is_locked()},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(verdicts, indent=2), flush=True)
    print("QUIET AND COLLIDING:", json.dumps(quiet_and_colliding, indent=2))
    win.close(); pump(app, 400)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
