#!/usr/bin/env python3
"""Every built-in Create Chart preset against the new margin and text rules.

Knut, #182, comment 5651302602 (EDITED):

    "Test the new margin and text rules on all built-in presets (except the
     "by pharmacist" presets), in order to check if the presets behave well
     with the new rules."

    "Make a new beta with all remaining text and margin modifications and make
     sure all parameters change text positions and that warnings come on
     overlap with patch area on all sides. Make sure also that the centring of
     bottom text and the vertical centring of left and right clip-border text
     works correctly for the different parameters that drive the to and from
     measurement to centre between, and check that text does not overlap with
     helper markers or clip-border area (when on)."

So the table this writes has, for every preset, two halves that must agree:

* **what the sheet does** -- does any of the four texts land on the patch
  area, on a helper-marker dash, or on the clip border;
* **what the panel says** -- the red overlap notices in the "Measured from
  Preview" frame.

A row where the sheet overlaps and the panel is silent is a fault. A row where
the panel warns and the sheet is clean is the same fault the other way up, and
this project has shipped that one twice.

CALL PATH. Every number here comes from the app's own route, and the driver
stops it one instruction before the raster rather than re-deriving anything:

    the real Presets dropdown (activated, the way a person picks)
      -> ui.tabs.tab_chart.TabChart._collect_manual()        -> ChartParams
      -> workflow.chart_creator.ChartCreator._engine_kwargs  -> the build kwargs
      -> workflow.layout_engine.chart.build_chart            -> the REAL geom
      -> (intercepted at raster.render_pages, which is handed geom + layout)

`chart.build_chart` assembles its geometry dict BY HAND and it is not
`LayoutRecipe.build_kwargs()`: the two have disagreed before, and the whole of
#182's helper-marker reserve once reached every estimate and no sheet at all
because of it. Intercepting `render_pages` is the only way to be certain the
geometry measured is the geometry drawn.

The panel's half is read by wrapping `MarginInspectorPanel.update_report`, so
it is the app's own arguments and not a re-derivation of them.

Usage::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-sweep.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-sweep-presets
    python scripts/drive_182_preset_text_overlap_sweep.py --out DIR [--limit N]
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

from PyQt6.QtCore import QTimer                                    # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox     # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                          # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

WORK = Path("/tmp/chromiq-sweep-work")

#: Knut's own exclusion, matched on the dropdown label the user reads.
EXCLUDE = "by pharmacist"

#: The one element this sweep's geometry analyser cannot see. See the note at
#: the verdict below.
_NOTE_PHRASE = "chart notes down the right edge"

modals: list[dict] = []
_timers: list = []


def pump(app, ms: int = 200) -> None:
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
        except Exception:                                      # noqa: BLE001
            w.close()
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


class _Stop(Exception):
    """Raised inside the intercepted renderer, carrying the real geometry."""

    def __init__(self, target, layout, geom, kwargs):
        super().__init__("geometry captured")
        self.target, self.layout, self.geom, self.kwargs = (
            target, layout, geom, kwargs)


def _synth_ti1(path: Path, n: int) -> Path:
    lines = ["CTI1", "", 'DESCRIPTOR "sweep"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7",
             "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
             "END_DATA_FORMAT", f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        lines.append(f"{i+1} {(i*37)%101}.0 {(i*71)%101}.0 {(i*13)%101}.0 "
                     "40.0 45.0 50.0")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def analyse(geom, layout, kw, w_mm: float, h_mm: float) -> dict:
    """Where every text lands, in mm, from the geometry the renderer was given.

    Each figure names the function that produced it, because a number without
    its call path cannot be checked by the next reader.
    """
    from workflow import text_edge_fit as tef
    from workflow.layout_engine import geometry, raster

    place = geometry.placement(geom, w_mm, h_mm, layout)
    edge = geom.pspa if (geom.edge_spacers and geom.pspa > 0) else 0.0
    patch_top = place.y_of(0) - edge
    steps = layout.steps_in_pass
    n_first = min(layout.total_patches, layout.patches_per_page)
    rows0 = min(steps, n_first) if steps else 0
    n_passes = (n_first + steps - 1) // steps if steps else 0
    patch_bottom = place.y_of(max(0, rows0 - 1)) + geom.plen + edge
    patch_left = place.x_of(0)
    patch_right = place.x_of(max(0, n_passes - 1)) + geom.pwid

    out: dict = {
        "paper_mm": [round(w_mm, 1), round(h_mm, 1)],
        "patch_area_mm": {"top": round(patch_top, 2),
                          "bottom": round(patch_bottom, 2),
                          "left": round(patch_left, 2),
                          "right": round(patch_right, 2)},
        "margins_are_law": bool(geom.margins_are_law),
        "hits": [],
    }

    def hit(what: str, over_mm: float, detail: str) -> None:
        if over_mm > tef.EPS_MM:
            out["hits"].append({"what": what, "by_mm": round(over_mm, 2),
                                "detail": detail})

    markers = bool(getattr(geom, "helper_markers", False))
    m_edge = float(getattr(geom, "helper_marker_edge_mm", 0.0) or 0.0)
    m_len = float(getattr(geom, "helper_marker_len_mm", 0.0) or 0.0)
    m_tb = bool(getattr(geom, "helper_markers_top_bottom", True))
    m_sd = bool(getattr(geom, "helper_markers_sides", True))
    # The dash's own ink, which is a SHORTER distance than the reserve: the
    # reserve is edge + length + 1.0 mm and the ink stops at edge + length.
    dash_end = (m_edge + m_len) if markers else 0.0
    out["helper_markers"] = {"on": markers, "edge_mm": m_edge,
                             "len_mm": m_len, "top_bottom": m_tb,
                             "sides": m_sd,
                             "dash_ink_ends_mm": round(dash_end, 2)}

    # ---- 1. the strip letters (geometry.placement + Geom.label_ink_bottom_mm)
    if kw.get("draw_indicators", True) and getattr(geom, "label_ink_bottom_mm", 0.0) > 0:
        lbl_top = place.leader_top + float(kw.get("strip_label_offset_mm") or 0.0)
        lbl_bottom = place.leader_top + float(geom.label_ink_bottom_mm)
        out["strip_letters_mm"] = {"top": round(lbl_top, 2),
                                   "bottom": round(lbl_bottom, 2),
                                   "reserve": round(
                                       geometry.strip_label_reserve_mm(geom), 2)}
        hit("strip letters over the patch area", lbl_bottom - patch_top,
            f"the band ends {lbl_bottom:.2f} mm down, the patches start at "
            f"{patch_top:.2f} mm")
        if markers and m_tb:
            hit("strip letters on the top marker dashes", dash_end - lbl_top,
                f"the band starts {lbl_top:.2f} mm down, the dashes end at "
                f"{dash_end:.2f} mm")

    # ---- 2. the bottom sheet text (text_edge_fit + raster.sheet_text_width_mm)
    lines = [t for t in (kw.get("chart_text") or "",
                         "stamp" if kw.get("stamp_command") else "") if t]
    if lines:
        size_mm = float(kw.get("chart_text_size_mm") or 0.0)
        fam = str(kw.get("chart_text_font") or "")
        bold = bool(kw.get("chart_text_bold"))
        ital = bool(kw.get("chart_text_italic"))
        dpi = float(kw.get("dpi") or 300)
        line_mm = raster.sheet_text_line_mm(size_mm, fam, bold, ital, dpi)
        bot = tef.sheet_text_bottom_mm(
            float(kw.get("text_edge") or 0.0), markers, m_edge, m_len, m_tb)
        clip_w = float(geom.lbord + geom.border) if geom.lbord > 0 else 0.0
        lo, hi = tef.bottom_text_bounds_mm(
            w_mm, float(getattr(geom, "text_edge_clip_mm", 0.0) or 0.0),
            markers, m_edge, m_len, m_sd,
            clip_border_mm=clip_w,
            clip_side=str(getattr(geom, "clip_side", "left") or "left"))
        need_w = raster.sheet_text_width_mm(lines, size_mm or 3.2, fam, bold,
                                            ital, dpi)
        block_top = h_mm - bot - line_mm * len(lines)
        out["bottom_text_mm"] = {
            "bounds": [round(lo, 2), round(hi, 2)],
            "centre": round((lo + hi) / 2.0, 2),
            "needs_mm": round(need_w, 2), "room_mm": round(hi - lo, 2),
            "block_top": round(block_top, 2),
            "reserve_from_bottom": round(bot, 2)}
        hit("the bottom line over the patch area", patch_bottom - block_top,
            f"the block starts {block_top:.2f} mm down, the patches end at "
            f"{patch_bottom:.2f} mm")
        hit("the bottom line too wide for its bounds", need_w - (hi - lo),
            f"it needs {need_w:.2f} mm and the bounds leave {hi - lo:.2f} mm")
        if markers and m_tb:
            hit("the bottom line on the bottom marker dashes",
                dash_end - bot,
                f"it is held {bot:.2f} mm up and the dashes reach "
                f"{dash_end:.2f} mm")

    # ---- 3. the clip band (geometry.clip_area_mm)
    if geom.lbord > 0 and str(kw.get("clip_content_mode", "off")) != "off":
        n_lines = 0
        if str(kw.get("clip_content_mode")) == "text":
            n_lines = len(raster.clip_text_lines(kw.get("clip_text") or ""))
        pt = float(kw.get("clip_text_size_mm") or 0.0) * 72.0 / 25.4
        area = geometry.clip_area_mm(geom, h_mm, w_mm, n_lines, pt)
        if area is not None:
            x, y, aw, ah = area
            band = tef.side_text_band_mm(
                h_mm, getattr(geom, "text_edge_top_mm", 0.0),
                getattr(geom, "text_edge_bottom_mm", 0.0),
                helper_markers=markers, marker_edge_mm=m_edge,
                marker_len_mm=m_len, marker_top_bottom=m_tb)
            out["clip_band_mm"] = {
                "x": round(x, 2), "y": round(y, 2),
                "w": round(aw, 2), "h": round(ah, 2),
                "wanted_y": round(band[0], 2), "wanted_h": round(band[1], 2)}
            hit("the clip band is not on its centring bounds",
                abs(y - band[0]) + abs(ah - band[1]),
                f"it is at y {y:.2f} h {ah:.2f}, the bounds ask for y "
                f"{band[0]:.2f} h {band[1]:.2f}")
            right = str(getattr(geom, "clip_side", "left") or "left") == "right"
            if right:
                hit("the clip text over the patch area", patch_right - x,
                    f"the band's inner edge is at {x:.2f} mm and the patches "
                    f"end at {patch_right:.2f} mm")
            else:
                hit("the clip text over the patch area",
                    (x + aw) - patch_left,
                    f"the band reaches {x + aw:.2f} mm and the patches start "
                    f"at {patch_left:.2f} mm")
            if markers and m_sd:
                hit("the clip text on the side marker dashes",
                    dash_end - (x if not right else w_mm - (x + aw)),
                    f"the band starts {x:.2f} mm in and the dashes end at "
                    f"{dash_end:.2f} mm")

    return out


def main() -> int:                                             # noqa: C901
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-sweep-proof")
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) \
        if "--limit" in sys.argv else 0
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    print(f"00 screen locked: {locked}", flush=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    settings = AppSettings()
    WORK.mkdir(parents=True, exist_ok=True)
    settings.set("custom_output_path", str(WORK))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    sandbox = {"settings_file": os.environ["CHROMIQ_SETTINGS_FILE"],
               "presets_dir": os.environ["CHROMIQ_PRESETS_DIR"],
               "custom_output_path": settings.get("custom_output_path", "")}
    print(f"00 sandbox: {sandbox}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.margin_inspector_panel import MarginInspectorPanel
    from ui.theme import apply_appearance
    from ui.tabs.tab_chart import BUILTIN_PRESET_GROUPS, TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    seen: dict = {}
    _orig = MarginInspectorPanel.update_report

    def _spy(self, report, violations, **kw):
        seen.clear()
        seen.update({
            "has_report": report is not None,
            "violations": [f"{v.edge} {v.measured_mm:.1f}<{v.threshold_mm:.1f}"
                           for v in violations],
            "thresholds_defined": bool(kw.get("thresholds_defined")),
            "notify": bool(kw.get("notify")),
            "text_warnings": list(kw.get("text_warnings") or []),
            "overlap_warnings": list(kw.get("overlap_warnings") or []),
        })
        return _orig(self, report, violations, **kw)

    MarginInspectorPanel.update_report = _spy         # type: ignore[assignment]

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    install_modal_watchdog(app)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"00 window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    from workflow.chart_creator import ChartCreator
    from workflow.layout_engine import chart as le_chart
    from workflow.layout_engine import papers, raster

    _real_render = raster.render_pages

    def _intercept(target, layout, geom, **kwargs):
        raise _Stop(target, layout, geom, kwargs)

    combo = tab._preset_combo
    todo = [(instr, label, key)
            for instr, entries in BUILTIN_PRESET_GROUPS
            for (label, _o, key) in entries
            if EXCLUDE not in label.lower()]
    skipped = [label for _i, entries in BUILTIN_PRESET_GROUPS
               for (label, _o, _k) in entries if EXCLUDE in label.lower()]
    if limit:
        todo = todo[:limit]
    print(f"    {len(todo)} built-in presets to sweep, "
          f"{len(skipped)} skipped by his exclusion\n", flush=True)

    rows: list[dict] = []
    ti1_dir = WORK / "_ti1"
    ti1_dir.mkdir(parents=True, exist_ok=True)
    # `build_chart` writes its .ti2 beside the stem BEFORE it renders, so the
    # folder has to exist even though the render is intercepted.
    (WORK / "_out").mkdir(parents=True, exist_ok=True)

    for n, (instr, label, key) in enumerate(todo, 1):
        idx = combo.findData(key)
        row: dict = {"n": n, "group": instr, "preset": label, "key": key}
        if idx < 0:
            row["error"] = "not in the dropdown"
            rows.append(row)
            print(f"    [{n:3d}] {label[:56]:<56} NOT IN THE DROPDOWN",
                  flush=True)
            continue
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText(f"Sweep{n:03d}")
        pump(app, 120)
        seen.clear()
        tab._margin_ti2 = None
        combo.setCurrentIndex(idx)
        combo.activated.emit(idx)                    # the way a person picks
        pump(app, 250)
        for _ in range(200):
            pump(app, 120)
            if getattr(tab, "_margin_ti2", None) and seen:
                break
        pump(app, 400)

        row["panel_status"] = tab._margin_panel.status_message()
        allw = list(seen.get("overlap_warnings") or [])
        row["panel_overlap_warnings"] = allw
        row["panel_text_warnings"] = list(seen.get("text_warnings") or [])
        # THE RIGHT-EDGE CHART NOTE IS NOT ON THIS ANALYSER'S LIST, and saying
        # "the sheet is clean" while the panel warns about it would be a false
        # disagreement. The note is stamped by `workflow/tiff_metadata.py` over
        # a FINISHED raster, using a white band it detects in the pixels; there
        # is no figure in `geometry` that predicts it, so the only honest way
        # to measure it is to render the page, which this sweep does not do.
        # It is reported in its own column instead of being scored.
        row["panel_note_warnings"] = [w for w in allw if _NOTE_PHRASE in w]
        row["panel_says_overlap"] = bool([w for w in allw
                                          if _NOTE_PHRASE not in w])

        try:
            params = tab._collect_manual()             # the app's own params
            import types as _t
            ns = _t.SimpleNamespace(_threshold_notes=[], _settings=settings)
            kw = ChartCreator._engine_kwargs(ns, params)
            row["instrument"] = kw.get("instrument")
            row["paper"] = kw.get("paper")
            npat = int(getattr(params, "patches", 0) or 0)
            src = getattr(tab, "_margin_ti2", None)
            if src and Path(src).exists():
                ti1 = Path(src)
                row["patch_source"] = "the tab's own preview .ti2"
            else:
                npat = npat if npat > 0 else 200
                ti1 = _synth_ti1(ti1_dir / f"p{n:03d}.ti1", npat)
                row["patch_source"] = f"a synthetic .ti1 of {npat} patches"
            raster.render_pages = _intercept          # stop before the raster
            try:
                le_chart.build_chart(ti1, WORK / "_out" / f"p{n:03d}", **kw)
                row["error"] = "the renderer was never reached"
            except _Stop as st:
                w_mm, h_mm = papers.dimensions_mm(kw.get("paper") or "A4")
                row["measured"] = analyse(st.geom, st.layout, st.kwargs,
                                          w_mm, h_mm)
                row["patches"] = int(st.layout.total_patches)
                row["pages"] = int(st.layout.pages)
            finally:
                raster.render_pages = _real_render
        except Exception as exc:                       # noqa: BLE001
            raster.render_pages = _real_render
            row["error"] = f"{type(exc).__name__}: {exc}"

        m = row.get("measured") or {}
        hits = m.get("hits") or []
        row["sheet_has_overlap"] = bool(hits)
        row["hit_names"] = [h["what"] for h in hits]
        if row.get("error"):
            row["verdict"] = "COULD NOT MEASURE"
        elif hits and row["panel_says_overlap"]:
            row["verdict"] = "overlap, and the panel says so"
        elif hits and not row["panel_says_overlap"]:
            row["verdict"] = "OVERLAP, PANEL SILENT"
        elif not hits and row["panel_says_overlap"]:
            row["verdict"] = "PANEL WARNS, SHEET CLEAN"
        else:
            row["verdict"] = "clean"
        rows.append(row)
        print(f"    [{n:3d}/{len(todo)}] {label[:52]:<52} {row['verdict']}"
              + (f"  <- {', '.join(row['hit_names'])}" if hits else ""),
              flush=True)
        (out / "preset-text-overlap-sweep.json").write_text(
            json.dumps({"sandbox": sandbox, "screen_locked": locked,
                        "skipped_by_his_exclusion": skipped, "rows": rows},
                       indent=1, ensure_ascii=False), encoding="utf-8")

    ok, why = capture_window(win, out / "sweep-window.png")
    print(f"\n99 capture: {'OK' if ok else 'REFUSED - ' + why}", flush=True)

    tally: dict[str, int] = {}
    for r in rows:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    print("\n    ---- tally ----")
    for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"    {v:4d}  {k}")

    # A plain-text table, because that is what the report carries.
    lines = ["| # | preset | paper | patches | text over the patch area, "
             "the markers or the clip border | the panel | the right-edge "
             "note |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        what = "; ".join(r.get("hit_names") or []) or "none"
        says = ("yes" if r.get("panel_says_overlap") else "silent")
        note = ("warned" if r.get("panel_note_warnings") else "-")
        lines.append(f"| {r['n']} | {r['preset']} | {r.get('paper','')} | "
                     f"{r.get('patches','')} | {what} | {says} | {note} |")
    (out / "preset-text-overlap-sweep.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    win.close()
    pump(app, 500)
    print(f"\nwrote {out / 'preset-text-overlap-sweep.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
