#!/usr/bin/env python3
"""Knut's three layout rulings of 2026-09-13, measured on the app's own sheets.

Drives the REAL ChromIQ window, on screen, through the real Manual layout
panel and the real Generate button, and measures the ink on the TIFFs the app
writes. Every element is isolated against a CONTROL sheet built by the same
button with that one element switched off, and the driver checks that the patch
block did not move between the two before it believes the difference.

The three rulings, from the issue rather than from anybody's summary:

* **5649810914, the strip labels.** *"the strip labels do not cross the "Text
  distance from edge" value (or the defined "Distance from page edge" +
  "Marker length" + 1.0mm, whichever is largest (if helper markers are
  enabled)), and then the text overlaps on top of the patch area top edge
  (according to top margin)."*
* **5649955254, the clip band.** Vertically centred between ``(0+T)`` and
  ``(H-B)``, with the helper markers' reserve standing in for whichever of T
  and B is the smaller.
* **5651269930 (an EDIT), the bottom line.** Horizontally centred between two
  bounds that depend on the clip-border side, on whether there is a clip
  border at all, and on whether the side markers reach further in than "Clip".

CALL PATH, because a driver that reaches the geometry by a route the app does
not take can only tell you about that route:

    the real Presets/panel widgets
      -> ui.dialogs.layout_options_panel.LayoutOptionsPanel.get_recipe()
      -> ui.tabs.tab_chart.TabChart._on_generate  (the real button)
      -> workflow.chart_creator.ChartCreator._engine_kwargs
      -> workflow.layout_engine.chart.build_chart
      -> workflow.layout_engine.raster.render_pages   -> the .tif this reads

Nothing here calls `LayoutRecipe.build_kwargs()` to derive a number: that is a
different dict from the one `chart.build_chart` assembles by hand, and the two
have disagreed before (see the comment at `chart.py`'s geom dict).

Usage::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-rulings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-rulings-presets
    python scripts/drive_182_layout_rulings.py --out DIR
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

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

WORK = Path("/tmp/chromiq-rulings-work")
PROJECT = "LayoutRulings"

modals: list[dict] = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def install_modal_watchdog(app):
    """No modal is ever left blocking, and every one that appears is recorded."""
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        title = w.windowTitle()
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:                             # noqa: BLE001
                    pass
        modals.append({"title": title, "text": text[:400]})
        print(f"    !! modal: {title!r} -> closing", flush=True)
        try:
            w.reject()
        except Exception:                                     # noqa: BLE001
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


# ---------------------------------------------------------------------------
# A RULER LAID ON THE APP'S OWN SHEET
# ---------------------------------------------------------------------------
def _read_gray(path: Path):
    import numpy as np
    import tifffile
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        arr = np.array(page.asarray())
        try:
            xres = page.tags["XResolution"].value
            dpi = float(xres[0]) / float(xres[1])
            if int(page.tags["ResolutionUnit"].value) == 3:   # centimetres
                dpi *= 2.54
        except Exception:                                     # noqa: BLE001
            dpi = 200.0
    return (arr.min(axis=2) if arr.ndim == 3 else arr), dpi


#: A row belongs to the patch block when this share of the DENSEST row's ink is
#: on it. A fixed share of the PAGE WIDTH cannot be used: a 64-patch i1 chart is
#: twelve columns wide and covers well under half the sheet.
PATCH_ROW_DENSITY_FRAC = 0.35


def patch_block(path: Path) -> dict:
    """Where the patch block is, in mm from the page's own edges."""
    import numpy as np
    g, dpi = _read_gray(path)
    H, W = g.shape[:2]
    full = 65535 if g.dtype.itemsize == 2 else 255
    ink = g < int(0.94 * full)
    mm = 25.4 / dpi
    density = ink.sum(axis=1) / max(1, W)
    peak = float(density.max())
    if peak <= 0.0:
        return {"error": "the sheet has no ink at all"}
    rows = np.flatnonzero(density >= peak * PATCH_ROW_DENSITY_FRAC)
    if not len(rows):
        return {"error": "no patch block"}
    band = ink[int(rows[0]):int(rows[-1]) + 1, :]
    cols = np.flatnonzero(band.any(axis=0))
    return {
        "dpi": round(dpi, 2),
        "page_w_mm": round(W * mm, 2), "page_h_mm": round(H * mm, 2),
        "top_mm": round(int(rows[0]) * mm, 2),
        "bottom_mm": round((int(rows[-1]) + 1) * mm, 2),
        "left_mm": round(int(cols[0]) * mm, 2),
        "right_mm": round((int(cols[-1]) + 1) * mm, 2),
    }


