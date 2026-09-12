#!/usr/bin/env python3
"""#182 CHALLENGE ROUND against the four-edge text specification.

Drives the REAL `MainWindow` on screen, sets every value through the REAL
`LayoutOptionsPanel` widgets, reads the recipe back out of the panel with
`apply_to_recipe`, renders the sheet with the app's own engine and MEASURES THE
INK. Nothing here trusts a widget's opinion of where it put something.

Every demo REFUSES to be written unless it demonstrates its own claim, in the
manner of `scripts/make_report_limit_demos.py`.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-chal.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-chal-presets
    python scripts/drive_182_challenge_four_edges.py --out DIR
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import replace
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

WORK = Path("/tmp/chromiq-chal-work")
PAPER_W, PAPER_H = 210.0, 297.0
DPI = 200
CLIP_TEXT = ("chart identification line\n"
             "top margin note for the instrument\n"
             "bottom margin note for the strip end\n"
             "left and right margin notes for the ruler")

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
        modals.append({"title": w.windowTitle()})
        print(f"    !! modal {w.windowTitle()!r} -> closed")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def render(recipe, npat: int = 306):
    """The sheet the app's own engine draws for this recipe."""
    from workflow.layout_engine import geometry, instruments, raster
    from workflow.layout_engine.ti1_reader import ColorTarget
    g = instruments.geom_from_build_kwargs(recipe.build_kwargs())
    lay = geometry.compute(g, PAPER_W, PAPER_H, npat)
    target = ColorTarget(color_rep="iRGB",
                         device_fields=["RGB_R", "RGB_G", "RGB_B"],
                         patches=[((50.0, 50.0, 50.0), (40.0, 45.0, 50.0))
                                  for _ in range(npat)])
    res = raster.render_pages(
        target, lay, g, seed=1, randomize=False,
        paper_w_mm=PAPER_W, paper_h_mm=PAPER_H, dpi=DPI,
        clip_content_mode=recipe.clip_content_mode,
        clip_text=recipe.clip_text,
        clip_text_font=recipe.clip_text_font,
        clip_text_size_mm=recipe.clip_text_size_mm,
        clip_flip_180=recipe.clip_flip_180,
        chart_text=recipe.chart_text,
        text_edge_mm=recipe.text_edge_mm,
        helper_markers=recipe.helper_markers,
        helper_marker_edge_mm=recipe.helper_marker_edge_mm,
        helper_marker_len_mm=recipe.helper_marker_len_mm,
        helper_markers_top_bottom=recipe.helper_markers_top_bottom,
        helper_markers_sides=recipe.helper_markers_sides)
    return g, res.images[0]


def mm2px(v: float) -> int:
    return int(round(v * DPI / 25.4))


def px2mm(v: float) -> float:
    return round(v * 25.4 / DPI, 2)


def is_paper(img) -> np.ndarray:
    """Pixels that are bare paper: no ink, no patch colour."""
    a = np.asarray(img.convert("RGB")).astype(int)
    return (a > 250).all(axis=2)


def ink(img, thresh: int = 250) -> np.ndarray:
    return np.asarray(img.convert("L")) < thresh


def claim(name: str, text: str, ok: bool, detail: dict) -> None:
    """A demo that does not demonstrate its own claim is a failure, loudly."""
    CLAIMS.append({"demo": name, "claim": text, "demonstrated": bool(ok),
                   **detail})
    print(f"  [{name}] {'DEMONSTRATED' if ok else '*** NOT DEMONSTRATED ***'}"
          f" :: {text}")
    for k, v in detail.items():
        print(f"        {k} = {v}")


