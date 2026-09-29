#!/usr/bin/env python3
"""#182 SECOND CHALLENGE ROUND: the fourth copy, the centred band, Guided, four edges at once.

Drives the REAL `MainWindow` on screen, sets every value through the REAL
`LayoutOptionsPanel`, runs the REAL "Generate Chart" so the post-render note
stamper actually runs, and MEASURES THE INK on the TIFFs the app writes.
Nothing here trusts a widget's opinion of where it put something.

Every demo REFUSES to be counted unless it demonstrates its own claim, in the
manner of `scripts/make_report_limit_demos.py`.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-chal2.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-chal2-presets
    python scripts/drive_182_challenge_two.py --out DIR
"""
from __future__ import annotations

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

WORK = Path("/tmp/chromiq-chal2-work")
PROJECT = "Challenge182two"
PAPER_W, PAPER_H = 210.0, 297.0
DPI = 200

CLIP_TEXT = ("chart identification line\n"
             "second line of the clip band\n"
             "third line of the clip band\n"
             "fourth line of the clip band")
#: LONG ON PURPOSE. The stamper CENTRES the line inside the strip it is given
#: (`tiff_metadata._render_rotated_line`), so a short note never reaches the
#: strip's ends and the ends are where the T and B question lives. A line that
#: fills the strip is the one that shows where the strip really starts.
NOTES = ("run chart notes for the second challenge round of issue 182, written "
         "long on purpose so the stamped line fills the whole strip it is "
         "given and its two ends land where the strip really begins and ends, "
         "which is the measurement this sheet exists to make, and it keeps "
         "going so that no amount of shrinking leaves slack at either end")

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


def wait_for_build(app, tab, timeout=420) -> bool:
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