def isolate(variant: Path, control: Path) -> dict:
    """The bounding box of what ONE element put on the sheet, in mm.

    *control* is the same recipe with that element switched off, built by the
    same button. The two sheets must agree about where the patch block is or
    the difference is the patch block and not the element, which is a mistake
    an earlier round of this project made and reported as a finding.
    """
    import numpy as np
    a, dpi = _read_gray(variant)
    b, _ = _read_gray(control)
    out: dict = {"dpi": round(dpi, 2)}
    pa, pb = patch_block(variant), patch_block(control)
    out["patch_block"] = pa
    out["control_patch_block"] = pb
    moved = [k for k in ("top_mm", "bottom_mm", "left_mm", "right_mm")
             if abs(float(pa.get(k, -1)) - float(pb.get(k, -2))) > 0.3]
    out["control_is_valid"] = not moved
    out["patch_block_moved_by"] = moved
    if a.shape != b.shape:
        out["error"] = f"different sheet sizes {a.shape} vs {b.shape}"
        return out
    d = a.astype(int) != b.astype(int)
    rows, cols = np.flatnonzero(d.any(axis=1)), np.flatnonzero(d.any(axis=0))
    if not len(rows):
        out["ink"] = None
        return out
    mm = 25.4 / dpi
    H, W = a.shape[:2]
    out["ink"] = {
        "top_mm": round(int(rows[0]) * mm, 2),
        "bottom_mm": round((int(rows[-1]) + 1) * mm, 2),
        "left_mm": round(int(cols[0]) * mm, 2),
        "right_mm": round((int(cols[-1]) + 1) * mm, 2),
        "from_bottom_mm": round((H - 1 - int(rows[-1])) * mm, 2),
        "from_right_mm": round((W - 1 - int(cols[-1])) * mm, 2),
        "centre_x_mm": round((int(cols[0]) + int(cols[-1]) + 1) / 2.0 * mm, 2),
        "centre_y_mm": round((int(rows[0]) + int(rows[-1]) + 1) / 2.0 * mm, 2),
        "pixels": int(d.sum()),
    }
    # How much of the element's ink lands INSIDE the patch block's rows, which
    # is the number Knut's ruling is about.
    if pa.get("top_mm") is not None:
        t = int(round(float(pa["top_mm"]) / mm))
        out["ink"]["pixels_inside_the_patch_rows"] = int(d[t:, :].sum())
        out["ink"]["over_the_patch_top_mm"] = round(
            max(0.0, (int(rows[-1]) + 1) * mm - float(pa["top_mm"])), 2)
    return out


def crop(path: Path, out: Path, name: str, y0_mm: float, y1_mm: float) -> str:
    """A strip of the real sheet, saved as a PNG so the ink can be SEEN.

    This is the app's own output, not a widget render, and it is what stands in
    for a photograph while the login session is locked.
    """
    from PIL import Image
    _g, dpi = _read_gray(path)
    im = Image.open(str(path)).convert("RGB")
    y0 = max(0, int(y0_mm * dpi / 25.4))
    y1 = min(im.height, int(y1_mm * dpi / 25.4))
    im.crop((0, y0, im.width, y1)).save(str(out / name))
    return name


