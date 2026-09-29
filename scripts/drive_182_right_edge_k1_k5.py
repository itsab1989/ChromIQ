#!/usr/bin/env python3
"""K1 and K5 from Knut's beta 7 report, measured by driving the REAL window.

K1 -- "the clip-border width is 24.0mm and the right margin is 24.0. […] When I
reduce the Clip-border width to […] 18mm, but leave the right margin on 24mm,
the chart does not change at all and the clip-border text still fits perfectly
[…] However, there is a red warning text."

K5 -- "the gap between the chart notes text line and the beginning of the
clip-border text is a little too narrow, and not exactly the normal distance two
text lines would have for the set font size."

Everything is read from the app's OWN calls, never re-derived here:

* ``MarginInspectorPanel.update_report`` is wrapped, so the warnings recorded
  are the strings the panel was handed;
* ``text_edge_fit.clip_text_squeeze`` / ``clip_text_collision`` /
  ``clip_text_overhang_mm`` and ``tiff_metadata._stamp_one`` are wrapped, so the
  ARGUMENTS in the report are the arguments the app passed;
* the ink is measured on the TIFFs the app itself wrote, taken from
  ``TabChart._margin_tiffs`` after a real press of "Generate Chart".

Sandboxed the way CLAUDE.md requires: a throwaway settings .ini, a throwaway
presets dir, and ``custom_output_path`` pinned inside a temp folder. Nothing of
the owner's is written. Check afterwards with

    defaults read com.chromiq.ChromIQ custom_output_path

Usage::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-rightedge.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-rightedge-presets \
        python scripts/drive_182_right_edge_k1_k5.py [--phase k1|k5|both]
"""
from __future__ import annotations

import json
import shutil
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

import numpy as np                                              # noqa: E402
import tifffile                                                 # noqa: E402
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
OUT = Path.home() / "Desktop" / "chromiq-182-right-edge"

#: Knut's own case for K1.
K1_PRESET = ("__chromiq_knut_cm_a3_900p_2pages_portrait_w10_0mm_fast_reading_speed__")
#: One page, 306 patches, the SAME clip family (24 mm band on the right, its
#: text at a typed 10 pt) -- the chart the code comments measure K5 on.
K5_PRESET = ("__chromiq_knut_cm_a4_306p_1page_portrait_w10_0mm_slow_reading_speed__")

CALLS: list[dict] = []          # every wrapped text_edge_fit / stamper call


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


# ---------------------------------------------------------------- ink measure
def ink_groups(tif: Path, dpi: float, thresh: int = 250) -> dict:
    """Contiguous runs of inked COLUMNS, measured from the paper's right edge.

    A column is inked when any pixel in it is darker than *thresh*. The groups
    are returned right-to-left, each as millimetres in from the right page
    edge, which is the frame every number in this area is quoted in.
    """
    arr = tifffile.imread(str(tif))
    if arr.ndim == 3:
        flat = arr.min(axis=2)
    else:
        flat = arr
    if flat.dtype == np.uint16:
        lim = int(thresh * 257)
    else:
        lim = thresh
    ink = flat < lim
    counts = ink.sum(axis=0)
    h, w = ink.shape
    groups = []
    x = w - 1
    while x >= 0:
        if counts[x] > 0:
            end = x
            while x >= 0 and counts[x] > 0:
                x -= 1
            start = x + 1
            rows = np.nonzero(ink[:, start:end + 1].any(axis=1))[0]
            groups.append({
                "px_from_right_outer": w - 1 - end,      # nearest the edge
                "px_from_right_inner": w - 1 - start,    # furthest inward
                "mm_from_right_outer": round((w - 1 - end) * 25.4 / dpi, 3),
                "mm_from_right_inner": round((w - 1 - start) * 25.4 / dpi, 3),
                "width_px": end - start + 1,
                "ink_px": int(ink[:, start:end + 1].sum()),
                "row_first": int(rows[0]) if rows.size else -1,
                "row_last": int(rows[-1]) if rows.size else -1,
                "row_span_mm": (round((int(rows[-1]) - int(rows[0])) * 25.4 / dpi, 1)
                                if rows.size else 0.0),
            })
        else:
            x -= 1
    return {"file": str(tif), "w": int(w), "h": int(h), "dpi": dpi,
            "groups": groups}


