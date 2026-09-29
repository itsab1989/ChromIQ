#!/usr/bin/env python3
"""#182 FOURTH CHALLENGE ROUND: the export nobody measured, and the state that survives.

Drives the REAL `MainWindow` on screen, sets every value through the REAL
`LayoutOptionsPanel` widgets, ticks the REAL "Also export a PDF" checkbox and
runs the REAL "Generate Chart" button, then MEASURES THE INK on BOTH artefacts
the app writes: the TIFF, and the vector PDF rendered back to a bitmap at the
same resolution through CoreGraphics.

Every measurement below therefore comes from the app's own call path
(`TabChart._on_generate` -> `ChartCreator` -> `layout_engine.chart.build_chart`
-> `_stamp_tiff_metadata`), never from `LayoutRecipe.build_kwargs()` handed
straight to the engine. That shortcut is what hid a dead rule for three rounds.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-chal4.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-chal4-presets
    python scripts/drive_182_challenge_four.py --out DIR [--only 01,02]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

import numpy as np                                                # noqa: E402
from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                         # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

WORK = Path("/tmp/chromiq-chal4-work")
PROJECT = "Challenge182four"
DPI = 200

CLIP_TEXT = ("clip band line one for the fourth round\n"
             "clip band line two\n"
             "clip band line three")
NOTES = ("run chart notes for the fourth challenge round of issue 182, made "
         "long on purpose so the stamped strip fills the edge it is given and "
         "both of its ends land where the reserve really begins and ends, "
         "which is the whole measurement this sheet exists to make")

modals: list[dict] = []
_timers: list = []
CLAIMS: list[dict] = []


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
        try:
            title = w.windowTitle()
            text = getattr(w, "text", lambda: "")()
        except Exception:                                          # noqa: BLE001
            title, text = "?", ""
        modals.append({"title": title, "text": str(text)[:300]})
        print(f"    !! modal {title!r} -> closed")
        try:
            w.reject()
        except Exception:                                          # noqa: BLE001
            w.close()
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def wait_for_build(app, tab, timeout=900) -> bool:
    end = time.time() + timeout
    pump(app, 800)
    while time.time() < end:
        app.processEvents()
        time.sleep(0.05)
        if tab._generate_btn.isEnabled() and not tab._runner.is_running:
            pump(app, 1500)
            if tab._generate_btn.isEnabled() and not tab._runner.is_running:
                return True
    return False


def claim(name: str, text: str, ok: bool, detail: dict) -> None:
    CLAIMS.append({"demo": name, "claim": text, "demonstrated": bool(ok),
                   **detail})
    print(f"  [{name}] {'DEMONSTRATED' if ok else '*** NOT DEMONSTRATED ***'}"
          f" :: {text}")
    for k, v in detail.items():
        print(f"        {k} = {v}")


# ---------------------------------------------------------------- ink ------

def tiff_gray(path: Path) -> tuple[np.ndarray, float]:
    """Grayscale array + real dpi from the TIFF's own resolution tags."""
    import tifffile
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        arr = np.array(page.asarray())
        dpi = float(DPI)
        try:
            xres = page.tags["XResolution"].value
            dpi = float(xres[0]) / float(xres[1])
            if int(page.tags["ResolutionUnit"].value) == 3:   # centimetre
                dpi *= 2.54
        except Exception:                                      # noqa: BLE001
            pass
    if arr.ndim == 3:
        arr = arr[..., :3].mean(axis=2)
    if arr.dtype == np.uint16:
        arr = (arr / 257.0)
    return arr.astype(np.float64), dpi


