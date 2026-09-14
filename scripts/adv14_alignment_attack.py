#!/usr/bin/env python3
"""ADVERSARY round 14 — the bottom-text Alignment control, attacked on screen.

Three things are measured in the REAL Create Chart tab, in a REAL window:

1. **"Centre between left and right margin" warns about ink that is on the
   paper.** `bottom_text_room_mm` returns `2 x min(centre-left, right-centre)`
   for that alignment, but `bottom_text_start_mm` CLAMPS a line that will not
   centre back to the left bound. On a sheet whose margins differ, the clamped
   line sits entirely inside the two side bounds while the panel prints
   "N mm of it runs off".
2. The Sheet text frame in a NARROW window, and in German and Norwegian.
3. Every door Knut named, for whether the alignment survives it.

Run::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv14.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv14-presets \
        python scripts/adv14_alignment_attack.py <out-dir> [lang] [width]

NEVER set QT_QPA_PLATFORM=offscreen here. It is a driver, not a test.
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
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

from onscreen_capture import capture_window                      # noqa: E402

LEFT_MM, RIGHT_MM = 12.0, 30.0
SEED = 123456789


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def reveal(app, w) -> str:
    from PyQt6.QtWidgets import QScrollArea
    steps, node = [], w
    while node is not None:
        if hasattr(node, "set_collapsed"):
            try:
                node.set_collapsed(False)
                steps.append(f"expanded {type(node).__name__}")
            except Exception as exc:                          # noqa: BLE001
                steps.append(f"could not expand: {exc}")
        node = node.parentWidget()
    pump(app, 400)
    node, area = w, None
    while node is not None:
        if isinstance(node, QScrollArea):
            area = node
            break
        node = node.parentWidget()
    if area is not None:
        area.ensureWidgetVisible(w, 40, 160)
        steps.append("scrolled")
    pump(app, 600)
    steps.append("visible" if w.visibleRegion().boundingRect().height() > 0
                 else "STILL NOT VISIBLE")
    return ", ".join(steps)


def ink_mm(recipe, ti1: Path, tag: str):
    """Where the custom Sheet-text line's ink lands, in mm from the left edge."""
    from dataclasses import replace

    import numpy as np
    from PIL import Image

    from workflow.layout_engine.chart import build_from_recipe

    def _r(r, suffix):
        base = Path(tempfile.mkdtemp(prefix=f"adv14-{tag}-{suffix}-"))
        res, used = build_from_recipe(str(ti1), str(base / "s"), r)
        page = sorted(base.glob("s*.tif"))[0]
        return np.asarray(Image.open(page).convert("L")).astype(np.int16), res

    base_r = replace(recipe, randomize=True, seed_fixed=True, seed=SEED,
                     stamp_command=False)
    on, res = _r(base_r, "on")
    off, _ = _r(replace(base_r, chart_text=" "), "off")
    if on.shape != off.shape:
        return {"error": "geometry moved between the two renders"}
    diff = abs(on - off) > 30
    cols = diff.any(axis=0).nonzero()[0]
    if cols.size == 0:
        return {"error": "no ink"}
    dpi = float(getattr(recipe, "dpi", 300) or 300)
    mm = lambda p: round(float(p) * 25.4 / dpi, 3)               # noqa: E731
    return {"ink_left_mm": mm(int(cols[0])), "ink_right_mm": mm(int(cols[-1]) + 1),
            "ink_width_mm": mm(int(cols[-1]) + 1 - int(cols[0])),
            "paper_w_mm": mm(on.shape[1])}


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1620

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv14-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    settings.set("language", lang)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    from core.i18n import set_language
    set_language(lang)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    from ui.theme import apply_appearance
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments, papers, raster
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(width, 1040)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    on_screen = {"visible": bool(win.isVisible()),
                 "geometry": [win.frameGeometry().width(),
                              win.frameGeometry().height()],
                 "language": lang}
    print(f"    ON SCREEN: {on_screen}", flush=True)

    combo, panel = tab._preset_combo, tab._manual_layout_panel
    # the first i1 engine preset in the dropdown
    pick = None
    for instr, entries in BUILTIN_PRESET_GROUPS:
        if "i1Pro /" not in instr:
            continue
        for n, (label, _o, key) in enumerate(entries, 1):
            if combo.findData(key) < 0:
                continue
            if tab._manual_target_name_edit is not None:
                tab._manual_target_name_edit.setText(f"Adv14x{n}")
            pump(app, 150)
            combo.setCurrentIndex(combo.findData(key))
            combo.activated.emit(combo.findData(key))
            pump(app, 1200)
            if bool(settings.get("use_chromiq_layout_engine", False)):
                pick = (label, key)
                break
        break
    assert pick, "no engine preset for i1 in the dropdown"
    print(f"    preset: {pick[0][:70]}", flush=True)

    ti1_path = None
    for _attr in ("_preset_ti1_path", "_builtin_ti1_path"):
        _v = getattr(tab, _attr, None)
        if _v and Path(_v).is_file():
            ti1_path = Path(_v)
            break
    for _ in range(300):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 600)
    # A4, so the arithmetic is on his own worked page rather than a 100x150
    # card the preset happened to carry.
    _pi = tab._paper_combo.findData("A4")
    if _pi >= 0:
        tab._paper_combo.setCurrentIndex(_pi)
        pump(app, 1200)
    print(f"    paper: {tab._paper_combo.currentData()}", flush=True)
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False)
        pump(app, 400)
    panel.margins["l"].setValue(LEFT_MM)
    panel.margins["r"].setValue(RIGHT_MM)
    pump(app, 600)

    findings: dict = {"on_screen": on_screen, "preset": pick[0]}

    # ---------- PHOTOGRAPH THE SHEET TEXT FRAME -----------------------------
    # THE LONGEST OPTION SHOWING, because that is the one that can be elided
    # or push the grid wider, and the default is the shortest of the three.
    _long = panel.chart_text_align.findData("between_margins")
    if _long >= 0:
        panel.chart_text_align.setCurrentIndex(_long)
    pump(app, 400)
    how = reveal(app, panel.chart_text_align)
    pump(app, 500)
    shot = out / f"sheet-text-{lang}-{width}px.png"
    cap = capture_window(win, shot)
    findings["photo"] = {"file": str(shot), "reveal": how, "capture": str(cap)}
    print(f"    photo: {shot}  ({cap})", flush=True)
    # geometry of every widget in the Sheet-text grid, to catch a clipped or
    # overlapping control the eye might miss
    geo = {}
    st = panel.chart_text_align.parentWidget()
    for name in ("chart_text", "chart_text_font", "chart_text_size",
                 "chart_text_align", "ct_bold", "ct_italic", "stamp_command",
                 "text_edge", "text_edge_top", "text_edge_clip"):
        w = getattr(panel, name, None)
        if w is None:
            continue
        r = w.geometry()
        geo[name] = {"x": r.x(), "y": r.y(), "w": r.width(), "h": r.height(),
                     "hint_w": w.sizeHint().width(),
                     "clipped_w": r.width() < w.sizeHint().width(),
                     "visible": bool(w.isVisible()),
                     "text": (w.currentText() if hasattr(w, "currentText")
                              else (w.text() if hasattr(w, "text") else ""))}
    findings["sheet_text_geometry"] = geo
    findings["panel_min_width"] = panel.minimumSizeHint().width()

    if lang != "en":
        (out / f"findings-{lang}-{width}.json").write_text(
            json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(findings["sheet_text_geometry"], indent=2,
                         ensure_ascii=False))
        return 0

    # ---------- THE FALSE OVERFLOW WARNING ----------------------------------
    rows = []
    for align in tef.BOTTOM_TEXT_ALIGNMENTS:
        i = panel.chart_text_align.findData(align)
        panel.chart_text_align.setCurrentIndex(i)
        panel.stamp_command.setChecked(False)
        # A line that fits between the two BOUNDS but is wider than the
        # "between margins" room. Grown here rather than guessed.
        panel.chart_text_size.setValue(9.0)
        pump(app, 300)
        r0 = panel.get_recipe()
        kw0 = r0.build_kwargs()
        g0 = raster.apply_furniture_reserves(
            instruments.geom_from_build_kwargs(kw0), kw0)
        pw = float(papers.dimensions_mm(r0.paper)[0])
        common = dict(clip_border_mm=(float(g0.lbord + g0.border)
                                      if getattr(g0, "lbord", 0) else 0.0),
                      clip_side=str(getattr(g0, "clip_side", "left") or "left"),
                      margin_left_mm=float(getattr(g0, "margin_l", 0.0) or 0.0),
                      margin_right_mm=float(getattr(g0, "margin_r", 0.0) or 0.0))
        pos = (pw, float(getattr(g0, "text_edge_clip_mm", 4.0) or 4.0),
               bool(r0.helper_markers), float(r0.helper_marker_edge_mm or 0.0),
               float(r0.helper_marker_len_mm or 0.0),
               bool(r0.helper_markers_sides))
        lo, hi = tef.bottom_text_bounds_mm(*pos, **common)
        text = "I"
        while True:
            w = raster.sheet_text_width_mm(
                [text + "I"], float(r0.chart_text_size_mm or 3.2),
                str(r0.chart_text_font or ""), bool(r0.chart_text_bold),
                bool(r0.chart_text_italic))
            if w > (hi - lo) - 1.0 or len(text) > 600:
                break
            text += "I"
        panel.chart_text.setText(text)
        pump(app, 800)
        tab._update_margin_inspector()
        pump(app, 900)
        r = panel.get_recipe()
        notes, overs = tab._engine_text_notes()
        bottom = [t for t in list(notes) + list(overs)
                  if "sheet text along the bottom is too wide" in t]
        got = ink_mm(r, ti1_path, f"{align}") if ti1_path else {"error": "no ti1"}
        rows.append({
            "align": align, "bounds": [lo, hi],
            "patch_centre_mm": tef.bottom_text_centre_mm(
                pw, common["margin_left_mm"], common["margin_right_mm"]),
            "room_mm": tef.bottom_text_room_mm(*pos, **common, align=align),
            "text_chars": len(text),
            "predicted_width_mm": round(w, 3),
            "panel_says": bottom,
            "ink": got,
            "ink_crosses_right_bound": (
                bool(got.get("ink_right_mm", 0) > hi + 0.2)
                if "ink_right_mm" in got else None),
        })
        print(json.dumps(rows[-1], indent=2), flush=True)
        if align == "between_margins":
            shot2 = out / "warning-between-margins.png"
            reveal(app, tab._margin_panel)
            pump(app, 400)
            print(f"    photo: {shot2} ({capture_window(win, shot2)})", flush=True)
    findings["overflow"] = rows

    # ---------- THE DOORS ---------------------------------------------------
    doors = []

    def note(name, value, extra=None):
        doors.append({"door": name, "align_after": value, **(extra or {})})
        print(f"    door {name}: {value}", flush=True)

    i = panel.chart_text_align.findData("between_margins")
    panel.chart_text_align.setCurrentIndex(i)
    pump(app, 500)
    note("set to between_margins", panel.get_recipe().chart_text_align)

    # a user preset saved and loaded back
    try:
        from workflow.layout_engine.presets import PresetStore
        store = PresetStore.load(Path(os.environ["CHROMIQ_PRESETS_DIR"])
                                 / "layouts.json")
    except Exception as exc:                                   # noqa: BLE001
        store = None
        note("PresetStore.load", f"ERROR {exc}")
    if store is not None:
        store.set("adv14", panel.get_recipe())
        p = Path(os.environ["CHROMIQ_PRESETS_DIR"])
        p.mkdir(parents=True, exist_ok=True)
        store.save(p / "layouts.json")
        again = PresetStore.load(p / "layouts.json")
        note("user preset save+load",
             again.get("adv14").chart_text_align if again.get("adv14") else "GONE")

    # switching instrument / preset in the dropdown
    before = panel.get_recipe().chart_text_align
    for instr, entries in BUILTIN_PRESET_GROUPS:
        if "i1Pro 3 Plus" not in instr:
            continue
        for label, _o, key in entries:
            if combo.findData(key) < 0:
                continue
            combo.setCurrentIndex(combo.findData(key))
            combo.activated.emit(combo.findData(key))
            pump(app, 1200)
            note("switch to another built-in preset",
                 panel.get_recipe().chart_text_align, {"was": before,
                                                       "preset": label[:50]})
            break
        break
    findings["doors"] = doors

    (out / "findings-en.json").write_text(
        json.dumps(findings, indent=2, ensure_ascii=False), encoding="utf-8")
    print("WROTE", out / "findings-en.json", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