def main() -> int:
    out = (Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv
           else Path("/tmp/chromiq-challenge-proof"))
    out.mkdir(parents=True, exist_ok=True)

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
          f"size {win.width()}x{win.height()}")

    tab = win._tab_chart
    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 800)
    tab._manual_target_name_edit.setText("Challenge182")
    pump(app, 600)
    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 600)

    from workflow.layout_engine.presets import LayoutRecipe

    BASE = dict(instrument="CM", paper="A4", dpi=DPI,
                layout_mode="area_first", area_method="by_grid",
                area_cols=17, area_rows=18,
                use_instrument_margins=False,
                clip_border=True, clip_border_width_mm=24.0,
                clip_side="right", clip_content_mode="text",
                clip_text=CLIP_TEXT, clip_flip_180=True,
                margin_top=34.0, margin_right=24.0,
                margin_bottom=18.0, margin_left=6.0,
                text_edge_top_mm=4.0, text_edge_bottom_mm=4.0,
                text_edge_mm=4.0, text_edge_clip_mm=4.0,
                show_strip_indicators=True, show_row_indicators=True,
                helper_markers=True, helper_marker_edge_mm=4.0,
                helper_marker_len_mm=2.0,
                helper_markers_top_bottom=True, helper_markers_sides=True,
                chart_text="", stamp_command=False,
                chart_text_size_mm=0.0, clip_text_size_mm=0.0)

    def through_the_panel(**over) -> LayoutRecipe:
        """Set the values on the REAL widgets and read the recipe back out."""
        want = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(want)
        pump(app, 800)
        got = panel.apply_to_recipe(LayoutRecipe.from_dict({**BASE, **over}))
        tab._update_margin_inspector()
        pump(app, 400)
        return got

    def field_text() -> str:
        mp = getattr(tab, "_margin_panel", None)
        if mp is None:
            return "<no margin panel>"
        try:
            return str(mp.status_message())
        except Exception as exc:                                  # noqa: BLE001
            return f"<raised {exc!r}>"

    def notices():
        try:
            return type(tab)._engine_text_notes(tab)
        except Exception as exc:                                  # noqa: BLE001
            return [f"<raised {exc!r}>"], []

    # ---------------------------------------------------------------- 01 ----
    # THE CLIP STRIP PASTES OPAQUE WHITE OVER THE PATCHES.
    #
    # `geometry.clip_area_mm` sizes the content rectangle with the
    # marker-effective page-edge reserve; `raster.render_page` recomputes the
    # overhang for the compositing MASK from the raw "Clip". The difference is
    # pasted as the strip's own opaque white background, which erases patches.
    print("\n01 the clip strip's white background over the row numbers "
          "and the patch block")
    from workflow import text_edge_fit as _tef
    LONG = CLIP_TEXT + "\n" + "\n".join(
        f"extra clip line number {i} for the challenge" for i in range(1, 7))
    rows01 = []
    for tag, txt, nlines, rownums, ml in (("a-short", CLIP_TEXT, 4, True, 24.0),
                                          ("b-long", LONG, 10, True, 24.0),
                                          ("c-no-row-numbers", LONG, 10,
                                           False, 12.0)):
        r = through_the_panel(clip_side="left", clip_border_width_mm=12.0,
                              margin_left=ml, margin_right=6.0,
                              clip_flip_180=False, text_edge_clip_mm=0.5,
                              show_row_indicators=rownums, clip_text=txt)
        w01, red01 = notices()
        g, im = render(r)
        # The control keeps the band and the mode and drops the glyphs, so the
        # patch block does not move and only the strip's own doing is measured.
        gc, imc = render(replace(r, clip_text=" "))
        assert abs(g.lbord - gc.lbord) < 1e-6, "the control moved the band"
        im.save(out / f"01{tag}-clip-strip-white-over-the-sheet.png")
        imc.save(out / f"01{tag}-control-same-band-no-text.png")

        # Ink that the control prints and this sheet has wiped to bare paper.
        erased = is_paper(im) & ~is_paper(imc)
        cols = np.where(erased.any(axis=0))[0]
        patch_x0 = mm2px(float(g.margin_l))
        on_labels = int(erased[:, :patch_x0].sum())
        on_patches = int(erased[:, patch_x0:].sum())
        _eff = _tef.geom_side_text_edge_mm(g)
        _zone = g.lbord + g.border
        _over_geom = _tef.clip_text_overhang_mm(_zone, _eff, nlines, 0.0)
        _over_mask = _tef.clip_text_overhang_mm(
            _zone, float(g.text_edge_clip_mm), nlines, 0.0)
        rows01.append({
            "case": tag, "clip_text_lines": nlines,
            "row_indicators": rownums,
            "erased_pixels_total": int(erased.sum()),
            "erased_pixels_on_the_row_numbers": on_labels,
            "erased_pixels_on_the_patch_block": on_patches,
            "patch_block_starts_mm": round(float(g.margin_l), 2),
            "erased_columns_mm_from_left_edge":
                [px2mm(cols[0]), px2mm(cols[-1])] if len(cols) else None,
            "clip_zone_mm": round(_zone, 2),
            "effective_page_edge_reserve_mm": round(_eff, 2),
            "overhang_the_geometry_drew_mm": round(_over_geom, 2),
            "overhang_the_mask_protected_mm": round(_over_mask, 2),
            "unprotected_mm": round(_over_geom - _over_mask, 2),
            "panel_red_notices": red01})
        print(f"      {tag}: {int(erased.sum())} pixels wiped to bare paper, "
              f"{on_labels} on the row numbers and {on_patches} on the "
              f"patches; the mask protected {_over_mask:.2f} mm of the "
              f"{_over_geom:.2f} mm the geometry drew")
    res["steps"].append({"step": "01", "rows": rows01})
    claim("01", "the clip strip's opaque white background is pasted over "
                "whatever is beside the band, wiping the row indicator "
                "numbers and then the patches themselves to bare paper",
          bool(rows01[0]["erased_pixels_on_the_row_numbers"] > 500
               and rows01[2]["erased_pixels_on_the_patch_block"] > 500
               and all(q["unprotected_mm"] > 0.05 for q in rows01)),
          {"rows": [{k: v for k, v in q.items()
                     if k != "panel_red_notices"} for q in rows01]})

    # ---------------------------------------------------------------- 02 ----
    # THE SAME SHEET WITH THE SIDE MARKERS OFF: the two agree, so the fault is
    # the marker reserve and not the overhang rule.
    print("\n02 the same sheet with the side helper markers off")
    r02 = through_the_panel(clip_side="left", clip_border_width_mm=12.0,
                            margin_left=24.0, margin_right=6.0,
                            clip_flip_180=False, text_edge_clip_mm=0.5,
                            helper_markers_sides=False)
    r02 = replace(r02, clip_text=LONG)
    g02, img02 = render(r02)
    g02c, img02c = render(replace(r02, clip_text=" "))
    img02.save(out / "02-side-markers-off-no-erasure.png")
    erased02 = is_paper(img02) & ~is_paper(img02c)
    claim("02", "with the side markers off the mask and the rectangle agree, "
                "so the same ten lines wipe nothing out",
          bool(erased02.sum() < 200),
          {"erased_pixels": int(erased02.sum())})

    # ---------------------------------------------------------------- 03 ----
    # THE CLIP BAND IS CENTRED VERTICALLY, SO IT IGNORES "T".
    print("\n03 the clip band's own top against 'T'")
    # Measured two ways: the app's own `geometry.clip_area_mm`, which is the
    # function under test, and the INK of the "notes" content, which fills the
    # rectangle it is handed so its extent is the rectangle's.
    from workflow.layout_engine import geometry as _geo
    rows03 = []
    for T, B in ((4.0, 4.0), (12.0, 4.0), (20.0, 4.0), (4.0, 20.0)):
        r = through_the_panel(clip_side="left", clip_border_width_mm=24.0,
                              margin_left=30.0, margin_right=6.0,
                              margin_top=34.0, margin_bottom=18.0,
                              clip_flip_180=False, clip_content_mode="notes",
                              text_edge_top_mm=T, text_edge_mm=B,
                              helper_markers=False)
        g, im = render(r)
        area = _geo.clip_area_mm(g, PAPER_H, PAPER_W)
        # The notes design paints a bordered block across the whole rectangle,
        # so the topmost ink inside the band's own columns is its top edge.
        band_cols = slice(0, mm2px(g.lbord + g.border))
        rws = np.where(ink(im)[:, band_cols].any(axis=1))[0]
        top_ink = px2mm(rws[0]) if len(rws) else None
        bot_ink = round(PAPER_H - px2mm(rws[-1]), 2) if len(rws) else None
        rows03.append({"T_mm": T, "B_mm": B,
                       "rect_top_mm": round(area[1], 2) if area else None,
                       "rect_height_mm": round(area[3], 2) if area else None,
                       "band_ink_top_mm": top_ink,
                       "band_ink_bottom_mm": bot_ink})
        im.save(out / f"03-clip-band-T{T:g}-B{B:g}.png")
        print(f"      T={T} B={B}: rectangle top {rows03[-1]['rect_top_mm']} mm "
              f"(spec says {T}), ink top {top_ink} mm, ink bottom {bot_ink} mm "
              f"(spec says {B})")
    res["steps"].append({"step": "03", "rows": rows03})
    _asym = [q for q in rows03 if q["T_mm"] != q["B_mm"]
             and q["rect_top_mm"] is not None]
    _bad = [q for q in _asym
            if q["rect_top_mm"] + 0.3 < q["T_mm"]
            or (q["band_ink_bottom_mm"] or 0.0) + 0.3 < q["B_mm"]]
    claim("03", "with T and B different the clip band's content rectangle is "
                "centred on the page instead of being held T from the top and "
                "B from the bottom, so it crosses one of the two reserves",
          bool(_asym and len(_bad) == len(_asym)),
          {"rows": rows03, "rows_that_cross_a_reserve": len(_bad)})

    # ---------------------------------------------------------------- 04 ----
    # "Clip" ABOVE THE BAND WIDTH CUTS THE TEXT OFF THE SHEET.
    print("\n04 'Clip' raised above the band width")
    rows04 = []
    for clip in (4.0, 15.0, 24.0, 30.0):
        r = through_the_panel(clip_side="left", clip_border_width_mm=24.0,
                              margin_left=40.0, margin_right=6.0,
                              clip_flip_180=False, text_edge_clip_mm=clip,
                              helper_markers=False)
        g, im = render(r)
        gc, imc = render(replace(r, clip_text=" "))
        d = ink(im) != ink(imc)
        cls = np.where(d.any(axis=0))[0]
        # The lines run UP the band, so one line of text is one group of
        # COLUMNS. Counting rows counts characters.
        lines_seen = 0
        if len(cls):
            lines_seen = int((np.diff(cls) > mm2px(0.6)).sum()) + 1
        _need = _tef.clip_text_needed_mm(4, 0.0)
        _rect_w = max(0.0, 24.0 - clip
                      + _tef.clip_text_overhang_mm(24.0, clip, 4, 0.0))
        rows04.append({"Clip_mm": clip,
                       "clip_text_lines_printed_of_4": lines_seen,
                       "text_ink_width_mm":
                           round(px2mm(cls[-1]) - px2mm(cls[0]), 2)
                           if len(cls) else 0.0,
                       "rectangle_width_mm": round(_rect_w, 2),
                       "the_text_needs_mm": round(_need, 2),
                       "text_ink_from_left_mm":
                           [px2mm(cls[0]), px2mm(cls[-1])] if len(cls) else None})
        im.save(out / f"04-clip-{clip:g}mm-on-a-24mm-band.png")
        print(f"      Clip={clip}: {lines_seen} of 4 lines printed, ink is "
              f"{rows04[-1]['text_ink_width_mm']} mm wide, the rectangle is "
              f"{_rect_w:.2f} mm and the text needs {_need:.2f} mm")
    res["steps"].append({"step": "04", "rows": rows04})
    _base = rows04[0]["clip_text_lines_printed_of_4"]
    claim("04", "raising 'Clip' above the clip band's width makes the content "
                "rectangle narrower than the text needs, so lines are cut off "
                "the sheet with nothing said",
          bool(any(q["clip_text_lines_printed_of_4"] < _base
                   and q["rectangle_width_mm"] + 0.05 < q["the_text_needs_mm"]
                   for q in rows04[1:])),
          {"rows": rows04})

    # ---------------------------------------------------------------- 05 ----
    # THE PANEL OFFERS "LOWER Clip" AND LOWERING IT MOVES NOTHING.
    print("\n05 the panel's 'lower Clip' remedy with the side markers on")
    rows05 = []
    for clip in (4.0, 2.0, 0.5, 0.0):
        r = through_the_panel(clip_side="left", clip_border_width_mm=12.0,
                              margin_left=24.0, margin_right=6.0,
                              clip_flip_180=False, text_edge_clip_mm=clip)
        w, red = notices()
        g, im = render(r)
        gc, imc = render(replace(r, clip_text=" "))
        d = ink(im) != ink(imc)
        cls = np.where(d.any(axis=0))[0]
        remedy = [m[m.index("Lowering “Clip”"):] for m in red
                  if "Lowering “Clip”" in m]
        rows05.append({"Clip_mm": clip,
                       "text_ink_from_left_mm":
                           [px2mm(cls[0]), px2mm(cls[-1])] if len(cls) else None,
                       "panel_remedy": remedy[:1]})
        im.save(out / f"05-lower-clip-{clip:g}mm.png")
        print(f"      Clip={clip}: ink {rows05[-1]['text_ink_from_left_mm']} mm")
    res["steps"].append({"step": "05", "rows": rows05})
    _spans = [tuple(r["text_ink_from_left_mm"]) for r in rows05
              if r["text_ink_from_left_mm"]]
    _offered = any(r["panel_remedy"] for r in rows05)
    claim("05", "the panel offers 'Lowering Clip to X would also do it' and "
                "lowering it moves no ink at all, because the helper markers' "
                "reserve is what is binding",
          bool(_offered and len(set(_spans)) == 1),
          {"rows": rows05, "distinct_ink_positions": len(set(_spans))})

    # ---------------------------------------------------------------- 06 ----
    # TURNING THE SIDE MARKERS ON COSTS PATCH AREA.
    print("\n06 what the side markers cost a chart with row indicators")
    rows06 = []
    from workflow.layout_engine import geometry as _gm
    for sides in (False, True):
        r = through_the_panel(clip_side="left", clip_border=False,
                              clip_content_mode="off",
                              area_method="by_size",
                              margin_left=2.0, margin_right=6.0,
                              helper_markers_sides=sides,
                              text_edge_clip_mm=4.0)
        g, im = render(r, npat=4000)
        lay = _gm.compute(g, PAPER_W, PAPER_H, 4000)
        rows06.append({"helper_markers_sides": sides,
                       "row_label_floor_mm": round(float(g.row_label_floor or 0), 2),
                       "left_margin_mm": round(float(g.margin_l), 2),
                       "patches_a_full_page_holds": int(lay.total_patches),
                       "columns": int(getattr(lay, "cols", 0)
                                      or getattr(lay, "n_cols", 0) or 0)})
        im.save(out / f"06-side-markers-{'on' if sides else 'off'}.png")
        print(f"      sides={sides}: floor {rows06[-1]['row_label_floor_mm']} mm, "
              f"left margin {rows06[-1]['left_margin_mm']} mm, "
              f"{rows06[-1]['patches_a_full_page_holds']} patches, "
              f"{rows06[-1]['columns']} columns")
    res["steps"].append({"step": "06", "rows": rows06})
    claim("06", "turning the ruler helper markers on for the sides raises the "
                "left margin on any chart with row indicators, so the patch "
                "area shrinks",
          bool(rows06[1]["left_margin_mm"] > rows06[0]["left_margin_mm"] + 0.05),
          {"rows": rows06,
           "left_margin_cost_mm": round(rows06[1]["left_margin_mm"]
                                        - rows06[0]["left_margin_mm"], 2),
           "patches_lost": rows06[0]["patches_a_full_page_holds"]
                           - rows06[1]["patches_a_full_page_holds"]})

    # -------------------------------------------------------------- photo ---
    locked_now = session_is_locked()
    res["screen_locked_at_end"] = locked_now
    p = out / "00-the-real-window.png"
    ok, why = capture_window(win, p)
    res["window_photo"] = p.name if ok else f"REFUSED: {why}"
    print(f"\n99 window photograph: {res['window_photo']}")

    res["all_claims_demonstrated"] = all(c["demonstrated"] for c in CLAIMS)
    (out / "challenge-measurements.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")
    print(f"\n== every claim demonstrated: {res['all_claims_demonstrated']}")
    win.close()
    pump(app, 400)
    return 0 if res["all_claims_demonstrated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