def pdf_gray(path: Path, dpi: float = DPI) -> np.ndarray:
    """Render page 1 of *path* to a grayscale array at *dpi*, via CoreGraphics.

    Rendered rather than parsed on purpose: the question this round asks of the
    PDF is what a RIP would actually put on paper, and only a renderer answers
    that. A content-stream parse would report an operator the page never inks.
    """
    import Quartz
    from CoreFoundation import CFURLCreateFromFileSystemRepresentation
    url = CFURLCreateFromFileSystemRepresentation(
        None, str(path).encode("utf-8"), len(str(path).encode("utf-8")), False)
    doc = Quartz.CGPDFDocumentCreateWithURL(url)
    if doc is None:
        raise RuntimeError(f"CoreGraphics could not open {path}")
    page = Quartz.CGPDFDocumentGetPage(doc, 1)
    box = Quartz.CGPDFPageGetBoxRect(page, Quartz.kCGPDFMediaBox)
    scale = dpi / 72.0
    w = int(round(box.size.width * scale))
    h = int(round(box.size.height * scale))
    cs = Quartz.CGColorSpaceCreateDeviceRGB()
    ctx = Quartz.CGBitmapContextCreate(
        None, w, h, 8, w * 4, cs, Quartz.kCGImageAlphaNoneSkipLast)
    Quartz.CGContextSetRGBFillColor(ctx, 1.0, 1.0, 1.0, 1.0)
    Quartz.CGContextFillRect(ctx, Quartz.CGRectMake(0, 0, w, h))
    Quartz.CGContextScaleCTM(ctx, scale, scale)
    Quartz.CGContextDrawPDFPage(ctx, page)
    data = Quartz.CGBitmapContextGetData(ctx)
    buf = data.as_buffer(w * h * 4)
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 4)[..., :3]
    return arr.mean(axis=2).astype(np.float64)


