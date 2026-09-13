#!/usr/bin/env python3
"""#182 THIRD CHALLENGE ROUND: the fifth copy, the second page, and the extremes.

Drives the REAL `MainWindow` on screen, sets every value through the REAL
`LayoutOptionsPanel` (spin boxes, not recipe fields, where the difference
matters), runs the REAL "Generate Chart" so the post-render note stamper
actually runs, and MEASURES THE INK on the TIFFs the app writes. Each element
is isolated against a control sheet built with that one element switched off.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-chal3.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-chal3-presets
    python scripts/drive_182_challenge_three.py --out DIR [--only 01,02]
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

WORK = Path("/tmp/chromiq-chal3-work")
PROJECT = "Challenge182three"
DPI = 200

CLIP_TEXT = ("chart identification line\n"
             "second line of the clip band\n"
             "third line of the clip band\n"
             "fourth line of the clip band")
NOTES = ("run chart notes for the third challenge round of issue 182, written "
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


def wait_for_build(app, tab, timeout=600) -> bool:
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
    import tifffile
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        arr = np.array(page.asarray())
        dpi = float(DPI)
        try:
            xres = page.tags["XResolution"].value
            dpi = float(xres[0]) / float(xres[1])
            if int(page.tags["ResolutionUnit"].value) == 3:
                dpi *= 2.54
        except Exception:                                          # noqa: BLE001
            pass
    if arr.ndim == 3:
        arr = arr.min(axis=2)
    if arr.dtype == np.uint16:
        arr = (arr // 257).astype(np.uint8)
    return arr, dpi


def diff_ink(a: np.ndarray, b: np.ndarray, thresh: int = 40) -> np.ndarray:
    """Pixels that got DARKER from a (control) to b (element switched on)."""
    return (a.astype(int) - b.astype(int)) > thresh


def extent_mm(mask: np.ndarray, dpi: float) -> dict:
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
           else Path("/tmp/chromiq-challenge3-proof"))
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

    # THE PHOTOGRAPH IS ATTEMPTED WHATEVER THE LOCK FLAG SAYS, because
    # CLAUDE.md says to measure the claim rather than believe it. A locked
    # session hands back the wallpaper, and `capture_window` proves the picture
    # contains the window by photographing the same rectangle with the window
    # hidden and requiring the two to differ.
    shot = out / "00-the-real-window.png"
    got = False
    try:
        got = capture_window(win, shot)
    except Exception as exc:                                       # noqa: BLE001
        res["window_photograph_error"] = repr(exc)
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
                area_cols=12, area_rows=14,
                use_instrument_margins=False,
                randomize=False, seed_fixed=True, seed=4242,
                clip_border=False, clip_border_width_mm=24.0,
                clip_side="left", clip_content_mode="off",
                clip_text=CLIP_TEXT, clip_flip_180=False,
                margin_top=20.0, margin_right=10.0,
                margin_bottom=20.0, margin_left=10.0,
                text_edge_top_mm=4.0, text_edge_mm=4.0, text_edge_clip_mm=4.0,
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

    def type_edges(clip=None, top=None, bottom=None):
        """Type into the three "Text distance from edge" boxes, as a user does.

        `set_recipe` reads them as ``value or 4.0``, so a recipe carrying 0.0
        shows 4.0 in the box and a driver that only sets the recipe can never
        reach the typed-zero state a user can.
        """
        if clip is not None:
            panel.text_edge_clip.setValue(float(clip))
        if top is not None:
            panel.text_edge_top.setValue(float(top))
        if bottom is not None:
            panel.text_edge.setValue(float(bottom))
        pump(app, 500)
        return {"box_clip": panel.text_edge_clip.value(),
                "box_top": panel.text_edge_top.value(),
                "box_bottom": panel.text_edge.value()}

    def set_patches(n: int) -> None:
        # "AUTO" COMPUTES THE COUNT TO FILL EXACTLY THE PAGES SET UNDER
        # printtarg -> Pages, so with it ticked a typed count is thrown away
        # and every chart comes out one page. The first pass of step 02 asked
        # for 150 patches on an 8x10 grid and got a single page for exactly
        # that reason.
        try:
            cb = getattr(tab, "_manual_auto_patches_check", None)
            if cb is not None and cb.isChecked():
                cb.setChecked(False)
                pump(app, 400)
        except Exception as exc:                                   # noqa: BLE001
            print(f"    !! could not untick Auto: {exc!r}")
        try:
            tab._manual_f_pw._control.setValue(int(n))
        except Exception as exc:                                   # noqa: BLE001
            print(f"    !! could not set patch count: {exc!r}")
        pump(app, 500)
        try:
            cb = getattr(tab, "_manual_auto_patches_check", None)
            print(f"    patch count now {tab._manual_f_pw._control.value()}, "
                  f"Auto = {cb is not None and cb.isChecked()}")
        except Exception:                                          # noqa: BLE001
            pass

    def build(tag: str, keep_all_pages: bool = False):
        for t in dst.rglob("*.tif"):
            t.unlink()
        tab._generate_btn.click()
        ok = wait_for_build(app, tab)
        pump(app, 1200)
        tifs = sorted(dst.rglob("*.tif"))
        if not ok or not tifs:
            print(f"    !! build {tag} produced nothing (ok={ok})")
            return None if not keep_all_pages else []
        if keep_all_pages:
            kept = []
            for i, t in enumerate(tifs, 1):
                k = out / f"{tag}__p{i}.tif"
                shutil.copy(t, k)
                kept.append(k)
            return kept
        keep = out / f"{tag}.tif"
        shutil.copy(tifs[0], keep)
        return keep

    def set_notes(on: bool) -> None:
        tab._manual_chart_notes_edit.setText(NOTES if on else "")
        tab._manual_stamp_cmd_check.setChecked(bool(on))
        pump(app, 600)

    def want(step: str) -> bool:
        return only is None or step in only

    # =================================================================== 01 ==
    # A TYPED ZERO IN "Text distance from edge". The renderer reads the boxes
    # through `LayoutRecipe.build_kwargs()`, which writes
    # `text_edge_clip = self.text_edge_clip_mm or 4.0` — so a typed 0 becomes
    # 4.0 for everything the layout engine draws, and the panel says so in
    # black: *"A distance of 0.0 mm is not used. ChromIQ prints at 4.0 mm
    # instead, so no text is set hard against the paper edge."*
    #
    # `chart_creator._stamp_tiff_metadata` reads the SAME three fields off the
    # recipe RAW (`float(getattr(_rec, "text_edge_clip_mm", 0.0) or 0.0)`), so
    # the note gets 0.0 where everything else gets 4.0.
    if want("01"):
        print("\n01 a typed 0 in the three edge boxes")
        FIVE = dict(clip_border=True, clip_border_width_mm=24.0,
                    clip_side="left", clip_content_mode="text",
                    margin_left=24.0, margin_right=12.0,
                    margin_top=22.0, margin_bottom=22.0,
                    chart_text="bottom of sheet text for the typed zero sheet",
                    show_strip_indicators=True, show_row_indicators=True)
        for tag, boxes in (("01a-boxes-4-4-4", (4.0, 4.0, 4.0)),
                           ("01b-boxes-0-0-0", (0.0, 0.0, 0.0))):
            apply(**FIVE)
            b = type_edges(clip=boxes[0], top=boxes[1], bottom=boxes[2])
            rec = panel.get_recipe()
            e = {"typed_boxes": b,
                 "recipe_text_edge_clip_mm": float(rec.text_edge_clip_mm),
                 "recipe_text_edge_top_mm": float(rec.text_edge_top_mm),
                 "recipe_text_edge_mm": float(rec.text_edge_mm),
                 "build_kwargs_text_edge_clip":
                     float(rec.build_kwargs().get("text_edge_clip")),
                 "build_kwargs_text_edge_top":
                     float(rec.build_kwargs().get("text_edge_top")),
                 "build_kwargs_text_edge":
                     float(rec.build_kwargs().get("text_edge")),
                 "panel_clip_notes": panel._text_edge_clip_note_lines()}
            try:
                _w, _o = type(tab)._engine_text_notes(tab)
                e["panel_notices"] = _w
            except Exception as exc:                               # noqa: BLE001
                e["panel_notices"] = f"<raised {exc!r}>"
            set_notes(True)
            full = build(f"{tag}__all-on")
            ctrls = {}
            set_notes(False)
            ctrls["note"] = build(f"{tag}__control-no-note")
            set_notes(True)
            apply(**{**FIVE, "clip_content_mode": "off"})
            type_edges(clip=boxes[0], top=boxes[1], bottom=boxes[2])
            ctrls["clip_content"] = build(f"{tag}__control-no-clip-content")
            apply(**{**FIVE, "chart_text": ""})
            type_edges(clip=boxes[0], top=boxes[1], bottom=boxes[2])
            ctrls["bottom_text"] = build(f"{tag}__control-no-bottom-text")
            apply(**{**FIVE, "show_strip_indicators": False})
            type_edges(clip=boxes[0], top=boxes[1], bottom=boxes[2])
            ctrls["strip_letters"] = build(f"{tag}__control-no-strip-letters")
            if full is not None:
                sheet, dpi = read_gray(full)
                e["sheet_dpi"] = dpi
                for name, ctl in ctrls.items():
                    if ctl is None:
                        e[name] = "control not built"
                        continue
                    a, _ = read_gray(ctl)
                    if a.shape != sheet.shape:
                        e[name] = f"control {a.shape} != sheet {sheet.shape}"
                        continue
                    e[name] = extent_mm(diff_ink(a, sheet), dpi)
                # THE CLIP BAND'S OWN INK, measured directly rather than by
                # difference: switching the content off also un-reserves the
                # band, so the "control" moves the whole patch block and the
                # difference is the page. The band is the only thing in the
                # first 24 mm of columns (the row labels sit at the raised
                # left margin), so those columns ARE the isolation.
                w_px = int(round(24.0 * dpi / 25.4))
                e["clip_band_columns"] = extent_mm(sheet[:, :w_px] < 200, dpi)
            res["steps"].append({"step": tag, **e})
            claim(tag, "every element on the sheet was isolated and measured",
                  full is not None and isinstance(e.get("note"), dict), e)

        # 01c THE SAME QUESTION ON THE EDGE THE NOTE'S THICKNESS TOUCHES.
        # With the clip band on the RIGHT the stamper packs the note against
        # the clip content instead of leaving it at the patch block, so its
        # right-hand end lands ON the page-edge reserve and the reserve is
        # measurable. On the left-hand band the note never reaches the limit,
        # so only its two ENDS can answer.
        RIGHTBAND = dict(clip_border=True, clip_border_width_mm=24.0,
                         clip_side="right", clip_content_mode="text",
                         margin_left=12.0, margin_right=24.0,
                         margin_top=22.0, margin_bottom=22.0,
                         show_strip_indicators=True, show_row_indicators=True)
        for tag, boxes in (("01c-right-band-boxes-4", (4.0, 4.0, 4.0)),
                           ("01d-right-band-boxes-0", (0.0, 0.0, 0.0))):
            apply(**RIGHTBAND)
            b = type_edges(clip=boxes[0], top=boxes[1], bottom=boxes[2])
            set_notes(True)
            full = build(f"{tag}__note-on")
            set_notes(False)
            ctl = build(f"{tag}__control-no-note")
            e = {"typed_boxes": b}
            if full is not None and ctl is not None:
                sheet, dpi = read_gray(full)
                a, _ = read_gray(ctl)
                e["sheet_dpi"] = dpi
                e["note"] = (extent_mm(diff_ink(a, sheet), dpi)
                             if a.shape == sheet.shape else "size mismatch")
                W = sheet.shape[1]
                x0 = W - int(round(24.0 * dpi / 25.4))
                e["clip_band_columns"] = extent_mm(sheet[:, x0:] < 200, dpi)
            res["steps"].append({"step": tag, **e})
            claim(tag, "the note packed against a right-hand clip band was "
                       "isolated and measured",
                  isinstance(e.get("note"), dict), e)

    # =================================================================== 02 ==
    # PAGE 2. Every measurement in every round so far has been page 1, and a
    # second page has the same four edges.
    #
    # THE MARKERS ARE OFF IN 02a ON PURPOSE. The side dashes are ink inside the
    # band's own columns, so with them on the "first 24 mm of columns" trick
    # measures a dash and not the clip text. 02b turns them on and measures
    # only the note, which is isolated by its own control and so is clean.
    if want("02"):
        print("\n02 a two page chart, both pages")
        for tag, markers, T, B, CLIP in (
                ("02a-two-page-no-markers", False, 10.0, 6.0, 4.0),
                ("02b-two-page-markers-on", True, 4.0, 4.0, 4.0)):
            TWO = dict(clip_border=True, clip_border_width_mm=24.0,
                       clip_side="left", clip_content_mode="text",
                       margin_left=24.0, margin_right=12.0,
                       margin_top=22.0, margin_bottom=22.0,
                       area_cols=8, area_rows=10,
                       helper_markers=markers, helper_marker_edge_mm=4.0,
                       helper_marker_len_mm=2.0,
                       helper_markers_top_bottom=True,
                       helper_markers_sides=True,
                       chart_text="bottom of sheet text on a two page chart",
                       show_strip_indicators=True, show_row_indicators=True)
            apply(**TWO)
            type_edges(clip=CLIP, top=T, bottom=B)
            set_patches(400)
            set_notes(True)
            pages = build(f"{tag}__all-on", keep_all_pages=True)
            set_notes(False)
            ctl_note = build(f"{tag}__control-no-note", keep_all_pages=True)
            set_notes(True)
            apply(**{**TWO, "show_strip_indicators": False})
            type_edges(clip=CLIP, top=T, bottom=B)
            set_patches(400)
            ctl_lbl = build(f"{tag}__control-no-strip-letters",
                            keep_all_pages=True)
            e = {"pages_built": len(pages or []),
                 "control_pages_built": len(ctl_note or []),
                 "T_asked_mm": T, "B_asked_mm": B, "clip_asked_mm": CLIP,
                 "markers": markers,
                 "marker_reserve_mm": 7.0 if markers else 0.0}
            if pages and ctl_note and len(pages) == len(ctl_note):
                for i, (pg, c) in enumerate(zip(pages, ctl_note), 1):
                    b, dpi = read_gray(pg)
                    a, _ = read_gray(c)
                    if a.shape != b.shape:
                        e[f"page{i}_note"] = "size mismatch"
                    else:
                        e[f"page{i}_note"] = extent_mm(diff_ink(a, b), dpi)
                    if not markers:
                        w_px = int(round(24.0 * dpi / 25.4))
                        e[f"page{i}_clip_band_columns"] = extent_mm(
                            b[:, :w_px] < 200, dpi)
                    if ctl_lbl and len(ctl_lbl) >= i:
                        lbl, _ = read_gray(ctl_lbl[i - 1])
                        e[f"page{i}_strip_letters"] = (
                            extent_mm(diff_ink(lbl, b), dpi)
                            if lbl.shape == b.shape else "size mismatch")
            res["steps"].append({"step": tag, **e})
            claim(tag,
                  "a two page chart was built and BOTH pages measured",
                  bool(pages) and len(pages) >= 2
                  and isinstance(e.get("page2_note"), dict), e)

    # =================================================================== 03 ==
    # THE EXTREMES.
    if want("03"):
        print("\n03 the parameter extremes")
        EXTREMES = (
            # zero margins on every side
            ("03a-zero-margins",
             dict(margin_top=0.0, margin_right=0.0, margin_bottom=0.0,
                  margin_left=0.0, clip_border=False, clip_content_mode="off",
                  chart_text="zero margin sheet", area_cols=10, area_rows=12),
             (4.0, 4.0, 4.0), 150),
            # markers LONGER than the margin
            ("03b-markers-longer-than-the-margin",
             dict(margin_top=6.0, margin_right=6.0, margin_bottom=6.0,
                  margin_left=6.0, clip_border=False, clip_content_mode="off",
                  helper_markers=True, helper_marker_edge_mm=4.0,
                  helper_marker_len_mm=20.0,
                  helper_markers_top_bottom=True, helper_markers_sides=True,
                  chart_text="markers longer than the margin",
                  area_cols=10, area_rows=12),
             (4.0, 4.0, 4.0), 150),
            # Clip larger than the band, on the SMALLEST paper ChromIQ offers
            ("03c-4x6-clip-30-on-a-24mm-band",
             dict(paper="4x6", clip_border=True, clip_border_width_mm=24.0,
                  clip_side="left", clip_content_mode="text",
                  margin_left=24.0, margin_right=6.0,
                  margin_top=8.0, margin_bottom=8.0,
                  area_cols=4, area_rows=6,
                  chart_text="small paper", show_strip_indicators=True),
             (30.0, 4.0, 4.0), 40),
            # forty lines of clip text on the LARGEST paper
            ("03d-A2-forty-lines-of-clip-text",
             dict(paper="A2", clip_border=True, clip_border_width_mm=24.0,
                  clip_side="left",
                  clip_content_mode="text",
                  clip_text="\n".join(f"clip text line {i}" for i in range(1, 41)),
                  margin_left=24.0, margin_right=12.0,
                  margin_top=20.0, margin_bottom=20.0,
                  area_cols=12, area_rows=16,
                  chart_text="forty lines on A2", show_strip_indicators=True),
             (4.0, 4.0, 4.0), 190),
        )
        for tag, over, boxes, patches in EXTREMES:
            apply(**{k: v for k, v in over.items()})
            b = type_edges(clip=boxes[0], top=boxes[1], bottom=boxes[2])
            set_patches(patches)
            rec = panel.get_recipe()
            paper = str(over.get("paper", "A4"))
            from workflow.layout_engine import papers as _papers
            pw_mm, ph_mm = _papers.dimensions_mm(paper)
            e = {"typed_boxes": b, "paper": paper,
                 "paper_w_mm": pw_mm, "paper_h_mm": ph_mm,
                 "panel_clip_notes": panel._text_edge_clip_note_lines()}
            try:
                warn, ovr = type(tab)._engine_text_notes(tab)
                e["panel_notices"] = warn
                e["panel_overlap_notices"] = ovr
            except Exception as exc:                               # noqa: BLE001
                e["panel_notices"] = f"<raised {exc!r}>"
            set_notes(True)
            full = build(f"{tag}__all-on")
            set_notes(False)
            ctl = build(f"{tag}__control-no-note")
            if full is not None and ctl is not None:
                sheet, dpi = read_gray(full)
                a, _ = read_gray(ctl)
                e["sheet_dpi"] = dpi
                e["sheet_px"] = list(sheet.shape)
                if a.shape == sheet.shape:
                    e["note"] = extent_mm(diff_ink(a, sheet), dpi)
                else:
                    e["note"] = "size mismatch"
                e["all_ink"] = extent_mm(sheet < 200, dpi)
            res["steps"].append({"step": tag, **e})
            claim(tag, "the sheet was built and its ink measured",
                  full is not None, e)

    # =================================================================== 05 ==
    # THE STRIP LETTERS AGAINST THE TOP DASHES. Step 02b left the letters at
    # the same 5.97 mm with the markers on as 01a measured with them off,
    # while the geometry's own `strip_label_reserve_mm` answers 7.0 mm for the
    # same recipe. One of the two is wrong and this asks the sheet.
    if want("05"):
        print("\n05 the strip letters against the top marker dashes")
        from workflow.layout_engine import geometry as _geo5
        from workflow.layout_engine import instruments as _ins5
        FIVE5 = dict(clip_border=False, clip_content_mode="off",
                     margin_left=12.0, margin_right=12.0,
                     margin_top=22.0, margin_bottom=22.0,
                     area_cols=10, area_rows=12,
                     show_strip_indicators=True, show_row_indicators=True,
                     chart_text="")
        for tag, markers in (("05a-markers-off", False),
                             ("05b-markers-on", True)):
            apply(**{**FIVE5, "helper_markers": markers,
                     "helper_marker_edge_mm": 4.0,
                     "helper_marker_len_mm": 2.0,
                     "helper_markers_top_bottom": True,
                     "helper_markers_sides": True})
            b = type_edges(clip=4.0, top=4.0, bottom=4.0)
            set_patches(120)
            rec = panel.get_recipe()
            kw = rec.build_kwargs()
            g = _ins5.geom_from_build_kwargs(kw)
            e = {"typed_boxes": b,
                 "recipe_helper_markers": bool(rec.helper_markers),
                 "recipe_helper_markers_top_bottom":
                     bool(rec.helper_markers_top_bottom),
                 "kw_helper_markers": kw.get("helper_markers"),
                 "kw_helper_markers_top_bottom":
                     kw.get("helper_markers_top_bottom"),
                 "geom_helper_markers": bool(g.helper_markers),
                 "geom_margins_are_law": bool(g.margins_are_law),
                 "geom_strip_indicator_gap": float(g.strip_indicator_gap),
                 "geom_label_band_mm": float(g.label_band_mm),
                 "strip_label_reserve_mm":
                     float(_geo5.strip_label_reserve_mm(g))}
            set_notes(False)
            full = build(f"{tag}__letters-on")
            apply(**{**FIVE5, "helper_markers": markers,
                     "helper_marker_edge_mm": 4.0,
                     "helper_marker_len_mm": 2.0,
                     "helper_markers_top_bottom": True,
                     "helper_markers_sides": True,
                     "show_strip_indicators": False})
            type_edges(clip=4.0, top=4.0, bottom=4.0)
            set_patches(120)
            ctl = build(f"{tag}__control-no-strip-letters")
            if full is not None and ctl is not None:
                sheet, dpi = read_gray(full)
                a, _ = read_gray(ctl)
                e["sheet_dpi"] = dpi
                e["strip_letters"] = (extent_mm(diff_ink(a, sheet), dpi)
                                      if a.shape == sheet.shape
                                      else "size mismatch")
                # Are the top dashes actually on the sheet? Rows 4.0 to 6.0 mm
                # carry them, and with the markers off that band is blank.
                r0 = int(round(4.0 * dpi / 25.4))
                r1 = int(round(6.0 * dpi / 25.4))
                e["ink_px_in_top_dash_band"] = int((sheet[r0:r1 + 1, :]
                                                    < 200).sum())
                if isinstance(e["strip_letters"], dict) \
                        and e["strip_letters"].get("any_ink"):
                    lt = e["strip_letters"]["top_mm"]
                    e["letter_ink_inside_top_dash_band"] = bool(lt <= 6.0)
            res["steps"].append({"step": tag, **e})
            claim(tag, "the strip letters were isolated and measured against "
                       "the reserve the geometry says it uses",
                  isinstance(e.get("strip_letters"), dict), e)

    # =================================================================== 06 ==
    # THE CLIP BAND'S TEXT AGAINST THE SIDE DASHES. This is the fault the
    # FIRST challenge round reported fixed, measured this time on the sheet
    # the app writes rather than on a geometry built beside it.
    #
    # The control is the SAME recipe with an empty "Clip-border content" text,
    # so the band is still reserved and the layout is bit-identical: the only
    # thing the difference can contain is the band's own text. Switching the
    # content mode off instead un-reserves the band and moves the page.
    if want("06"):
        print("\n06 the clip band's text against the side dashes")
        from workflow import text_edge_fit as _tef6
        from workflow.layout_engine import geometry as _geo6
        from workflow.layout_engine import instruments as _ins6
        SIX = dict(clip_border=True, clip_border_width_mm=24.0,
                   clip_side="left", clip_content_mode="text",
                   margin_left=24.0, margin_right=12.0,
                   margin_top=22.0, margin_bottom=22.0,
                   area_cols=10, area_rows=12,
                   show_strip_indicators=True, show_row_indicators=False,
                   chart_text="")
        for tag, markers in (("06a-clip-text-markers-off", False),
                             ("06b-clip-text-markers-on", True)):
            MK = dict(helper_markers=markers, helper_marker_edge_mm=4.0,
                      helper_marker_len_mm=2.0,
                      helper_markers_top_bottom=True,
                      helper_markers_sides=True)
            apply(**{**SIX, **MK, "clip_text": CLIP_TEXT})
            b = type_edges(clip=4.0, top=4.0, bottom=4.0)
            set_patches(120)
            rec = panel.get_recipe()
            g = _ins6.geom_from_build_kwargs(rec.build_kwargs())
            area = _geo6.clip_area_mm(g, 297.0, 210.0,
                                      *panel._clip_text_fit_inputs())
            e = {"typed_boxes": b, "markers": markers,
                 "panel_geom_helper_markers": bool(g.helper_markers),
                 "panel_geom_side_text_edge_mm":
                     float(_tef6.geom_side_text_edge_mm(g)),
                 "panel_clip_area_x_mm":
                     None if area is None else round(area[0], 2)}
            set_notes(False)
            full = build(f"{tag}__clip-text-on")
            apply(**{**SIX, **MK, "clip_text": ""})
            type_edges(clip=4.0, top=4.0, bottom=4.0)
            set_patches(120)
            ctl = build(f"{tag}__control-empty-clip-text")
            if full is not None and ctl is not None:
                sheet, dpi = read_gray(full)
                a, _ = read_gray(ctl)
                e["sheet_dpi"] = dpi
                e["clip_text_ink"] = (extent_mm(diff_ink(a, sheet), dpi)
                                      if a.shape == sheet.shape
                                      else "size mismatch")
                # The side dash band on the LEFT edge runs 4.0 to 6.0 mm in.
                c0 = int(round(4.0 * dpi / 25.4))
                c1 = int(round(6.0 * dpi / 25.4))
                if isinstance(e["clip_text_ink"], dict):
                    m = diff_ink(a, sheet)
                    e["clip_text_px_inside_side_dash_band"] = int(
                        m[:, c0:c1 + 1].sum())
            res["steps"].append({"step": tag, **e})
            claim(tag, "the clip band's own text was isolated and measured "
                       "against the side dash band",
                  isinstance(e.get("clip_text_ink"), dict), e)

    # =================================================================== 07 ==
    # THE ROW INDICATOR LABELS' FLOOR. `raster.apply_row_label_geometry`
    # floors the labels at the largest of the clip border, "Clip" and the
    # ruler markers' reach, and raises the left margin to hold them. The panel
    # quotes that floor; this asks the sheet for it.
    if want("07"):
        print("\n07 the row indicator labels against the side dashes")
        from workflow.layout_engine import instruments as _ins7
        SEVEN = dict(clip_border=False, clip_content_mode="off",
                     margin_left=4.0, margin_right=12.0,
                     margin_top=22.0, margin_bottom=22.0,
                     area_cols=10, area_rows=12,
                     show_strip_indicators=True, show_row_indicators=True,
                     chart_text="")
        for tag, markers in (("07a-row-labels-markers-off", False),
                             ("07b-row-labels-markers-on", True)):
            MK = dict(helper_markers=markers, helper_marker_edge_mm=4.0,
                      helper_marker_len_mm=2.0,
                      helper_markers_top_bottom=True,
                      helper_markers_sides=True)
            apply(**{**SEVEN, **MK})
            b = type_edges(clip=4.0, top=4.0, bottom=4.0)
            set_patches(120)
            rec = panel.get_recipe()
            g = _ins7.geom_from_build_kwargs(rec.build_kwargs())
            e = {"typed_boxes": b, "markers": markers,
                 "panel_geom_row_label_floor_mm":
                     float(getattr(g, "row_label_floor", 0.0) or 0.0),
                 "panel_geom_margin_l_mm": float(g.margin_l)}
            set_notes(False)
            full = build(f"{tag}__row-labels-on")
            apply(**{**SEVEN, **MK, "show_row_indicators": False})
            type_edges(clip=4.0, top=4.0, bottom=4.0)
            set_patches(120)
            ctl = build(f"{tag}__control-no-row-labels")
            if full is not None and ctl is not None:
                sheet, dpi = read_gray(full)
                a, _ = read_gray(ctl)
                e["sheet_dpi"] = dpi
                e["row_labels_and_shift"] = (
                    extent_mm(diff_ink(a, sheet), dpi)
                    if a.shape == sheet.shape else "size mismatch")
            res["steps"].append({"step": tag, **e})
            claim(tag, "the row indicator labels' leftmost ink was measured "
                       "against the floor the panel quotes",
                  isinstance(e.get("row_labels_and_shift"), dict), e)

    # =================================================================== 04 ==
    # THE PANEL'S OWN NOTE ABOUT THE MARKERS, WITH A TYPED ZERO. The block
    # compares the markers' raw ink reach against the TYPED box, not against
    # the distance the sheet uses, so a marker reserve BELOW the 4 mm a typed
    # zero resolves to still fires and names a distance nothing is drawn at.
    if want("04"):
        print("\n04 the panel note when the markers reserve less than 4 mm")
        from workflow import text_edge_fit as _tef
        from workflow.layout_engine import geometry as _geo
        from workflow.layout_engine import instruments as _ins
        for tag, boxes, m_edge, m_len in (
                ("04a-typed-0-markers-0.5+1.0", (0.0, 4.0, 4.0), 0.5, 1.0),
                ("04b-typed-4-markers-0.5+1.0", (4.0, 4.0, 4.0), 0.5, 1.0)):
            apply(clip_border=True, clip_border_width_mm=24.0,
                  clip_side="left", clip_content_mode="text",
                  margin_left=24.0, margin_right=12.0,
                  helper_markers=True, helper_marker_edge_mm=m_edge,
                  helper_marker_len_mm=m_len,
                  helper_markers_top_bottom=True, helper_markers_sides=True)
            b = type_edges(clip=boxes[0], top=boxes[1], bottom=boxes[2])
            rec = panel.get_recipe()
            g = _ins.geom_from_build_kwargs(rec.build_kwargs())
            area = _geo.clip_area_mm(g, 297.0, 210.0,
                                     *panel._clip_text_fit_inputs())
            e = {"typed_boxes": b,
                 "marker_edge_mm": m_edge, "marker_len_mm": m_len,
                 "marker_ink_reach_mm":
                     _tef.helper_marker_ink_reach_mm(m_edge, m_len),
                 "geom_text_edge_clip_mm": float(g.text_edge_clip_mm),
                 "effective_side_edge_mm":
                     _tef.geom_side_text_edge_mm(g),
                 "clip_area_x_mm": None if area is None else round(area[0], 2),
                 "panel_clip_notes": panel._text_edge_clip_note_lines()}
            res["steps"].append({"step": tag, **e})
            claim(tag, "the panel note was collected beside the geometry it "
                       "describes", True, e)

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
