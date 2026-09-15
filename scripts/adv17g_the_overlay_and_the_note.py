#!/usr/bin/env python3
"""Adversary 17g, driven in a REAL window.

F2  The live-preview HELPER-MARKER OVERLAY reads the two marker boxes RAW.
    `LayoutRecipe.build_kwargs` sends ``helper_marker_edge_mm or 2.0``, so a
    box typed 0 draws 2 mm dashes on every sheet; the overlay -- whose own
    comment says it "positively claims to BE the ink on the sheet" -- asks
    `geometry.helper_marker_lines_mm` for markers 0 mm long and gets none.
    Round 6 swept `_marker_reserve_args` through `_engine_text_notes` and its
    test greps that ONE method, so it cannot see this.

F1  `chart_creator` -- the code that PLACES the stamped note -- reads the same
    two boxes raw, so the panel now predicts a reserve the stamper is never
    given.

F3  "try another Alignment", offered ungated by the bottom-text WIDTH message,
    measured on Knut's own preset.
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


def notices(tab):
    panel = getattr(tab, "_margin_panel", None)
    last = getattr(panel, "_last_status", None) if panel is not None else None
    return list((last[1].get("overlap_warnings") or []) if last else [])


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17g-"))
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
        tab._manual_target_name_edit.setText("adv17g")
    combo = tab._preset_combo
    i = combo.findData(PRESET); assert i >= 0, "Knut's preset is not in the list"
    combo.setCurrentIndex(i); combo.activated.emit(i); pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 1000)
    panel = tab._manual_layout_panel
    res = {"window_on_screen": onscreen, "F2": {}, "F1": {}, "F3": {}}

    def refresh():
        pump(app, 200); tab._update_margin_inspector(); pump(app, 320)
        return notices(tab)

    # ------------------------------------------------------------------ F2
    # A strip reader, so both marker combs are live (a honeycomb greys one).
    if panel.instr.findData("i1") >= 0:
        panel.instr.setCurrentIndex(panel.instr.findData("i1")); pump(app, 900)
    panel.paper.setCurrentIndex(panel.paper.findData("A4"))
    panel.layout_mode.setCurrentIndex(panel.layout_mode.findData("area_first"))
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False); pump(app, 400)
    for k, v in (("t", 20.0), ("b", 20.0), ("l", 20.0), ("r", 20.0)):
        panel.margins[k].setValue(v)
    panel.helper_markers_cb.setChecked(True); pump(app, 400)
    panel.helper_markers_top_bottom.setChecked(True)
    panel.helper_markers_sides.setChecked(True)
    pump(app, 400)

    f2 = {}
    for edge, length in ((2.0, 2.0), (0.0, 0.0)):
        panel.helper_marker_edge.setValue(edge)
        panel.helper_marker_len.setValue(length)
        pump(app, 600)
        tab._refresh_helper_marker_overlay(); pump(app, 600)
        got = tab._helper_marker_lines_frac()
        lines, pending = (got if got is not None else (None, False))
        n_overlay = 0 if not lines else len(lines)
        # …and the SAME CALL with the boxes read AS THE ENGINE READS THEM.
        # `_helper_marker_lines_frac` builds its geometry from the chart's own
        # `channels.json`, so this repeats that exactly and changes ONE thing:
        # `or 2.0`, which is what `LayoutRecipe.build_kwargs` sends the
        # renderer. Anything else would be comparing two different sheets.
        import re as _re
        from core.text_io import read_text
        from workflow.layout_engine import instruments, geometry, papers
        from workflow.layout_engine.presets import LayoutRecipe
        ch = Path(tab._margin_ti2).with_suffix(".channels.json")
        rec_sheet = LayoutRecipe.from_channels_json(ch)
        m = _re.search(r"NUMBER_OF_SETS\s+(\d+)",
                       read_text(Path(tab._margin_ti2), lenient=True))
        n_patch = int(m.group(1)) if m else 0
        kwargs = rec_sheet.build_kwargs(); kwargs["area_target_count"] = n_patch
        g = instruments.geom_from_build_kwargs(kwargs)
        w_mm, h_mm = papers.dimensions_mm(rec_sheet.paper)
        lay = geometry.compute(g, w_mm, h_mm, n_patch)
        sheet = geometry.helper_marker_lines_mm(
            g, w_mm, h_mm, lay,
            edge_mm=(float(panel.helper_marker_edge.value()) or 2.0),
            length_mm=(float(panel.helper_marker_len.value()) or 2.0),
            per_patch=int(panel.helper_marker_per_patch.value()),
            top_bottom=bool(panel.helper_markers_top_bottom.isChecked()),
            sides=bool(panel.helper_markers_sides.isChecked()))
        rec = tab._current_layout_recipe()
        kw = rec.build_kwargs()
        f2[f"boxes_{edge:.1f}_{length:.1f}"] = {
            "overlay_dashes": n_overlay, "sheet_dashes": len(sheet),
            "pending_caption": bool(pending),
            "build_kwargs_edge": float(kw["helper_marker_edge"]),
            "build_kwargs_len": float(kw["helper_marker_len"]),
            "recipe_edge": float(getattr(rec, "helper_marker_edge_mm", 0.0) or 0.0),
            "recipe_len": float(getattr(rec, "helper_marker_len_mm", 0.0) or 0.0)}
        print(f"    F2 boxes {edge:.1f}/{length:.1f}: overlay {n_overlay} dashes, "
              f"sheet {len(sheet)} dashes, pending caption {bool(pending)}",
              flush=True)
        capture_window(win, out / f"F2-boxes-{edge:.0f}-{length:.0f}"
                            f"-overlay-{n_overlay}-sheet-{len(sheet)}.png")
    res["F2"] = f2
    # …AND AFTER A REAL GENERATE, where the overlay is no longer a proposal
    # but the app's claim about the ink on the sheet in front of the reader.
    panel.helper_marker_edge.setValue(0.0); panel.helper_marker_len.setValue(0.0)
    pump(app, 600)
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    tab._refresh_helper_marker_overlay(); pump(app, 800)
    got = tab._helper_marker_lines_frac()
    lines, pending = (got if got is not None else (None, False))
    tif = list(getattr(tab, "_margin_tiffs", []) or [])
    dash = None
    if tif:
        import numpy as _np
        from PIL import Image as _Im
        a = _np.asarray(_Im.open(str(tif[0])).convert("L"))
        H, W = a.shape[:2]
        dpi = 300.0
        try:
            dpi = float(tab._current_layout_recipe().dpi or 300)
        except Exception:
            pass
        top = a[:int(6.0 / 25.4 * dpi), :] < 200
        colruns = top.any(axis=0).astype(int)
        dash = int(((colruns[1:] == 1) & (colruns[:-1] == 0)).sum() + colruns[0])
    res["F2"]["after_generate"] = {
        "overlay_dashes": 0 if not lines else len(lines),
        "pending_caption": bool(pending),
        "dash_columns_in_the_top_6mm_of_the_real_tiff": dash,
        "tiff": str(tif[0]) if tif else ""}
    print(f"    F2 after Generate: overlay "
          f"{0 if not lines else len(lines)} dashes, pending {bool(pending)}, "
          f"the TIFF the app just wrote has {dash} dash columns in its top "
          f"6 mm", flush=True)
    capture_window(win, out / "F2-after-Generate-overlay-empty-sheet-inked.png")

    # ------------------------------------------------------------------ F1
    # The panel's own claimed distance, against what chart_creator hands the
    # stamper for the SAME recipe.
    from workflow import text_edge_fit as tef
    from ui.tabs.tab_chart import _marker_reserve_args
    panel.helper_marker_edge.setValue(0.0); panel.helper_marker_len.setValue(0.0)
    panel.text_edge_clip.setValue(0.1)
    panel.margins["r"].setValue(6.0)
    if hasattr(panel, "stamp_cmd_check"):
        pass
    cb = getattr(tab, "_manual_stamp_cmd_check", None)
    if cb is not None:
        cb.setChecked(True)
    pump(app, 500)
    msgs = refresh()
    side = [m for m in msgs if "down the right edge" in m]
    rec = tab._current_layout_recipe()
    eff = float(rec.effective_text_edge_clip_mm)
    shipped = tef.side_text_edge_mm(
        eff, helper_markers=bool(rec.helper_markers),
        marker_edge_mm=float(getattr(rec, "helper_marker_edge_mm", 0.0) or 0.0),
        marker_len_mm=float(getattr(rec, "helper_marker_len_mm", 0.0) or 0.0),
        marker_sides=bool(rec.helper_markers_sides))
    mke, mkl = _marker_reserve_args(rec)
    panel_says = tef.side_text_edge_mm(
        eff, helper_markers=bool(rec.helper_markers), marker_edge_mm=mke,
        marker_len_mm=mkl, marker_sides=bool(rec.helper_markers_sides))
    res["F1"] = {"message": side[0] if side else "",
                 "chart_creator_hands_the_stamper_mm": shipped,
                 "the_panel_predicts_mm": panel_says}
    print(f"    F1 panel {panel_says:.2f} mm vs chart_creator {shipped:.2f} mm",
          flush=True)
    if side:
        print(f"       {side[0][:160]}", flush=True)
        capture_window(win, out / "F1-the-panel-names-a-distance-the-stamper-"
                                  "is-not-given.png")

    # ----------------------------------------------------------------- F1b
    # A REAL sheet with a REAL clip-border text down the right edge, built by
    # the app, so the note's placement can be measured against ink the ENGINE
    # drew rather than against arithmetic.
    if panel.clip_side.findData("right") >= 0:
        panel.clip_side.setCurrentIndex(panel.clip_side.findData("right"))
    panel.clip_width.setValue(20.0)
    if panel.clip_content_mode.findData("text") >= 0:
        panel.clip_content_mode.setCurrentIndex(
            panel.clip_content_mode.findData("text"))
    panel.clip_text.setPlainText("ChromIQ adversary 17g")
    panel.clip_text_size.setValue(10.0)
    panel.helper_marker_edge.setValue(0.0); panel.helper_marker_len.setValue(0.0)
    panel.text_edge_clip.setValue(0.1)
    pump(app, 800)
    tab._generate_btn.click()
    for _ in range(900):
        pump(app, 200)
        if tab._generate_btn.isEnabled() and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 2500)
    rec1 = tab._current_layout_recipe()
    res["F1b"] = {
        "tiff": str((getattr(tab, "_margin_tiffs", []) or [""])[0]),
        "dpi": float(getattr(rec1, "dpi", 0) or 0),
        "clip_border_width_mm": float(getattr(rec1, "clip_border_width_mm", 0) or 0),
        "clip_text": str(getattr(rec1, "clip_text", "") or ""),
        "clip_text_size_mm": float(getattr(rec1, "clip_text_size_mm", 0) or 0),
        "clip_side": str(getattr(rec1, "clip_side", "") or ""),
        "effective_text_edge_clip_mm": float(rec1.effective_text_edge_clip_mm),
        "helper_marker_edge_mm": float(getattr(rec1, "helper_marker_edge_mm", 0) or 0),
        "helper_marker_len_mm": float(getattr(rec1, "helper_marker_len_mm", 0) or 0),
        "helper_markers": bool(getattr(rec1, "helper_markers", False)),
        "helper_markers_sides": bool(getattr(rec1, "helper_markers_sides", True)),
        "notices": [m for m in refresh() if "right edge" in m]}
    print(f"    F1b sheet with a right clip border: {res['F1b']['tiff']}",
          flush=True)
    capture_window(win, out / "F1b-a-right-clip-border-with-text.png")

    # ------------------------------------------------------------------ F3
    # "try another Alignment", on Knut's own preset.
    combo.setCurrentIndex(combo.findData(PRESET)); combo.activated.emit(
        combo.findData(PRESET)); pump(app, 1800)
    for _ in range(300):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None):
            break
    pump(app, 800)
    rec = tab._current_layout_recipe()
    from workflow.layout_engine import instruments as _ins, papers as _pap
    g = _ins.geom_from_build_kwargs(rec.build_kwargs())
    pw, _ph = _pap.dimensions_mm(rec.paper)
    mke, mkl = _marker_reserve_args(rec)
    rooms = {}
    for a in tef.BOTTOM_TEXT_ALIGNMENTS:
        rooms[a] = tef.bottom_text_room_mm(
            pw, float(rec.effective_text_edge_clip_mm),
            bool(rec.helper_markers), mke, mkl, bool(rec.helper_markers_sides),
            clip_border_mm=(float(getattr(rec, "clip_border_width_mm", 0.0) or 0.0)
                            if getattr(rec, "clip_border", False) else 0.0),
            clip_side=str(getattr(rec, "clip_side", "left") or "left"),
            margin_left_mm=float(getattr(g, "margin_l", 0.0) or 0.0),
            margin_right_mm=float(getattr(g, "margin_r", 0.0) or 0.0),
            align=a)
    res["F3"] = {"preset": PRESET, "paper": rec.paper,
                 "room_mm_by_alignment": rooms,
                 "current_alignment": str(getattr(rec, "chart_text_align", "")),
                 "best_minus_current_mm": round(
                     max(rooms.values()) - rooms.get(
                         str(getattr(rec, "chart_text_align", ""))
                         or tef.BOTTOM_TEXT_ALIGN_DEFAULT,
                         max(rooms.values())), 3)}
    print(f"    F3 room by alignment on Knut's preset: "
          f"{ {k: round(v,2) for k,v in rooms.items()} }", flush=True)
    capture_window(win, out / "F3-knuts-preset-alignment-room.png")

    (out / "adv17g.json").write_text(json.dumps(res, indent=2),
                                     encoding="utf-8")
    win.close(); pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
