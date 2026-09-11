#!/usr/bin/env python3
"""On-screen reproduction / proof for Knut's #182 comment of 2026-09-11T15:06:22Z.

Drives the REAL ChromIQ window, on screen, against a sandboxed settings file, a
sandboxed presets folder and a sandboxed working folder, using KNUT'S OWN
project (``testHex``, a CR30 hex chart on A4, from "test projects.zip") and his
own numbers.

It answers, for each item:

  K1  With Chart Notes set and "Stamp settings used on the chart" on, right
      margin 6 mm and "Text distance from edge" -> Clip 4 mm, how big is the
      note actually printed?  Measured off the TIFF the app writes, in points.
  K4  What does the "Measured from Preview" message field say, verbatim, with
      a right-side clip border at 24 mm and the right margin at 24 / 28 / 30?
  K6  With the clip border narrowed to 16 mm and the clip-border content frame
      Size on "auto", how big is the clip-border text printed?

Usage:

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-textfit.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-textfit-presets
    python scripts/drive_182_text_shrink_floor.py --out DIR [--tag before]
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
from PyQt6.QtWidgets import QApplication                         # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                       # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

#: Knut's own clip-border text, from the ColorMunki preset family he was using
#: when he wrote the comment (`ui/tabs/tab_chart.py::_CM_CLIP_TEXT`). It is
#: FOUR lines, which is what makes the clip-border fitter shrink at all: one
#: short line in a 16 mm band never reaches the floor.
CM_CLIP_TEXT = (
    "————————————————————————————————————————————————————————————————————————\n"
    "{project} - {rundescription} - {paper} - {instrument} - {patchcount} - "
    "{page} - {date} - {seed}\n"
    "Top margin: 34 mm to avoid knobs underneath to get caught in page edge. "
    "Bottom margin: 18 mm to have 12 mm white space for comfortably ending "
    "strip.\n"
    "Left margin: 14 mm so 'glide-rails' do not fall outside of page (needs "
    "18 mm to patch centre). Right margin: 24 mm to allow for reading last "
    "strip using ruler."
)

WORK = Path("/tmp/chromiq-textfit-work")
KNUT_PROJECTS = Path("/tmp/k182-proof/projects")
PROJECT = "testHex"

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
        print(f"    !! modal: {title!r} -> closing")
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
# Measuring ink on the sheet the app itself wrote.
# --------------------------------------------------------------------------

def measure_ink_band(path: Path, from_right_mm_lo: float,
                     from_right_mm_hi: float) -> dict:
    """Width (across the sheet) of the ink inside a vertical band.

    The chart note and the clip-border text are rotated lines down a side
    margin, so their GLYPH HEIGHT is measured across the sheet, between two
    distances from the paper edge. Points are 1/72 inch, which is the unit
    Knut states his floor in.
    """
    import numpy as np
    import tifffile
    with tifffile.TiffFile(str(path)) as tf:
        page = tf.pages[0]
        arr = np.array(page.asarray())
        try:
            xres = page.tags["XResolution"].value
            dpi = float(xres[0]) / float(xres[1])
            # ResolutionUnit 3 is CENTIMETRES, and the engine writes that.
            # Read as inches it turns 200 dpi into 78.7 and every millimetre
            # below is wrong by 2.54.
            if int(page.tags["ResolutionUnit"].value) == 3:
                dpi *= 2.54
        except Exception:
            dpi = 200.0
    g = arr.min(axis=2) if arr.ndim == 3 else arr
    H, W = g.shape[:2]
    px_per_mm = dpi / 25.4
    x_hi = min(W, W - int(round(from_right_mm_lo * px_per_mm)))
    x_lo = max(0, W - int(round(from_right_mm_hi * px_per_mm)))
    if x_hi <= x_lo:
        return {"dpi": dpi, "error": "empty band"}
    sub = g[:, x_lo:x_hi]
    full = 65535 if sub.dtype.itemsize == 2 else 255
    inked_cols = (sub < int(0.6 * full)).any(axis=0)
    if not inked_cols.any():
        return {"dpi": round(dpi, 1), "inked": False,
                "band_px": [int(x_lo), int(x_hi)]}
    idx = np.flatnonzero(inked_cols)
    width_px = int(idx[-1] - idx[0] + 1)
    return {
        "dpi": round(dpi, 1),
        "inked": True,
        "band_px": [int(x_lo), int(x_hi)],
        "ink_width_px": width_px,
        "ink_width_mm": round(width_px * 25.4 / dpi, 3),
        "ink_width_pt": round(width_px * 72.0 / dpi, 2),
        "nearest_edge_mm": round((W - (x_lo + int(idx[-1]))) * 25.4 / dpi, 3),
    }


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


def diff_note_ink(before: Path, after: Path) -> dict:
    """The ink ONE sheet has and the other does not, measured across the sheet.

    Two builds of the same chart that differ only in "Run Chart Notes" and
    "Stamp settings used on the chart" differ by exactly the note, so the
    columns that changed ARE the note's glyph height. Measuring an inked band
    instead would measure the patch block next to it.
    """
    import numpy as np
    a, dpi = _read_gray(before)
    b, _ = _read_gray(after)
    if a.shape != b.shape:
        return {"error": f"shape {a.shape} vs {b.shape}"}
    W = a.shape[1]
    changed = (a.astype(int) != b.astype(int)).any(axis=0)
    if not changed.any():
        return {"dpi": round(dpi, 1), "changed": False}
    idx = np.flatnonzero(changed)
    width_px = int(idx[-1] - idx[0] + 1)
    return {
        "dpi": round(dpi, 1),
        "changed": True,
        "note_width_px": width_px,
        "note_width_mm": round(width_px * 25.4 / dpi, 3),
        "note_width_pt": round(width_px * 72.0 / dpi, 2),
        "note_inner_edge_from_right_mm": round((W - int(idx[0])) * 25.4 / dpi, 2),
        "note_outer_edge_from_right_mm": round((W - int(idx[-1])) * 25.4 / dpi, 2),
    }


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/k182-proof/onscreen")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    out.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"

    res: dict = {"tag": tag, "modals": modals,
                 "screen_locked": session_is_locked()}
    print(f"00 screen locked: {res['screen_locked']}")

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
    print(f"00 sandbox: settings {os.environ['CHROMIQ_SETTINGS_FILE']}, work {WORK}")

    src = KNUT_PROJECTS / PROJECT
    dst = WORK / PROJECT
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"00 staged Knut's project at {dst}")

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1620, 1060)
    win.show()
    pump(app, 1200)
    install_modal_watchdog(app)

    tab = win._tab_chart

    picked = False
    w = getattr(tab, "_target_combo", None)
    if w is not None:
        for i in range(w.count()):
            if w.itemText(i).strip() == PROJECT:
                w.setCurrentIndex(i)
                picked = True
                break
    pump(app, 900)
    res["target_picked_from_combo"] = picked

    if tab._current_mode() != "manual":
        tab._switch_mode("manual")
    pump(app, 600)
    if not picked:
        tab._manual_target_name_edit.setText(PROJECT)
        pump(app, 600)

    panel = tab._manual_layout_panel
    panel._expert_frame.set_collapsed(False)
    pump(app, 500)

    meta = json.loads((src / "runs/run1/meta.json").read_text(encoding="utf-8"))
    rec = meta["create_chart_ui"]["engine_recipe"]
    res["knut_chart_notes"] = meta["chart_notes"]

    tab._manual_chart_notes_edit.setText(meta["chart_notes"])
    tab._manual_stamp_cmd_check.setChecked(True)
    pump(app, 400)

    from workflow.layout_engine.presets import LayoutRecipe
    base = LayoutRecipe.from_dict(rec)
    panel.set_recipe(base)
    pump(app, 900)

    steps: list[dict] = []

    def apply(**over):
        # A FIXED SEED, or two builds of "the same" chart differ everywhere and
        # the diff measures the shuffle instead of the note. Knut's recipe
        # randomises with no seed.
        r = LayoutRecipe.from_dict({**rec, "randomize": True,
                                    "seed_fixed": True, "seed": 4242, **over})
        panel.set_recipe(r)
        pump(app, 800)

    notes_text = meta["chart_notes"]

    def snapshot(name: str, comment: str, generate: bool = False,
                 band=(0.0, 0.0), measure: str | None = None) -> dict:
        pump(app, 700)
        st: dict = {"step": name, "comment": comment}
        r = panel.get_recipe()
        st["margin_right_mm"] = round(float(r.margin_right), 2)
        st["text_edge_clip_mm"] = round(float(r.text_edge_clip_mm), 2)
        st["clip_border_on"] = bool(r.clip_border)
        st["clip_border_width_mm"] = round(float(r.clip_border_width_mm), 2)
        st["clip_side"] = r.clip_side
        st["clip_content_mode"] = r.clip_content_mode
        st["instrument"] = r.instrument
        st["chart_text_size_pt"] = round(float(panel.chart_text_size.value()), 2)
        st["clip_text_size_pt"] = round(float(panel.clip_text_size.value()), 2)
        try:
            warns, over = type(tab)._engine_text_notes(tab)
        except Exception as exc:                                   # noqa: BLE001
            warns, over = [f"<raised {exc!r}>"], []
        st["all_notices"] = warns
        st["overlap_notices"] = over
        def build():
            for t in dst.rglob("*.tif"):
                t.unlink()
            tab._generate_btn.click()
            okb = wait_for_build(app, tab)
            pump(app, 1500)
            return okb, sorted(dst.rglob("*.tif"))

        if generate:
            baseline = None
            if measure == "note":
                # Build once with the notes and the stamp OFF, so the ink the
                # two sheets differ by IS the note.
                tab._manual_chart_notes_edit.setText("")
                tab._manual_stamp_cmd_check.setChecked(False)
                pump(app, 600)
                _ok0, tifs0 = build()
                if tifs0:
                    baseline = out / f"{tag}_{name}__baseline.tif"
                    shutil.copy(tifs0[0], baseline)
                tab._manual_chart_notes_edit.setText(notes_text)
                tab._manual_stamp_cmd_check.setChecked(True)
                pump(app, 600)
            elif measure == "clip":
                cur = panel.get_recipe().to_dict()
                panel.set_recipe(LayoutRecipe.from_dict(
                    {**cur, "clip_content_mode": "off"}))
                pump(app, 700)
                _ok0, tifs0 = build()
                if tifs0:
                    baseline = out / f"{tag}_{name}__baseline.tif"
                    shutil.copy(tifs0[0], baseline)
                panel.set_recipe(LayoutRecipe.from_dict(cur))
                pump(app, 700)
            st["build_finished"], tifs = build()
            st["tifs"] = [str(t) for t in tifs]
            if tifs:
                lo, hi = band
                if hi <= lo:
                    lo, hi = 0.0, st["margin_right_mm"] + 2.0
                st["ink"] = measure_ink_band(tifs[0], lo, hi)
                if baseline is not None:
                    st["measured"] = diff_note_ink(baseline, tifs[0])
                    shutil.copy(tifs[0], out / f"{tag}_{name}__sheet.tif")
        ok, why = capture_window(win, out / f"{tag}_{name}.png")
        st["shot"] = f"{tag}_{name}.png" if ok else ""
        st["shot_refused"] = why
        steps.append(st)
        print(f"  {name}: right={st['margin_right_mm']} clip={st['text_edge_clip_mm']} "
              f"band={st['clip_border_width_mm']} -> {len(over)} overlap notice(s)"
              + (f"  measured={st.get('measured') or st.get('ink')}"
                 if generate else ""))
        for line in over:
            print("     RED: " + line.replace("\n", " "))
        return st

    only = sys.argv[sys.argv.index("--only") + 1].split(",") \
        if "--only" in sys.argv else None

    def want(k: str) -> bool:
        return only is None or k in only

    # ---- K1: his exact complaint. Right margin 6, Clip 4, notes + stamp on,
    #      no clip border in the way.
    if want("k1"):
        apply(clip_border=False, clip_content_mode="off", margin_right=6.0,
              text_edge_clip_mm=4.0, chart_text_size_mm=0.0)
        snapshot("k1_right6_clip4_auto", "K1: Knut's mini-font case",
                 generate=True, measure="note")
        apply(clip_border=False, clip_content_mode="off", margin_right=6.0,
              text_edge_clip_mm=4.0, chart_text_size_mm=12.0 * 25.4 / 72.0)
        snapshot("k1_right6_clip4_12pt",
                 "K1: a specific Sheet-text size, no shrink",
                 generate=True, measure="note")

    # ---- K4: the warning in his screenshot. Right-side clip border, 24 mm.
    k4 = dict(instrument="i1", clip_border=True, clip_side="right",
              clip_content_mode="text", clip_text=CM_CLIP_TEXT,
              clip_border_width_mm=24.0, text_edge_clip_mm=4.0,
              hflag=False, cm_density=1)
    if want("k4"):
        apply(margin_right=24.0, **k4)
        snapshot("k4_band24_right24", "K4: his screenshot's state")
        apply(margin_right=28.0, **k4)
        snapshot("k4_band24_right28", "K4: he showed 28 mm frees room")
        apply(margin_right=30.0, **k4)
        snapshot("k4_band24_right30", "K4: 30 mm, his test.tif state",
                 generate=True)

    # ---- K6: the clip-border text shrinking without a floor.
    if want("k6"):
        k6 = dict(k4)
        k6["clip_border_width_mm"] = 16.0
        apply(margin_right=10.0, clip_text_size_mm=0.0, **k6)
        snapshot("k6_band16_auto",
                 "K6: clip-border text shrinks without a floor",
                 generate=True, band=(0.0, 17.0), measure="clip")
        apply(margin_right=10.0, clip_text_size_mm=6.0 * 25.4 / 72.0, **k6)
        snapshot("k6_band16_6pt", "K6: a typed size below 8 pt must still work",
                 generate=True, band=(0.0, 17.0), measure="clip")

    res["steps"] = steps
    res["home_chromiq_untouched"] = not (Path.home() / "ChromIQ" / PROJECT).exists()
    (out / f"{tag}-result.json").write_text(json.dumps(res, indent=2),
                                            encoding="utf-8")
    print("written", out / f"{tag}-result.json")

    for t in _timers:
        t.stop()
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
