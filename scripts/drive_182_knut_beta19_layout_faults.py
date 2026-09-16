#!/usr/bin/env python3
"""A tester's five beta-19 layout findings, driven in the REAL Create Chart tab.

Each case is set through the widgets a person touches, the panel's own red
field is read back verbatim, and the sheet is rendered and MEASURED so the
message is checked against ink rather than against the prediction that produced
it.

The five:

1. **Auto-size picks a size that fires its own warning.** "Size = auto" for the
   strip and row indicators chose a size whose row-label band did not fit the
   left margin, so the panel reported a widening. His rule: auto should find a
   size where there is no warning, down to the 7 pt floor.
2. **The label height is measured short.** The ink probe was "W8"; strip labels
   print a **Q**, whose descender it cannot see.
3. **A silent overlap against the top helper markers** in "Prioritise patch
   size", reached by the top margin or by a negative "Label offset".
4. **A silent overlap of the bottom text against the clip border**, because the
   panel measured an auto-sized line at the 7 pt floor while the renderer draws
   it at up to 16 pt.
5. **The left-margin warning read the setting, not the sheet**, and named a
   value that means nothing in "Prioritise patch size".

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-k20.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-k20-presets \\
        python scripts/drive_182_knut_beta19_layout_faults.py <out-dir>

**Never set QT_QPA_PLATFORM=offscreen for this.** It is a driver, not a test:
`widget.grab()` is not a photograph and cannot show what the window server did.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
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


def check(app, box, want: bool) -> None:
    """Tick or untick *box* the way a person does.

    `.setChecked()` emits `toggled` but NOT `clicked`, and the panel connects
    `_mark_row_indicators_touched` to `clicked`: driven with setChecked the row
    indicators were quietly turned back off by the next preset refresh and the
    run measured a chart with no row band at all (`rlwi = 0`).
    """
    if bool(box.isChecked()) != bool(want):
        box.click()
    pump(app, 250)
    assert bool(box.isChecked()) is bool(want), (
        f"{box.text()!r} would not go to {want}")


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def install_excepthook() -> list:
    """`main.py`'s hook, so a fault in the app is recorded and not swallowed."""
    seen: list = []
    prev = sys.excepthook

    def hook(exc_type, exc, tb):
        seen.append("".join(traceback.format_exception(exc_type, exc, tb)))
        prev(exc_type, exc, tb)

    sys.excepthook = hook
    return seen


