#!/usr/bin/env python3
"""§R8 "Size = auto" driven in a REAL window, twice in a row — combined round 4.

The auto-size walk changes a size the user did not type, and its own author
found a stateful fault in it that only a guard could see (the first build left
the settled size on the geometry, so a second pass would have drawn 19 pt into
a band reserved for 16). This driver asks the question the guard cannot: does
the APP, clicking Generate twice on the same chart, print the same sheet?

For each case it

* loads a real preset through the real Manual presets dropdown,
* types a left margin and either "auto" (0.0 in the Size box) or a size,
* presses **Generate**, measures the rendered TIFF, then presses **Generate
  again** and measures the second one,
* compares the two sheets pixel for pixel, and measures the ROW LABEL INK
  height off the raster rather than believing the panel,
* photographs the window.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20r4.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20r4-presets \\
        python scripts/adv_b20r4_autosize_on_screen.py <out-dir>

**Never set QT_QPA_PLATFORM=offscreen for this** (CLAUDE.md): a `widget.grab()`
is not a photograph, and this driver is about the app, not the suite.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def install_excepthook() -> list:
    """`main.py`'s hook, so a fault in the app is recorded and not swallowed."""
    seen: list = []
    prev = sys.excepthook

    def hook(exc_type, exc, tb):
        seen.append("".join(traceback.format_exception(exc_type, exc, tb)))
        prev(exc_type, exc, tb)

    sys.excepthook = hook
    return seen


