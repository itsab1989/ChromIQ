#!/usr/bin/env python3
"""Knut's beta 15 bottom-text case, in the REAL Create Chart tab.

Knut, 2026-09-14, on the preset
`CR30-Letter-792p-2pages-Portrait-w11.0mm-Hexagonal-Straight` with a custom
Sheet text, Size = auto and the left-margin alignment::

    When bottom margin is 11.0mm there is a warning ... You can clearly see
    that there is ample space both on top and below the bottom text line, so
    the warning should not happen. Measurements are obviously calculated wrong.
    Bottom margin in Measured from Preview shows 12.8mm.

    It also seems that the bottom text is not shrunk while in size = auto ...
    This means that the size = auto setting should shrink size when the height
    or width comes close to its limits.

This drives his preset for real, sweeps the bottom margin, and for every value
records BOTH numbers that matter and then measures the sheet:

* what the panel says, verbatim;
* the REQUESTED bottom margin and the MEASURED one, off the app's own margin
  inspector (`measure_from_engine`, the exact patch rectangles);
* where the text block is, computed the way `render_pages` places it;
* and the INK: the last patch row, the text's own rows and the helper markers,
  read off the rendered TIFF by run length, because a hexagon row is a few long
  runs and a line of type is many short ones.

**THE INK IS THE ARBITER.** The panel's height check and the engine's furniture
reserve are two pieces of arithmetic about the same paper, and Knut's complaint
is that they disagree with the picture. Only the picture settles it.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-bt.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-bt-presets \\
        python scripts/drive_182_knut_bottom_text_height.py <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
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

PRESET = "__chromiq_knut_cr30_letter_792p_2pages_portrait_w11_0mm_hexagonal_straight__"
#: His own three values, plus the ones around them.
MARGINS = (7.5, 9.0, 10.0, 11.0, 11.5, 13.0, 16.0)
TEXT = "test-{project}-page {page}-{date}-{paper}-{instrument}-{patchcount} patches-{pages}-seed {seed}-{dpi} dpi"


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def text_ink_mm(recipe, ti1: Path, tag: str) -> dict:
    """Where the bottom text's own ink lands, and where the patches stop.

    **TWO RENDERS WITH THE GEOMETRY PINNED.** The off-pass keeps `chart_text`
    at a single SPACE, which is truthy, so `nlines` stays 1, the bottom reserve
    and every patch size are identical, and a space draws nothing. The
    difference is then the line's own ink and nothing else. Run-length tricks
    were tried first and merged the type with the last row of hexagons, which
    is how three earlier probes on this project produced confident wrong
    numbers.

    The patch area's bottom comes from the app's OWN patch rectangles, not from
    the picture: `ChartResult.strip_rects` is what the margin inspector reads.
    """
    from dataclasses import replace

    import numpy as np
    from PIL import Image
    from workflow.layout_engine.chart import build_from_recipe

    def render(text, suffix):
        base = Path(tempfile.mkdtemp(prefix=f"bt-{tag}-{suffix}-"))
        res, used = build_from_recipe(
            str(ti1), str(base / "s"),
            replace(recipe, chart_text=text, randomize=True,
                    seed_fixed=True, seed=123456789))
        page = sorted(base.glob("s*.tif"))[0]
        return np.asarray(Image.open(page).convert("L")).astype(np.int16), res

    on, res = render(recipe.chart_text, "on")
    off, _r2 = render(" ", "off")
    dpi = float(getattr(recipe, "dpi", 200) or 200)
    mm = lambda px: round(float(px) * 25.4 / dpi, 2)             # noqa: E731
    out = {"paper_h_mm": mm(on.shape[0])}
    if on.shape != off.shape:
        out["error"] = "the geometry moved between the two renders"
        return out
    diff = np.abs(on - off) > 30
    rows = np.where(diff.any(axis=1))[0]
    if rows.size:
        out["text_top_up_mm"] = mm(on.shape[0] - int(rows[0]))
        out["text_bottom_up_mm"] = mm(on.shape[0] - int(rows[-1]) - 1)
        out["text_ink_height_mm"] = mm(int(rows[-1]) + 1 - int(rows[0]))
    # the patch area's own bottom, from the rectangles the app records
    rects = [r for r in (res.strip_rects or []) if int(r.get("page", 0)) == 0]
    if rects:
        y1 = max(int(r["y"]) + int(r["h"]) for r in rects)
        out["patch_bottom_up_mm"] = mm(on.shape[0] - y1)
        if "text_top_up_mm" in out:
            out["gap_patches_to_text_mm"] = round(
                out["patch_bottom_up_mm"] - out["text_top_up_mm"], 2)
    return out


def predicted_patch_bottom_mm(recipe, geom, npat: int) -> "float | None":
    """Where the patch area will stop, from the SAME functions the renderer
    uses, with no chart built.

    The measured report cannot answer this while a spin box is being edited:
    it describes the chart already in the preview, and its `bottom_mm` was
    **10.29 mm for every one of seven different bottom margins** in this
    driver's own run. A prediction has to come from the recipe on screen.
    """
    from workflow.layout_engine import geometry, papers
    try:
        w, h = papers.dimensions_mm(recipe.paper)
        lay = geometry.compute(geom, w, h, max(1, int(npat)))
        pl = geometry.placement(geom, w, h, lay)
        last = (pl.y0_first + (lay.steps_in_pass - 1) * (pl.plen + pl.pspa)
                + pl.plen)
        return round(h - last, 2)
    except Exception as exc:                                  # noqa: BLE001
        return None


def on_screen(tab) -> list:
    """The bottom-text notices the WINDOW is showing, not the ones a function
    would answer if asked again.

    `_engine_text_notes` is called by `_update_margin_inspector` with the
    measured report; calling it again from a driver with no report asks a
    different question and gets a different answer, which is how a probe ends
    up agreeing with itself.
    """
    panel = getattr(tab, "_margin_panel", None)
    last = getattr(panel, "_last_status", None) if panel is not None else None
    if not last:
        return []
    msgs = [m for m in (last[1].get("overlap_warnings") or [])
            if "along the bottom" in m]
    # THE TWO BOTTOM WARNINGS ARE DIFFERENT QUESTIONS and must not be counted
    # together: one is about the line's HEIGHT against the patches, the other
    # about its WIDTH against the paper. Lumping them made every row of the
    # first sweep read "warn=1" whatever the height check said.
    return {"height": [m for m in msgs if "runs into the patches" in m
                       or "run into the patches" in m],
            "width": [m for m in msgs if "too wide for the paper" in m]}


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-bt-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    from ui.theme import apply_appearance
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    # WHAT THE CHECK IS REALLY GIVEN. The panel calls `_engine_text_notes`
    # with the measured report; this records the report it was handed so the
    # driver can quote the same numbers the check used.
    _seen: dict = {}
    _orig_notes = TabChart._engine_text_notes

    def _notes(self, report=None):
        _seen["bottom_mm"] = getattr(report, "bottom_mm", None)
        _seen["page_h_mm"] = getattr(report, "page_h_mm", None)
        _seen["has_report"] = report is not None
        return _orig_notes(self, report)
    TabChart._engine_text_notes = _notes            # type: ignore[assignment]

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    win.raise_()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)

    combo = tab._preset_combo
    i = combo.findData(PRESET)
    assert i >= 0, "his preset is not in the dropdown"
    if tab._manual_target_name_edit is not None:
        tab._manual_target_name_edit.setText("test")
    pump(app, 300)
    combo.setCurrentIndex(i)
    combo.activated.emit(i)
    pump(app, 1500)
    for _ in range(400):
        pump(app, 120)
        if getattr(tab, "_margin_ti2", None) and getattr(tab, "_margin_tiffs", None):
            break
    pump(app, 800)
    panel = tab._manual_layout_panel
    r0 = panel.get_recipe()
    print(f"    preset: {combo.currentText()[:70]}", flush=True)
    print(f"    layout_mode={r0.layout_mode} dpi={r0.dpi} paper={r0.paper} "
          f"markers={r0.helper_markers} edge={r0.helper_marker_edge_mm} "
          f"len={r0.helper_marker_len_mm} B={r0.text_edge_mm}", flush=True)
    if panel.use_instr_margins.isChecked():
        panel.use_instr_margins.setChecked(False)
        pump(app, 400)
    panel.chart_text.setText(TEXT)
    panel.stamp_command.setChecked(False)
    panel.chart_text_size.setValue(0.0)          # auto
    pump(app, 600)

    ti1 = None
    for attr in ("_preset_ti1_path", "_builtin_ti1_path"):
        v = getattr(tab, attr, None)
        if v and Path(v).is_file():
            ti1 = Path(v)
            break
    assert ti1 is not None, "no .ti1 to render from"

    from workflow import text_edge_fit as tef
    from workflow.layout_engine import instruments, raster
    from workflow.layout_engine.chart import build_from_recipe
    from dataclasses import replace as _replace

    rows = []
    for mb in MARGINS:
        panel.margins["b"].setValue(float(mb))
        pump(app, 700)
        tab._update_margin_inspector()
        pump(app, 900)
        r = panel.get_recipe()
        kw = r.build_kwargs()
        geom = raster.apply_furniture_reserves(
            instruments.geom_from_build_kwargs(kw), kw)
        said = on_screen(tab)
        # WHAT THE RENDERER WILL DO, in its own terms
        nlines = len(tab._bottom_sheet_text_lines(r))
        line_mm = raster.sheet_text_line_mm(
            r.chart_text_size_mm, r.chart_text_font, r.chart_text_bold,
            r.chart_text_italic, r.dpi)
        bot_res = tef.sheet_text_bottom_mm(
            float(r.text_edge_mm or 0.0), bool(r.helper_markers),
            float(r.helper_marker_edge_mm or 0.0),
            float(r.helper_marker_len_mm or 0.0),
            bool(r.helper_markers_top_bottom))
        # …and the sheet itself, built the way Generate builds it
        ink = text_ink_mm(r, ti1, f"m{mb:g}")
        # the app's OWN margin inspector on that chart
        measured = ink.get("patch_bottom_up_mm")
        _npat = (tab._onscreen_patch_total() or tab._estimate_patch_total()
                 or 792)
        row = {
            "requested_bottom_margin_mm": mb,
            "predicted_patch_bottom_mm": predicted_patch_bottom_mm(
                r, geom, _npat),
            "report_bottom_mm": _seen.get("bottom_mm"),
            "report_seen": _seen.get("has_report"),
            "geom_margin_b_mm": round(float(geom.margin_b or 0.0), 2),
            "bottom_reserve_mm": round(float(
                getattr(geom, "bottom_reserve_mm", 0.0) or 0.0), 2),
            "measured_bottom_mm": measured,
            "text_reserve_from_edge_mm": round(bot_res, 2),
            "line_box_mm": round(line_mm, 2),
            "block_needs_mm": round(bot_res + nlines * line_mm, 2),
            "panel_said": said,
            "ink": ink,
        }
        rows.append(row)
        print(f"    margin {mb:5.1f}  predicted="
              f"{row['predicted_patch_bottom_mm']}"
              f"  measured {ink.get('patch_bottom_up_mm')}"
              f"  text {ink.get('text_top_up_mm')}.."
              f"{ink.get('text_bottom_up_mm')} (h "
              f"{ink.get('text_ink_height_mm')})  gap "
              f"{ink.get('gap_patches_to_text_mm')}  "
              f"height-warn={len(said['height'])} "
              f"width-warn={len(said['width'])}", flush=True)

    # A TYPED SIZE BIG ENOUGH TO REALLY COLLIDE, so the verdict below has a
    # positive case to prove and is not merely "nothing ever collided".
    panel.margins["b"].setValue(11.0)
    for pt in (7.0, 14.0, 28.0, 48.0):
        panel.chart_text_size.setValue(float(pt))
        pump(app, 700)
        tab._update_margin_inspector()
        pump(app, 700)
        r = panel.get_recipe()
        said = on_screen(tab)
        ink = text_ink_mm(r, ti1, f"pt{pt:g}")
        rows.append({"requested_bottom_margin_mm": 11.0, "typed_size_pt": pt,
                     "panel_said": said, "ink": ink,
                     "measured_bottom_mm": None})
        print(f"    size {pt:5.1f} pt  text "
              f"{ink.get('text_top_up_mm')}..{ink.get('text_bottom_up_mm')} "
              f"gap above {ink.get('gap_patches_to_text_mm')}  "
              f"height-warn={len(said['height'])} "
              f"width-warn={len(said['width'])}", flush=True)
    panel.chart_text_size.setValue(0.0)
    pump(app, 500)

    shot = out / "01-create-chart-bottom-text.png"
    ok, why = capture_window(win, shot)
    print(f"    photo: {'ok' if ok else 'REFUSED: ' + str(why)}", flush=True)

    def warned(row):
        return bool(row["panel_said"]["height"])

    def really_collides(row):
        g = row["ink"].get("gap_patches_to_text_mm")
        return g is not None and g < 0

    sweep = [r for r in rows if "typed_size_pt" not in r]
    typed = [r for r in rows if "typed_size_pt" in r]
    verdicts = {
        # …over the MARGIN SWEEP, where the size is fixed at auto. A typed size
        # moves the text on purpose, so including those rows here would make
        # the claim false for the right reason.
        "the text never moves when only the bottom margin moves": len({
            r["ink"].get("text_top_up_mm") for r in sweep
            if r["ink"].get("text_top_up_mm") is not None}) == 1,
        "no sheet in the margin sweep has the patches touching the text":
            not any(really_collides(r) for r in sweep),
        "a big enough typed size really does collide": any(
            really_collides(r) for r in typed),
        "the prediction agrees with the rendered sheet": all(
            abs(r["predicted_patch_bottom_mm"]
                - r["ink"]["patch_bottom_up_mm"]) <= 0.1
            for r in sweep
            if r.get("predicted_patch_bottom_mm") is not None
            and r["ink"].get("patch_bottom_up_mm") is not None),
        "the panel never warns about a sheet with a clear gap": not [
            r for r in rows if warned(r) and not really_collides(r)],
        "the panel warns about every sheet that really collides": not [
            r for r in rows if really_collides(r) and not warned(r)],
    }
    (out / "bottom-text-height.json").write_text(
        json.dumps({"preset": PRESET, "text": TEXT,
                    "photo": shot.name if ok else f"REFUSED: {why}",
                    "rows": rows, "verdicts": verdicts}, indent=2),
        encoding="utf-8")
    print(json.dumps(verdicts, indent=2), flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    win.close()
    pump(app, 400)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
