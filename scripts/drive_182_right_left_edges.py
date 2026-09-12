#!/usr/bin/env python3
"""#182 RIGHT AND LEFT PAGE EDGES — driven in the REAL window, on screen.

Knut's specification of 2026-09-12 (issue 182, comment 5648155099) for the two
side edges, exercised one parameter at a time against the real
`LayoutOptionsPanel` in a real `MainWindow`, with a photograph of the window at
each step and the ink measured off the sheet the app itself writes.

Two things are recorded at every step and they are deliberately kept apart:

* what the WINDOW says: the "Measured from Preview" frame's red message field
  and the ⓘ notices, read off the live widgets;
* what the PAPER says: the ink's own distance from the page edge, measured on
  the rendered page rather than taken from the widget's opinion of where it put
  it. Several findings on this project have been the difference between the two.

The helper markers are switched OFF wherever the measurement is of the TEXT: the
side dashes print in the same strip, and the first run of this measurement
reported the text pinned at 4.0 mm on every setting, which was the dashes being
measured and not the text.

Usage:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-edges.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-edges-presets
    python scripts/drive_182_right_left_edges.py --out DIR
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

import numpy as np                                                # noqa: E402
from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

WORK = Path("/tmp/chromiq-edges-work")
TARGET = "EdgesRightLeft"
PAPER_W, PAPER_H = 210.0, 297.0
DPI = 200

#: Knut's own four-line clip note, the shape the ColorMunki family carries.
CLIP_TEXT = ("chart identification line\n"
             "top margin note for the instrument\n"
             "bottom margin note for the strip end\n"
             "left and right margin notes for the ruler")

modals: list[dict] = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app):
    """A driver that blocks on a modal gets clicked by the owner instead."""
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        modals.append({"title": w.windowTitle()})
        print(f"    !! modal: {w.windowTitle()!r} -> closing")
        try:
            w.reject()
        except Exception:
            w.close()
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


# --------------------------------------------------------------- the paper --
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


def _ink(img, thresh: int = 250):
    return np.asarray(img.convert("L")) < thresh


def text_ink_mm(with_text, without_text, side: str):
    """Where the CLIP CONTENT'S OWN INK lies, in mm in from *side*'s page edge.

    **THE RULER DASHES PRINT IN THE SAME STRIP, AND MEASURING THEM INSTEAD OF
    THE TEXT IS THE TRAP THIS FUNCTION EXISTS TO AVOID.** The first run of this
    driver reported the text pinned at 4.01 mm on every setting, which was the
    side markers sitting at their own 4.0 mm and not the text at all.

    Telling them apart by how much of a column is inked does NOT work, and that
    was the second attempt: measured on these very sheets, clip-text columns
    run 0.003 to 0.15 of the page height and marker columns 0.02 to 0.08, so
    the two ranges overlap and no threshold separates them.

    What does work is a control: the same recipe rendered with the clip content
    switched OFF draws the same patches and the same dashes and no text, so the
    columns that DIFFER are the text and nothing else.
    """
    d = _ink(with_text) != _ink(without_text)
    cols = np.where(d.any(axis=0))[0]
    if not len(cols):
        return None, None
    lo_mm = round(cols[0] * 25.4 / DPI, 2)
    hi_mm = round(cols[-1] * 25.4 / DPI, 2)
    if side == "right":
        # outermost (nearest the page edge) first
        return round(PAPER_W - hi_mm, 2), round(PAPER_W - lo_mm, 2)
    return lo_mm, hi_mm


def any_ink_mm(img, side: str, window_mm: float = 24.0):
    """The outermost ink of ANY kind, which on a marker sheet is a dash."""
    ink = _ink(img)
    if side == "right":
        lo = int(round((PAPER_W - window_mm) * DPI / 25.4))
        cols = np.where(ink[:, lo:].any(axis=0))[0]
        return None if not len(cols) else round(
            PAPER_W - (lo + cols[-1]) * 25.4 / DPI, 2)
    hi = int(round(window_mm * DPI / 25.4))
    cols = np.where(ink[:, :hi].any(axis=0))[0]
    return None if not len(cols) else round(cols[0] * 25.4 / DPI, 2)


def main() -> int:
    out = (Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv
           else Path("/tmp/chromiq-edges-proof"))
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"screen_locked_at_start": locked, "modals": modals,
                 "steps": []}
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
    print(f"00 sandbox ok: {os.environ['CHROMIQ_SETTINGS_FILE']} / {WORK}")

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
    pump(app, 700)
    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 600)

    from workflow.layout_engine.presets import LayoutRecipe

    #: The preset Knut reported the fault on, as the panel takes it.
    BASE = dict(instrument="CM", paper="A4", dpi=DPI,
                layout_mode="area_first", area_method="by_grid",
                area_cols=17, area_rows=18,
                use_instrument_margins=False,
                clip_border=True, clip_border_width_mm=24.0,
                clip_side="right", clip_content_mode="text",
                clip_text=CLIP_TEXT, clip_flip_180=True,
                margin_top=34.0, margin_right=24.0,
                margin_bottom=18.0, margin_left=6.0,
                text_edge_top_mm=8.0, text_edge_mm=4.0, text_edge_clip_mm=4.0,
                show_strip_indicators=True,
                helper_markers=True, helper_marker_edge_mm=4.0,
                helper_marker_len_mm=2.0,
                chart_text="", stamp_command=False,
                chart_text_size_mm=0.0, clip_text_size_mm=0.0)

    def apply(**over):
        r = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(r)
        pump(app, 900)
        tab._update_margin_inspector()
        pump(app, 500)
        return r

    def field_text() -> str:
        mp = getattr(tab, "_margin_panel", None)
        if mp is None:
            return "<no margin panel>"
        try:
            return str(mp.status_message())
        except Exception as exc:                                  # noqa: BLE001
            return f"<raised {exc!r}>"

    def snap(name: str, comment: str, side: str = "right",
             shot: bool = False, **over) -> dict:
        r = apply(**over)
        try:
            warns, red = type(tab)._engine_text_notes(tab)
        except Exception as exc:                                  # noqa: BLE001
            warns, red = [f"<raised {exc!r}>"], []
        g, img = render(r)
        # The control: the same sheet with the clip text replaced by a single
        # space. It keeps the content MODE, so the band is still reserved and
        # the patch block does not move; only the glyphs go.
        #
        # `clip_content_mode="off"` was tried first and is WRONG here: on a
        # ColorMunki the band exists only while clip content is on, so the
        # control had no band, the whole layout shifted, and the diff lit up
        # paper the text never touched. It reported the text at 2.74 mm on a
        # sheet where the geometry and a direct mid-page reading both say 4.13.
        from dataclasses import replace as _replace
        _g2, ctrl = render(_replace(r, clip_text=" "))
        assert abs(_g2.lbord - g.lbord) < 1e-6, (
            "the control moved the band, so the difference is not the text")
        measured, inner = text_ink_mm(img, ctrl, side)
        all_ink = any_ink_mm(img, side)
        st = {"step": name, "comment": comment,
              "Clip_mm": r.text_edge_clip_mm,
              "helper_markers": bool(r.helper_markers),
              "helper_marker_edge_mm": r.helper_marker_edge_mm,
              "helper_marker_len_mm": r.helper_marker_len_mm,
              "helper_markers_sides": bool(r.helper_markers_sides),
              "clip_border_width_mm": r.clip_border_width_mm,
              "clip_side": r.clip_side,
              "clip_text_ink_mm_from_%s_page_edge" % side: measured,
              "clip_text_ink_reaches_mm": inner,
              "any_ink_mm_from_%s_page_edge" % side: all_ink,
              "row_label_floor_mm": round(float(g.row_label_floor or 0.0), 2),
              "margin_l_mm": round(float(g.margin_l), 2),
              "panel_message_field": field_text(),
              "red_overlap_notices": red,
              "clip_tip_note": (panel._text_edge_tip.live_note()
                                if hasattr(panel, "_text_edge_tip") else "")}
        sheet = out / f"{name}-sheet.png"
        img.save(sheet)
        st["sheet"] = sheet.name
        if shot:
            p = out / f"{name}-window.png"
            ok, why = capture_window(win, p)
            st["window_photo"] = p.name if ok else f"REFUSED: {why}"
            print(f"      photo: {st['window_photo']}")
        res["steps"].append(st)
        print(f"  [{name}] ink {measured} mm from the {side} edge; "
              f"{len(red)} red notice(s)")
        return st

    print("\n== A. the reported fault: raising Clip, markers OFF ==")
    for i, clip in enumerate((3.0, 4.0, 5.0, 6.0, 8.0, 12.0, 15.0)):
        snap(f"A{i+1}-clip-{clip:g}mm",
             f"Clip = {clip} mm, helper markers OFF. Before the fix the ink "
             f"froze at 4.90 mm for every Clip above 5.",
             shot=(clip in (4.0, 5.0, 12.0)),
             text_edge_clip_mm=clip, helper_markers=False)

    print("\n== B. the new distance rule: the ruler helper markers ==")
    snap("B1-markers-off", "Markers OFF: the text-box sits at Clip = 4.0 mm.",
         shot=True, text_edge_clip_mm=4.0, helper_markers=False)
    snap("B2-markers-on-sides-on",
         "Markers ON, Sides ON, 4.0 mm in and 2.0 mm long: the text-box must "
         "sit at 4.0 + 2.0 + 1.0 = 7.0 mm.",
         shot=True, text_edge_clip_mm=4.0, helper_markers=True,
         helper_markers_sides=True)
    snap("B3-markers-on-sides-off",
         "Markers ON but Sides OFF: no dashes down this edge, so the text-box "
         "goes back to Clip = 4.0 mm.",
         text_edge_clip_mm=4.0, helper_markers=True,
         helper_markers_sides=False)
    snap("B4-clip-beats-the-markers",
         "Clip = 12.0 mm with the same markers: whichever reaches further in "
         "wins, and here that is Clip.",
         shot=True, text_edge_clip_mm=12.0, helper_markers=True)
    snap("B5-longer-markers",
         "Markers 6.0 mm in and 5.0 mm long: the reserve follows them to "
         "6 + 5 + 1 = 12.0 mm.",
         text_edge_clip_mm=4.0, helper_markers=True,
         helper_marker_edge_mm=6.0, helper_marker_len_mm=5.0)

    print("\n== C. the left edge: row indicators crossed with the markers ==")
    # A 16 mm band, NOT 6 mm: `lbord = clip_border_width - border`, so on this
    # ColorMunki (border 6.0) a 6 mm "Clip border width" reserves nothing at
    # all and there is no band for the text to live in. The first run of this
    # driver asked for 6 mm and measured no clip ink on any of C1 to C3.
    LEFT = dict(clip_side="left", clip_border_width_mm=16.0, margin_left=6.0,
                show_row_indicators=True, text_edge_clip_mm=4.0)
    snap("C1-rows-on-markers-off",
         "Row indicators ON, markers OFF: their left edge is the larger of the "
         "clip-border width and Clip.",
         side="left", shot=True, helper_markers=False, **LEFT)
    snap("C2-rows-on-markers-on",
         "Row indicators ON, markers ON: their left edge must also clear "
         "4.0 + 2.0 + 1.0 = 7.0 mm, and the left margin carries the cost.",
         side="left", shot=True, helper_markers=True, **LEFT)
    snap("C3-rows-off-markers-on",
         "Row indicators OFF, markers ON: only the clip text is on this edge.",
         side="left", helper_markers=True,
         **{**LEFT, "show_row_indicators": False})
    snap("C4-rows-on-wide-border",
         "Row indicators ON with a 26 mm clip border: the border is now the "
         "largest of the three and decides.",
         side="left", helper_markers=True,
         **{**LEFT, "clip_border_width_mm": 26.0})

    # His table's other half: with NO clip border the row indicators' floor is
    # the larger of "Clip" and the marker reserve, with nothing else in it.
    # C1 to C4 above all carry a band wider than both, so the border decides
    # there and the marker term never shows.
    NOBORDER = dict(clip_side="left", clip_border=False,
                    clip_content_mode="off", clip_text="",
                    margin_left=6.0, show_row_indicators=True,
                    text_edge_clip_mm=4.0)
    for name, mk, why in (
            ("C5-noborder-rows-on-markers-off", dict(helper_markers=False),
             "No clip border, row indicators ON, markers OFF: their floor is "
             "Clip = 4.0 mm."),
            ("C6-noborder-rows-on-markers-on", dict(helper_markers=True),
             "No clip border, row indicators ON, markers ON: their floor must "
             "rise to 4.0 + 2.0 + 1.0 = 7.0 mm."),
            ("C7-noborder-rows-on-sides-off",
             dict(helper_markers=True, helper_markers_sides=False),
             "…and Sides OFF puts it back to 4.0 mm.")):
        r = apply(**{**NOBORDER, **mk})
        from workflow.layout_engine import instruments as _inst
        g = _inst.geom_from_build_kwargs(r.build_kwargs())
        res["steps"].append({
            "step": name, "comment": why,
            "row_label_floor_mm": round(float(g.row_label_floor or 0.0), 2),
            "margin_l_mm": round(float(g.margin_l), 2),
            "clip_border": False})
        print(f"  [{name}] row label floor {g.row_label_floor:.2f} mm, "
              f"margin_l {g.margin_l:.2f} mm")

    print("\n== D. the height rule ==")
    for name, over, why in (
            ("D1-height-markers-off",
             dict(helper_markers=False, text_edge_top_mm=8.0, text_edge_mm=4.0),
             "A4 less T 8.0 and B 4.0 = 285.0 mm."),
            ("D2-height-markers-on",
             dict(helper_markers=True, text_edge_top_mm=8.0, text_edge_mm=4.0),
             "…or 297 - (4x2 + 2x2 + 2) = 283.0 mm, whichever is smaller."),
            ("D3-height-topbottom-off",
             dict(helper_markers=True, helper_markers_top_bottom=False,
                  text_edge_top_mm=8.0, text_edge_mm=4.0),
             "Top/bottom OFF: no dashes at the ends, so 285.0 mm again.")):
        r = apply(**over)
        from workflow.layout_engine import geometry, instruments
        g = instruments.geom_from_build_kwargs(r.build_kwargs())
        area = geometry.clip_area_mm(g, PAPER_H, PAPER_W)
        res["steps"].append({"step": name, "comment": why,
                             "band_height_mm": round(area[3], 2),
                             "band_y_mm": round(area[1], 2)})
        print(f"  [{name}] band height {area[3]:.2f} mm")

    (out / "onscreen.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out / 'onscreen.json'}")
    print(f"modals seen: {len(modals)}")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
