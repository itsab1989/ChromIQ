#!/usr/bin/env python3
"""Drive the REAL ChromIQ window through #163 — the clip-border branding.

soul-traveller reported that the "ChromIQ branding" clip content prints the
icon only when there is no text, and only the text once there is any. This
script proves the fix where it matters: in the running app, on the panel's own
live preview, and on a page TIFF built by the layout engine from the recipe the
panel produces.

    python scripts/drive_163_clip_branding.py [target]

Basti's preferences are copied into a throwaway .ini and a project is copied to
a temp folder — nothing of his is touched. Screenshots land in the folder the
script prints at the end.
"""
from __future__ import annotations

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
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
CLIP_LINES = "Knut Petersen\nEpson P900\nHahnemuehle"
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _pixmap_array(label) -> "np.ndarray | None":
    """The clip preview as RGB pixels, straight off the widget."""
    pix = label.pixmap()
    if pix is None or pix.isNull():
        return None
    img = pix.toImage().convertToFormat(img_fmt())
    w, h = img.width(), img.height()
    buf = img.constBits()
    buf.setsize(img.sizeInBytes())
    return np.frombuffer(buf, np.uint8).reshape(h, img.bytesPerLine() // 4, 4)[:, :w, :3]


def img_fmt():
    from PyQt6.QtGui import QImage
    return QImage.Format.Format_RGB32


def _wordmark_rows(arr: np.ndarray) -> int:
    """How many pixel rows carry the wordmark's magenta "IQ".

    Pinkness, not distance to (255, 69, 115): a loose distance also matches the
    grey antialiasing of ordinary black text, and a tight one finds nothing once
    the glyph is small. Magenta over white keeps red above green at any coverage;
    grey has red == green. (Format_RGB32 hands the bytes over as B, G, R.)
    """
    b, g, r = arr[..., 0].astype(int), arr[..., 1].astype(int), arr[..., 2].astype(int)
    return int((((r - g) > 40) & (b > g)).any(axis=1).sum())


def _shot(lp, path: Path) -> None:
    """The Clip-border content group as it looks on screen, real styling."""
    grp = lp._clip_content_grp
    pix = grp.grab()
    ok = pix.save(str(path))
    if not ok:
        print(f"    (screenshot failed: visible={grp.isVisible()} "
              f"size={grp.size().width()}x{grp.size().height()} "
              f"null={pix.isNull()})")


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "Canon-Pro300-CanonSG-i1Pro"
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)          # the real look, not a bare widget

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_163_"))
    shots = sandbox / "shots"
    shots.mkdir()
    from core.settings import AppSettings
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sandbox / "settings.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    settings = AppSettings()
    settings._qs = dst

    configured = str(settings.get("custom_output_path") or "").strip()
    real_root = Path(configured) if configured else (Path.home() / "ChromIQ")
    if not real_root.is_dir():
        real_root = Path.home() / "ChromIQ"
    work = sandbox / "ChromIQ"
    work.mkdir()
    if (real_root / target).is_dir():
        shutil.copytree(real_root / target, work / target)
    settings.set("custom_output_path", str(work))
    print(f"Sandbox: {sandbox}\n")

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.dialogs.layout_options_panel import mm_to_pt
    from ui.main_window import MainWindow

    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 900)
    lp = tab._manual_layout_panel

    print("SCENARIO 1 — the branding clip content, as the panel shows it")
    # The clip band only exists on an i1/p3 chart with the clip border ON, so
    # put the panel in the state soul-traveller uses before judging anything.
    lp._expert_frame.set_collapsed(False)      # the clip content lives in Expert
    lp.instr.setCurrentIndex(lp.instr.findData("i1"))
    pump(app, 400)
    lp.mode.setCurrentIndex(lp.mode.findData("clip"))
    lp.clip_width.setValue(24.0)
    pump(app, 400)
    check(lp.selection()[2] == "clip", "the chart has a clip border",
          f"{lp.clip_width.value():.0f} mm wide")
    i = lp.clip_content_mode.findData("branding")
    check(i >= 0, "the panel offers ChromIQ branding as clip content")
    lp.clip_content_mode.setCurrentIndex(i)
    pump(app, 400)
    lp.clip_text.setPlainText(CLIP_LINES)
    lp.clip_text_size.setValue(0.0)                 # "auto"
    pump(app, 700)
    auto = _pixmap_array(lp.clip_preview)
    check(auto is not None, "the live preview draws something")
    _shot(lp, shots / "1_auto.png")

    print("\nSCENARIO 2 — the Size box must change the PREVIEW, not just the sheet")
    lp.clip_text_size.setValue(mm_to_pt(6.0))
    pump(app, 700)
    six = _pixmap_array(lp.clip_preview)
    _shot(lp, shots / "2_six_mm.png")
    check(six is not None and auto is not None
          and not np.array_equal(auto, six),
          "setting Size to 6 mm redraws the preview",
          "the preview ignored the Size box before this fix")
    check(six is not None and _wordmark_rows(six) > 0,
          "the ChromIQ wordmark is still in the preview at 6 mm",
          f"{_wordmark_rows(six) if six is not None else 0} magenta rows")

    print("\nSCENARIO 3 — the recipe the panel hands to the engine")
    rec = lp.get_recipe()
    check(abs(rec.clip_text_size_mm - 6.0) < 0.05,
          "the recipe carries the 6 mm the user typed",
          f"clip_text_size_mm={rec.clip_text_size_mm:.2f}")
    check(rec.clip_content_mode == "branding", "…and the branding mode")
    check(rec.clip_text.strip() == CLIP_LINES,
          "…and the three lines, unaltered")

    print("\nSCENARIO 4 — a REAL page built by the layout engine from that recipe")
    ti1 = next(iter(sorted(work.glob("*/*.ti1"))), None)
    if ti1 is None:
        check(False, "a .ti1 to build from", f"none under {work}")
    else:
        from workflow.layout_engine import chart as le_chart
        kw = rec.build_kwargs()
        kw["instrument"] = "i1"
        kw["paper"] = "A4"
        out = sandbox / "page"
        res = le_chart.build_chart(ti1, out, **kw)
        tif = next(iter(sorted(sandbox.glob("page*.tif"))), None)
        check(tif is not None, "the engine wrote a page TIFF",
              f"{res.layout.total_patches} patches, {res.layout.pages} page(s)")
        if tif is not None:
            from PIL import Image
            page = Image.open(tif).convert("RGB")
            arr = np.asarray(page).astype(int)
            # ONLY the clip band. A wider slice reaches the patch columns, and a
            # magenta PATCH then passes for the wordmark — the first version of
            # this check "passed" on the unfixed code for exactly that reason.
            px_per_mm = page.width / 210.0                   # A4 across
            band_px = int(round(rec.clip_border_width_mm * px_per_mm))
            band = arr[:, :band_px]
            r_, g_, b_ = band[..., 0], band[..., 1], band[..., 2]
            mag = ((r_ - g_) > 40) & (b_ > g_)      # pinkness — see _wordmark_rows
            ys = np.where(mag.any(axis=1))[0]        # along the strip
            xs = np.where(mag.any(axis=0))[0]        # ACROSS the band = cap height
            wm_mm = (xs.max() - xs.min() + 1) / px_per_mm if len(xs) else 0.0
            check(wm_mm >= 3.0,
                  "the printed sheet carries a legible ChromIQ wordmark",
                  f"the magenta 'IQ' is {wm_mm:.1f} mm tall in a "
                  f"{rec.clip_border_width_mm:.0f} mm band")
            ink = (band.sum(axis=2) < 700)
            cols = np.where(ink.any(axis=0))[0]
            inked = np.where(ink.any(axis=1))[0]
            if len(inked):
                # Crop on the INK, not on the wordmark: when the wordmark has
                # been squeezed out there is nothing magenta left to centre on.
                pad = int(round(6 * px_per_mm))
                page.crop((0, max(0, inked.min() - pad), band_px + 4,
                           min(page.height, inked.max() + pad))
                          ).save(str(shots / "4_printed_band.png"))
            check(len(cols) > 0 and cols.min() > 0 and cols.max() < band_px - 1,
                  "no clip content is cut off at either edge of the band",
                  f"ink spans columns {int(cols.min())}–{int(cols.max())} "
                  f"of {band_px}")
            rows_ = np.where(ink.any(axis=1))[0]
            check(len(rows_) > 0, "the band is not blank")

    print("\nSCENARIO 5 — one line at 3 mm: what the preview claims will print")
    # 3 mm is well away from the size the automatic fit would choose here (~8 mm),
    # so a preview that ignores the Size box is obvious at a glance.
    lp.clip_text.setPlainText("Knut Petersen")
    lp.clip_text_size.setValue(mm_to_pt(3.0))
    pump(app, 700)
    pix = lp.clip_preview.pixmap()
    if pix is not None and not pix.isNull():
        pix.save(str(shots / "5_preview_3mm.png"))
    big = _wordmark_rows(_pixmap_array(lp.clip_preview))
    check(big > 0, "the preview still shows the wordmark at 3 mm",
          f"{big} magenta rows")

    print(f"\nScreenshots: {shots}")
    bad = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    win.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