def sheet_ink_mm(recipe, ti1: Path, tag: str, out: Path) -> "dict | None":
    """Where the ink really lands on the sheet this recipe describes.

    **THE RASTER, NOT THE RECIPE.** Every number the panel prints is a
    prediction; the only way to check one is to draw the page and look at it.
    The seed is pinned so the sheet measured is the sheet predicted.
    """
    import numpy as np
    from PIL import Image
    from workflow.layout_engine import chart as _chart
    work = Path(tempfile.mkdtemp(prefix="chromiq-k20-ink-"))
    try:
        res = _chart.build_from_recipe(recipe, ti1, str(work / "sheet"))
        tif = sorted(work.glob("sheet*.tif"))
        if not tif:
            return None
        im = Image.open(tif[0]).convert("RGB")
        (out / "sheets").mkdir(parents=True, exist_ok=True)
        im.save(out / "sheets" / f"{tag}.png")
        a = np.asarray(im).astype(int)
        dpi = float(getattr(recipe, "dpi", 300) or 300)
        px2mm = 25.4 / dpi
        mx, mn = a.max(2), a.min(2)
        black = (mx < 100) & ((mx - mn) < 30)
        coloured = (a.sum(2) < 720) & ((mx - mn) > 25)
        if not coloured.any():
            return None
        crows = np.where(coloured.any(1))[0]
        ccols = np.where(coloured.any(0))[0]
        brows = np.where(black.any(1))[0]
        out_d = {
            "patch_top_mm": round(float(crows[0]) * px2mm, 3),
            "patch_bottom_mm": round(float(a.shape[0] - crows[-1] - 1) * px2mm, 3),
            "patch_left_mm": round(float(ccols[0]) * px2mm, 3),
            "patch_right_mm": round(float(a.shape[1] - ccols[-1] - 1) * px2mm, 3),
            "first_black_mm": round(float(brows[0]) * px2mm, 3),
            "paper_h_mm": round(float(a.shape[0]) * px2mm, 2),
            "paper_w_mm": round(float(a.shape[1]) * px2mm, 2),
            "patches": res.layout.total_patches,
            "sheet": f"sheets/{tag}.png",
        }
        # The strip labels' own ink: the deepest neutral-dark row ABOVE the
        # patches, which is what the top warning is about.
        top_px = int(out_d["patch_top_mm"] / px2mm)
        band = black[:max(1, top_px + int(6.0 / px2mm)), :]
        rows = np.where(band.any(1))[0]
        if len(rows):
            out_d["label_ink_bottom_mm"] = round(float(rows[-1] + 1) * px2mm, 3)
        return out_d
    except Exception as exc:                       # noqa: BLE001
        return {"error": repr(exc)}
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    crashes = install_excepthook()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-k20-"))
    settings = AppSettings()
    # PINNED, not merely sandboxed: an unset value in a fresh store still
    # points the app at the user's real ~/ChromIQ.
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    on_screen = bool(win.isVisible())
    geo = win.frameGeometry()
    print(f"    window on screen: {on_screen} {geo.width()}x{geo.height()}",
          flush=True)

    panel = tab._manual_layout_panel
    assert panel is not None, "the ChromIQ layout panel is not on this tab"
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("K20Case")
    pump(app, 400)
    # **UNTICK "Use instrument margins" FIRST, OR THE MARGIN BOXES ARE INERT.**
    # `_sync_instr_margins` makes all four read-only while it is on, and the
    # recipe still carries the typed numbers, so a driver that types into them
    # records the state it meant and measures the state the instrument chose.
    # The first run of this driver did exactly that: it typed a 5.0 mm top
    # margin for the helper-marker case and the geometry used the instrument's.
    check(app, panel.use_instr_margins, False)

    def generate(tag: str) -> bool:
        """Press Generate Chart and wait for the sheet AND its measurement.

        The strip-label, bottom-text and left-margin checks all read
        `report.*_mm` and are SILENT without it, so a driver that never
        generates measures nothing and reports every case clean.
        """
        tab._margin_report = None
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 120)
            if getattr(tab, "_margin_report", None) is not None:
                break
        rep = getattr(tab, "_margin_report", None)
        if rep is None:
            print(f"    [{tag}] GENERATE produced no measurement", flush=True)
            return False
        print(f"    [{tag}] measured L/R/T/B = "
              f"{rep.left_mm:.2f}/{rep.right_mm:.2f}/"
              f"{rep.top_mm:.2f}/{rep.bottom_mm:.2f} mm", flush=True)
        return True

    rows: list = []

    def notice(tag: str, photograph: bool = False) -> dict:   # noqa: C901
        """The panel's own notices, plus a photograph of the real window."""
        pump(app, 600)
        tab._update_margin_inspector()
        pump(app, 900)
        r = panel.get_recipe()
        warns, over = TabChart._engine_text_notes(
            tab, getattr(tab, "_margin_report", None))
        from workflow.layout_engine import instruments as _i
        _g = _i.geom_from_build_kwargs(r.build_kwargs())
        row = {
            "case": tag,
            "layout_mode": r.layout_mode,
            "margin_left": r.margin_left, "margin_top": r.margin_top,
            "margin_bottom": r.margin_bottom,
            "text_edge_top_mm": getattr(r, "text_edge_top_mm", None),
            "strip_label_offset_mm": getattr(r, "strip_label_offset_mm", None),
            "helper_markers": getattr(r, "helper_markers", None),
            "stamp_command": getattr(r, "stamp_command", None),
            "indicator_size_mm": getattr(r, "indicator_size_mm", None),
            "show_row_indicators": bool(getattr(r, "show_row_indicators", False)),
            "show_strip_indicators": bool(getattr(r, "show_strip_indicators", False)),
            "clip_border": bool(getattr(r, "clip_border", False)),
            "geom_margin_l": round(float(_g.margin_l), 3),
            "geom_rlwi": round(float(_g.rlwi), 3),
            "geom_label_ink_top_mm": round(
                float(getattr(_g, "label_ink_top_mm", 0.0) or 0.0), 3),
            "geom_label_ink_reach_mm": round(
                float(getattr(_g, "label_ink_reach_mm", 0.0) or 0.0), 3),
            "row_label_size_pt": round(
                float(getattr(_g, "row_label_size_mm", 0.0) or 0.0) * 72.0 / 25.4, 2),
            "measured": (None if getattr(tab, "_margin_report", None) is None
                         else {k: round(float(getattr(tab._margin_report, k)), 3)
                               for k in ("left_mm", "right_mm", "top_mm",
                                         "bottom_mm")}),
            "warnings": list(over),
            "notes": [w for w in warns if w not in over],
        }
        if photograph:
            shot = out / f"{tag}.png"
            ok, why = capture_window(win, shot)
            row["photograph"] = str(shot) if ok else None
            row["photograph_refused"] = None if ok else why
            print(f"      photograph: {'OK' if ok else 'REFUSED: ' + why}",
                  flush=True)
        rows.append(row)
        print(f"    [{tag}] {len(over)} warning(s)", flush=True)
        for m in over:
            print(f"        {m[:150]}", flush=True)
        return row

    # ---------------------------------------------------------------- case 5
    # The left-margin warning on a patch-first sheet with room to spare.
    panel.layout_mode.setCurrentIndex(
        max(0, panel.layout_mode.findData("patch_first")))
    pump(app, 500)
    check(app, panel.show_row_indicators, True)
    panel.margins["l"].setValue(10.0)
    generate("case5")
    notice("case5-patch-first-left-margin", photograph=True)

    # ---------------------------------------------------------------- case 3
    # The strip letters driven into the top helper markers, both his ways.
    check(app, panel.show_indicators, True)
    check(app, panel.helper_markers_cb, True)
    panel.helper_marker_edge.setValue(4.0)
    panel.helper_marker_len.setValue(2.0)
    panel.margins["t"].setValue(5.0)
    panel.strip_label_offset.setValue(0.0)
    generate("case3a")
    notice("case3a-markers-top-margin-5", photograph=True)

    panel.margins["t"].setValue(10.0)
    panel.strip_label_offset.setValue(-5.5)
    generate("case3b")
    notice("case3b-markers-label-offset-minus-5.5", photograph=True)

    # the control: a sheet that clears them must stay quiet
    panel.margins["t"].setValue(12.0)
    panel.strip_label_offset.setValue(0.0)
    generate("case3c")
    notice("case3c-control-clears-the-markers")

    # ---------------------------------------------------------------- case 4
    # The bottom text against the clip border, with the layout stamp on.
    # The clip border is not a layout-panel control: it is printtarg's -L, and
    # an i1Pro chart carries one unless that box suppresses it. The default is
    # a border, which is the state his case is in.
    panel.clip_side.setCurrentIndex(max(0, panel.clip_side.findData("right")))
    # A LINE WITH SOMETHING IN IT. With the box empty the stamp alone is the
    # bottom block, and on this sheet it fits at every size "auto" can reach,
    # so the case could not tell the fixed panel from the broken one.
    panel.chart_text.setText(
        "ChromIQ profile chart, paper batch 7, printer PRO-300, "
        "rendering intent relative colorimetric")
    check(app, panel.stamp_command, True)
    panel.chart_text_size.setValue(0.0)            # "auto"
    generate("case4")
    notice("case4-bottom-text-auto-with-stamp", photograph=True)

    # ---------------------------------------------------------------- case 1
    # "Size = auto" on a chart whose row band would widen the left margin.
    check(app, panel.stamp_command, False)
    panel.layout_mode.setCurrentIndex(
        max(0, panel.layout_mode.findData("area_first")))
    check(app, panel.helper_markers_cb, False)
    panel.margins["t"].setValue(10.0)
    # TIGHT ENOUGH THAT THE WALK HAS SOMETHING TO DO. At 13 mm this sheet's
    # auto size already fits and neither the raise nor the shrink happens, so
    # the case proved nothing. 11 mm is under what the band needs.
    panel.margins["l"].setValue(11.0)
    check(app, panel.show_row_indicators, True)
    panel.indicator_size.setValue(0.0)             # "auto"
    generate("case1")
    row = notice("case1-auto-size-left-margin", photograph=True)
    print(f"      margin_l={row['geom_margin_l']} asked=13.0 "
          f"band={row['geom_rlwi']} settled={row['row_label_size_pt']} pt",
          flush=True)

    # ---------------------------------------------------------------- case 2
    # The Q's descender, on a generated sheet.
    panel.margins["t"].setValue(13.0)
    panel.text_edge_top.setValue(9.0)
    panel.indicator_size.setValue(11.0)   # POINTS, which is what the box is
    generate("case2")
    row = notice("case2-label-reach-at-T-9.0", photograph=True)
    print(f"      label_ink_reach_mm={row['geom_label_ink_reach_mm']}",
          flush=True)

    # ------------------------------------------------- case 2, walked
    # **THE T AT WHICH THE NOTICE ARRIVES, AND THE T AT WHICH IT WOULD HAVE.**
    # His measurement was that the letters touch the patches half a millimetre
    # before the panel says so. The probe is what moved, so the honest
    # demonstration is to walk "T" over that boundary on GENERATED sheets and
    # record, at each step, the reach the panel now predicts, the reach the old
    # "W8" probe would have predicted, and whether the notice fired.
    from PIL import Image, ImageDraw
    from workflow.layout_engine import raster as _r2
    from workflow.layout_engine.raster import _font, DEFAULT_INDICATOR_FONT

    def w8_reach_mm(size_mm: float, dpi: float) -> float:
        """What the retired probe would have answered for this label size."""
        mm2px = dpi / 25.4
        ind_px = max(6, round(size_mm * mm2px))
        f = _font(ind_px, DEFAULT_INDICATOR_FONT, False, False)
        im = Image.new("RGBA", (ind_px * 8, ind_px * 6), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((ind_px * 2, ind_px * 2), "W8", font=f,
                                fill=(0, 0, 0, 255), anchor="la")
        bb = im.getbbox()
        return ((bb[3] - ind_px * 2) / mm2px) if bb else 0.0

    def strips_on(g, kw) -> int:
        """How many strips this chart really has, from the probe's own count."""
        try:
            return len(_r2._indicator_probe_text(kw, g))
        except Exception:                          # noqa: BLE001
            return 0

    walk: list = []
    for t in (8.0, 8.5, 9.0, 9.5, 10.0):
        panel.text_edge_top.setValue(t)
        generate(f"case2-T{t}")
        row = notice(f"case2-walk-T{t}")
        r = panel.get_recipe()
        # **THE PANEL'S OWN GEOMETRY, COUNT AND ALL.** `_engine_text_notes`
        # adds `area_target_count` before it builds this, because that is what
        # tells the ink probe whether a "Q" is printed. Built without it here,
        # the walk read a no-descender reach while the panel was judging with
        # the descender, and the two columns of this table described different
        # charts.
        from workflow.layout_engine import instruments as _i2
        _kw_walk = r.build_kwargs()
        _np = int(getattr(tab, "_estimate_patch_total", lambda: 0)() or 0)
        if _np > 0:
            _kw_walk = dict(_kw_walk, area_target_count=_np)
        g = _i2.geom_from_build_kwargs(_kw_walk)
        size_mm = float(getattr(r, "indicator_size_mm", 0.0) or 0.0)
        dpi = float(getattr(r, "dpi", 300) or 300)
        now = float(getattr(g, "label_ink_reach_mm", 0.0) or 0.0)
        then = w8_reach_mm(size_mm, dpi) if size_mm else 0.0
        fired = any("strip letters are printed over the patches" in w
                    for w in row["warnings"])
        # **AND WHAT THE RETIRED PROBE WOULD HAVE DONE ON THIS SAME SHEET.**
        # Without the counterfactual the walk only shows a notice firing, which
        # proves nothing about the fault: the fault is that it fired too LATE.
        # Same inequality, same measured top margin, same tolerance, the only
        # difference being which reach goes in.
        # **THE PANEL'S OWN ANCHOR, NOT ONE RECOMPUTED HERE.** The first
        # version worked the anchor out from "T" with `edge_reserve_mm`, which
        # is only half of what `geometry.strip_label_leader_top_mm` does: the
        # strip-indicator gap and the chart offset Y are in the real one. The
        # two disagreed, so the counterfactual printed "would have been SILENT"
        # on rows where the panel had in fact fired.
        from workflow import text_edge_fit as _tef3
        from workflow.layout_engine import geometry as _geo3
        _top = float(row["measured"]["top_mm"])
        _tol = _tef3.edge_tolerance_mm(dpi)
        _anchor = float(_geo3.strip_label_leader_top_mm(g))
        would = (_anchor + then) > (_top + _tol)
        # **AND HOW MANY STRIPS THIS CHART HAS, which is what decides whether
        # the fix can show anything here at all.** "Q" is the seventeenth
        # label; on a chart with fewer strips the new probe and the old one
        # give the same answer by design, and the walk is a control rather than
        # a demonstration.
        _strips = strips_on(g, _kw_walk)
        walk.append({"T_mm": t, "measured_top_mm": _top,
                     "strips_on_this_chart": _strips,
                     "a_Q_is_printed": _strips >= 17,
                     "reach_now_mm": round(now, 3),
                     "reach_with_W8_probe_mm": round(then, 3),
                     "the_Q_is_worth_mm": round(now - then, 3),
                     "letters_reach_mm": round(_anchor + now, 3),
                     "W8_would_have_said_mm": round(_anchor + then, 3),
                     "tolerance_mm": round(_tol, 3),
                     "notice_fired": fired,
                     "notice_would_have_fired_with_W8": would})
        print(f"    [T {t}] letters reach {_anchor + now:.3f} mm vs patches at "
              f"{_top:.2f}; fired={fired}; {_strips} strips"
              f"{' (a Q is printed)' if _strips >= 17 else ' (no Q on this chart)'}"
              f"; with the old probe it would "
              f"{'also have fired' if would else 'have been SILENT'}",
              flush=True)
    (out / "case2-T-walk.json").write_text(
        json.dumps(walk, indent=2), encoding="utf-8")

    (out / "panel-notices.json").write_text(
        json.dumps({"window_on_screen": on_screen,
                    "window": f"{geo.width()}x{geo.height()}",
                    "crashes": crashes, "cases": rows},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n    wrote {out / 'panel-notices.json'}", flush=True)
    if crashes:
        print(f"    !! {len(crashes)} unhandled exception(s) in the app",
              flush=True)
    win.close()
    pump(app, 400)
    return 1 if crashes else 0


if __name__ == "__main__":
    raise SystemExit(main())
