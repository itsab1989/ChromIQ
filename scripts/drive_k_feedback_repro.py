#!/usr/bin/env python3
"""Reproduce Knut's 2026-08-23 batch in the REAL window, before anything is fixed.

Four claims, driven the way he drove them:

  K1  "Markers per patch": 4 draws 5, and the ones inside the patch are not
      evenly distributed; 3 and 5 look right.
  K2  Clip-border content: with a ColorMunki preset the panel's own Preview
      stays blank in every content mode.
  K3  "Clip area" shows only "—" for the same selection.
  K4  Notes box ignores the Text field, so the field should be disabled — is it
      disabled, and does it LOOK disabled?

    python scripts/drive_k_feedback_repro.py [--out DIR]

Basti's preferences are copied into a throwaway .ini — nothing of his is
touched. Screenshots land in --out (default: ~/Desktop/chromiq-knut-repro).
"""
from __future__ import annotations

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

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  [{'OK ' if ok else 'BUG'}] {name}" + (f"  — {detail}" if detail else ""))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(widget, path: Path) -> None:
    pix = widget.grab()
    if not pix.save(str(path)):
        print(f"    (screenshot failed for {path.name})")


def main() -> int:
    out = Path.home() / "Desktop" / "chromiq-knut-repro"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_krepro_"))
    from core.settings import AppSettings
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

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.show()
    pump(app, 2500)
    tab = win._tab_chart
    tab._switch_mode("manual")
    pump(app, 900)
    lp = tab._manual_layout_panel
    lp._expert_frame.set_collapsed(False)
    pump(app, 400)

    # ---- a ColorMunki chart, as Knut's preset makes one -------------------
    lp.instr.setCurrentIndex(lp.instr.findData("CM"))
    pump(app, 600)
    print(f"Instrument: {lp.instr.currentData()}  mode={lp.selection()[2]}")

    print("\nK2/K3 — clip-border content on a ColorMunki chart")
    for key in ("text", "branding", "notes", "image"):
        i = lp.clip_content_mode.findData(key)
        lp.clip_content_mode.setCurrentIndex(i)
        if key in ("text", "branding"):
            lp.clip_text.setPlainText("Knut Larsson\nEpson P900\nHahnemuehle")
        pump(app, 700)
        pix = lp.clip_preview.pixmap()
        blank = pix is None or pix.isNull()
        dims = lp.clip_dims_label.text()
        check(not blank, f"content={key}: the panel Preview draws something",
              f"pixmap={'none' if blank else 'present'}")
        check(dims not in ("—", "-", ""), f"content={key}: Clip area is measured",
              f"shows {dims!r}")
        shot(lp._clip_content_grp, out / f"before_clip_{key}.png")
        if key == "notes":
            en = lp.clip_text.isEnabled()
            check(not en, "Notes box: the Text field is disabled",
                  f"isEnabled={en}")

    print("\nK1 — markers per patch, as the overlay and the recipe show it")
    lp.helper_markers_cb.setChecked(True)
    pump(app, 300)
    from workflow.layout_engine import instruments, geometry, papers
    for n in (3, 4, 5, 6):
        lp.helper_marker_per_patch.setValue(n)
        pump(app, 400)
        rec = lp.get_recipe()
        g = instruments.geom_from_build_kwargs(rec.build_kwargs())
        w_mm, h_mm = papers.dimensions_mm(rec.paper)
        lay = geometry.compute(g, w_mm, h_mm, 480)
        pl = geometry.placement(g, w_mm, h_mm, lay)
        lines = geometry.helper_marker_lines_mm(
            g, w_mm, h_mm, lay, edge_mm=rec.helper_marker_edge_mm,
            length_mm=rec.helper_marker_len_mm,
            per_patch=rec.helper_marker_per_patch)
        ys = sorted({round(y0, 3) for (x0, y0, x1, y1) in lines if abs(y0 - y1) < 1e-9})
        top, bot = pl.y_of(1), pl.y_of(1) + g.plen
        inside = [y for y in ys if top - 1e-6 < y < bot + 1e-6]
        span = [y for y in ys if top - g.pspa <= y <= bot + g.pspa]
        # distances measured from the patch's own edges
        d = [round(inside[0] - top, 2)] + \
            [round(b - a, 2) for a, b in zip(inside, inside[1:])] + \
            [round(bot - inside[-1], 2)] if inside else []
        print(f"  n={n}: {len(span)} dashes from spacer-centre to spacer-centre, "
              f"{len(inside)} strictly inside the patch")
        print(f"        gaps measured from the patch edges: {d}")
        check(len(inside) == n - 2,
              f"n={n}: exactly {n} dashes per patch counting both ends",
              f"{len(inside)} inside + 2 ends = {len(inside) + 2}")
        check(len(set(d)) <= 1 if d else False,
              f"n={n}: evenly distributed between the patch's start and end",
              f"gaps {d}")

    shot(win, out / "before_window.png")
    print(f"\nScreenshots: {out}")
    bad = [r for r in RESULTS if not r[0]]
    print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} behaved as Knut expects")
    win.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