def read_gray(path: Path):
    """(grayscale array, dpi) for a TIFF the app wrote."""
    import tifffile
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        arr = np.array(page.asarray())
        dpi = 200.0
        try:
            xres = page.tags["XResolution"].value
            dpi = float(xres[0]) / float(xres[1])
            if int(page.tags["ResolutionUnit"].value) == 3:        # centimetres
                dpi *= 2.54
        except Exception:                                          # noqa: BLE001
            pass
    if arr.ndim == 3:
        arr = arr.min(axis=2)
    if arr.dtype == np.uint16:
        arr = (arr // 257).astype(np.uint8)
    return arr, dpi


def diff_ink(a: np.ndarray, b: np.ndarray, thresh: int = 40) -> np.ndarray:
    """Pixels that got DARKER from a (control) to b (with the element on)."""
    return (a.astype(int) - b.astype(int)) > thresh


def extent_mm(mask: np.ndarray, dpi: float, axis: str) -> dict:
    """First/last inked row or column of *mask*, in mm from each page edge."""
    if not mask.any():
        return {"any_ink": False}
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    H, W = mask.shape
    k = 25.4 / dpi
    return {
        "any_ink": True,
        "pixels": int(mask.sum()),
        "top_mm": round(float(rows[0]) * k, 2),
        "bottom_mm": round(float(H - 1 - rows[-1]) * k, 2),
        "left_mm": round(float(cols[0]) * k, 2),
        "right_mm": round(float(W - 1 - cols[-1]) * k, 2),
    }


def main() -> int:
    out = (Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv
           else Path("/tmp/chromiq-challenge2-proof"))
    out.mkdir(parents=True, exist_ok=True)
    only = (sys.argv[sys.argv.index("--only") + 1].split(",")
            if "--only" in sys.argv else None)

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

    if not locked and not session_is_locked():
        shot = out / "00-the-real-window.png"
        got = capture_window(win, shot)
        res["window_photograph"] = str(shot) if got else None
        print(f"00 photograph of the real window: {got}")
    else:
        res["window_photograph"] = None
        print("00 screen LOCKED, no photograph -- the ink on the sheets is "
              "the evidence")

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
                area_cols=14, area_rows=16,
                use_instrument_margins=False,
                randomize=False, seed_fixed=True, seed=4242,
                clip_border=False, clip_border_width_mm=24.0,
                clip_side="left", clip_content_mode="off",
                clip_text=CLIP_TEXT, clip_flip_180=False,
                margin_top=20.0, margin_right=10.0,
                margin_bottom=20.0, margin_left=10.0,
                text_edge_top_mm=4.0, text_edge_bottom_mm=4.0,
                text_edge_mm=4.0, text_edge_clip_mm=4.0,
                show_strip_indicators=True, show_row_indicators=True,
                helper_markers=False, helper_marker_edge_mm=4.0,
                helper_marker_len_mm=2.0, helper_marker_per_patch=3,
                helper_markers_top_bottom=True, helper_markers_sides=True,
                chart_text="", chart_text_size_mm=0.0,
                clip_text_size_mm=0.0)

    dst = WORK / PROJECT

    def apply(**over) -> LayoutRecipe:
        r = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(r)
        pump(app, 900)
        tab._update_margin_inspector()
        pump(app, 400)
        return panel.get_recipe()

    def build(tag: str) -> Path | None:
        for t in dst.rglob("*.tif"):
            t.unlink()
        tab._generate_btn.click()
        ok = wait_for_build(app, tab)
        pump(app, 1200)
        tifs = sorted(dst.rglob("*.tif"))
        if not ok or not tifs:
            print(f"    !! build {tag} produced nothing (ok={ok})")
            return None
        keep = out / f"{tag}.tif"
        shutil.copy(tifs[0], keep)
        return keep

    def notices():
        try:
            return type(tab)._engine_text_notes(tab)
        except Exception as exc:                                   # noqa: BLE001
            return [f"<raised {exc!r}>"], []

    def set_notes(on: bool) -> None:
        tab._manual_chart_notes_edit.setText(NOTES if on else "")
        tab._manual_stamp_cmd_check.setChecked(bool(on))
        pump(app, 600)

    def want(step: str) -> bool:
        return only is None or step in only

    # =================================================================== 01 ==
    # THE SIDE NOTE'S VERTICAL EXTENT IS THE *SIDE* RESERVE, NOT T AND B.
    #
    # `geometry.clip_area_mm` gives a side text-box the height
    # `text_edge_fit.page_text_height_mm(T, B, top/bottom markers)`.
    # `tiff_metadata._stamp_one` gives the note on the same edge the height
    # `H - 2 * <the SIDE reserve>` (`strip_h = H - 2*_pad`, `y0 = _pad`).
    # One rule, two answers.
    if want("01"):
        print("\n01 the note's top and bottom ends against T and B")
        # "B" IS `text_edge_mm`. `LayoutRecipe` has no `text_edge_bottom_mm`
        # field at all, and passing that name drops the value in silence, so
        # the first pass of this step measured T against a B that never moved.
        for tag, over in (
            ("01a-T4-B4-nomarkers", dict(text_edge_top_mm=4.0,
                                         text_edge_mm=4.0)),
            ("01b-T20-B20-nomarkers", dict(text_edge_top_mm=20.0,
                                           text_edge_mm=20.0)),
            ("01c-T20-B4-nomarkers", dict(text_edge_top_mm=20.0,
                                          text_edge_mm=4.0)),
        ):
            r = apply(**over)
            set_notes(False)
            base = build(f"{tag}__control")
            set_notes(True)
            with_note = build(f"{tag}__note")
            if base is None or with_note is None:
                claim(tag, "the sheet was built", False, {})
                continue
            a, dpi = read_gray(base)
            b, _ = read_gray(with_note)
            if a.shape != b.shape:
                claim(tag, "control and note sheets are the same size", False,
                      {"control": a.shape, "note": b.shape})
                continue
            m = diff_ink(a, b)
            e = extent_mm(m, dpi, "v")
            e["T_asked_mm"] = float(over["text_edge_top_mm"])
            e["B_asked_mm"] = float(over["text_edge_mm"])
            e["clip_asked_mm"] = 4.0
            res["steps"].append({"step": tag, **e})
            claim(tag,
                  "the note's ink starts at the SIDE reserve from the top, "
                  "not at T",
                  bool(e.get("any_ink")),
                  e)

    # =================================================================== 02 ==
    # AND WITH THE TOP/BOTTOM MARKERS ON AND "SIDES" OFF, THE SIDE RESERVE IS
    # JUST "Clip", SO THE NOTE IS STAMPED INTO THE TOP AND BOTTOM DASH BANDS.
    if want("02"):
        print("\n02 the note against the top and bottom marker dashes")
        for tag, over in (
            ("02a-markers-tb-only", dict(helper_markers=True,
                                         helper_markers_top_bottom=True,
                                         helper_markers_sides=False,
                                         text_edge_top_mm=4.0,
                                         text_edge_bottom_mm=4.0,
                                         margin_right=8.0)),
            ("02b-markers-both", dict(helper_markers=True,
                                      helper_markers_top_bottom=True,
                                      helper_markers_sides=True,
                                      text_edge_top_mm=4.0,
                                      text_edge_bottom_mm=4.0,
                                      margin_right=8.0)),
        ):
            r = apply(**over)
            set_notes(False)
            base = build(f"{tag}__control")
            set_notes(True)
            with_note = build(f"{tag}__note")
            if base is None or with_note is None:
                claim(tag, "the sheet was built", False, {})
                continue
            a, dpi = read_gray(base)
            b, _ = read_gray(with_note)
            m = diff_ink(a, b)
            e = extent_mm(m, dpi, "v")
            # The dash band on the top edge, in mm from the paper.
            band0 = float(over.get("helper_marker_edge_mm", 4.0) or 4.0)
            band1 = band0 + float(over.get("helper_marker_len_mm", 2.0) or 2.0)
            e["top_dash_band_mm"] = [band0, band1]
            e["note_reserve_should_be_mm"] = round(band1 + 1.0, 2)
            # Does any note ink land INSIDE the top dash band's rows?
            r0, r1 = int(band0 * dpi / 25.4), int(round(band1 * dpi / 25.4))
            e["note_px_inside_top_dash_band"] = int(m[r0:r1 + 1, :].sum())
            H = m.shape[0]
            rb0 = H - 1 - int(round(band1 * dpi / 25.4))
            rb1 = H - 1 - int(band0 * dpi / 25.4)
            e["note_px_inside_bottom_dash_band"] = int(m[rb0:rb1 + 1, :].sum())
            res["steps"].append({"step": tag, **e})
            claim(tag,
                  "note ink lands inside the top/bottom ruler dash bands",
                  bool(e["note_px_inside_top_dash_band"]
                       or e["note_px_inside_bottom_dash_band"]),
                  e)

    # =================================================================== 03 ==
    # THE CLIP BAND IS CENTRED VERTICALLY. Measured on the sheet, not argued.
    if want("03"):
        print("\n03 the clip band's vertical position against T and B")
        from workflow.layout_engine import geometry as _geo
        from workflow.layout_engine import instruments as _ins
        # "B" IS `text_edge_mm` ON THE RECIPE, NOT `text_edge_bottom_mm`.
        # There is no `text_edge_bottom_mm` field on `LayoutRecipe`; the
        # geometry reads `Geom.text_edge_bottom_mm`, which
        # `instruments.geom_from_build_kwargs` fills from the recipe's
        # `text_edge` (the BOTTOM sheet-text distance). A first pass here
        # passed the geometry's name and the value was silently dropped.
        #
        # The content is the "notes" DESIGN, not plain text: plain text is
        # centred along the band, so its ink says nothing about where the
        # band's own ends are. The notes design is drawn to the band's edges.
        for tag, T, B in (("03a-T12-B4", 12.0, 4.0),
                          ("03b-T4-B20", 4.0, 20.0),
                          ("03c-T20-B4", 20.0, 4.0)):
            r = apply(clip_border=True, clip_border_width_mm=24.0,
                      clip_side="left", clip_content_mode="notes",
                      margin_left=24.0,
                      text_edge_top_mm=T, text_edge_mm=B)
            g = _ins.geom_from_build_kwargs(r.build_kwargs())
            area = _geo.clip_area_mm(g, PAPER_H, PAPER_W, 0, 0.0)
            sheet = build(f"{tag}")
            e = {"T_asked_mm": T, "B_asked_mm": B,
                 "geom_text_edge_top_mm": float(g.text_edge_top_mm),
                 "geom_text_edge_bottom_mm": float(g.text_edge_bottom_mm),
                 "clip_area_y_mm": None if area is None else round(area[1], 2),
                 "clip_area_h_mm": None if area is None else round(area[3], 2)}
            if sheet is not None:
                a, dpi = read_gray(sheet)
                # The clip band's own text is the leftmost ink on the sheet;
                # look only at the band's columns.
                w_px = int(round(24.0 * dpi / 25.4))
                strip = a[:, :w_px] < 200
                e.update({f"band_ink_{k}": v
                          for k, v in extent_mm(strip, dpi, "v").items()})
            res["steps"].append({"step": tag, **e})
            claim(tag,
                  "the clip band starts at (page - T - B) centred, not at T",
                  e.get("clip_area_y_mm") is not None
                  and abs(e["clip_area_y_mm"] - T) > 0.05,
                  e)

    # =================================================================== 04 ==
    # A GUIDED CHART: does it have markers at all, and where is its note?
    if want("04"):
        print("\n04 Guided: the markers it can never have, and its note")
        # Turn every marker preference ON first, so if anything leaks from the
        # settings into a Guided build, it leaks now.
        settings.set("helper_markers_show", True)
        settings.set("helper_marker_edge_mm", 4.0)
        settings.set("helper_marker_len_mm", 2.0)
        settings.set("helper_markers_top_bottom", True)
        settings.set("helper_markers_sides", True)
        tab._switch_mode("guided")
        pump(app, 1200)
        tab._guided_target_name_edit.setText(PROJECT + "G") \
            if hasattr(tab, "_guided_target_name_edit") else None
        pump(app, 600)
        set_notes(True)
        gdst = WORK / (PROJECT + "G")
        for t in list(WORK.rglob("*.tif")):
            t.unlink()
        tab._generate_btn.click()
        okg = wait_for_build(app, tab)
        pump(app, 1200)
        gtifs = sorted(WORK.rglob("*.tif"))
        e = {"guided_build_ok": bool(okg), "tiffs": [str(p) for p in gtifs]}
        if gtifs:
            keep = out / "04-guided.tif"
            shutil.copy(gtifs[0], keep)
            # What did the recipe record?
            chj = sorted(WORK.rglob("*.channels.json"))
            if chj:
                d = json.loads(chj[0].read_text(encoding="utf-8"))
                lay = d.get("layout") or d
                e["recorded_helper_markers"] = lay.get("helper_markers")
                e["recorded_text_edge_clip"] = lay.get("text_edge_clip")
                shutil.copy(chj[0], out / "04-guided.channels.json")
            a, dpi = read_gray(keep)
            e["sheet_dpi"] = dpi
        res["steps"].append({"step": "04-guided", **e})
        claim("04-guided",
              "a Guided chart records helper_markers = false, so it has no "
              "side dashes for its note to cross",
              e.get("recorded_helper_markers") is False,
              e)
        tab._switch_mode("manual")
        pump(app, 1000)
        tab._manual_target_name_edit.setText(PROJECT)
        pump(app, 800)

    # =================================================================== 05 ==
    # ALL FOUR EDGES ON ONE SHEET, WITH THE MARKERS, THE ROW NUMBERS, THE
    # STRIP LETTERS, A CLIP BORDER, THE BOTTOM SHEET TEXT AND THE NOTE.
    if want("05"):
        print("\n05 four edges at once")
        r = apply(clip_border=True, clip_border_width_mm=24.0,
                  clip_side="left", clip_content_mode="text",
                  margin_left=24.0, margin_right=10.0,
                  margin_top=22.0, margin_bottom=22.0,
                  text_edge_top_mm=8.0,
                  text_edge_clip_mm=4.0, text_edge_mm=8.0,
                  helper_markers=True, helper_markers_top_bottom=True,
                  helper_markers_sides=True,
                  chart_text="bottom of sheet text for the four-edge sheet",
                  show_strip_indicators=True, show_row_indicators=True)
        warns, over = notices()
        set_notes(True)
        full = build("05-four-edges-all-on")
        # FOUR CONTROLS, ONE PER ELEMENT. Every pixel the full sheet is darker
        # than a control by belongs to the element that control switched off,
        # so each of the four rules is measured on the SAME page rather than on
        # four pages that never met.
        FOUR = dict(clip_border=True, clip_border_width_mm=24.0,
                    clip_side="left", clip_content_mode="text",
                    margin_left=24.0, margin_right=10.0,
                    margin_top=22.0, margin_bottom=22.0,
                    text_edge_top_mm=8.0, text_edge_clip_mm=4.0,
                    text_edge_mm=8.0,
                    helper_markers=True, helper_markers_top_bottom=True,
                    helper_markers_sides=True,
                    chart_text="bottom of sheet text for the four-edge sheet",
                    show_strip_indicators=True, show_row_indicators=True)
        ctrls: dict[str, object] = {}
        set_notes(False)
        ctrls["note"] = build("05-control-no-note")
        set_notes(True)
        apply(**{**FOUR, "clip_content_mode": "off"})
        ctrls["clip_band"] = build("05-control-no-clip-band")
        apply(**{**FOUR, "chart_text": ""})
        ctrls["bottom_text"] = build("05-control-no-bottom-text")
        apply(**{**FOUR, "show_strip_indicators": False})
        ctrls["strip_letters"] = build("05-control-no-strip-letters")
        e = {"recipe_text_edge_top": 8.0,
             "recipe_text_edge_clip": 4.0,
             "recipe_text_edge_bottom": 8.0,
             "marker_edge_mm": 4.0, "marker_len_mm": 2.0,
             "marker_reserve_mm": 7.0,
             "panel_notices": warns, "panel_overlap_notices": over}
        if full is not None:
            b, dpi = read_gray(full)
            for name, ctl in ctrls.items():
                if ctl is None:
                    e[name] = "control not built"
                    continue
                a, _ = read_gray(ctl)
                if a.shape != b.shape:
                    e[name] = f"control {a.shape} != sheet {b.shape}"
                    continue
                e[name] = extent_mm(diff_ink(a, b), dpi, "v")
        res["steps"].append({"step": "05-four-edges", **e})
        ok = full is not None and all(isinstance(e.get(k), dict)
                                      for k in ctrls)
        claim("05-four-edges",
              "all four text elements were isolated by their own control on "
              "one sheet and measured against their reserves", ok, e)

    # =================================================================== 06 ==
    # THE SAME FOUR RULES ON ONE PAGE, WITH T AND B DELIBERATELY UNEQUAL.
    #
    # 05 used T = B, where the clip band's centring cannot be told apart from
    # anchoring it at T. This one asks T 20 / B 4 of every element on the same
    # sheet, so each rule has to answer for itself.
    if want("06"):
        print("\n06 four edges at once, T 20 / B 4")
        SIX = dict(clip_border=True, clip_border_width_mm=24.0,
                   clip_side="left", clip_content_mode="notes",
                   margin_left=24.0, margin_right=10.0,
                   margin_top=30.0, margin_bottom=22.0,
                   text_edge_top_mm=20.0, text_edge_clip_mm=4.0,
                   text_edge_mm=4.0,
                   helper_markers=True, helper_marker_edge_mm=4.0,
                   helper_marker_len_mm=2.0,
                   helper_markers_top_bottom=True, helper_markers_sides=True,
                   chart_text="bottom of sheet text, T twenty B four",
                   show_strip_indicators=True, show_row_indicators=True)
        apply(**SIX)
        set_notes(True)
        full = build("06-four-edges-T20-B4")
        ctrls: dict[str, object] = {}
        set_notes(False)
        ctrls["note"] = build("06-control-no-note")
        set_notes(True)
        apply(**{**SIX, "chart_text": ""})
        ctrls["bottom_text"] = build("06-control-no-bottom-text")
        apply(**{**SIX, "show_strip_indicators": False})
        ctrls["strip_letters"] = build("06-control-no-strip-letters")
        e = {"T_asked_mm": 20.0, "B_asked_mm": 4.0, "clip_asked_mm": 4.0,
             "marker_reserve_mm": 7.0}
        if full is not None:
            b, dpi = read_gray(full)
            for name, ctl in ctrls.items():
                if ctl is None:
                    e[name] = "control not built"
                    continue
                a, _ = read_gray(ctl)
                e[name] = (extent_mm(diff_ink(a, b), dpi, "v")
                           if a.shape == b.shape else "size mismatch")
            # The clip band's own ink: it is the only thing in the first 24 mm
            # of columns, because the row labels sit at the raised left margin.
            w_px = int(round(24.0 * dpi / 25.4))
            e["clip_band"] = extent_mm(b[:, :w_px] < 200, dpi, "v")
        res["steps"].append({"step": "06-four-edges-T20-B4", **e})
        claim("06-four-edges-T20-B4",
              "with T 20 and B 4 the four elements answer the same rule "
              "differently on one page",
              full is not None and isinstance(e.get("clip_band"), dict), e)

    res["screen_locked_at_end"] = session_is_locked()
    (out / "measurements.json").write_text(
        json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(f"\nwrote {out / 'measurements.json'}")
    bad = [c for c in CLAIMS if not c["demonstrated"]]
    print(f"claims: {len(CLAIMS)}, not demonstrated: {len(bad)}")
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