def ink_box(arr: np.ndarray, dpi: float, thresh: float = 200.0,
            x0mm=None, x1mm=None, y0mm=None, y1mm=None) -> dict | None:
    """Bounding box (mm from each page edge) of dark pixels in a window."""
    h, w = arr.shape
    def px(v, n):
        return None if v is None else max(0, min(n, int(round(v * dpi / 25.4))))
    xa, xb = px(x0mm, w) or 0, px(x1mm, w) if x1mm is not None else w
    ya, yb = px(y0mm, h) or 0, px(y1mm, h) if y1mm is not None else h
    sub = arr[ya:yb, xa:xb]
    mask = sub < thresh
    if not mask.any():
        return None
    ys, xs = np.nonzero(mask)
    mm = 25.4 / dpi
    return {
        "top_mm": round((ya + ys.min()) * mm, 3),
        "bottom_from_page_mm": round((h - (ya + ys.max() + 1)) * mm, 3),
        "left_mm": round((xa + xs.min()) * mm, 3),
        "right_from_page_mm": round((w - (xa + xs.max() + 1)) * mm, 3),
        "px": int(mask.sum()),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"screen_locked_at_start": locked, "modals": modals,
                 "claims": CLAIMS, "steps": []}
    print(f"00 screen locked at start: {locked}")

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
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: {os.environ['CHROMIQ_SETTINGS_FILE']} -> {WORK}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1660, 1040)
    win.show()
    pump(app, 1800)
    install_modal_watchdog(app)
    res["window_is_visible"] = bool(win.isVisible())
    print(f"00 real window visible: {win.isVisible()}  "
          f"{win.width()}x{win.height()}")

    shot = out / "00-the-real-window.png"
    got = False
    try:
        got = capture_window(win, shot)
    except Exception as exc:                                       # noqa: BLE001
        res["window_photograph_error"] = repr(exc)
    if isinstance(got, tuple):
        got, why = got
        res["window_photograph_refused_because"] = why
    res["window_photograph"] = str(shot) if got else None
    res["capture_window_succeeded"] = bool(got)
    print(f"00 photograph of the real window: {got} (locked={locked})")

    tab = win._tab_chart
    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 800)
    tab._manual_target_name_edit.setText(PROJECT)
    pump(app, 800)
    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 600)

    from workflow.layout_engine.presets import LayoutRecipe

    BASE = dict(instrument="CM", paper="A4", dpi=DPI,
                layout_mode="area_first", area_method="by_grid",
                area_cols=10, area_rows=12,
                use_instrument_margins=False,
                randomize=False, seed_fixed=True, seed=4242,
                clip_border=False, clip_border_width_mm=24.0,
                clip_side="left", clip_content_mode="text",
                clip_text=CLIP_TEXT, clip_flip_180=False,
                margin_top=20.0, margin_right=10.0,
                margin_bottom=20.0, margin_left=26.0,
                text_edge_top_mm=4.0, text_edge_mm=4.0, text_edge_clip_mm=4.0,
                show_strip_indicators=True, show_row_indicators=True,
                helper_markers=True, helper_marker_edge_mm=4.0,
                helper_marker_len_mm=2.0, helper_marker_per_patch=3,
                helper_markers_top_bottom=True, helper_markers_sides=True,
                chart_text="bottom sheet text {project} {paper}",
                chart_text_size_mm=0.0, clip_text_size_mm=0.0,
                export_pdf=True)

    dst = WORK / PROJECT

    def apply(**over) -> LayoutRecipe:
        r = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(r)
        pump(app, 900)
        tab._update_margin_inspector()
        pump(app, 400)
        return panel.get_recipe()

    def set_notes(on: bool) -> None:
        tab._manual_chart_notes_edit.setText(NOTES if on else "")
        tab._manual_stamp_cmd_check.setChecked(bool(on))
        pump(app, 600)

    def build(tag: str):
        """Click the REAL Generate button; keep the TIFF and the PDF."""
        for t in list(dst.rglob("*.tif")) + list(dst.rglob("*.pdf")):
            t.unlink()
        tab._generate_btn.click()
        ok = wait_for_build(app, tab)
        pump(app, 1500)
        tifs = sorted(dst.rglob("*.tif"))
        pdfs = sorted(dst.rglob("*.pdf"))
        kept: dict = {"ok": ok, "tif": None, "pdf": None}
        if tifs:
            k = out / f"{tag}.tif"
            shutil.copy(tifs[0], k)
            kept["tif"] = k
        if pdfs:
            k = out / f"{tag}.pdf"
            shutil.copy(pdfs[0], k)
            kept["pdf"] = k
        print(f"    build {tag}: ok={ok} tif={bool(tifs)} pdf={bool(pdfs)}")
        return kept

    def want(step: str) -> bool:
        return only is None or step in only

    # =================================================================== 01 ==
    # DOES THE PDF CARRY WHAT THE TIFF CARRIES?
    #
    # The vector PDF is written INSIDE `layout_engine.chart.build_chart`, from
    # the collected display list. The run's chart notes and the command stamp
    # are added AFTERWARDS by `chart_creator._stamp_tiff_metadata`, which is
    # handed `tiffs` and nothing else. So the sheet a RIP receives may not be
    # the sheet the printer receives. Measured rather than reasoned: build one
    # chart with the notes ON and one with them OFF, and compare BOTH outputs.
    if want("01"):
        print("\n== 01 the PDF export against the TIFF, notes ON vs OFF ==")
        apply()
        panel.export_pdf.setChecked(True)
        pump(app, 400)
        set_notes(True)
        a = build("01-notes-on")
        set_notes(False)
        b = build("01-notes-off")
        step: dict = {"step": "01", "notes_on": {}, "notes_off": {}}
        if a["tif"] and b["tif"]:
            ta, dpi_a = tiff_gray(a["tif"])
            tb, dpi_b = tiff_gray(b["tif"])
            step["tiff_dpi"] = [dpi_a, dpi_b]
            step["tiff_changed_px"] = int((np.abs(ta - tb) > 8).sum())
            step["tiff_ink_notes_on"] = ink_box(ta, dpi_a)
            step["tiff_ink_notes_off"] = ink_box(tb, dpi_b)
            claim("01a", "the run's chart notes change the TIFF",
                  step["tiff_changed_px"] > 0,
                  {"pixels_that_differ": step["tiff_changed_px"]})
        if a["pdf"] and b["pdf"]:
            pa = pdf_gray(a["pdf"])
            pb = pdf_gray(b["pdf"])
            step["pdf_shape"] = list(pa.shape)
            step["pdf_changed_px"] = int((np.abs(pa - pb) > 8).sum())
            step["pdf_ink_notes_on"] = ink_box(pa, DPI)
            step["pdf_ink_notes_off"] = ink_box(pb, DPI)
            claim("01b",
                  "the run's chart notes reach the PDF the same way they "
                  "reach the TIFF",
                  step["pdf_changed_px"] > 0,
                  {"pdf_pixels_that_differ": step["pdf_changed_px"],
                   "tiff_pixels_that_differ": step.get("tiff_changed_px")})
        res["steps"].append(step)
        print(json.dumps(step, indent=2, default=str))

    # =================================================================== 02 ==
    # THE FOUR EDGES, TIFF AGAINST PDF, ELEMENT BY ELEMENT.
    #
    # Same sheet, both artefacts, ink measured in the same windows. If #182's
    # text placement is real it is real on both; a difference here is a chart
    # that prints one way and RIPs another.
    if want("02"):
        print("\n== 02 the same sheet's ink, TIFF against PDF ==")
        apply()
        panel.export_pdf.setChecked(True)
        pump(app, 400)
        set_notes(False)
        c = build("02-plain")
        step = {"step": "02"}
        if c["tif"] and c["pdf"]:
            t, dpi_t = tiff_gray(c["tif"])
            p = pdf_gray(c["pdf"])
            step["tiff_shape"], step["pdf_shape"] = list(t.shape), list(p.shape)
            step["tiff_dpi"] = dpi_t
            # Whole-page ink, then the four edge bands where #182's text lives.
            windows = {
                "whole_page": {},
                "top_band_0_to_20mm": dict(y0mm=0, y1mm=20),
                "bottom_band_last_20mm": dict(y0mm=277, y1mm=297),
                "left_band_0_to_26mm": dict(x0mm=0, x1mm=26),
                "right_band_last_12mm": dict(x0mm=198, x1mm=210),
            }
            for nm, wdw in windows.items():
                step[f"tiff_{nm}"] = ink_box(t, dpi_t, **wdw)
                step[f"pdf_{nm}"] = ink_box(p, DPI, **wdw)
            same = []
            for nm in windows:
                a_, b_ = step[f"tiff_{nm}"], step[f"pdf_{nm}"]
                if a_ is None or b_ is None:
                    same.append((nm, "one side has no ink", a_, b_))
                    continue
                for k in ("top_mm", "bottom_from_page_mm", "left_mm",
                          "right_from_page_mm"):
                    if abs(a_[k] - b_[k]) > 0.6:
                        same.append((nm, k, a_[k], b_[k]))
            step["disagreements_over_0_6mm"] = same
            claim("02", "the PDF places the same ink as the TIFF in every "
                        "edge band", not same, {"disagreements": same})
        res["steps"].append(step)
        print(json.dumps(step, indent=2, default=str))

    # =================================================================== 03 ==
    # STATE THAT SURVIVES A GESTURE A DRIVER DOES NOT MAKE.
    #
    # Switch the instrument away and back, switch the paper away and back,
    # then build. A sheet that differs from one built without the detour is a
    # stale reserve living somewhere across the switch.
    if want("03"):
        print("\n== 03 does a detour through another instrument change the sheet ==")
        apply()
        panel.export_pdf.setChecked(False)
        pump(app, 400)
        set_notes(False)
        ref = build("03-direct")
        # the detour, through the REAL selector widgets
        apply()
        try:
            panel.instr.setCurrentIndex(
                max(0, panel.instr.findData("i1")))
        except Exception as exc:                                   # noqa: BLE001
            print(f"    !! instrument switch failed: {exc!r}")
        pump(app, 900)
        try:
            panel.paper.setCurrentIndex(max(0, panel.paper.findData("A3")))
        except Exception as exc:                                   # noqa: BLE001
            print(f"    !! paper switch failed: {exc!r}")
        pump(app, 900)
        after = apply()          # back to the same recipe the reference used
        det = build("03-after-detour")
        step = {"step": "03",
                "recipe_after_detour": {
                    k: getattr(after, k, None) for k in
                    ("instrument", "paper", "helper_markers",
                     "helper_marker_edge_mm", "helper_marker_len_mm",
                     "text_edge_mm", "text_edge_top_mm", "text_edge_clip_mm",
                     "show_row_indicators", "layout_mode")}}
        if ref["tif"] and det["tif"]:
            ta, da = tiff_gray(ref["tif"])
            tb, db = tiff_gray(det["tif"])
            if ta.shape == tb.shape:
                step["pixels_that_differ"] = int((np.abs(ta - tb) > 8).sum())
            else:
                step["pixels_that_differ"] = "different page size"
            step["ink_direct"] = ink_box(ta, da)
            step["ink_after_detour"] = ink_box(tb, db)
            claim("03", "a detour through another instrument and paper leaves "
                        "the sheet identical",
                  step["pixels_that_differ"] == 0,
                  {"pixels_that_differ": step["pixels_that_differ"]})
        res["steps"].append(step)
        print(json.dumps(step, indent=2, default=str))

    # =================================================================== 04 ==
    # IS `TEXT_EDGE_DEFAULT_MM` ONE RULE OR SIX COPIES?
    #
    # Round three put the "a typed 0 means 4 mm" substitution in ONE place and
    # routed `build_kwargs()` and the stamper through it. The constant 4.0 is
    # still spelled out in `instruments.py` (twice as a `Geom` default and
    # twice as `or 4.0` in `build()`), in `raster.py`, in `chart.build_chart`'s
    # own defaults and in the panel's `set_recipe`. If those are live copies
    # rather than dead ones, moving the single constant moves only some of the
    # ink. Run this step once on the tip and once with the constant changed;
    # every element that did NOT move is reading a different copy.
    if want("04"):
        print("\n== 04 a typed zero in all three boxes ==")
        from workflow.layout_engine import presets as _pr
        const = float(getattr(_pr, "TEXT_EDGE_DEFAULT_MM", -1.0))
        print(f"    TEXT_EDGE_DEFAULT_MM in this process = {const}")
        # Markers OFF, so the ONLY thing holding text off the edges is the
        # typed-zero substitution and nothing else.
        apply(helper_markers=False, clip_content_mode="text",
              margin_left=26.0, export_pdf=False)
        panel.export_pdf.setChecked(False)
        pump(app, 300)
        # TYPED into the real boxes: `set_recipe` reads `value or 4.0`, so a
        # recipe carrying 0.0 shows 4.0 and only typing reaches the real state.
        panel.text_edge_clip.setValue(0.0)
        panel.text_edge_top.setValue(0.0)
        panel.text_edge.setValue(0.0)
        pump(app, 600)
        boxes = {"clip": panel.text_edge_clip.value(),
                 "top": panel.text_edge_top.value(),
                 "bottom": panel.text_edge.value()}
        print(f"    the three boxes now read {boxes}")
        set_notes(True)
        z = build("04-typed-zero")
        step = {"step": "04", "TEXT_EDGE_DEFAULT_MM": const, "boxes": boxes}
        if z["tif"]:
            t, dpi_t = tiff_gray(z["tif"])
            h, w = t.shape
            pw, ph = w * 25.4 / dpi_t, h * 25.4 / dpi_t
            # Each element in its own window, so one cannot mask another.
            step["strip_letters_top_band"] = ink_box(t, dpi_t, x0mm=30,
                                                     x1mm=pw - 14, y0mm=0,
                                                     y1mm=19)
            step["bottom_sheet_text"] = ink_box(t, dpi_t, x0mm=30,
                                                x1mm=pw - 14, y0mm=ph - 16,
                                                y1mm=ph)
            step["clip_band_left"] = ink_box(t, dpi_t, x0mm=0, x1mm=25)
            step["chart_note_right_edge"] = ink_box(t, dpi_t, x0mm=pw - 11,
                                                    x1mm=pw)
            step["whole_page"] = ink_box(t, dpi_t)
        res["steps"].append(step)
        print(json.dumps(step, indent=2, default=str))

    # =================================================================== 05 ==
    # THE MARKER SWITCHES CROSSED AGAINST THE EDGES THEY RESERVE.
    #
    # Knut's rule has two halves and each is gated by a DIFFERENT checkbox:
    # "Sides" governs the left/right reserve, "Top/bottom" the top/bottom one.
    # Proving each alone proves nothing about the pair, so all four
    # combinations are built and the ink on all four edges is measured on each.
    # The clip band is on the RIGHT here, which is the edge the reported
    # collision was on.
    if want("05"):
        print("\n== 05 markers x sides x top/bottom, four edges each ==")
        combos = [(False, True, True), (True, False, False),
                  (True, True, False), (True, False, True), (True, True, True)]
        rows = []
        for on, sides, tb in combos:
            tag = (f"05-markers{'ON' if on else 'OFF'}"
                   f"-sides{'ON' if sides else 'OFF'}"
                   f"-topbot{'ON' if tb else 'OFF'}")
            apply(helper_markers=on, helper_markers_sides=sides,
                  helper_markers_top_bottom=tb, clip_side="right",
                  clip_content_mode="text", margin_left=10.0,
                  margin_right=26.0, export_pdf=False)
            panel.export_pdf.setChecked(False)
            pump(app, 300)
            set_notes(False)
            b = build(tag)
            row = {"markers": on, "sides": sides, "top_bottom": tb,
                   "tif": str(b["tif"])}
            if b["tif"]:
                t, dpi_t = tiff_gray(b["tif"])
                h, w = t.shape
                pw, ph = w * 25.4 / dpi_t, h * 25.4 / dpi_t
                # The clip band's TEXT, on the right, away from the dashes'
                # own column: measured in the band but inside the marker reach
                # so a dash cannot be mistaken for a glyph.
                row["clip_text_right_from_page_mm"] = (
                    ink_box(t, dpi_t, x0mm=pw - 26, x1mm=pw,
                            y0mm=40, y1mm=ph - 40) or {}).get(
                                "right_from_page_mm")
                row["strip_letters_top_mm"] = (
                    ink_box(t, dpi_t, x0mm=30, x1mm=pw - 30, y0mm=0,
                            y1mm=19) or {}).get("top_mm")
                row["bottom_text_from_page_mm"] = (
                    ink_box(t, dpi_t, x0mm=30, x1mm=pw - 30, y0mm=ph - 16,
                            y1mm=ph) or {}).get("bottom_from_page_mm")
                row["page_ink"] = ink_box(t, dpi_t)
            rows.append(row)
            print(f"    {tag}: {json.dumps({k: v for k, v in row.items() if k != 'tif'})}")
        step = {"step": "05", "rows": rows}
        # The rule: the side reserve grows ONLY when markers AND sides are on.
        by = {(r["markers"], r["sides"], r["top_bottom"]): r for r in rows}
        base = by.get((False, True, True), {})
        s_on = by.get((True, True, True), {})
        s_off = by.get((True, False, True), {})
        step["side_reserve_grew_only_with_sides"] = {
            "markers_off": base.get("clip_text_right_from_page_mm"),
            "markers_on_sides_off": s_off.get("clip_text_right_from_page_mm"),
            "markers_on_sides_on": s_on.get("clip_text_right_from_page_mm"),
        }
        step["top_reserve_grew_only_with_top_bottom"] = {
            "markers_off": base.get("strip_letters_top_mm"),
            "markers_on_tb_off": by.get((True, True, False), {}).get(
                "strip_letters_top_mm"),
            "markers_on_tb_on": s_on.get("strip_letters_top_mm"),
        }
        res["steps"].append(step)
        print(json.dumps(step, indent=2, default=str))

    # =================================================================== 06 ==
    # THE SIDE RESERVE, ISOLATED AGAINST A CONTROL SHEET.
    #
    # Step 05 measured the marker DASHES and called them text: at a 4.0 mm
    # marker distance the dash ink starts at 3.94 mm, which is exactly where a
    # naive window says "the text is at 3.94". So each marker state is built
    # TWICE here -- once with the clip band's text and once with the band's
    # content switched off, everything else identical -- and the clip text's
    # position is the bounding box of the DIFFERENCE. Nothing else on the sheet
    # changes between the two, so the difference is the text and only the text.
    #
    # Knut's rule, #182: the side text-box edge sits at whichever goes further
    # in, "Clip" or ("Distance from page edge" + "Marker length" + 1.0mm), and
    # the second half applies only when BOTH "Print helper markers" and "Sides"
    # are on. With Clip 4.0, markers 4.0 and a 2.0 mm dash that is 4.0 against
    # 7.0.
    if want("06"):
        print("\n== 06 the clip band's text, isolated against a control ==")
        states = [("markers OFF", False, True),
                  ("markers ON, Sides OFF", True, False),
                  ("markers ON, Sides ON", True, True)]
        rows = []
        for label, on, sides in states:
            pair = {}
            for content, nm in (("text", "with-text"), ("off", "band-empty")):
                apply(helper_markers=on, helper_markers_sides=sides,
                      helper_markers_top_bottom=True, clip_side="right",
                      clip_content_mode=content, margin_left=10.0,
                      margin_right=26.0, export_pdf=False)
                panel.export_pdf.setChecked(False)
                pump(app, 300)
                set_notes(False)
                tag = (f"06-{'on' if on else 'off'}"
                       f"-sides{'on' if sides else 'off'}-{nm}")
                b = build(tag)
                pair[nm] = b["tif"]
            row = {"state": label, "markers": on, "sides": sides}
            if pair.get("with-text") and pair.get("band-empty"):
                ta, dpi_t = tiff_gray(pair["with-text"])
                tb, _ = tiff_gray(pair["band-empty"])
                if ta.shape == tb.shape:
                    d = (np.abs(ta - tb) > 8)
                    if d.any():
                        ys, xs = np.nonzero(d)
                        h, w = ta.shape
                        mm = 25.4 / dpi_t
                        row["clip_text_right_from_page_mm"] = round(
                            (w - xs.max() - 1) * mm, 3)
                        row["clip_text_left_mm"] = round(xs.min() * mm, 3)
                        row["clip_text_top_mm"] = round(ys.min() * mm, 3)
                        row["clip_text_bottom_from_page_mm"] = round(
                            (h - ys.max() - 1) * mm, 3)
                        row["pixels_of_text"] = int(d.sum())
                    else:
                        row["clip_text_right_from_page_mm"] = "NO DIFFERENCE"
                else:
                    row["clip_text_right_from_page_mm"] = "page size changed"
            rows.append(row)
            print(f"    {label}: {json.dumps({k: v for k, v in row.items()})}")
        step = {"step": "06", "rows": rows}
        got = {r["state"]: r.get("clip_text_right_from_page_mm") for r in rows}
        step["knuts_rule"] = {
            "expected_markers_off_mm": 4.0,
            "expected_markers_on_sides_off_mm": 4.0,
            "expected_markers_on_sides_on_mm": 7.0,
            "measured": got}
        ok = (isinstance(got.get("markers ON, Sides ON"), float)
              and abs(got["markers ON, Sides ON"] - 7.0) < 0.7
              and isinstance(got.get("markers OFF"), float)
              and abs(got["markers OFF"] - 4.0) < 0.7
              and isinstance(got.get("markers ON, Sides OFF"), float)
              and abs(got["markers ON, Sides OFF"] - 4.0) < 0.7)
        claim("06", "the clip text keeps 4 mm without the side dashes and "
                    "7 mm with them, and the Sides box alone decides", ok, got)
        res["steps"].append(step)
        print(json.dumps(step, indent=2, default=str))

    (out / "result.json").write_text(json.dumps(res, indent=2, default=str),
                                     encoding="utf-8")
    print(f"\nwrote {out / 'result.json'}")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