def right_region(prof: dict, mm_limit: float = 60.0) -> list[dict]:
    """Only the groups within *mm_limit* of the right page edge."""
    return [g for g in prof["groups"] if g["mm_from_right_outer"] < mm_limit]


# ------------------------------------------------------------------- the spies
def install_spies():
    from workflow import text_edge_fit as tef
    from workflow import tiff_metadata as tmeta

    for name in ("clip_text_squeeze", "clip_text_collision",
                 "clip_text_overhang_mm", "clip_text_reach_mm",
                 "clip_content_inset_mm", "clip_band_needed_mm"):
        orig = getattr(tef, name)

        def make(n, f):
            def wrapper(*a, **k):
                out = f(*a, **k)
                CALLS.append({"fn": f"text_edge_fit.{n}",
                              "args": [repr(x) for x in a],
                              "kwargs": {kk: repr(vv) for kk, vv in k.items()},
                              "result": repr(out)})
                return out
            return wrapper
        setattr(tef, name, make(name, orig))

    _stamp = tmeta._stamp_one

    def stamp_spy(path, text, *a, **k):
        CALLS.append({"fn": "tiff_metadata._stamp_one",
                      "path": str(path), "text": text,
                      "args": [repr(x) for x in a],
                      "kwargs": {kk: repr(vv) for kk, vv in k.items()}})
        return _stamp(path, text, *a, **k)
    tmeta._stamp_one = stamp_spy


def take_calls(prefix: str = "") -> list[dict]:
    out = [c for c in CALLS if not prefix or c["fn"].startswith(prefix)]
    CALLS.clear()
    return out


# --------------------------------------------------------------------- driving
def build_app_window(app):
    from core.settings import AppSettings

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-rightedge-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst
    work = sandbox / "ChromIQ"
    work.mkdir()
    settings.set("custom_output_path", str(work))
    settings.set("restore_last_session", False)
    settings.set("appearance", "light")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    settings.set("use_chromiq_layout_engine", True)
    print(f"    sandbox: {sandbox}", flush=True)

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    install_spies()

    from ui.main_window import MainWindow
    from ui.theme import apply_appearance
    from ui.tabs.tab_chart import TabChart
    from ui.margin_inspector_panel import MarginInspectorPanel
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    seen: dict = {}
    _orig = MarginInspectorPanel.update_report

    def _spy(self, report, violations, **kw):
        seen.clear()
        seen.update({
            "report": None if report is None else {
                "L": round(report.left_mm, 2), "R": round(report.right_mm, 2),
                "T": round(report.top_mm, 2), "B": round(report.bottom_mm, 2),
                "page_w": round(report.page_w_mm, 1),
                "page_h": round(report.page_h_mm, 1),
            },
            "violations": [f"{v.edge} {v.measured_mm:.1f}<{v.threshold_mm:.1f}"
                           for v in violations],
            "text_warnings": list(kw.get("text_warnings") or []),
            "overlap_warnings": list(kw.get("overlap_warnings") or []),
        })
        return _orig(self, report, violations, **kw)
    MarginInspectorPanel.update_report = _spy          # type: ignore[assignment]

    apply_appearance(app, None, "light")
    win = MainWindow(settings)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 3000)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)
    return win, tab, seen, work


def select_preset(app, tab, key: str, seen: dict) -> bool:
    combo = tab._preset_combo
    idx = combo.findData(key)
    if idx < 0:
        print(f"    preset {key} NOT in the dropdown", flush=True)
        return False
    seen.clear()
    tab._margin_ti2 = None
    combo.setCurrentIndex(idx)
    combo.activated.emit(idx)
    # The preset is APPLIED here; whether it also builds depends on
    # "Auto-update preview", which is off in Knut's own screenshot. Every state
    # below presses Generate for itself, so this only has to settle the panel.
    pump(app, 4000)
    print(f"    preset applied: {combo.currentText()[:60]}", flush=True)
    return True


