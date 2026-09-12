#!/usr/bin/env python3
"""On-screen proof for the TOP and BOTTOM page edges of #182 (Knut, 2026-09-12).

Drives the REAL ChromIQ window, on screen, against a sandboxed settings file, a
sandboxed presets folder and a sandboxed working folder. Nothing here asks a
widget where it thinks it put something: every distance is read off the INK of
the sheet the app itself wrote.

What it answers, one parameter at a time:

  T1  The strip letters against the page top edge. Where does their ink land as
      "T" is swept, as "Label offset" is swept, and with the ruler helper
      markers on for top and bottom? Knut's rule is
      ``max(T, edge + length + 1.0) + offset`` from the page's top edge.
  B1  The sheet text along the bottom. Does it move when "B" changes? Where is
      its ink relative to the helper markers' band? Knut reports two faults
      here and both are checked against the ink.
  B2  The WIDTH of the bottom text against the paper, with the reserve his rule
      names: ``paper - 2*Clip`` markers off, ``paper - (2*edge + 2*len + 2)``
      markers on.
  C1  The clip-border-width-overrules-the-margin red edge: which widget carries
      the red outline, which carries the tooltip, in each of the four states.

Usage:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-tb.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-tb-presets
    python scripts/drive_182_top_bottom_edges.py --out DIR [--tag before]
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

from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtGui import QFontDatabase                             # noqa: E402
from PyQt6.QtWidgets import QApplication                          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked     # noqa: E402

WORK = Path("/tmp/chromiq-tb-work")
PROJECT = "tbedges"

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
        print(f"    !! modal: {title!r} -> closing")
        try:
            w.reject()
        except Exception:                                     # noqa: BLE001
            w.close()
    t = QTimer()
    t.setInterval(400)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def wait_for_build(app, tab, timeout=300) -> bool:
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


# --------------------------------------------------------------------------
# A RULER LAID ON THE APP'S OWN SHEET.
# --------------------------------------------------------------------------
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
#: on it. A fixed share of the PAGE WIDTH cannot be used here, which the first
#: version of this ruler learned the hard way: a 64-patch i1 chart is twelve
#: columns wide and covers well under half the sheet, so a 0.5 threshold found
#: "no patch block" on every one of twenty sheets. A share of the densest row
#: is scale-free and finds the block on a full sheet and a sparse one alike.
PATCH_ROW_DENSITY_FRAC = 0.35


def edge_map(path: Path) -> dict:
    """Every run of ink ABOVE and BELOW the patch block, in mm from the page.

    Reported from the page's own top and bottom edges, because that is the
    frame every rule in Knut's two sections is written in.
    """
    import numpy as np
    g, dpi = _read_gray(path)
    H, W = g.shape[:2]
    full = 65535 if g.dtype.itemsize == 2 else 255
    ink = g < int(0.94 * full)
    mm = 25.4 / dpi
    density = ink.sum(axis=1) / max(1, W)
    peak = float(density.max())
    if peak <= 0.0:
        return {"dpi": round(dpi, 2), "error": "the sheet has no ink at all"}
    patch = np.flatnonzero(density >= peak * PATCH_ROW_DENSITY_FRAC)
    if not len(patch):
        return {"dpi": round(dpi, 2), "error": "no patch block"}
    patch_top, patch_bottom = int(patch[0]), int(patch[-1])
    rows = ink.any(axis=1)

    def runs(lo: int, hi: int) -> list:
        out, start = [], None
        for y in range(lo, hi):
            if rows[y] and start is None:
                start = y
            elif not rows[y] and start is not None:
                out.append((start, y - 1))
                start = None
        if start is not None:
            out.append((start, hi - 1))
        return out

    def describe(rr, from_bottom: bool) -> list:
        return [{
            "y0_mm": round(a * mm, 2), "y1_mm": round((b + 1) * mm, 2),
            "from_paper_edge_mm": (round((H - 1 - b) * mm, 2) if from_bottom
                                   else round(a * mm, 2)),
            "cols_inked_max": int(ink[a:b + 1, :].sum(axis=1).max()),
            "x0_mm": round(int(np.flatnonzero(
                ink[a:b + 1, :].any(axis=0))[0]) * mm, 2),
            "x1_mm": round((int(np.flatnonzero(
                ink[a:b + 1, :].any(axis=0))[-1]) + 1) * mm, 2),
        } for a, b in rr]

    return {
        "dpi": round(dpi, 2),
        "page_w_mm": round(W * mm, 2), "page_h_mm": round(H * mm, 2),
        "patch_top_from_paper_edge_mm": round(patch_top * mm, 2),
        "patch_bottom_from_paper_edge_mm": round((H - 1 - patch_bottom) * mm, 2),
        "ink_above_patches": describe(runs(0, patch_top), False),
        "ink_below_patches": describe(runs(patch_bottom + 1, H), True),
    }


def keep_edge_crops(tif: Path, out: Path, stem: str,
                    top_mm: float = 45.0, bottom_mm: float = 30.0) -> list:
    """Save the top and bottom strips of the real sheet as PNGs, with a
    millimetre scale down the side, so the ink can be SEEN and not only
    tabulated. These are what stands in for a photograph while the login
    session is locked: they are the app's own output, not a widget render.
    """
    from PIL import Image, ImageDraw
    import numpy as np
    g, dpi = _read_gray(tif)
    H, W = g.shape[:2]
    mm2px = dpi / 25.4
    made = []
    for name, y0, y1, ruler_from_bottom in (
            ("top", 0, int(round(top_mm * mm2px)), False),
            ("bottom", H - int(round(bottom_mm * mm2px)), H, True)):
        y0, y1 = max(0, y0), min(H, y1)
        crop = Image.fromarray(np.asarray(g[y0:y1, :]).astype("uint8")
                               if g.dtype.itemsize == 1
                               else (np.asarray(g[y0:y1, :]) >> 8
                                     ).astype("uint8")).convert("RGB")
        d = ImageDraw.Draw(crop)
        for m in range(0, int(max(top_mm, bottom_mm)) + 1):
            y = (int(round((H - m * mm2px) - y0)) if ruler_from_bottom
                 else int(round(m * mm2px - y0)))
            if not (0 <= y < crop.height):
                continue
            long_tick = (m % 5 == 0)
            d.line((0, y, 26 if long_tick else 14, y),
                   fill=(210, 40, 40) if long_tick else (240, 150, 150))
            if long_tick:
                d.text((30, max(0, y - 6)), f"{m} mm", fill=(210, 40, 40))
        p = out / f"{stem}-{name}.png"
        crop.save(p)
        made.append(p.name)
    return made


def widget_state(w) -> dict:
    """What a spin box is WEARING: its stylesheet and its tooltip."""
    if w is None:
        return {"present": False}
    qss = w.styleSheet() or ""
    return {
        "present": True,
        "enabled": bool(w.isEnabled()),
        "value": round(float(w.value()), 2) if hasattr(w, "value") else None,
        "red_outline": "d9534f" in qss.lower(),
        "stylesheet_tail": qss[-140:],
        "tooltip": (w.toolTip() or "")[:400],
    }


def main() -> int:                                            # noqa: C901
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-tb-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    locked = session_is_locked()
    res: dict = {"tag": tag, "modals": modals, "screen_locked": locked,
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
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, "
          f"work {WORK}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    pump(app, 1400)
    install_modal_watchdog(app)
    res["window_visible"] = bool(win.isVisible())
    print(f"00 window visible: {res['window_visible']}")

    tab = win._tab_chart
    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 700)
    tab._manual_target_name_edit.setText(PROJECT)
    pump(app, 700)

    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 600)

    # A small chart, so targen answers in seconds and the sweep can be long.
    # Nothing here depends on the patch count; every distance is measured from
    # the page edge.
    chk = getattr(tab, "_manual_auto_patches_check", None)
    if chk is not None and chk.isChecked():
        chk.setChecked(False)
        pump(app, 400)
    pw = getattr(tab, "_manual_f_pw", None)
    if pw is not None:
        pw._control.setValue(64)
        pump(app, 400)
    res["patch_count"] = (int(pw._control.value()) if pw is not None else None)

    from workflow.layout_engine.presets import LayoutRecipe

    BASE = dict(
        instrument="i1", paper="A4",
        # MARGINS ARE THE LAW **AND THEY ARE THE TYPED ONES**, which is the
        # mode every rule in Knut's two sections is written for. Two routes
        # reach the law and only one of them keeps the numbers on screen:
        # `geometry` takes ``law = area_first or use_instrument_margins``, but
        # "Use instrument margins" then DISABLES the margin boxes and puts the
        # instrument's own numbers in, so a sweep of "Top" in that mode moves a
        # margin nobody typed. Measured here: with it on and 15 mm typed, the
        # patch block still began 38 mm down the sheet. Area-first gives the
        # law and keeps the typed margins.
        layout_mode="area_first", use_instrument_margins=False,
        margin_top=15.0, margin_bottom=15.0, margin_left=12.0,
        margin_right=12.0,
        text_edge_top_mm=4.0, text_edge_mm=4.0, text_edge_clip_mm=4.0,
        chart_text="CUSTOM TEXT HERE", stamp_command=False,
        show_strip_indicators=True, show_row_indicators=False,
        helper_markers=False, helper_marker_edge_mm=4.0,
        helper_marker_len_mm=2.0, helper_markers_top_bottom=True,
        helper_markers_sides=True,
        clip_border=False, patches=60,
        randomize=False, seed_fixed=True, seed=4242,
    )

    _WATCH = ("text_edge_top_mm", "text_edge_mm", "text_edge_clip_mm",
              "strip_label_offset_mm", "margin_top", "margin_bottom",
              "margin_left", "margin_right", "helper_markers",
              "helper_marker_edge_mm", "helper_marker_len_mm", "chart_text",
              "chart_text_size_mm", "stamp_command", "paper")

    def apply(**over):
        """Push a recipe in, and read back what the PANEL now holds.

        Reading back the object that was pushed in records the REQUEST and not
        the STATE, and the two differ: a field the panel has no control for is
        dropped on the way through, and a value it clamps comes back changed.
        The first version of this driver reported a 3 mm "Label offset" that
        never reached the sheet, and a 6 mm top margin the instrument had
        already overruled.
        """
        want = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(want)
        pump(app, 800)
        got = panel.get_recipe()
        drift = {k: [getattr(want, k, None), getattr(got, k, None)]
                 for k in _WATCH
                 if getattr(want, k, None) != getattr(got, k, None)}
        return got, drift

    def build():
        for t in (WORK / PROJECT).rglob("*.tif"):
            t.unlink()
        tab._generate_btn.click()
        okb = wait_for_build(app, tab)
        pump(app, 1200)
        return okb, sorted((WORK / PROJECT).rglob("*.tif"))

    shots = 0

    def shoot(name: str) -> "str | None":
        nonlocal shots
        shots += 1
        p = out / f"{shots:02d}-{name}.png"
        ok, why = capture_window(win, p)
        if not ok:
            print(f"    !! capture refused: {why}")
            return None
        return p.name

    def step(name: str, comment: str, generate: bool = True,
             capture: bool = False, **over) -> dict:
        pokes = over.pop("_type_into", None)
        r, drift = apply(**over)
        if pokes:
            # TYPE IT IN, THE WAY A PERSON DOES. The ten label-style fields
            # (`_LABEL_STYLE_FIELDS`) are not taken from a recipe that does not
            # declare `label_style_explicit`: `set_recipe` calls
            # `_seed_label_style_from_defaults()` straight afterwards and the
            # boxes show Preferences' values instead. So a "Label offset"
            # pushed in through a recipe is not the offset the sheet is drawn
            # with, and the first version of this driver reported it as a fault
            # in the renderer when it was an artefact of how the driver set it.
            for attr, val in pokes.items():
                getattr(panel, attr).setValue(val)
                pump(app, 350)
            r = panel.get_recipe()
            st_pokes = {a: v for a, v in pokes.items()}
        else:
            st_pokes = {}
        st: dict = {"step": name, "comment": comment}
        if st_pokes:
            st["typed_into_the_boxes"] = st_pokes
        if drift:
            st["panel_changed_what_was_asked_for"] = drift
            print(f"      (the panel changed: {drift})")
        st["settings"] = {
            "T": round(float(r.text_edge_top_mm), 2),
            "B": round(float(r.text_edge_mm), 2),
            "Clip": round(float(r.text_edge_clip_mm), 2),
            "label_offset": round(float(
                getattr(r, "strip_label_offset_mm", 0.0) or 0.0), 2),
            "margin_top": round(float(r.margin_top), 2),
            "margin_bottom": round(float(r.margin_bottom), 2),
            "helper_markers": bool(r.helper_markers),
            "marker_edge": round(float(r.helper_marker_edge_mm or 0.0), 2),
            "marker_len": round(float(r.helper_marker_len_mm or 0.0), 2),
            "chart_text": r.chart_text,
            "chart_text_size_mm": round(float(r.chart_text_size_mm or 0.0), 2),
            "stamp": bool(r.stamp_command),
            "paper": r.paper,
        }
        try:
            notes, over_notes = tab._engine_text_notes()
            st["panel_messages"] = list(over_notes)
            st["panel_all_notes"] = list(notes)
        except Exception as e:                                # noqa: BLE001
            st["panel_messages_error"] = f"{type(e).__name__}: {e}"
        if capture:
            st["screenshot"] = shoot(name)
        if generate:
            okb, tifs = build()
            st["build_ok"] = okb
            st["tifs"] = [t.name for t in tifs]
            if tifs:
                st["sheet_crops"] = keep_edge_crops(
                    tifs[0], out, f"{len(res['steps']) + 1:02d}-{name}")
            if tifs:
                st["ink"] = edge_map(tifs[0])
        res["steps"].append(st)
        print(f"  {name}: {comment}")
        if "ink" in st and "error" not in st["ink"]:
            for where, rr in (("above", st["ink"]["ink_above_patches"]),
                              ("below", st["ink"]["ink_below_patches"])):
                for run in rr:
                    print(f"      {where}: {run['from_paper_edge_mm']:6.2f} mm "
                          f"from the edge | y {run['y0_mm']:.2f}.."
                          f"{run['y1_mm']:.2f} | x {run['x0_mm']:.2f}.."
                          f"{run['x1_mm']:.2f}")
        return st

    # ------------------------------------------------- T1: the top edge
    print("\nT1  the strip letters against the page top edge")
    step("T1a-T4", "T = 4 mm, no markers, no offset", capture=True,
         text_edge_top_mm=4.0)
    step("T1b-T8", "T = 8 mm", text_edge_top_mm=8.0)
    step("T1c-T12", "T = 12 mm", text_edge_top_mm=12.0)
    step("T1d-offset3", "T = 4 mm, Label offset typed as 3 mm",
         text_edge_top_mm=4.0, _type_into={"strip_label_offset": 3.0})
    step("T1d2-offset6", "T = 4 mm, Label offset typed as 6 mm",
         text_edge_top_mm=4.0, _type_into={"strip_label_offset": 6.0})
    step("T1d3-offset-neg", "T = 4 mm, Label offset typed as -3 mm",
         text_edge_top_mm=4.0, _type_into={"strip_label_offset": -3.0})
    step("T1e-markers", "T = 4 mm, markers ON top/bottom, edge 4 len 2",
         capture=True, text_edge_top_mm=4.0, helper_markers=True,
         helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0)
    step("T1f-markers-long", "markers edge 4 len 8", text_edge_top_mm=4.0,
         helper_markers=True, helper_marker_edge_mm=4.0,
         helper_marker_len_mm=8.0)
    step("T1g-tight-margin", "T = 4 mm, top margin 6 mm", text_edge_top_mm=4.0,
         margin_top=6.0)

    # ------------------------------------------------- B1: the bottom edge
    print("\nB1  the sheet text along the page bottom edge")
    for b in (2.0, 4.0, 8.0, 16.0):
        step(f"B1-B{b:g}", f"B = {b} mm, no markers", text_edge_mm=b,
             capture=(b == 4.0))
    step("B1e-markers", "B = 4 mm, markers ON, edge 4 len 2", capture=True,
         text_edge_mm=4.0, helper_markers=True, helper_marker_edge_mm=4.0,
         helper_marker_len_mm=2.0)
    step("B1f-markers-long", "B = 4 mm, markers edge 4 len 8",
         text_edge_mm=4.0, helper_markers=True, helper_marker_edge_mm=4.0,
         helper_marker_len_mm=8.0)
    step("B1g-stamp", "B = 4 mm, both lines on", text_edge_mm=4.0,
         stamp_command=True)

    # ------------------------------------------------- B2: the width
    print("\nB2  the width of the bottom text against the paper")
    LONG = ("Canon PRO-300 on Hahnemuehle Photo Rag 308 gsm, printed with "
            "colour management switched off in the driver, 2880x1440 dpi")
    step("B2a-long-auto", "a long custom text, Size auto", capture=True,
         chart_text=LONG)
    step("B2b-long-45", "the same text at Size 4.5 mm", chart_text=LONG,
         chart_text_size_mm=4.5)
    step("B2c-long-markers", "the same text, markers ON", chart_text=LONG,
         helper_markers=True, helper_marker_edge_mm=4.0,
         helper_marker_len_mm=2.0)

    # ------------------------------------------------- other papers
    print("\nP  the same two rules on the other common papers")
    for paper in ("A3", "Letter", "A4L"):
        try:
            step(f"P-{paper}", f"{paper}, T 4 / B 4, markers ON",
                 paper=paper, helper_markers=True,
                 helper_marker_edge_mm=4.0, helper_marker_len_mm=2.0)
        except Exception as e:                                # noqa: BLE001
            res["steps"].append({"step": f"P-{paper}",
                                 "error": f"{type(e).__name__}: {e}"})

    # ------------------------------------------------- C1: the red edge
    print("\nC1  the clip-border-overrules-the-margin red edge")
    red: list[dict] = []
    for label, over in (
        ("editable margins, clip 24 > left margin 12",
         dict(clip_border=True, clip_border_width_mm=24.0, clip_side="left",
              margin_left=12.0, use_instrument_margins=False)),
        ("editable margins, clip 8 < left margin 20",
         dict(clip_border=True, clip_border_width_mm=8.0, clip_side="left",
              margin_left=20.0, use_instrument_margins=False)),
        ("LOCKED margins, clip 24 wins",
         dict(clip_border=True, clip_border_width_mm=24.0, clip_side="left",
              use_instrument_margins=True)),
        ("LOCKED margins, clip 2 loses",
         dict(clip_border=True, clip_border_width_mm=2.0, clip_side="left",
              use_instrument_margins=True)),
        ("clip band OFF",
         dict(clip_border=False, use_instrument_margins=False)),
        ("editable margins, clip 24 > RIGHT margin 12, Side=right",
         dict(clip_border=True, clip_border_width_mm=24.0, clip_side="right",
              margin_right=12.0, use_instrument_margins=False)),
    ):
        apply(clip_content_mode="text", clip_text="clip line", **over)
        pump(app, 600)
        red.append({
            "case": label,
            "clip_width": widget_state(getattr(panel, "clip_width", None)),
            "margin_left": widget_state(panel.margins.get("l")),
            "margin_right": widget_state(panel.margins.get("r")),
        })
        print(f"  {label}")
        for k in ("clip_width", "margin_left", "margin_right"):
            s = red[-1][k]
            if s.get("present") and (s.get("red_outline") or s.get("tooltip")):
                print(f"      {k}: red={s['red_outline']} "
                      f"enabled={s['enabled']} tip={s['tooltip'][:70]!r}")
    res["red_edge"] = red
    shoot("C1-red-edge-last-case")

    (out / f"{tag}.json").write_text(json.dumps(res, indent=2),
                                     encoding="utf-8")
    print(f"\nwrote {out / (tag + '.json')}  ({shots} screenshots)")
    win.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
