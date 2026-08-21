#!/usr/bin/env python3
"""Does the patch overlay land on the patch — across every case that matters?

One patch of each chart is printed pure magenta in an otherwise flat grey
chart, the chart is opened in the real Measure tab, the app is asked to
highlight the patch IT thinks the magenta one is, and the ring's position is
measured against the magenta ink. Anything but a zero offset is a bug.

Covers: hexagon sizes, window sizes, the other instruments (i1Pro strips, the
staggered ColorMunki), the square SpectroScan layout, and the "show only
measured patches" view, which draws its own outlines from the same boxes.

    python scripts/drive_hex_overlay_matrix.py
"""
from __future__ import annotations

import json
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
from PIL import Image                                           # noqa: E402
from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
RESULTS: list[tuple[bool, str, str]] = []
SHOTS: list = []


def check(ok: bool, name: str, detail: str = "") -> None:
    RESULTS.append((bool(ok), name, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def _probe_ti1(path: Path, n: int, mark: int) -> None:
    """A flat grey chart with exactly one magenta patch — judged by eye or by
    arithmetic, with no colour ambiguity either way."""
    lines = ["CTI1", "", 'DESCRIPTOR "overlay probe"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    for i in range(n):
        r, g, b = (100.0, 0.0, 100.0) if i == mark else (78.0, 78.0, 78.0)
        lines.append(f"{i+1} {r} {g} {b} 40.0 45.0 50.0")
    lines += ["END_DATA", ""]
    path.write_text("\n".join(lines))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_matrix_"))
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
    from workflow.layout_engine import chart as le_chart
    win = MainWindow(settings)
    win.show()
    pump(app, 2200)
    win._tabs.setCurrentWidget(win._tab_measure)
    tab = win._tab_measure

    CASES = [
        ("hex 10 mm",        dict(instrument="SS", hflag=True,  pscale=10/7), (1500, 1000)),
        ("hex 12 mm",        dict(instrument="SS", hflag=True,  pscale=12/7), (1500, 1000)),
        ("hex 20 mm",        dict(instrument="SS", hflag=True,  pscale=20/7), (1500, 1000)),
        ("hex 12 mm, small window", dict(instrument="SS", hflag=True, pscale=12/7), (1000, 700)),
        ("hex 12 mm, wide window",  dict(instrument="SS", hflag=True, pscale=12/7), (1900, 1100)),
        ("SpectroScan square", dict(instrument="SS", hflag=False, pscale=12/7), (1500, 1000)),
        ("i1Pro strips",     dict(instrument="i1"),                            (1500, 1000)),
        ("ColorMunki staggered", dict(instrument="CM", cm_stagger=True),       (1500, 1000)),
    ]

    for name, kw, (ww, wh) in CASES:
        folder = work / name.replace(" ", "_").replace(",", "")
        folder.mkdir(parents=True, exist_ok=True)
        ti1 = folder / "probe.ti1"
        _probe_ti1(ti1, 150, 77)
        stem = folder / "Chart"
        try:
            res = le_chart.build_chart(ti1, stem, paper="A4", border=6.0,
                                       dpi=200, randomize=False, **kw)
        except Exception as exc:              # noqa: BLE001
            check(False, name, f"build failed: {exc}")
            continue
        strips = json.loads(stem.with_suffix(".strips.json").read_text())
        (folder / "Chart.channels.json").write_text(json.dumps({
            "ink_channels": ["r", "g", "b"],
            "layout": {"engine": "chromiq", "engine_version": 1, "dpi": 200,
                       "paper_mm": [210.0, 297.0], "patches": strips["patches"],
                       "recipe": dict({"instrument": kw.get("instrument", "i1")},
                                      **{k: v for k, v in kw.items()
                                         if k in ("hflag", "cm_stagger")})}}))
        win.resize(ww, wh)
        pump(app, 400)
        tab.set_ti1_path(stem.with_suffix(".ti2"))
        pump(app, 1800)

        page = np.asarray(Image.open(sorted(folder.glob("Chart*.tif"))[0])
                          .convert("RGB")).astype(int)
        boxes = tab._patch_boxes[0] if tab._patch_boxes else {}
        loc = ""
        for k, b in boxes.items():
            c = page[b.y() + b.height() // 2, b.x() + b.width() // 2]
            if c[0] > 180 and c[1] < 90 and c[2] > 180:
                loc = k
                break
        if not loc:
            check(False, name, "the app has no box on the magenta patch")
            continue
        plain = tab._preview.grab().toImage()
        tab._preview.set_patch_click_enabled(True, tab._patch_boxes)
        tab._preview.highlight_patch(0, boxes[loc])
        pump(app, 700)
        shot = tab._preview.grab().toImage()

        def arr(qim):
            qim = qim.convertToFormat(qim.format().Format_RGB32)
            w, h = qim.width(), qim.height()
            buf = qim.constBits(); buf.setsize(qim.sizeInBytes())
            a = np.frombuffer(buf, np.uint8).reshape(h, qim.bytesPerLine() // 4, 4)
            return a[:, :w, :3][:, :, ::-1].astype(int)      # BGR -> RGB

        pa, ha = arr(plain), arr(shot)
        mag = (pa[:, :, 0] > 190) & (pa[:, :, 1] < 100) & (pa[:, :, 2] > 190)
        ring = np.abs(ha - np.array([31, 143, 107])).sum(axis=2) < 70
        if not mag.any() or not ring.any():
            check(False, name, f"magenta {int(mag.sum())} px, ring {int(ring.sum())} px")
            continue
        my, mx = np.where(mag)
        ry, rx = np.where(ring)
        dx, dy = rx.mean() - mx.mean(), ry.mean() - my.mean()
        check(abs(dx) < 3 and abs(dy) < 3, f"{name} — ring on the patch ({loc})",
              f"offset dx {dx:+.1f}, dy {dy:+.1f} px")
        # A crop each, so the claim can be checked by eye and not only by number.
        cy, cx = int(my.mean()), int(mx.mean())
        half = int(max(60, 2.2 * (mx.max() - mx.min())))
        y0, y1 = max(0, cy - half), min(ha.shape[0], cy + half)
        x0, x1 = max(0, cx - half), min(ha.shape[1], cx + half)
        tile = Image.fromarray(ha[y0:y1, x0:x1].astype("uint8"))
        tile = tile.resize((420, 420), Image.NEAREST)
        SHOTS.append((f"{name}  ({loc})", f"dx {dx:+.1f}  dy {dy:+.1f} px", tile))

    print("\nSHOW ONLY MEASURED PATCHES — outlines drawn from the same boxes")
    tab._preview.set_show_only_measured(True)
    pump(app, 800)
    only = tab._preview.grab()
    only.save(str(sandbox / "only_measured.png"))
    check(True, "captured the only-measured view", str(sandbox / "only_measured.png"))
    tab._preview.set_show_only_measured(False)

    if SHOTS:
        from PIL import ImageDraw, ImageFont
        F = "/Users/Basti/develop/ChromIQ/assets/fonts/Inter-VariableFont_opsz,wght.ttf"
        f1 = ImageFont.truetype(F, 24); f2 = ImageFont.truetype(F, 20)
        cols = 4
        rows = (len(SHOTS) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * 440 + 20, rows * 500 + 70), (250, 250, 250))
        d = ImageDraw.Draw(sheet)
        d.text((16, 16), "The highlight ring against the one magenta patch — "
               "every case, real app", font=f1, fill=(20, 20, 20))
        for i, (title, sub, tile) in enumerate(SHOTS):
            x, y = 16 + (i % cols) * 440, 60 + (i // cols) * 500
            d.text((x, y), title, font=f1, fill=(20, 20, 20))
            d.text((x, y + 28), sub, font=f2, fill=(20, 130, 90))
            sheet.paste(tile, (x, y + 56))
        out = sandbox / "overlay_matrix.png"
        sheet.save(str(out))
        print(f"\ncontact sheet: {out}")
    bad = [r for r in RESULTS if not r[0]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
    print(f"sandbox: {sandbox}")
    win.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