def generate(app, tab, timeout_s: int = 600) -> list[Path]:
    """Press the real Generate button and return the TIFFs the app recorded."""
    before = list(getattr(tab, "_margin_tiffs", []) or [])
    tab._margin_tiffs = []
    tab._generate_btn.click()
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        pump(app, 250)
        tiffs = list(getattr(tab, "_margin_tiffs", []) or [])
        if tiffs and tab._generate_btn.isEnabled():
            pump(app, 1200)
            return list(getattr(tab, "_margin_tiffs", []) or [])
    print("    GENERATE DID NOT FINISH IN TIME", flush=True)
    return before


def photo(win, name: str) -> str:
    from scripts.onscreen_capture import capture_window
    OUT.mkdir(parents=True, exist_ok=True)
    ok, why = capture_window(win, OUT / name)
    print(f"    photo {name}: {'OK' if ok else 'REFUSED - ' + why}", flush=True)
    return "OK" if ok else f"REFUSED: {why}"


def recipe_facts(tab) -> dict:
    r = tab._current_layout_recipe()
    from workflow.layout_engine import instruments
    from workflow.layout_engine.raster import clip_text_lines
    geom = instruments.geom_from_build_kwargs(r.build_kwargs())
    lines = clip_text_lines(getattr(r, "clip_text", "") or "")
    return {
        "clip_border_width_mm": float(r.clip_border_width_mm),
        "clip_side": str(r.clip_side),
        "clip_content_mode": str(r.clip_content_mode),
        "clip_text_size_mm": float(r.clip_text_size_mm or 0.0),
        "clip_text_size_pt": round(float(r.clip_text_size_mm or 0.0) * 72 / 25.4, 2),
        "clip_lines": len(lines),
        "chart_text_size_mm": float(getattr(r, "chart_text_size_mm", 0.0) or 0.0),
        "margin_right": float(r.margin_right),
        "margin_left": float(r.margin_left),
        "dpi": int(r.dpi),
        "text_edge_clip_mm": float(r.text_edge_clip_mm),
        "effective_text_edge_clip_mm": float(r.effective_text_edge_clip_mm),
        "helper_markers": bool(r.helper_markers),
        "helper_marker_edge_mm": float(r.helper_marker_edge_mm),
        "helper_marker_len_mm": float(r.helper_marker_len_mm),
        "helper_markers_sides": bool(r.helper_markers_sides),
        "geom.lbord": float(geom.lbord), "geom.border": float(geom.border),
        "geom.margin_r": float(geom.margin_r),
        "geom.margin_l": float(geom.margin_l),
        "geom.clip_side": str(getattr(geom, "clip_side", "")),
    }


# ------------------------------------------------------------------ the phases
def phase_k1(app, win, tab, seen, work) -> dict:
    print("\n=== K1: Knut's A3 900p 2-page portrait, clip 24 -> 18\n", flush=True)
    rec: dict = {"preset": K1_PRESET, "states": []}
    panel = tab._manual_layout_panel

    for tag, clip_w in (("clip24", 24.0), ("clip18", 18.0)):
        # THE NAME FIRST, THEN THE PRESET. Typing a target name loads that
        # target's own stored settings, which puts the Presets box back on
        # "none" and undoes the preset if it is applied the other way round.
        name = f"K1{tag}"
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText(name)
        pump(app, 800)
        if not select_preset(app, tab, K1_PRESET, seen):
            rec["error"] = "the preset is not in the dropdown"
            return rec
        panel.clip_width.setValue(clip_w)
        pump(app, 1500)
        take_calls()                       # drop what the typing produced
        state = {
            "tag": tag, "clip_width_typed": clip_w,
            "right_margin_typed": float(panel.margins["r"].value()),
            "recipe": recipe_facts(tab),
        }
        tiffs = generate(app, tab)
        pump(app, 1000)
        take_calls()                       # the build's own calls, not wanted
        # The panel's own arguments, taken from the update the build triggered.
        tab._update_margin_inspector()
        pump(app, 600)
        state.update({
            "panel_status": panel_status(tab),
            "text_warnings": list(seen.get("text_warnings") or []),
            "overlap_warnings": list(seen.get("overlap_warnings") or []),
            "report": seen.get("report"),
            "calls": take_calls("text_edge_fit"),
        })
        state["photo"] = photo(win, f"k1-{tag}-window.png")
        state["tiffs"] = [str(t) for t in tiffs]
        prof = []
        for i, t in enumerate(tiffs):
            keep = OUT / f"k1-{tag}-page{i + 1}.tif"
            OUT.mkdir(parents=True, exist_ok=True)
            shutil.copy2(t, keep)
            p = ink_groups(keep, float(state["recipe"]["dpi"]))
            p["right_groups"] = right_region(p)
            prof.append(p)
        state["ink"] = prof
        rec["states"].append(state)
        print(f"    {tag}: warnings={len(state['overlap_warnings'])} "
              f"tiffs={len(tiffs)}", flush=True)
    return rec


