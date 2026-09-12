#!/usr/bin/env python3
"""SYMMETRY AUDIT — what the REAL window says about each of the four sides.

Drives the real ChromIQ window, on screen, against a sandboxed settings file, a
sandboxed presets folder and a sandboxed working folder. For each state it
records what the "Measured from Preview" frame's red message field says, so the
claim "the four sides are ruled by the same type of rules" can be checked
against what a user is actually told rather than against the code.

The ink itself is measured off the written TIFF at the sheet's own resolution
by `/tmp/chromiq-symmetry-proof/measure.py`; this half is the SCREEN.

Usage:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-symmetry.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-symmetry-presets
    python scripts/drive_182_four_side_symmetry.py --out DIR
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

WORK = Path("/tmp/chromiq-symmetry-work")
TARGET = "SymmetryAudit"

modals: list[dict] = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app):
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:
                    pass
        modals.append({"title": w.windowTitle(), "text": text[:300]})
        print(f"    !! modal: {w.windowTitle()!r} -> closing")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-symmetry-proof/onscreen")
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"screen_locked_at_start": locked, "modals": modals, "steps": []}
    print(f"00 screen locked: {locked}")

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox ok: {os.environ['CHROMIQ_SETTINGS_FILE']} / {WORK}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1660, 1080)
    win.show()
    pump(app, 1500)
    install_modal_watchdog(app)

    tab = win._tab_chart
    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 700)
    tab._manual_target_name_edit.setText(TARGET)
    pump(app, 700)

    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 600)

    from workflow.layout_engine.presets import LayoutRecipe

    BASE = dict(instrument="i1", paper="A4", dpi=200,
                layout_mode="area_first", use_instrument_margins=False,
                clip_border=False, clip_content_mode="off",
                margin_top=20.0, margin_right=20.0,
                margin_bottom=30.0, margin_left=20.0,
                text_edge_top_mm=8.0, text_edge_mm=4.0, text_edge_clip_mm=4.0,
                show_strip_indicators=True, show_row_indicators=True,
                chart_text="", stamp_command=False,
                chart_text_size_mm=0.0, clip_text_size_mm=0.0)

    def apply(**over):
        r = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(r)
        pump(app, 900)
        tab._update_margin_inspector()
        pump(app, 500)

    def field_text() -> str:
        """The 'Measured from Preview' frame's own red message field."""
        mp = getattr(tab, "_margin_panel", None)
        if mp is None:
            return "<no margin panel>"
        try:
            return str(mp.status_message())
        except Exception as exc:                                  # noqa: BLE001
            return f"<raised {exc!r}>"

    def snap(name: str, comment: str, shot: bool = False) -> dict:
        pump(app, 700)
        try:
            warns, over = type(tab)._engine_text_notes(tab)
        except Exception as exc:                                  # noqa: BLE001
            warns, over = [f"<raised {exc!r}>"], []
        r = tab._current_layout_recipe()
        st = {"step": name, "comment": comment,
              "recipe_as_the_app_reads_it": {
                  "margin_top": r.margin_top, "margin_right": r.margin_right,
                  "margin_bottom": r.margin_bottom, "margin_left": r.margin_left,
                  "T": r.text_edge_top_mm, "B": r.text_edge_mm,
                  "Clip": r.text_edge_clip_mm,
                  "layout_mode": r.layout_mode,
                  "chart_text": (r.chart_text or "")[:24],
                  "chart_text_size_pt": round(r.chart_text_size_mm * 72 / 25.4, 2),
                  "clip_border": bool(r.clip_border),
                  "clip_border_width_mm": r.clip_border_width_mm,
                  "clip_content_mode": r.clip_content_mode,
                  "clip_text_size_pt": round(r.clip_text_size_mm * 72 / 25.4, 2),
                  "use_instrument_margins": bool(r.use_instrument_margins),
                  "stamp_command": bool(r.stamp_command),
              },
              "chart_notes_field": (tab._manual_chart_notes_edit.text()
                                    if getattr(tab, "_manual_chart_notes_edit", None)
                                    else None),
              "panel_message_field": field_text(),
              "red_overlap_notices": over,
              "all_notices": warns}
        if shot:
            p = out / f"{name}.png"
            ok, why = capture_window(win, p)
            st["screenshot"] = str(p) if ok else f"REFUSED: {why}"
            print(f"      photo: {st['screenshot']}")
        res["steps"].append(st)
        print(f"  [{name}] red notices: {len(over)}")
        for o in over:
            print(f"      · {o[:150]}")
        return st

    # A clean slate: no chart notes, no settings stamp, so each side's message
    # is the only one on screen.
    if getattr(tab, "_manual_chart_notes_edit", None) is not None:
        tab._manual_chart_notes_edit.setText("")
    if getattr(tab, "_manual_stamp_cmd_check", None) is not None:
        tab._manual_stamp_cmd_check.setChecked(False)
    pump(app, 500)

    # ---------------------------------------------------------------- BOTTOM
    apply(chart_text="ChromIQ symmetry audit sheet text",
          chart_text_size_mm=0.0)
    snap("B1_bottom_auto", "bottom sheet text, Size auto, bottom margin 30 mm",
         shot=True)

    for pt in (12.0, 18.0, 28.0):
        apply(chart_text="ChromIQ symmetry audit sheet text",
              chart_text_size_mm=pt * 25.4 / 72.0)
        snap(f"B2_bottom_{pt:g}pt",
             f"bottom sheet text at a TYPED {pt:g} pt, bottom margin 30 mm; "
             f"measured ink crosses the 4 mm 'B' limit")

    apply(chart_text="A" * 400, chart_text_size_mm=0.0)
    snap("B3_bottom_400_chars",
         "a 400-character bottom line; measured, it runs off the right edge")

    # The bottom margin that HAS room for an auto line and not for a big one.
    # 12 mm of margin less the 4 mm "B" leaves 8.0 mm: an auto line takes 4.2
    # and a typed 28 pt takes 9.88. Before the fix the panel said 4.2 mm for
    # both and stayed silent on both.
    for pt in (0.0, 12.0, 18.0, 28.0):
        apply(margin_bottom=12.0,
              chart_text="ChromIQ symmetry audit sheet text",
              chart_text_size_mm=(pt * 25.4 / 72.0) if pt else 0.0)
        snap(f"B4_tight_bottom_{pt:g}pt",
             f"bottom margin 12 mm, B 4 mm, Sheet text Size "
             f"{'auto' if not pt else f'{pt:g} pt'}")

    # ------------------------------------------------------------------- TOP
    for mt in (20.0, 8.0, 4.0, 2.0):
        apply(margin_top=mt)
        snap(f"T1_top_margin_{mt:g}",
             f"top margin {mt:g} mm against T = 8 mm",
             shot=(mt == 2.0))

    # ------------------------------------------------------------------ CLIP
    for band in (26.0, 16.0, 12.0, 8.0):
        apply(margin_top=20.0, margin_left=40.0,
              clip_border=True, clip_border_width_mm=band, clip_side="left",
              clip_content_mode="text",
              clip_text="LINE ONE\nLINE TWO\nLINE THREE\nLINE FOUR")
        snap(f"C1_clip_left_{band:g}mm",
             f"{band:g} mm left clip band, four lines, Clip = 4 mm",
             shot=(band == 12.0))

    apply(margin_top=20.0, margin_left=40.0,
          clip_border=True, clip_border_width_mm=30.0, clip_side="left",
          clip_content_mode="text",
          clip_text="X" * 200)
    snap("C2_clip_200_chars",
         "a 200-character clip line; measured, it is cut at both page edges")

    # ----------------------------------------------------------------- RIGHT
    apply(margin_right=4.0, clip_border=False,
          clip_content_mode="off")
    tab._manual_chart_notes_edit.setText("Symmetry audit right-edge note")
    pump(app, 800)
    tab._update_margin_inspector()
    snap("R1_right_note_margin_4", "run chart notes, right margin 4 mm",
         shot=True)
    tab._manual_chart_notes_edit.setText("")
    pump(app, 500)

    (out / "onscreen.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out/'onscreen.json'}")
    print(f"screen locked at end: {session_is_locked()}")
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
