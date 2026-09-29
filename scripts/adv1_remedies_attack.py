#!/usr/bin/env python3
"""ADVERSARY ONE — do what every warning says, and see whether it goes away.

Drives the REAL ChromIQ window. For each state that raises a red notice in the
"Measured from Preview" frame, the remedy the notice NAMES is read out of the
sentence itself, applied to the control it names, and the notice list is asked
again. A remedy that leaves the same notice standing is a remedy that does not
remedy, which is the fault this project has shipped twice.

Usage:
    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv1.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv1-presets
    python scripts/adv1_remedies_attack.py --out DIR
"""
from __future__ import annotations

import json
import os
import re
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

WORK = Path("/tmp/chromiq-adv1-work")
TARGET = "Adv1Remedy"

_timers: list = []
modals: list[dict] = []


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
        modals.append({"title": w.windowTitle()})
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
        else Path("/tmp/chromiq-adv1-proof/remedies")
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"screen_locked_at_start": locked, "cases": []}
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
    pump(app, 900)
    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 600)

    from workflow.layout_engine.presets import LayoutRecipe

    BASE = dict(instrument="i1", paper="A4", dpi=200,
                layout_mode="area_first", use_instrument_margins=False,
                clip_border=False, clip_content_mode="off", patches=120,
                margin_top=20.0, margin_right=20.0,
                margin_bottom=30.0, margin_left=20.0,
                text_edge_top_mm=8.0, text_edge_mm=4.0, text_edge_clip_mm=4.0,
                show_strip_indicators=True, show_row_indicators=True,
                chart_text="", stamp_command=False,
                randomize=True, seed_fixed=True, seed=4242,
                chart_text_size_mm=0.0, clip_text_size_mm=0.0)

    def apply(over: dict) -> None:
        panel.set_recipe(LayoutRecipe.from_dict({**BASE, **over}))
        pump(app, 700)
        tab._update_margin_inspector()
        pump(app, 350)

    def notices() -> list:
        try:
            _w, over = type(tab)._engine_text_notes(tab)
        except Exception as exc:                                  # noqa: BLE001
            return [f"<raised {exc!r}>"]
        return over

    def num(msg: str, pattern: str):
        m = re.search(pattern, msg)
        return float(m.group(1)) if m else None

    def case(name: str, over: dict, notes: str, remedies) -> None:
        """`remedies` is a list of (label, fn(msg, over) -> new_over | None)."""
        apply(over)
        before = notices()
        rec = {"case": name, "note": notes, "recipe": over,
               "before": before, "remedies": []}
        if not before:
            rec["remedies"].append({"label": "<no notice raised>", "ok": None})
            print(f"  [{name}] NO NOTICE")
            res["cases"].append(rec)
            return
        print(f"  [{name}] {len(before)} notice(s)")
        for b in before:
            print(f"      · {b[:190]}")
        for label, fn in remedies:
            newo = None
            for b in before:
                newo = fn(b, dict(over))
                if newo is not None:
                    break
            if newo is None:
                rec["remedies"].append({"label": label,
                                        "applied": None,
                                        "note": "the sentence did not name it"})
                print(f"      REMEDY {label}: not named")
                continue
            apply(newo)
            after = notices()
            gone = len(after) < len(before)
            rec["remedies"].append({"label": label, "applied": newo,
                                    "after": after, "fewer_notices": gone})
            print(f"      REMEDY {label} -> {newo}: "
                  f"{len(before)} notices became {len(after)}"
                  f"{'  *** NO CHANGE ***' if not gone else ''}")
            for a in after:
                print(f"          · {a[:190]}")
            apply(over)
        res["cases"].append(rec)

    # ---------------------------------------------------------- BOTTOM TEXT
    def r_bottom(msg, o):
        v = num(msg, r"Raise “Bottom” under “Margins \(mm\)” by about ([\d.]+)")
        if v is None:
            return None
        o["margin_bottom"] = round(o["margin_bottom"] + v + 0.05, 2)
        return o

    def r_B(msg, o):
        if "lower “B” under" not in msg:
            return None
        o["text_edge_mm"] = 0.5          # the box's own floor is 0.0
        return o

    case("bottom_text_tight",
         {**BASE, "margin_bottom": 5.0, "chart_text": "sheet text",
          "chart_text_size_mm": 0.0},
         "bottom sheet text, margin 5 mm, B 4 mm",
         [("raise Bottom by the shortfall", r_bottom),
          ("lower B to 0.5", r_B)])

    # ----------------------------------------------------------- STRIP LETTERS
    def r_top(msg, o):
        v = num(msg, r"Raise “Top” under “Margins \(mm\)” by (?:about|at least) ([\d.]+)")
        if v is None:
            return None
        o["margin_top"] = round(o["margin_top"] + v + 0.05, 2)
        return o

    case("strip_letters_squeezed",
         {**BASE, "margin_top": 8.0},
         "top margin 8 mm against T = 8 mm",
         [("raise Top by the shortfall", r_top)])

    case("strip_letters_off_the_sheet",
         {**BASE, "margin_top": 2.0},
         "top margin 2 mm against T = 8 mm",
         [("raise Top by the shortfall", r_top)])

    # ------------------------------------------------------------ CHART NOTES
    def r_right_by(msg, o):
        v = num(msg, r"Raise “Right” under “Margins \(mm\)” by about ([\d.]+)")
        if v is None:
            return None
        o["margin_right"] = round(o["margin_right"] + v + 0.05, 2)
        return o

    def r_right_to(msg, o):
        v = num(msg, r"Raise “Right” under “Margins \(mm\)” to about ([\d.]+)")
        if v is None:
            return None
        o["margin_right"] = round(v + 0.05, 2)
        return o

    def r_clip_lower(msg, o):
        if "lower “Clip” under “Text distance from edge" not in msg:
            return None
        o["text_edge_clip_mm"] = 0.5     # the box's own floor is 0.0
        return o

    tab._manual_chart_notes_edit.setText("adversary one right edge note")
    pump(app, 500)
    case("chart_note_tight_right",
         {**BASE, "margin_right": 4.0},
         "run chart notes, right margin 4 mm, no clip border",
         [("raise Right by the shortfall", r_right_by),
          ("lower Clip to 0.5", r_clip_lower)])

    case("chart_note_clip_band_right",
         {**BASE, "margin_right": 24.0, "clip_border": True,
          "clip_border_width_mm": 24.0, "clip_side": "right",
          "clip_content_mode": "text", "clip_text": "one\ntwo"},
         "a 24 mm right clip band, right margin 24 mm, notes on",
         [("raise Right to the named margin", r_right_to),
          ("raise Right by the shortfall", r_right_by)])
    tab._manual_chart_notes_edit.setText("")
    pump(app, 400)

    # ------------------------------------------------------------- CLIP TEXT
    _four = "clip line one\nclip line two\nclip line three\nclip line four"

    def r_band(msg, o):
        v = num(msg, r"Widen “Clip border width” to about ([\d.]+)")
        if v is None:
            return None
        o["clip_border_width_mm"] = round(v, 2)
        o["margin_left"] = max(o.get("margin_left", 20.0), round(v, 2))
        return o

    def r_clip_to(msg, o):
        v = num(msg, r"Lowering “Clip” to ([\d.]+) mm would also do it")
        if v is None:
            return None
        o["text_edge_clip_mm"] = round(v, 2)
        return o

    def r_clip_raise(msg, o):
        v = num(msg, r"Raising “Clip” to ([\d.]+) mm instead")
        if v is None:
            return None
        o["text_edge_clip_mm"] = round(v, 2)
        return o

    def r_clip_size(msg, o):
        if "set a smaller Size under “Clip-border content”" not in msg:
            return None
        o["clip_text_size_mm"] = 5.0 * 25.4 / 72.0          # 5 pt, below the floor
        return o

    for band in (12.0, 16.0):
        case(f"clip_text_left_{band:g}",
             {**BASE, "margin_left": band, "clip_border": True,
              "clip_border_width_mm": band, "clip_side": "left",
              "clip_content_mode": "text", "clip_text": _four},
             f"{band:g} mm left clip band, four lines, row indicators on",
             [("widen the band to the named width", r_band),
              ("lower Clip to the named value", r_clip_to),
              ("raise Clip to the named value", r_clip_raise),
              ("set a smaller clip Size", r_clip_size)])

    # eight lines: deep enough to reach the patches as well as the labels
    _eight = "\n".join(f"clip line {i}" for i in range(1, 9))
    case("clip_text_left_16_deep",
         {**BASE, "margin_left": 16.0, "clip_border": True,
          "clip_border_width_mm": 16.0, "clip_side": "left",
          "clip_content_mode": "text", "clip_text": _eight},
         "16 mm left clip band, EIGHT lines",
         [("widen the band to the named width", r_band),
          ("lower Clip to the named value", r_clip_to),
          ("raise Clip to the named value", r_clip_raise),
          ("set a smaller clip Size", r_clip_size)])

    # -------------------------------------------------- THE ROW-INDICATOR RAISE
    def r_left_to(msg, o):
        v = num(msg, r"aise “Left” under “Margins \(mm\)” to ([\d.]+)")
        if v is None:
            return None
        o["margin_left"] = round(v, 2)
        return o

    def r_row_size(msg, o):
        if "set a smaller Size under “Row indicators”" not in msg:
            return None
        # `set_recipe` re-seeds the label style from Preferences unless the
        # recipe says it owns it, so without this flag the value is discarded.
        o["indicator_size_mm"] = 4.0 * 25.4 / 72.0        # 4 pt
        o["label_style_explicit"] = True
        return o

    def r_rows_off(msg, o):
        if "Switching “Show row indicators” off" not in msg:
            return None
        o["show_row_indicators"] = False
        return o

    case("row_label_raise",
         {**BASE, "margin_left": 4.0},
         "left margin 4 mm, row indicators on",
         [("raise Left to the named margin", r_left_to),
          ("set a smaller row-indicator Size", r_row_size),
          ("lower Clip to 0.5", r_clip_lower),
          ("switch row indicators off", r_rows_off)])

    case("row_label_raise_with_band",
         {**BASE, "margin_left": 4.0, "clip_border": True,
          "clip_border_width_mm": 26.0, "clip_side": "left",
          "clip_content_mode": "branding"},
         "left margin 4 mm, a 26 mm left clip border",
         [("raise Left to the named margin", r_left_to),
          ("set a smaller row-indicator Size", r_row_size),
          ("lower Clip to 0.5", r_clip_lower),
          ("switch row indicators off", r_rows_off)])

    (out / "remedies.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out/'remedies.json'}")
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
