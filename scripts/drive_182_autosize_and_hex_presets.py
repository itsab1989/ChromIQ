#!/usr/bin/env python3
"""The auto-size ruling and the eight CR30 hexagonal presets, driven on screen.

Loads each preset through the REAL Manual presets dropdown, reads the panel's
own notices back, builds the sheet and MEASURES the rendered TIFF. The patch
count and the page count come off the build result, not off the preset's name,
because the whole reason B8-265 was held was a fear that they would stop
agreeing.

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b20p.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b20p-presets \\
        python scripts/drive_182_autosize_and_hex_presets.py <out-dir> [key ...]

With no keys it drives every CR30 preset whose key contains "hexagonal",
which is the eight Hexagonal ones AND the six Hexagonal-Straight ones. The
straight six are the control group: the ruling must not move them.

``--size-pt N`` types a size into "Strip and row indicators" after the
preset has loaded, which is how a tester's own manual measurement is
reproduced before eight shipped files are edited.

**Never set QT_QPA_PLATFORM=offscreen for this.** It is a driver, not a test:
`widget.grab()` is not a photograph and cannot show what the window server did.
"""
from __future__ import annotations

import json
import os
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


def sheet_ink_mm(recipe, ti1: Path, tag: str, out: Path) -> "dict | None":
    """Where the ink really lands, and how many patches on how many pages.

    **THE RASTER, NOT THE RECIPE.** Every number the panel prints is a
    prediction; the only way to check one is to draw the page and look at it.
    """
    import numpy as np
    from dataclasses import replace as _replace
    from PIL import Image
    from workflow.layout_engine import chart as _chart
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20p-ink-"))
    try:
        # `build_from_recipe(ti1, out_base, recipe)` and it returns a PAIR.
        # Called with the recipe first it raises `'str' object has no attribute
        # 'build_kwargs'` inside the try, which this function turns into an
        # {"error": ...} row -- a driver can therefore report fourteen clean
        # presets having measured no ink at all, which is what the first run of
        # this one did.
        #
        # THE SEED IS PINNED so two runs draw the same sheet. Randomisation
        # moves no geometry, but an unpinned seed makes the saved PNGs
        # impossible to diff by eye.
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
        crows = np.where(coloured.any(1))[0]
        ccols = np.where(coloured.any(0))[0]
        d = {
            "patch_top_mm": round(float(crows[0]) * px2mm, 3),
            "patch_left_mm": round(float(ccols[0]) * px2mm, 3),
            "patch_right_mm": round(float(a.shape[1] - ccols[-1] - 1) * px2mm, 3),
            "patch_bottom_mm": round(float(a.shape[0] - crows[-1] - 1) * px2mm, 3),
            "paper_w_mm": round(float(a.shape[1]) * px2mm, 2),
            "paper_h_mm": round(float(a.shape[0]) * px2mm, 2),
            "tiff_pages": len(tifs),
            "layout_pages": int(res.layout.pages),
            "patches_per_page": int(res.layout.patches_per_page),
            "total_patches": int(res.layout.total_patches),
            "sheet": f"sheets/{tag}.png",
        }
        # THE ROW LABELS' OWN INK, strictly LEFT of the patch block. That is
        # the band the left margin has to hold, and the only number on the
        # sheet that can contradict the panel about it.
        left_px = int(d["patch_left_mm"] / px2mm)
        if left_px > 2:
            strip = black[:, :left_px]
            cols = np.where(strip.any(0))[0]
            if len(cols):
                d["row_label_ink_left_mm"] = round(float(cols[0]) * px2mm, 3)
                d["row_label_ink_right_mm"] = round(
                    float(cols[-1] + 1) * px2mm, 3)
        # HELPER MARKER INK down the LEFT page edge, outside the row-label
        # floor: this is what "the markers are not drawn" has to be measured
        # by, since a preview that shows nothing is not evidence about paper.
        d["left_edge_dark_cols"] = int(
            black[:, :max(1, int(3.0 / px2mm))].any(0).sum())
        return d
    except Exception as exc:                       # noqa: BLE001
        return {"error": repr(exc)}
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def main() -> int:                                      # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    argv = list(sys.argv[1:])
    size_pt = None
    if "--size-pt" in argv:
        i = argv.index("--size-pt")
        size_pt = float(argv[i + 1])
        del argv[i:i + 2]
    margin_l = None
    if "--margin-left" in argv:
        i = argv.index("--margin-left")
        margin_l = float(argv[i + 1])
        del argv[i:i + 2]
    out = Path(argv[0]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    wanted = argv[1:]
    crashes = install_excepthook()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20p-"))
    settings = AppSettings()
    # PINNED, not merely sandboxed: an unset value in a fresh store still
    # points the app at the user's real ~/ChromIQ.
    settings.set("custom_output_path", str(work))
    settings.set("use_chromiq_layout_engine", True)
    settings.set("restore_last_session", False)
    settings.set("appearance", "dark")
    settings.set("margin_inspector_show", True)
    settings.set("margin_violation_notify", True)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
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

    # `"cr30_" IN the key, not `startswith`: a built-in preset's key is the
    # slug wrapped in the reserved-name sentinel
    # (`__chromiq_knut_cr30_a4_420p…__`), so a prefix match silently selects
    # NOTHING and the driver reports a clean run over zero presets.
    cr30 = [p for p in KNUT_PRESETS
            if "cr30_" in p.key and "hexagonal" in p.key]
    if wanted:
        cr30 = [p for p in cr30 if any(w in p.key for w in wanted)]
    print(f"    {len(cr30)} preset(s) to drive", flush=True)

    rows = []
    for p in cr30:
        tag = (p.key + (f"-at{size_pt:g}pt" if size_pt is not None else "")
               + (f"-L{margin_l:g}" if margin_l is not None else ""))
        print(f"  == {p.name}", flush=True)
        if tab._manual_target_name_edit is not None:
            tab._manual_target_name_edit.setText("B20P")
        tab._activate_builtin_preset(p.key)
        pump(app, 1800)
        if size_pt is not None:
            panel.indicator_size.setValue(size_pt)
            pump(app, 900)
        if margin_l is not None:
            panel.margins["l"].setValue(margin_l)
            pump(app, 900)
        # **PRESS GENERATE, OR THE PANEL HAS MEASURED NOTHING.** The
        # "Measured from Preview" figures -- the ones a tester quotes when he
        # says the left margin is 14.1 mm -- are `tab._margin_report`, and it
        # is None until a sheet has been built and measured. Several of the
        # panel's own checks read it too and are SILENT without it, so a
        # driver that skips this reports every case clean.
        tab._margin_report = None
        tab._generate_btn.click()
        for _ in range(900):
            pump(app, 120)
            if getattr(tab, "_margin_report", None) is not None:
                break
        tab._update_margin_inspector()
        pump(app, 900)
        r = panel.get_recipe()
        warns, over = TabChart._engine_text_notes(
            tab, getattr(tab, "_margin_report", None))
        from workflow.layout_engine import instruments as _i
        g = _i.geom_from_build_kwargs(r.build_kwargs())
        settled_mm = float(getattr(g, "row_label_size_mm", 0.0) or 0.0)
        row = {
            "key": p.key, "name": p.name,
            "typed_size_pt": size_pt,
            "recipe_margin_left": r.margin_left,
            "recipe_indicator_size_mm": getattr(r, "indicator_size_mm", None),
            "recipe_indicator_size_pt": (
                None if not getattr(r, "indicator_size_mm", 0.0)
                else round(float(r.indicator_size_mm) * 72.0 / 25.4, 2)),
            "panel_size_box_pt": float(panel.indicator_size.value()),
            "helper_markers": bool(getattr(r, "helper_markers", False)),
            "helper_markers_top_bottom": bool(
                getattr(r, "helper_markers_top_bottom", True)),
            "helper_markers_sides": bool(
                getattr(r, "helper_markers_sides", True)),
            "geom_margin_l": round(float(g.margin_l), 3),
            "geom_rlwi": round(float(g.rlwi), 3),
            "geom_row_label_floor": round(
                float(getattr(g, "row_label_floor", 0.0) or 0.0), 3),
            "settled_auto_size_pt": (None if settled_mm <= 0
                                     else round(settled_mm * 72.0 / 25.4, 2)),
            "panel_warnings": list(over),
            "panel_notes": [w for w in warns if w not in over],
            "declared_patches": p.patches,
            "declared_pages": p.pages,
            "measured_from_preview": (
                None if getattr(tab, "_margin_report", None) is None
                else {k: round(float(getattr(tab._margin_report, k)), 3)
                      for k in ("left_mm", "right_mm", "top_mm", "bottom_mm")}),
        }
        ti1 = resource_path(p.ti1_asset)
        row["ink"] = sheet_ink_mm(r, Path(ti1), tag, out)
        shot = out / f"{tag}.png"
        ok, why = capture_window(win, shot)
        row["photograph"] = str(shot) if ok else None
        row["photograph_refused"] = None if ok else why
        _mfp = row["measured_from_preview"] or {}
        print(f"     margin_l={row['geom_margin_l']} rlwi={row['geom_rlwi']} "
              f"settled={row['settled_auto_size_pt']}pt "
              f"measured_left={_mfp.get('left_mm')} "
              f"warnings={len(over)} photo={'OK' if ok else why}", flush=True)
        for m in over:
            print(f"        WARN {m[:170]}", flush=True)
        ink = row["ink"] or {}
        print(f"     ink: pages={ink.get('layout_pages')} "
              f"ppp={ink.get('patches_per_page')} "
              f"total={ink.get('total_patches')} "
              f"patch_left={ink.get('patch_left_mm')} "
              f"label_ink_left={ink.get('row_label_ink_left_mm')}", flush=True)
        rows.append(row)

    name = ("results" + ("" if size_pt is None else f"-at{size_pt:g}pt")
            + ("" if margin_l is None else f"-L{margin_l:g}") + ".json")
    (out / name).write_text(
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