def panel_status(tab) -> str:
    try:
        return tab._margin_panel.status_message()
    except Exception:                                  # noqa: BLE001
        return "<unavailable>"


#: The note Knut would type. Long enough to be a real line, short enough that
#: nothing is cut at the floor.
K5_NOTE = "Canon PRO-1000 / Photo Rag 308 / no colour management"


def phase_k5(app, win, tab, seen, work) -> dict:
    """Every case is built TWICE, with the note and without it, at a FIXED seed.

    The pair differs by the note alone, so the note's ink columns are the diff
    and nothing has to be guessed from a shape. The right margin is opened to
    34 mm because at the preset's own 24 mm the band leaves no white paper for
    the note at all and it is stamped over the patches, which is a different
    fault (§2f) from the one K5 is about.
    """
    print("\n=== K5: the gap between the chart note and the clip text\n", flush=True)
    rec: dict = {"preset": K5_PRESET, "states": []}
    panel = tab._manual_layout_panel

    # (tag, clip size pt, sheet-text size pt, right margin mm)
    cases = [
        ("clip10-noteauto", 10.0, 0.0, 34.0),
        ("clip14-noteauto", 14.0, 0.0, 34.0),
        ("clip7-noteauto", 7.0, 0.0, 34.0),
        ("clip10-note12", 10.0, 12.0, 34.0),
    ]
    for tag, clip_pt, note_pt, margin_r in cases:
        for withnote in (False, True):
            full = f"{tag}-{'note' if withnote else 'control'}"
            if tab._manual_target_name_edit is not None:
                tab._manual_target_name_edit.setText("K5" + tag.replace("-", ""))
            pump(app, 700)
            if not select_preset(app, tab, K5_PRESET, seen):
                rec["error"] = "the preset is not in the dropdown"
                return rec
            # A FIXED SEED, so the control and the note build are the same sheet.
            panel.randomize_cb.setChecked(True)
            panel.fixed_seed_cb.setChecked(True)
            panel.seed_spin.setValue(4812)
            panel.margins["r"].setValue(margin_r)
            panel.clip_text_size.setValue(clip_pt)
            panel.chart_text_size.setValue(note_pt)   # the Sheet text frame's Size
            if tab._manual_chart_notes_edit is not None:
                tab._manual_chart_notes_edit.setText(K5_NOTE if withnote else "")
            pump(app, 1500)
            take_calls()
            state = {
                "tag": full, "with_note": withnote, "note": K5_NOTE if withnote else "",
                "clip_pt": clip_pt, "note_pt": note_pt, "margin_r": margin_r,
                "recipe": recipe_facts(tab),
            }
            tiffs = generate(app, tab)
            pump(app, 800)
            state["stamp_calls"] = take_calls("tiff_metadata")
            tab._update_margin_inspector()
            pump(app, 500)
            state["overlap_warnings"] = list(seen.get("overlap_warnings") or [])
            state["report"] = seen.get("report")
            state["calls"] = take_calls("text_edge_fit")
            state["tiffs"] = [str(t) for t in tiffs]
            prof = []
            for i, t in enumerate(tiffs):
                keep = OUT / f"k5-{full}-page{i + 1}.tif"
                OUT.mkdir(parents=True, exist_ok=True)
                shutil.copy2(t, keep)
                p = ink_groups(keep, float(state["recipe"]["dpi"]))
                p["right_groups"] = right_region(p)
                prof.append(p)
            state["ink"] = prof
            if withnote:
                state["photo"] = photo(win, f"k5-{tag}-window.png")
            rec["states"].append(state)
            g = prof[0]["right_groups"] if prof else []
            print(f"    {full}: {len(g)} ink groups in the right 60 mm",
                  flush=True)
    return rec