def main() -> int:                                            # noqa: C901
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-rulings-proof")
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"screen_locked": locked, "modals": modals, "steps": []}
    print(f"00 screen locked: {locked}", flush=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
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
    res["sandbox"] = {"settings_file": os.environ["CHROMIQ_SETTINGS_FILE"],
                      "presets_dir": os.environ["CHROMIQ_PRESETS_DIR"],
                      "custom_output_path": settings.get("custom_output_path", "")}
    print(f"00 sandbox: {res['sandbox']}", flush=True)

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 1400)
    install_modal_watchdog(app)
    res["window_visible"] = bool(win.isVisible())
    res["window_size"] = [win.frameGeometry().width(),
                          win.frameGeometry().height()]
    print(f"00 window visible: {res['window_visible']} {res['window_size']}",
          flush=True)

    tab = win._tab_chart
    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 700)
    tab._manual_target_name_edit.setText(PROJECT)
    pump(app, 700)

    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 600)

    chk = getattr(tab, "_manual_auto_patches_check", None)
    if chk is not None and chk.isChecked():
        chk.setChecked(False)
        pump(app, 400)
    pw = getattr(tab, "_manual_f_pw", None)
    if pw is not None:
        pw._control.setValue(64)
        pump(app, 400)

    from workflow.layout_engine.presets import LayoutRecipe

    BASE = dict(
        instrument="i1", paper="A4",
        # Area-first gives "margins are law" AND keeps the typed numbers on
        # screen; "Use instrument margins" also gives the law but replaces the
        # boxes with the instrument's own, so a sweep there moves a margin
        # nobody typed.
        layout_mode="area_first", use_instrument_margins=False,
        margin_top=15.0, margin_bottom=15.0, margin_left=12.0,
        margin_right=12.0,
        text_edge_top_mm=4.0, text_edge_mm=4.0, text_edge_clip_mm=4.0,
        chart_text="", stamp_command=False,
        show_strip_indicators=True, show_row_indicators=False,
        helper_markers=False, helper_marker_edge_mm=4.0,
        helper_marker_len_mm=2.0, helper_markers_top_bottom=True,
        helper_markers_sides=True,
        clip_border=False, clip_content_mode="off", patches=60,
        randomize=False, seed_fixed=True, seed=4242,
    )

    _WATCH = ("text_edge_top_mm", "text_edge_mm", "text_edge_clip_mm",
              "strip_label_offset_mm", "margin_top", "margin_bottom",
              "margin_left", "margin_right", "helper_markers",
              "helper_marker_edge_mm", "helper_marker_len_mm",
              "helper_markers_sides", "helper_markers_top_bottom",
              "chart_text", "chart_text_size_mm", "stamp_command", "paper",
              "clip_border", "clip_border_width_mm", "clip_side",
              "clip_content_mode", "clip_text", "show_strip_indicators")

    def apply(**over):
        """Push a recipe in and read back what the PANEL now holds.

        Reading back the object that was pushed in records the REQUEST and not
        the STATE: a field the panel has no control for is dropped on the way
        through, and a value it clamps comes back changed.
        """
        want = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(want)
        pump(app, 800)
        got = panel.get_recipe()
        drift = {k: [getattr(want, k, None), getattr(got, k, None)]
                 for k in _WATCH
                 if getattr(want, k, None) != getattr(got, k, None)}
        return got, drift

    built = 0

    def build(name: str):
        """Press the REAL Generate button and keep the sheet it writes."""
        nonlocal built
        for t in (WORK / PROJECT).rglob("*.tif"):
            t.unlink()
        tab._generate_btn.click()
        ok = wait_for_build(app, tab)
        pump(app, 1200)
        tifs = sorted((WORK / PROJECT).rglob("*.tif"))
        if not (ok and tifs):
            return None
        built += 1
        keep = out / f"sheet-{built:02d}-{name}.tif"
        keep.write_bytes(tifs[0].read_bytes())
        return keep

    def panel_says() -> dict:
        p = tab._margin_panel
        return {"status": p.status_message(), "notes": p.text_notes()}

    def shoot(name: str) -> "str | None":
        """Photograph the REAL window, or say why not.

        One per case rather than one at the end: the thing worth seeing is the
        red message in "Measured from Preview" for THAT recipe, and by the end
        of the run it has been replaced eleven times.
        """
        f = out / f"window-{name}.png"
        ok, why = capture_window(win, f)
        if not ok:
            print(f"    !! capture refused: {why}", flush=True)
            return None
        return f.name

    def case(name: str, comment: str, control_over: dict, **over) -> dict:
        """One ruling, one sheet, one control sheet, one measurement."""
        r, drift = apply(**over)
        v = build(f"{name}")
        says = panel_says()
        shot = shoot(name)
        r2, drift2 = apply(**{**over, **control_over})
        c = build(f"{name}-control")
        row = {"case": name, "comment": comment,
               "recipe_drift": drift, "control_drift": drift2,
               "panel": says,
               "photograph": shot,
               "sheet": v.name if v else None,
               "control_sheet": c.name if c else None}
        if v and c:
            row["measured"] = isolate(v, c)
        res["steps"].append(row)
        print(f"  [{name}] {json.dumps(row.get('measured', {}).get('ink'))}",
              flush=True)
        (out / "rulings.json").write_text(
            json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
        return row

    # ---------------------------------------------------------- ruling 1 ---
    # The strip letters hold the reserve and cross onto the patches.
    row = case("r1-labels-tight",
               "T=4, top margin 6: the band must start at 4.0 and cross 6.0",
               {"show_strip_indicators": False},
               margin_top=6.0, text_edge_top_mm=4.0)
    if row.get("sheet"):
        crop(out / row["sheet"], out, f"crop-{row['sheet'][:-4]}.png", 0, 30)

    case("r1-labels-T12",
         "T=12 with a 15 mm margin: the band starts at 12.0, no clamp",
         {"show_strip_indicators": False},
         margin_top=15.0, text_edge_top_mm=12.0)

    case("r1-labels-markers",
         'T=1 with the markers at 4+2: the reserve is 7.0, not "T"',
         {"show_strip_indicators": False},
         margin_top=6.0, text_edge_top_mm=1.0, helper_markers=True)

    # ---------------------------------------------------------- ruling 2a --
    # The bottom line is centred between his two bounds.
    for tag, over in (
        ("plain", {}),
        ("markers", {"helper_markers": True, "text_edge_clip_mm": 1.0}),
        ("border-left", {"clip_border": True, "clip_border_width_mm": 26.0,
                         "clip_side": "left"}),
        ("border-right", {"clip_border": True, "clip_border_width_mm": 26.0,
                          "clip_side": "right"}),
    ):
        case(f"r2a-bottom-{tag}", "the bottom line's own centre",
             {"chart_text": ""},
             chart_text="IIIIIIIIII", chart_text_size_mm=3.2, **over)

    case("r2a-bottom-plain-long",
         "the same line, three times as long: it must grow both ways",
         {"chart_text": ""},
         chart_text="I" * 30, chart_text_size_mm=3.2)

    # ---------------------------------------------------------- ruling 2b --
    # The clip band is centred between the T and B bounds.
    case("r2b-clip-band-T12-B4",
         "T=12, B=4, markers off: the band runs 12.0 to 293.0",
         {"clip_content_mode": "off"},
         clip_border=True, clip_border_width_mm=26.0, clip_side="left",
         clip_content_mode="text", clip_text="ChromIQ layout ruling test",
         text_edge_top_mm=12.0, text_edge_mm=4.0, margin_top=15.0)

    case("r2b-clip-band-T12-B4-markers",
         "the same with the markers at 4+2: 12.0 to 290.0",
         {"clip_content_mode": "off"},
         clip_border=True, clip_border_width_mm=26.0, clip_side="left",
         clip_content_mode="text", clip_text="ChromIQ layout ruling test",
         text_edge_top_mm=12.0, text_edge_mm=4.0, margin_top=15.0,
         helper_markers=True)

    case("r2b-clip-band-right",
         "the same band on the right edge",
         {"clip_content_mode": "off"},
         clip_border=True, clip_border_width_mm=26.0, clip_side="right",
         clip_content_mode="text", clip_text="ChromIQ layout ruling test",
         text_edge_top_mm=12.0, text_edge_mm=4.0, margin_top=15.0)

    # ---------------------------------------------------------- ruling 2c --
    # The chart note and the settings stamp, on the same vertical bounds.
    #
    # THE BOTTOM LINE COMES WITH THE STAMP, so this one is measured first and
    # on its own: ticking "Stamp settings used on the chart" puts a line along
    # the BOTTOM as well as feeding the right-edge note, and a control with the
    # tick off cannot separate them.
    case("r2c-stamp-bottom-line",
         "the stamp's BOTTOM line, with the notes box empty",
         {"stamp_command": False},
         stamp_command=True, text_edge_top_mm=12.0, text_edge_mm=4.0,
         margin_top=15.0, margin_right=25.0)

    # ...and now the RIGHT-EDGE note, isolated against a sheet that has the
    # same stamp and an EMPTY notes box. The difference is then the note alone.
    # `chart_creator` assembles the note from the run's Chart Notes plus the
    # stamp lines, so the box on the tab is what puts it on the sheet, and the
    # first run of this driver found nothing down the right edge because the
    # box was empty.
    _notes_edit = getattr(tab, "_manual_chart_notes_edit", None)
    if _notes_edit is not None:
        _over = dict(stamp_command=True, text_edge_top_mm=12.0,
                     text_edge_mm=4.0, margin_top=15.0, margin_right=25.0)
        _r, _drift = apply(**_over)
        _notes_edit.setText(
            "Canon PRO-300 on Photo Rag, colour management off in the driver")
        pump(app, 700)
        _v = build("r2c-right-edge-note")
        _says = panel_says()
        _shot = shoot("r2c-right-edge-note")
        _notes_edit.setText("")
        pump(app, 700)
        _r2, _drift2 = apply(**_over)
        _c = build("r2c-right-edge-note-control")
        _row = {"case": "r2c-right-edge-note",
                "comment": "the note's two ends against T=12 and B=4",
                "recipe_drift": _drift, "control_drift": _drift2,
                "panel": _says,
                "photograph": _shot,
                "sheet": _v.name if _v else None,
                "control_sheet": _c.name if _c else None}
        if _v and _c:
            _row["measured"] = isolate(_v, _c)
        res["steps"].append(_row)
        print(f"  [r2c-right-edge-note] "
              f"{json.dumps(_row.get('measured', {}).get('ink'))}", flush=True)
        (out / "rulings.json").write_text(
            json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")

    # One photograph of the real window, if the screen allows it.
    ok, why = capture_window(win, out / "window.png")
    res["capture"] = {"ok": ok, "why": why, "screen_locked": session_is_locked()}
    print(f"\n99 capture: {'OK' if ok else 'REFUSED - ' + why}", flush=True)

    (out / "rulings.json").write_text(
        json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    win.close()
    pump(app, 500)
    print(f"\nwrote {out / 'rulings.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
