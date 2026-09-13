#!/usr/bin/env python3
"""K2 / K3 / K4 (#182, Knut, beta 7): the truncations that say nothing.

Drives the REAL ChromIQ window, on screen, against a sandboxed settings file, a
sandboxed presets folder and a sandboxed working folder. Nothing of the owner's
is touched; check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

For every combination of

    "Run 1 Chart Notes"  x  "Stamp settings down the right edge"
    x  clip border ON/OFF  x  clip-border content text

it records

  * what the "Measured from Preview" panel says, verbatim, from the tab's own
    `_engine_text_notes()` -- the same list the red message field renders;
  * what the SHEET does, from the TIFF the app itself wrote: the note's ink,
    whether the printed line ends in an ellipsis, and where the clip text's
    ink starts and stops along the page;
  * a crop of the note strip and of the clip band, rotated upright and scaled,
    so the ellipsis and the cut ends can be READ rather than inferred.

Usage::

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-warngaps.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-warngaps-presets
    python scripts/drive_182_warning_gaps.py --out DIR [--only a,b,c,d]
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

from PyQt6.QtCore import QTimer                                  # noqa: E402
from PyQt6.QtGui import QFontDatabase                            # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,               # noqa: E402
                             QMessageBox)

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

WORK = Path("/tmp/chromiq-warngaps-work")
KNUT_PROJECTS = Path("/tmp/k182-proof/projects")
PROJECT = "testHex"

#: A note that FITS an A4 sheet on its own at the 7 pt floor, so the panel's
#: existing "characters are cut off" warning stays silent, and that no longer
#: fits once the stamp's own lines are joined onto the same line. Knut's K3.
NOTES_MED = ("Canon Pro-1000 on Hahnemuehle Photo Rag 308 gsm, printed with "
             "colour management OFF in the driver, Highest quality, no paper "
             "profile selected, second calibration run of the week")

#: Long enough to be cut on its own, which is the case the panel DOES catch.
NOTES_LONG = NOTES_MED + (" -- kept as the reference sheet for the studio and "
                          "filed with the print log for the January batch of "
                          "portrait work, do not discard before the profile "
                          "has been signed off by the retoucher and archived")

#: One long line of clip-border content: Knut's K4. It must not fit the page
#: height even at the 7 pt floor.
CLIP_LONG = ("Clip border content: this sheet belongs to the studio profiling "
             "set and must be handled by its edges only, never touched on the "
             "patch area, kept flat and dry, read within twenty four hours of "
             "printing, and returned to the archive box afterwards with the "
             "print log sheet stapled to it for the record")

CLIP_SHORT = "Clip border content: studio profiling set"

modals: list[dict] = []
_timers: list = []


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
        title = w.windowTitle()
        text = ""
        for attr in ("text", "toPlainText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text = str(f())
                    break
                except Exception:
                    pass
        modals.append({"title": title, "text": text[:400]})
        print(f"    !! modal: {title!r} -> closing", flush=True)
        try:
            w.reject()
        except Exception:
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
# Measuring the sheet the app itself wrote.
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
            if int(page.tags["ResolutionUnit"].value) == 3:
                dpi *= 2.54
        except Exception:
            dpi = 200.0
    return (arr.min(axis=2) if arr.ndim == 3 else arr), dpi


def diff_columns(before: Path, after: Path) -> dict:
    """The columns two otherwise identical sheets differ in.

    Two builds of the same chart that differ only in the note (or only in the
    clip content) differ by exactly that element, so the changed columns ARE
    its footprint across the sheet. Measuring an inked band instead would
    measure the patch block beside it.
    """
    import numpy as np
    a, dpi = _read_gray(before)
    b, _ = _read_gray(after)
    if a.shape != b.shape:
        return {"error": f"shape {a.shape} vs {b.shape}"}
    H, W = a.shape[:2]
    d = (a.astype(int) != b.astype(int))
    cols = d.any(axis=0)
    if not cols.any():
        return {"dpi": round(dpi, 1), "changed": False}
    ci = np.flatnonzero(cols)
    ri = np.flatnonzero(d.any(axis=1))
    return {
        "dpi": round(dpi, 1), "changed": True,
        "page_w_mm": round(W * 25.4 / dpi, 2),
        "page_h_mm": round(H * 25.4 / dpi, 2),
        "x_px": [int(ci[0]), int(ci[-1])],
        "y_px": [int(ri[0]), int(ri[-1])],
        "width_mm": round((ci[-1] - ci[0] + 1) * 25.4 / dpi, 2),
        "width_pt": round((ci[-1] - ci[0] + 1) * 72.0 / dpi, 2),
        "from_left_mm": round(int(ci[0]) * 25.4 / dpi, 2),
        "from_right_mm": round((W - 1 - int(ci[-1])) * 25.4 / dpi, 2),
        "ink_top_mm": round(int(ri[0]) * 25.4 / dpi, 2),
        "ink_bottom_from_page_bottom_mm": round((H - 1 - int(ri[-1])) * 25.4 / dpi, 2),
        "ink_length_mm": round((ri[-1] - ri[0] + 1) * 25.4 / dpi, 2),
    }


def crop_upright(sheet: Path, x_px, y_px, out: Path, scale: int = 3,
                 pad: int = 6) -> str:
    """Save the rotated side text as an upright, readable PNG."""
    from PIL import Image
    im = Image.open(str(sheet)).convert("L")
    x0 = max(0, x_px[0] - pad)
    x1 = min(im.width, x_px[1] + 1 + pad)
    y0 = max(0, y_px[0] - pad)
    y1 = min(im.height, y_px[1] + 1 + pad)
    sub = im.crop((x0, y0, x1, y1))
    # Rendered with .rotate(90) (CCW), so it reads bottom-to-top: turn it back.
    sub = sub.transpose(Image.Transpose.ROTATE_270)
    sub = sub.resize((sub.width * scale, sub.height * scale),
                     Image.Resampling.LANCZOS)
    out.parent.mkdir(parents=True, exist_ok=True)
    sub.save(str(out))
    return str(out)


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-warngaps-proof")
    only = (sys.argv[sys.argv.index("--only") + 1].split(",")
            if "--only" in sys.argv else None)
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"modals": modals, "screen_locked": session_is_locked(),
                 "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM", "<unset>")}
    print(f"00 screen locked: {res['screen_locked']}  "
          f"QT_QPA_PLATFORM={res['qt_qpa_platform']}", flush=True)

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
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    settings.set("restore_last_session", False)
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(WORK), "SANDBOX FAILED"
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, "
          f"work {WORK}", flush=True)

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    src = KNUT_PROJECTS / PROJECT
    dst = WORK / PROJECT
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"00 staged {dst}", flush=True)

    # ---- GROUND TRUTH, TAKEN WHERE THE APP MAKES THE CALL -----------------
    # `stamp_chart_metadata` receives the very lines `chart_creator` joined;
    # `fit_rotated_line` returns the very string `_stamp_one` draws. Wrapping
    # both records what went on the paper instead of predicting it.
    from workflow import tiff_metadata as _tm
    stamped: list[dict] = []
    _orig_stamp = _tm.stamp_chart_metadata
    _orig_fit = _tm.fit_rotated_line

    inside = [False]

    def _spy_stamp(tiff_paths, lines, *a, **k):
        stamped.append({"lines": list(lines),
                        "joined": _tm._JOIN.join(
                            s.strip() for s in lines if s and s.strip())})
        inside[0] = True
        try:
            return _orig_stamp(tiff_paths, lines, *a, **k)
        finally:
            inside[0] = False

    def _spy_fit(text, strip_h, strip_w, *a, **k):
        shown, font = _orig_fit(text, strip_h, strip_w, *a, **k)
        kept = len(shown) - 1 if shown.endswith("…") else len(shown)
        if stamped and inside[0]:
            stamped[-1].setdefault("fits", []).append({
                "strip_h_px": int(strip_h), "strip_w_px": int(strip_w),
                "in_chars": len(text), "out_chars": len(shown),
                "cut_chars": max(0, len(text) - kept),
                "ends_with_ellipsis": shown.endswith("…"),
                "printed_tail": shown[-52:],
                "cut_tail": text[kept:][:80],
            })
        return shown, font

    _tm.stamp_chart_metadata = _spy_stamp
    _tm.fit_rotated_line = _spy_fit

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart
    TabChart._confirm_displacing_results = lambda self, *a, **k: True
    win = MainWindow(settings)
    win.resize(1660, 1080)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 1500)
    install_modal_watchdog(app)
    print(f"00 window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)
    res["window_visible"] = bool(win.isVisible())

    tab = win._tab_chart
    win._tabs.setCurrentWidget(tab)
    pump(app, 600)

    picked = False
    w = getattr(tab, "_target_combo", None)
    if w is not None:
        for i in range(w.count()):
            if w.itemText(i).strip() == PROJECT:
                w.setCurrentIndex(i)
                picked = True
                break
    pump(app, 900)
    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 800)
    if not picked:
        tab._manual_target_name_edit.setText(PROJECT)
        pump(app, 600)

    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 500)

    meta = json.loads((src / "runs/run1/meta.json").read_text(encoding="utf-8"))
    rec = meta["create_chart_ui"]["engine_recipe"]

    from workflow.layout_engine.presets import LayoutRecipe

    #: One A4 base for every case, with a fixed seed so two builds of the same
    #: chart differ only in the element under test.
    BASE = {**rec, "paper": "A4", "randomize": True, "seed_fixed": True,
            "seed": 4242, "clip_border": False, "clip_content_mode": "off",
            "clip_side": "right", "clip_border_width_mm": 26.0,
            "margin_right": 30.0, "text_edge_clip_mm": 4.0,
            "text_edge_top_mm": 4.0, "text_edge_mm": 4.0,
            "chart_text_size_mm": 0.0, "clip_text_size_mm": 0.0,
            "helper_markers": False}

    def apply(**over):
        r = LayoutRecipe.from_dict({**BASE, **over})
        panel.set_recipe(r)
        pump(app, 900)
        return r

    steps: list[dict] = []

    def build_once() -> "list[Path]":
        for t in dst.rglob("*.tif"):
            t.unlink()
        tab._generate_btn.click()
        ok = wait_for_build(app, tab)
        pump(app, 1500)
        return ok, sorted(dst.rglob("*.tif"))

    def case(name: str, comment: str, notes: str, stamp: bool,
             overrides: dict, isolate: str) -> dict:
        """Run one combination. *isolate* names the element the baseline build
        switches OFF, so the diff is that element's own ink."""
        print(f"\n== {name}: {comment}", flush=True)
        st: dict = {"case": name, "comment": comment,
                    "notes_chars": len(notes), "notes": notes,
                    "stamp_on": bool(stamp)}

        # ---- baseline: the element under test switched off ----------------
        base_over = dict(overrides)
        if isolate == "clip":
            base_over["clip_content_mode"] = "off"
        apply(**base_over)
        if isolate == "note":
            tab._manual_chart_notes_edit.setText("")
            tab._manual_stamp_cmd_check.setChecked(False)
        else:
            tab._manual_chart_notes_edit.setText(notes)
            tab._manual_stamp_cmd_check.setChecked(bool(stamp))
        pump(app, 700)
        okb, tifs0 = build_once()
        baseline = None
        if tifs0:
            baseline = out / f"{name}__baseline.tif"
            shutil.copy(tifs0[0], baseline)

        # ---- the state under test -----------------------------------------
        r = apply(**overrides)
        tab._manual_chart_notes_edit.setText(notes)
        tab._manual_stamp_cmd_check.setChecked(bool(stamp))
        pump(app, 900)

        st["recipe"] = {
            "paper": r.paper, "margin_right_mm": round(float(r.margin_right), 2),
            "clip_border": bool(r.clip_border), "clip_side": r.clip_side,
            "clip_border_width_mm": round(float(r.clip_border_width_mm), 2),
            "clip_content_mode": r.clip_content_mode,
            "clip_text_chars": len(r.clip_text or ""),
            "clip_text_size_pt": round(float(panel.clip_text_size.value()), 2),
            "chart_text_size_pt": round(float(panel.chart_text_size.value()), 2),
            "text_edge_clip_mm": round(float(r.text_edge_clip_mm), 2),
            "text_edge_top_mm": round(float(r.text_edge_top_mm), 2),
            "text_edge_bottom_mm": round(float(r.text_edge_mm), 2),
        }

        # ---- WHAT THE PANEL SAYS, from the tab's own call ------------------
        try:
            warns, over = type(tab)._engine_text_notes(tab)
        except Exception as exc:                                   # noqa: BLE001
            warns, over = [f"<raised {exc!r}>"], []
        st["panel_all_notices"] = warns
        st["panel_red_notices"] = over
        st["panel_red_count"] = len(over)
        mp = getattr(tab, "_margin_panel", None)
        if mp is not None:
            try:
                st["panel_status_message"] = mp.status_message()
            except Exception:                                       # noqa: BLE001
                pass

        # ---- WHAT THE SHEET DOES -------------------------------------------
        stamped.clear()
        st["build_finished"], tifs = build_once()
        st["stamped_on_the_sheet"] = stamped[0] if stamped else None
        if tifs:
            sheet = out / f"{name}__sheet.tif"
            shutil.copy(tifs[0], sheet)
            st["sheet"] = str(sheet)
            if baseline is not None:
                d = diff_columns(baseline, sheet)
                st["measured"] = d
                if d.get("changed"):
                    st["crop"] = crop_upright(sheet, d["x_px"], d["y_px"],
                                              out / f"{name}__crop.png")

        # ---- WHAT THE SHIPPED FITTER SAYS IT PRINTED ------------------------
        # Not a re-implementation: `tiff_metadata.fit_rotated_line` is the very
        # function `_stamp_one` calls, asked with the line `chart_creator`
        # actually joins.
        if isolate == "note":
            st["fitter"] = predict_note(tab, r, notes, stamp)
        else:
            st["clip_area"] = clip_area(r)

        ok, why = capture_window(win, out / f"{name}.png")
        st["shot"] = f"{name}.png" if ok else ""
        st["shot_refused"] = "" if ok else why
        steps.append(st)
        print(f"   panel red notices: {len(over)}", flush=True)
        for line in over:
            print("     RED: " + line.replace("\n", " ")[:300], flush=True)
        print(f"   measured: {st.get('measured')}", flush=True)
        print(f"   fitter:   {st.get('fitter')}", flush=True)
        return st

    def clip_area(r) -> dict:
        """The rectangle the clip text is drawn into, from the shipped geometry.

        `geometry.clip_area_mm` is what `raster.render_pages` passes to
        `_vtext` as its canvas, so its HEIGHT is the length the line has along
        the page and anything longer is cropped by the canvas at both ends
        (`_vtext` centres with anchor "mm").
        """
        from workflow.layout_engine import geometry, instruments, papers
        from workflow.layout_engine.raster import clip_text_lines
        from workflow import text_edge_fit as tef
        pw, ph = papers.dimensions_mm(str(r.paper))
        geom = instruments.geom_from_build_kwargs(r.build_kwargs())
        lines = (clip_text_lines(r.clip_text or "")
                 if r.clip_content_mode == "text" else [])
        size_pt = float(r.clip_text_size_mm or 0.0) * 72.0 / 25.4
        area = geometry.clip_area_mm(geom, ph, pw, len(lines), size_pt)
        return {
            "paper_mm": [round(pw, 2), round(ph, 2)],
            "lines": [len(ln) for ln in lines],
            "clip_text_size_pt_typed": round(size_pt, 2),
            "floor_pt": tef.text_floor_pt(size_pt),
            "area_x_y_w_h_mm": (None if area is None
                                else [round(v, 2) for v in area]),
            "length_along_page_mm": (None if area is None else round(area[3], 2)),
            "band_thickness_mm": (None if area is None else round(area[2], 2)),
        }

    def _panel_joined(tab, notes: str, stamp: bool) -> str:
        """Exactly what `_engine_text_notes` now measures, so the two can be
        compared character for character rather than by their answers."""
        if not stamp:
            return notes
        try:
            pm = tab._collect_manual()
            pm.chart_notes = notes
            pm.stamp_commands = True
            n = tab._estimate_patch_total() or int(getattr(pm, "patches", 0) or 0)
            from workflow import tiff_metadata as _t
            return _t._JOIN.join(tab._creator.stamp_lines(pm, int(n)))
        except Exception as exc:                                   # noqa: BLE001
            return f"<raised {exc!r}>"

    def predict_note(tab, r, notes: str, stamp: bool) -> dict:
        """What `_stamp_one` prints, asked of the shipped fitter."""
        from workflow import tiff_metadata as tm
        from workflow import text_edge_fit as tef
        from workflow.layout_engine import papers, instruments
        pw, ph = papers.dimensions_mm(str(r.paper))
        geom = instruments.geom_from_build_kwargs(r.build_kwargs())
        dpi = float(getattr(r, "dpi", 200) or 200)
        mm2px = dpi / 25.4
        eff = tef.side_text_edge_mm(
            float(r.effective_text_edge_clip_mm),
            helper_markers=bool(r.helper_markers),
            marker_edge_mm=float(r.helper_marker_edge_mm or 0.0),
            marker_len_mm=float(r.helper_marker_len_mm or 0.0),
            marker_sides=bool(r.helper_markers_sides))
        top = tef.edge_reserve_mm(float(r.effective_text_edge_top_mm),
                                  bool(r.helper_markers),
                                  float(r.helper_marker_edge_mm or 0.0),
                                  float(r.helper_marker_len_mm or 0.0),
                                  bool(r.helper_markers_top_bottom))
        bot = tef.edge_reserve_mm(float(r.effective_text_edge_mm),
                                  bool(r.helper_markers),
                                  float(r.helper_marker_edge_mm or 0.0),
                                  float(r.helper_marker_len_mm or 0.0),
                                  bool(r.helper_markers_top_bottom))
        H = int(round(ph * mm2px))
        strip_h = H - int(round(top * mm2px)) - int(round(bot * mm2px))
        size_pt = float(r.chart_text_size_mm or 0.0) * 72.0 / 25.4
        strip_w = min(tm.NOTE_STRIP_MAX_PX,
                      int(round(max(0.0, float(r.margin_right) - eff) * mm2px)))
        strip_w = max(strip_w, tef.note_min_strip_px(dpi, size_pt))

        # The line `chart_creator._stamp_tiff_metadata` joins.
        pieces = []
        if notes:
            pieces.append(notes)
        if stamp:
            pieces.append("targen -v -d2 -G -e4 -B4 -f560 " + str(dst))
            pieces.append("ChromIQ layout engine")
            pieces.append("ChromIQ 4.3.0-beta.6")
        joined = tm._JOIN.join(pieces)
        notes_only = notes

        def fit(text):
            if not text:
                return {"chars": 0, "shown_chars": 0, "cut": 0, "tail": ""}
            shown, _f = tm.fit_rotated_line(
                text, strip_h, strip_w, anchor_px=tm._NOTE_PATCH_GAP_PX,
                font_family=str(r.chart_text_font or ""), size_pt=size_pt,
                dpi=dpi)
            kept = len(shown) - 1 if shown.endswith("…") else len(shown)
            return {"chars": len(text), "shown_chars": len(shown),
                    "cut": max(0, len(text) - kept),
                    "ends_with_ellipsis": shown.endswith("…"),
                    "tail": shown[-46:]}
        return {
            "strip_h_px": strip_h, "strip_w_px": strip_w,
            "the_line_the_stamper_gets": fit(joined),
            "the_line_the_panel_measures": fit(notes_only),
            "the_line_the_panel_now_builds": _panel_joined(tab, notes, stamp),
            "panel_note_characters_lost": tm.note_characters_lost(
                notes_only, ph, eff,
                max(0.0, float(r.margin_right) - eff), dpi, size_pt,
                str(r.chart_text_font or ""), top, bot),
            "joined_line_chars": len(joined),
        }

    def want(k: str) -> bool:
        return only is None or k in only

    # (z) the control: a short note, stamp off, nothing else on.
    if want("z"):
        case("z_control_short_note", "control: a short note, nothing else",
             "This chart is a test", False, {}, "note")

    # (d) chart notes alone, long enough to be cut. The panel DOES catch this.
    if want("d"):
        case("d_notes_alone_long", "K3 control: notes alone, long enough to cut",
             NOTES_LONG, False, {}, "note")

    # (a) stamp ON + chart notes: neither is cut alone, the joined line is.
    if want("a"):
        case("a_stamp_plus_notes", "K3(a): stamp ON + chart notes",
             NOTES_MED, True, {}, "note")

    # (s) the stamp ON with NO chart notes at all: the panel measures the
    #     notes box, which is empty, so it cannot warn about anything.
    if want("s"):
        case("s_stamp_alone", "K3 crossing: the stamp ON, notes box EMPTY",
             "", True, {}, "note")

    # (e) a long note AND the stamp: the panel warns, but from the notes
    #     alone, so its count is not the sheet's.
    if want("e"):
        case("e_long_notes_and_stamp",
             "K3 crossing: long notes + stamp - the panel under-reports",
             NOTES_LONG, True, {}, "note")

    # (b) stamp ON + chart notes + clip border on the right.
    if want("b"):
        case("b_stamp_notes_clipborder",
             "K3(b): stamp ON + chart notes + clip border on the right",
             NOTES_MED, True,
             {"clip_border": True, "clip_side": "right",
              "clip_content_mode": "text", "clip_text": CLIP_SHORT,
              "margin_right": 34.0}, "note")

    # (c) clip border ON + a custom clip text too long for the page height.
    if want("c"):
        case("c_cliptext_too_long",
             "K4: clip border ON, custom text too long for the page height",
             "", False,
             {"clip_border": True, "clip_side": "left",
              "clip_content_mode": "text", "clip_text": CLIP_LONG,
              "clip_border_width_mm": 26.0, "margin_left": 30.0}, "clip")

    # (c2) the same with a typed size, which never shrinks at all.
    if want("c2"):
        case("c2_cliptext_too_long_typed",
             "K4: the same clip text at a typed 9 pt (a typed size never shrinks)",
             "", False,
             {"clip_border": True, "clip_side": "left",
              "clip_content_mode": "text", "clip_text": CLIP_LONG,
              "clip_text_size_mm": 9.0 * 25.4 / 72.0,
              "clip_border_width_mm": 26.0, "margin_left": 30.0}, "clip")

    # (c3) the control: the same band with a clip text that fits.
    if want("c3"):
        case("c3_cliptext_fits", "K4 control: a clip text that fits the page",
             "", False,
             {"clip_border": True, "clip_side": "left",
              "clip_content_mode": "text", "clip_text": CLIP_SHORT,
              "clip_border_width_mm": 26.0, "margin_left": 30.0}, "clip")

    # ---- K2: every message that names the 7 pt floor, on screen ----------
    #: A bottom "Custom text" too wide for A4, which is Knut's own K2 case.
    SHEET_LONG = ("{project} - {date} - printed on the Canon Pro-1000 with "
                  "colour management switched off in the driver, Highest "
                  "quality, Hahnemuehle Photo Rag 308 gsm, second run")

    def k2(name: str, comment: str, notes: str, stamp: bool,
           overrides: dict, shot: bool = True) -> dict:
        print(f"\n== {name}: {comment}", flush=True)
        r = apply(**overrides)
        tab._manual_chart_notes_edit.setText(notes)
        tab._manual_stamp_cmd_check.setChecked(bool(stamp))
        pump(app, 900)
        # THE MESSAGE FIELD ONLY EXISTS ONCE THERE IS A PREVIEW TO MEASURE, so
        # the chart is built before the window is photographed.
        built, tifs = build_once()
        pump(app, 1200)
        tab._update_margin_inspector()
        pump(app, 900)
        try:
            warns, over = type(tab)._engine_text_notes(tab)
        except Exception as exc:                                   # noqa: BLE001
            warns, over = [f"<raised {exc!r}>"], []
        st = {"case": name, "comment": comment,
              "chart_text": overrides.get("chart_text", ""),
              "chart_text_size_pt": round(
                  float(panel.chart_text_size.value()), 2),
              "margin_right_mm": round(float(r.margin_right), 2),
              "panel_red_notices": over, "panel_all_notices": warns,
              "panel_red_count": len(over), "build_finished": built,
              "sheet": (str(shutil.copy(tifs[0], out / f"{name}__sheet.tif"))
                        if tifs else None)}
        mp = getattr(tab, "_margin_panel", None)
        if mp is not None:
            try:
                st["panel_status_message"] = mp.status_message()
            except Exception:                                       # noqa: BLE001
                pass
        if shot:
            ok, why = capture_window(win, out / f"{name}.png")
            st["shot"] = f"{name}.png" if ok else ""
            st["shot_refused"] = "" if ok else why
        steps.append(st)
        for line in over:
            print("     RED: " + line.replace("\n", " ")[:400], flush=True)
        return st

    if want("k2"):
        k2("k2_sheet_text_too_wide_auto",
           "K2: Knut's own case - a long Custom text, Size auto",
           "", False, {"chart_text": SHEET_LONG, "chart_text_size_mm": 0.0})
        k2("k2_sheet_text_too_wide_typed",
           "K2 sibling: the same line at a typed 10 pt",
           "", False, {"chart_text": SHEET_LONG,
                       "chart_text_size_mm": 10.0 * 25.4 / 72.0})
        k2("k2_note_thickness_narrow_margin",
           "K2: the chart-note thickness messages, which also name 7 pt",
           NOTES_MED, True, {"margin_right": 5.0, "chart_text_size_mm": 0.0})
        k2("k2_note_thickness_clipborder_right",
           "K2: the same with a right-hand clip border",
           NOTES_MED, True,
           {"margin_right": 5.0, "clip_border": True, "clip_side": "right",
            "clip_content_mode": "text", "clip_text": CLIP_SHORT,
            "clip_border_width_mm": 26.0, "chart_text_size_mm": 0.0})
        k2("k2_clip_text_squeeze",
           "K2: the clip-border-text message, which also names 7 pt",
           "", False,
           {"clip_border": True, "clip_side": "left",
            "clip_content_mode": "text",
            "clip_text": "\n".join([CLIP_SHORT] * 6),
            "clip_border_width_mm": 12.0, "margin_left": 30.0})

    res["steps"] = steps
    res["home_chromiq_untouched"] = not (Path.home() / "ChromIQ" / PROJECT).exists()
    (out / "warning-gaps.json").write_text(
        json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nwritten " + str(out / "warning-gaps.json"), flush=True)

    for t in _timers:
        t.stop()
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