def phase_k1m(app, win, tab, seen, work) -> dict:
    """Does the warning fire where it SHOULD, and only there?

    Five (band, right margin, clip size) combinations, each built twice at a
    fixed seed: once with the clip content on and once with it off. The two
    rasters differ by the clip band's ink alone, so where that ink lands is a
    subtraction and not a judgement, and "the text is printed over the patches"
    can be counted in pixels.
    """
    print("\n=== K1-matrix: where the warning is right to fire\n", flush=True)
    rec: dict = {"preset": K5_PRESET, "states": []}
    panel = tab._manual_layout_panel
    cases = [
        ("b24-m24-s10", 24.0, 24.0, 10.0),
        ("b18-m24-s10", 18.0, 24.0, 10.0),
        ("b12-m12-s10", 12.0, 12.0, 10.0),
        ("b12-m32-s10", 12.0, 32.0, 10.0),
        ("b24-m24-s14", 24.0, 24.0, 14.0),
    ]
    for tag, band, margin_r, clip_pt in cases:
        pages: dict = {}
        for mode in ("text", "off"):
            if tab._manual_target_name_edit is not None:
                tab._manual_target_name_edit.setText("K1M" + tag.replace("-", ""))
            pump(app, 700)
            if not select_preset(app, tab, K5_PRESET, seen):
                rec["error"] = "the preset is not in the dropdown"
                return rec
            panel.randomize_cb.setChecked(True)
            panel.fixed_seed_cb.setChecked(True)
            panel.seed_spin.setValue(4812)
            panel.clip_width.setValue(band)
            panel.margins["r"].setValue(margin_r)
            panel.clip_text_size.setValue(clip_pt)
            panel._select_clip_content(mode)
            if tab._manual_chart_notes_edit is not None:
                tab._manual_chart_notes_edit.setText("")
            pump(app, 1500)
            take_calls()
            tiffs = generate(app, tab)
            pump(app, 800)
            keep = OUT / f"k1m-{tag}-{mode}-page1.tif"
            if tiffs:
                shutil.copy2(tiffs[0], keep)
            pages[mode] = keep
            if mode == "text":
                tab._update_margin_inspector()
                pump(app, 500)
                state = {
                    "tag": tag, "band": band, "margin_r": margin_r,
                    "clip_pt": clip_pt,
                    "recipe": recipe_facts(tab),
                    "report": seen.get("report"),
                    "overlap_warnings": list(seen.get("overlap_warnings") or []),
                    "calls": take_calls("text_edge_fit"),
                }
                state["photo"] = photo(win, f"k1m-{tag}-window.png")
        # The clip band's own ink, by subtraction.
        state["ink_diff"] = clip_ink_over_patches(
            pages["off"], pages["text"], float(state["recipe"]["dpi"]),
            float((state["report"] or {}).get("R") or margin_r))
        state["ink"] = [dict(ink_groups(pages["text"],
                                        float(state["recipe"]["dpi"])),
                             right_groups=right_region(
                                 ink_groups(pages["text"],
                                            float(state["recipe"]["dpi"]))))]
        rec["states"].append(state)
        print(f"    {tag}: warnings={len(state['overlap_warnings'])} "
              f"clip ink on the patch area = "
              f"{state['ink_diff']['ink_px_over_patches']} px", flush=True)
    return rec


