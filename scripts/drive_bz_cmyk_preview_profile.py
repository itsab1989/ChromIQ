#!/usr/bin/env python3
"""Drive the REAL ChromIQ window and show what the bundled CMYK profile does.

`assets/USWebCoatedSWOP.icc` — Adobe's "U.S. Web Coated (SWOP) v2" — shipped in
every release from v2.3.0 with no licence and no record that anyone had checked
we were allowed to. It is replaced by ArgyllCMS's public-domain
`assets/profiles/cmyk.icm`. That changes what a CMYK TIFF preview looks like on
every platform, so it has to be shown in the running app, not argued from a
table.

    python scripts/drive_bz_cmyk_preview_profile.py <a-cmyk.tif> [outdir]

Run it once on this tree and once on a checkout that still has the Adobe file:
the two runs are the after and the before. It also runs the fallback case with
the bundled profile moved out of the way, which is what a user with Adobe
software installed and a stripped build would get.

Basti's preferences are never touched: CHROMIQ_SETTINGS_FILE is set before
anything imports core.settings, and the run prints the value it ends with.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Sandbox the settings BEFORE core.settings can be imported by anything.
_SANDBOX = Path(tempfile.mkdtemp(prefix="chromiq_bz_"))
os.environ.setdefault("CHROMIQ_SETTINGS_FILE", str(_SANDBOX / "settings.ini"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

import numpy as np                                              # noqa: E402
from PyQt6.QtGui import QFontDatabase, QImage                    # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox    # noqa: E402

from core.resource_path import resource_path                     # noqa: E402


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def as_array(widget) -> np.ndarray:
    """The widget exactly as painted, as RGB — no re-render, no second path.

    The ``.copy()`` is load-bearing, and its absence cost a whole run of this
    script. ``np.frombuffer(img.constBits())`` is a VIEW onto the QImage's
    memory; ``img`` dies when this function returns, the allocator hands the
    same block to the next grab, and two different renders come back
    byte-identical. The first version of this script duly reported
    "identical=True, meanDE76=0.00" for two pictures whose PNGs on disk plainly
    differed.
    """
    img = widget.grab().toImage().convertToFormat(QImage.Format.Format_RGB32)
    w, h = img.width(), img.height()
    buf = img.constBits()
    buf.setsize(img.sizeInBytes())
    arr = np.frombuffer(buf, np.uint8).reshape(h, img.bytesPerLine() // 4, 4)
    return arr[:, :w, 2::-1].copy()        # BGRA -> RGB, detached from Qt


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    a = rgb.reshape(-1, 3).astype(float) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805],
                  [0.2126, 0.7152, 0.0722],
                  [0.0193, 0.1192, 0.9505]])
    xyz = (lin @ m.T) / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[:, 1] - 16,
                     500 * (f[:, 0] - f[:, 1]),
                     200 * (f[:, 1] - f[:, 2])], 1)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    tif = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else _SANDBOX / "shots"
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    # The style the app actually ships (main.py), not the platform default.
    try:
        from main import WinButtonLayoutStyle
        app.setStyle(WinButtonLayoutStyle("Fusion"))
    except Exception:
        app.setStyle("Fusion")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    from core.settings import AppSettings
    settings = AppSettings()
    work = _SANDBOX / "ChromIQ"
    work.mkdir(exist_ok=True)
    settings.set("custom_output_path", str(work))

    QDialog.exec = lambda self: 1                      # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui import tiff_preview as tp
    from ui.main_window import MainWindow

    win = MainWindow(settings)
    win.resize(1500, 1000)
    win.show()
    pump(app, 2500)

    preview = win._tab_chart._preview          # the app's own shared preview
    bundled_name = getattr(tp, "_BUNDLED_CMYK_PROFILE",
                           "assets/USWebCoatedSWOP.icc")
    bundled = Path(resource_path(bundled_name))

    results: list[tuple[str, np.ndarray]] = []

    def shot(tag: str, note: str) -> None:
        tp._cmyk_icc_transform = None          # the app's own cache, reset
        used = {"path": None}
        real = tp._get_cmyk_transform
        preview.load_tiff([tif])
        pump(app, 2000)
        arr = as_array(preview)
        png = out / f"{tag}.png"
        preview.grab().save(str(png))
        badge = ""
        try:
            badge = preview._ink_badge.text() or preview._badge_lbl.text()
        except Exception:
            pass
        print(f"  [{tag}] {note}")
        print(f"         badge: {badge!r}")
        print(f"         shot:  {png}")
        results.append((tag, arr))
        del real, used

    print(f"\nSandbox:  {_SANDBOX}")
    print(f"TIFF:     {tif}")
    print(f"Bundled:  {bundled_name} -> exists={bundled.exists()}\n")

    shot("A-bundled", f"bundled profile present ({bundled.name})")

    if bundled.exists():
        hidden = bundled.with_suffix(bundled.suffix + ".hidden")
        bundled.rename(hidden)
        try:
            sysp = Path("/Library/Application Support/Adobe/Color/Profiles/"
                        "Recommended/USWebCoatedSWOP.icc")
            gen = Path("/System/Library/ColorSync/Profiles/"
                       "Generic CMYK Profile.icc")
            shot("B-fallback",
                 "bundled profile REMOVED — system Adobe present: "
                 f"{sysp.exists()}, ColorSync generic present: {gen.exists()}")
        finally:
            hidden.rename(bundled)

    if len(results) >= 2:
        (ta, a), (tb, b) = results[0], results[1]
        if a.shape == b.shape:
            d = np.sqrt(((srgb_to_lab(a) - srgb_to_lab(b)) ** 2).sum(1))
            print(f"\n  {ta} vs {tb} on the painted pixels: "
                  f"meanDE76={d.mean():.2f} p95={np.percentile(d, 95):.2f} "
                  f"max={d.max():.2f}  identical={np.array_equal(a, b)}")
        else:
            print(f"\n  {ta} and {tb} differ in size: {a.shape} vs {b.shape}")

    pump(app, 800)
    win.close()
    print(f"\nSettings file used: {os.environ['CHROMIQ_SETTINGS_FILE']}")
    print(f"Shots: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