def render(recipe, ti1: Path, tag: str, out: Path) -> dict:
    """Draw the sheet and measure it. THE RASTER, NOT THE PANEL."""
    import numpy as np
    from dataclasses import replace as _replace
    from PIL import Image
    from workflow.layout_engine import chart as _chart
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r4-"))
    try:
        res, _used = _chart.build_from_recipe(
            ti1, str(work / "sheet"), _replace(recipe, seed=20260917))
        tifs = sorted(work.glob("sheet*.tif"))
        if not tifs:
            return {"error": "no TIFF"}
        im = Image.open(tifs[0]).convert("RGB")
        (out / "sheets").mkdir(parents=True, exist_ok=True)
        im.save(out / "sheets" / f"{tag}.png")
        a = np.asarray(im).astype(int)
        dpi = float(getattr(recipe, "dpi", 300) or 300)
        px2mm = 25.4 / dpi
        mx, mn = a.max(2), a.min(2)
        black = (mx < 100) & ((mx - mn) < 30)
        coloured = (a.sum(2) < 720) & ((mx - mn) > 25)
        if not coloured.any():
            return {"error": "no colour on the sheet"}
        ccols = np.where(coloured.any(0))[0]
        crows = np.where(coloured.any(1))[0]
        d = {
            "patch_left_mm": round(float(ccols[0]) * px2mm, 3),
            "patch_top_mm": round(float(crows[0]) * px2mm, 3),
            "tiff_pages": len(tifs),
            "layout_pages": int(res.layout.pages),
            "patches_per_page": int(res.layout.patches_per_page),
            "total_patches": int(res.layout.total_patches),
            "sheet": f"sheets/{tag}.png",
        }
        # THE ROW LABELS' OWN INK, strictly left of the patch block, and its
        # HEIGHT — which is the only number on paper that can contradict the
        # settled size. A single label's cap height is measured on the tallest
        # unbroken run of dark rows inside the band.
        left_px = int(d["patch_left_mm"] / px2mm)
        if left_px > 2:
            strip = black[:, :left_px]
            cols = np.where(strip.any(0))[0]
            if len(cols):
                d["row_label_ink_left_mm"] = round(float(cols[0]) * px2mm, 3)
                d["row_label_ink_right_mm"] = round(float(cols[-1] + 1) * px2mm, 3)
                rows_on = strip.any(1)
                runs, start = [], None
                for i, on in enumerate(rows_on):
                    if on and start is None:
                        start = i
                    elif not on and start is not None:
                        runs.append(i - start); start = None
                if start is not None:
                    runs.append(len(rows_on) - start)
                if runs:
                    # The MEDIAN run, not the tallest: a digit with no
                    # ascender and one with a descender differ, and a pair of
                    # rows whose labels touch would report one tall run.
                    runs.sort()
                    d["row_label_glyph_median_mm"] = round(
                        runs[len(runs) // 2] * px2mm, 3)
                    d["row_label_glyph_max_mm"] = round(runs[-1] * px2mm, 3)
                    d["row_label_lines"] = len(runs)
        # A HASH OF THE WHOLE SHEET, so "the second build is the same sheet"
        # is a measurement and not an impression.
        import hashlib
        d["sha256"] = hashlib.sha256(a.astype("uint8").tobytes()).hexdigest()[:16]
        return d
    except Exception as exc:                       # noqa: BLE001
        return {"error": repr(exc)}
    finally:
        shutil.rmtree(work, ignore_errors=True)


#: (preset key fragment, left margin mm, Size box pt or None to leave it).
#: 0.0 in the Size box is "auto" — `layout_options_panel.small_pt` sets
#: `setSpecialValueText(tr("auto"))` on the minimum.
CASES = [
    # The design authority's own chart, put back to "auto" at the margin he
    # reported it at. This is the case §R8 was written for.
    ("cr30_a4_420p", 13.0, 0.0),
    ("cr30_a4_420p", 11.0, 0.0),     # narrower still: does it walk further?
    ("cr30_a4_420p", 26.0, 0.0),     # wide: nothing to settle, no walk
    ("cr30_a4_420p", 13.0, 19.0),    # TYPED, and must never be touched
    ("cr30_a4_420p", 13.0, 7.0),     # TYPED at the auto floor
    ("cr30_a4_153p", 13.0, 0.0),     # the low-patch hexagonal chart
    ("cr30_letter_780p", 13.0, 0.0),
    ("cr30_a4_450p", 11.0, 0.0),     # the STRAIGHT cut, flat-top honeycomb
    ("cr30_a4_1350p", 11.0, 0.0),    # straight, three pages
    ("cr30_a4_192p", 11.0, 0.0),     # SQUARE patches, same family
    ("cr30_a4_1080p", 9.0, 0.0),     # square, three pages, narrow margin
    ("cr30_letter_88p", 9.0, 0.0),   # square, Letter
]


def main() -> int:                                      # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), \
        "this is a DRIVER: it opens a real window (CLAUDE.md)"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    crashes = install_excepthook()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r4-out-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox output: {work}", flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore

    from ui.main_window import MainWindow
    from ui.tabs.tab_chart import TabChart, KNUT_PRESETS
    from ui.theme import apply_appearance
    from core.resource_path import resource_path
    TabChart._confirm_displacing_results = lambda self, *a, **k: True

    apply_appearance(app, None, "dark")
    win = MainWindow(settings)
    win.resize(1680, 1060)
    win.show()
    win.raise_()
    win.activateWindow()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_chart)
    tab = win._tab_chart
    pump(app, 800)
    tab._user_switch_mode("manual")
    pump(app, 1500)
    print(f"    window on screen: {win.isVisible()} "
          f"{win.frameGeometry().width()}x{win.frameGeometry().height()}",
          flush=True)
    panel = tab._manual_layout_panel
    assert panel is not None, "the ChromIQ layout panel is not on this tab"

    rows = []
    for frag, margin, size_pt in CASES:
        p = next((q for q in KNUT_PRESETS if frag in q.key), None)
        if p is None:
            rows.append({"case": frag, "error": "preset not found"}); continue
        tag = f"{frag}-L{margin:g}-{'auto' if size_pt == 0.0 else f'{size_pt:g}pt'}"
        print(f"  == {p.name}  L={margin}  size={'auto' if not size_pt else size_pt}",
              flush=True)
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText("B20R4")
        tab._activate_builtin_preset(p.key)
        pump(app, 1800)
        panel.indicator_size.setValue(size_pt)
        pump(app, 600)
        panel.margins["l"].setValue(margin)
        pump(app, 900)
        box_reads = panel.indicator_size.text()

        def generate():
            tab._margin_report = None
            tab._generate_btn.click()
            for _ in range(900):
                pump(app, 120)
                if getattr(tab, "_margin_report", None) is not None:
                    break
            tab._update_margin_inspector()
            pump(app, 700)

        from workflow.layout_engine import instruments as _i
        from workflow.layout_engine import raster as _raster
        ti1 = Path(resource_path(p.ti1_asset))

        def snapshot(which: str) -> dict:
            r = panel.get_recipe()
            g = _i.geom_from_build_kwargs(r.build_kwargs())
            settled = float(getattr(g, "row_label_size_mm", 0.0) or 0.0)
            drawn = _raster.effective_row_label_size_mm(
                g, int(r.dpi), r.indicator_font,
                float(r.indicator_size_mm or 0.0))
            warns, over = TabChart._engine_text_notes(
                tab, getattr(tab, "_margin_report", None))
            return {
                "recipe_margin_left": r.margin_left,
                "recipe_indicator_size_mm": r.indicator_size_mm,
                "geom_margin_l": round(float(g.margin_l), 4),
                "geom_rlwi": round(float(g.rlwi), 4),
                "geom_row_label_floor": round(
                    float(getattr(g, "row_label_floor", 0.0) or 0.0), 4),
                "settled_pt": (None if settled <= 0
                               else round(settled * 72.0 / 25.4, 3)),
                "drawn_row_label_pt": round(drawn * 72.0 / 25.4, 3),
                "warnings": list(over),
                "measured_left_mm": (
                    None if getattr(tab, "_margin_report", None) is None
                    else round(float(tab._margin_report.left_mm), 3)),
                "ink": render(r, ti1, f"{tag}-{which}", out),
            }

        generate()
        first = snapshot("build1")
        generate()
        second = snapshot("build2")

        shot = out / f"{tag}.png"
        ok, why = capture_window(win, shot)
        i1, i2 = first["ink"] or {}, second["ink"] or {}
        row = {
            "case": tag, "preset": p.name,
            "asked_margin_left": margin,
            "size_box_pt": size_pt,
            "size_box_reads": box_reads,
            "typed": bool(size_pt),
            "build1": first, "build2": second,
            "same_sheet": bool(i1.get("sha256")
                               and i1.get("sha256") == i2.get("sha256")),
            "photograph": str(shot) if ok else None,
            "photograph_refused": None if ok else why,
        }
        rows.append(row)
        print(f"     box reads {box_reads!r}  "
              f"margin_l {first['geom_margin_l']} / {second['geom_margin_l']}  "
              f"settled {first['settled_pt']} / {second['settled_pt']} pt  "
              f"drawn {first['drawn_row_label_pt']} / "
              f"{second['drawn_row_label_pt']} pt", flush=True)
        print(f"     ink glyph median {i1.get('row_label_glyph_median_mm')} / "
              f"{i2.get('row_label_glyph_median_mm')} mm   "
              f"patch_left {i1.get('patch_left_mm')} / {i2.get('patch_left_mm')} "
              f"  SAME SHEET: {row['same_sheet']}  photo={'OK' if ok else why}",
              flush=True)
        for m in first["warnings"]:
            print(f"        WARN1 {m[:150]}", flush=True)

    (out / "results.json").write_text(
        json.dumps({"rows": rows, "crashes": crashes}, indent=2),
        encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    for c in crashes:
        print(c, flush=True)
    win.close()
    pump(app, 500)
    return 0


if __name__ == "__main__":
    sys.exit(main())