def phase_k1s(app, win, tab, seen, work) -> dict:
    """K1 again, as a STRICT pixel comparison: one project name, one seed.

    Knut's claim is "the chart does not change at all". The two sheets are
    built into the same project at the same seed, so the only thing that can
    differ is what the clip-border width did, and the difference is countable.
    """
    print("\n=== K1-strict: the same sheet at clip 24 and clip 18\n", flush=True)
    rec: dict = {"preset": K1_PRESET, "states": []}
    panel = tab._manual_layout_panel
    for tag, clip_w in (("s24", 24.0), ("s18", 18.0)):
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText("K1strict")
        pump(app, 800)
        if not select_preset(app, tab, K1_PRESET, seen):
            rec["error"] = "the preset is not in the dropdown"
            return rec
        panel.randomize_cb.setChecked(True)
        panel.fixed_seed_cb.setChecked(True)
        panel.seed_spin.setValue(4812)
        panel.clip_width.setValue(clip_w)
        pump(app, 1500)
        take_calls()
        tiffs = generate(app, tab)
        pump(app, 800)
        for i, t in enumerate(tiffs):
            shutil.copy2(t, OUT / f"k1strict-{tag}-page{i + 1}.tif")
        tab._update_margin_inspector()
        pump(app, 500)
        rec["states"].append({
            "tag": tag, "clip_width": clip_w,
            "report": seen.get("report"),
            "warnings": list(seen.get("overlap_warnings") or []),
            "pages": len(tiffs),
        })
        print(f"    {tag}: {len(tiffs)} pages, "
              f"{len(seen.get('overlap_warnings') or [])} warnings", flush=True)
    return rec


def clip_ink_over_patches(control: Path, withtext: Path, dpi: float,
                          patch_right_mm: float) -> dict:
    """Where the clip band's own ink landed, by subtracting the two sheets."""
    a = tifffile.imread(str(control))
    b = tifffile.imread(str(withtext))
    if a.shape != b.shape:
        return {"error": f"shapes differ {a.shape} vs {b.shape}"}
    fa = a.min(axis=2) if a.ndim == 3 else a
    fb = b.min(axis=2) if b.ndim == 3 else b
    changed = fa.astype(int) != fb.astype(int)
    ink = (fb < (250 * 257 if fb.dtype == np.uint16 else 250)) & changed
    h, w = ink.shape
    cols = np.nonzero(ink.any(axis=0))[0]
    if cols.size == 0:
        return {"clip_ink_px": 0, "ink_px_over_patches": 0}
    # The patch area starts this many px in from the right page edge.
    edge_x = w - 1 - int(round(patch_right_mm * dpi / 25.4))
    return {
        "clip_ink_px": int(ink.sum()),
        "clip_ink_mm_from_right_outer": round((w - 1 - int(cols[-1])) * 25.4 / dpi, 3),
        "clip_ink_mm_from_right_inner": round((w - 1 - int(cols[0])) * 25.4 / dpi, 3),
        "patch_right_mm_from_right": patch_right_mm,
        "ink_px_over_patches": int(ink[:, :edge_x + 1].sum()),
        "patch_area_pixels_changed": int(changed[:, :edge_x + 1].sum()),
    }


def main() -> int:
    phase = "both"
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--phase":
            phase = args[i + 1]
    app = QApplication.instance() or QApplication(sys.argv)
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from scripts.onscreen_capture import session_is_locked, wake_the_screen
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    if session_is_locked():
        print("    wake: %s / %s" % wake_the_screen(), flush=True)

    win, tab, seen, work = build_app_window(app)
    OUT.mkdir(parents=True, exist_ok=True)
    out: dict = {}
    if (OUT / "k1-k5.json").is_file():      # keep the other phase's record
        try:
            out = json.loads((OUT / "k1-k5.json").read_text(encoding="utf-8"))
        except Exception:                   # noqa: BLE001
            out = {}
    out["when"] = time.strftime("%Y-%m-%d %H:%M:%S")
    out["window_visible"] = bool(win.isVisible())
    if phase in ("k1", "both"):
        out["k1"] = phase_k1(app, win, tab, seen, work)
        (OUT / "k1-k5.json").write_text(json.dumps(out, indent=1,
                                                   ensure_ascii=False),
                                        encoding="utf-8")
    if phase in ("k5", "both"):
        out["k5"] = phase_k5(app, win, tab, seen, work)
    if phase in ("k1m", "both"):
        out["k1m"] = phase_k1m(app, win, tab, seen, work)
    if phase in ("k1s", "both"):
        out["k1s"] = phase_k1s(app, win, tab, seen, work)
    (OUT / "k1-k5.json").write_text(json.dumps(out, indent=1, ensure_ascii=False),
                                    encoding="utf-8")
    print(f"\n    wrote {OUT / 'k1-k5.json'}", flush=True)
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
