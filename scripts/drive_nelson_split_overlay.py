#!/usr/bin/env python3
"""Proof for Nelson Lau: the expected-vs-measured split on his own 10x15 cm
chart, with and without the chart's geometry sidecar.

He reported (printerknowledge, post 149403) that his own 10 x 15 cm mini target
shows no expected/measured split while measuring. The split needs the chart's
per-patch PIXEL geometry, which ChromIQ writes beside the chart as
`<stem>.channels.json`. A page re-made in another program arrives without it,
so there is nothing to split.

In 4.2.1 his target ships as a built-in preset, and that bundle carries the
geometry -- so the split works with no extra step. This drives the real window
twice on the SAME chart to show both halves of that:

  A. the bundle as ChromIQ ships it            -> the split draws
  B. the identical TIFF with the sidecar gone  -> it does not

A measurement is synthesised from the chart's own .ti2 with a small, deliberate
shift, so every patch has an expected and a measured colour and the split is
visible. Nothing about the geometry is faked: the boxes come from the shipped
sidecar.

Settings are sandboxed; nothing of the user's is touched.
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

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"
SHOTS = Path.home() / "Desktop" / "ChromIQ-hex-proof" / "09-for-nelson"
BUNDLE = ROOT / "assets/charts/pharmacist/rgb/i1pro/100x150/photocard600"


def pump(app, ms):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _fake_ti3(ti2: Path, out: Path) -> None:
    """A measurement of this chart: its own .ti2 with every reading shifted.

    Not a real instrument read, and it does not pretend to be: the point is
    only that a measured value EXISTS for each patch, so the split has two
    colours to draw. The geometry is the chart's own.
    """
    text = ti2.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    out_lines, in_data, fields = [], False, []
    for ln in lines:
        s = ln.strip()
        if s.startswith("BEGIN_DATA_FORMAT"):
            out_lines.append(ln); continue
        if s.startswith("END_DATA_FORMAT"):
            out_lines.append(ln); continue
        if s.startswith("BEGIN_DATA"):
            in_data = True; out_lines.append(ln); continue
        if s.startswith("END_DATA"):
            in_data = False; out_lines.append(ln); continue
        if not fields and ("RGB_R" in s or "XYZ_X" in s) and not in_data:
            fields = s.split()
            out_lines.append(ln); continue
        if in_data and s and not s.startswith("#"):
            parts = s.split()
            try:
                idx = {n: k for k, n in enumerate(fields)}
                for name, d in (("XYZ_X", 1.7), ("XYZ_Y", -1.3), ("XYZ_Z", 2.1)):
                    if name in idx:
                        parts[idx[name]] = f"{max(0.0, float(parts[idx[name]]) + d):.4f}"
            except Exception:      # noqa: BLE001
                pass
            out_lines.append(" ".join(parts)); continue
        out_lines.append(ln)
    out.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


def run(app, keep_sidecar: bool, tag: str) -> int:
    from core.settings import AppSettings
    sb = Path(tempfile.mkdtemp(prefix="chromiq-nelson-"))
    src = QSettings(str(REAL_PLIST), QSettings.Format.NativeFormat)
    dst = QSettings(str(sb / "s.ini"), QSettings.Format.IniFormat)
    for k in src.allKeys():
        dst.setValue(k, src.value(k))
    dst.sync()
    s = AppSettings()
    s._qs = dst
    work = sb / "ChromIQ"
    proj = work / "PhotoCard600" / "runs" / "run1"
    proj.mkdir(parents=True)
    s.set("custom_output_path", str(work))
    s.set("restore_last_session", False)

    for f in BUNDLE.iterdir():
        shutil.copy2(f, proj / f.name)
    stem = proj / "photocard600"
    if not keep_sidecar:
        (proj / "photocard600.channels.json").unlink(missing_ok=True)
        for j in proj.glob("*.strips.json"):
            j.unlink()
    _fake_ti3(stem.with_suffix(".ti2"), stem.with_suffix(".ti3"))

    QDialog.exec = lambda self: 1                  # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.main_window import MainWindow
    win = MainWindow(s)
    win.resize(1500, 1000)
    win.show()
    pump(app, 2500)
    win._tabs.setCurrentWidget(win._tab_measure)
    tab = win._tab_measure
    tab.set_ti1_path(stem.with_suffix(".ti2"))
    pump(app, 2500)

    boxes = sum(len(d) for d in (tab._patch_boxes or []))
    drew = False
    try:
        drew = bool(tab._show_overlay_from_existing_ti3())
    except Exception as exc:      # noqa: BLE001
        print(f"      overlay raised {type(exc).__name__}: {exc}")
    pump(app, 1500)

    SHOTS.mkdir(parents=True, exist_ok=True)
    pm = tab._preview.grab()
    ok = (not pm.isNull()) and pm.save(str(SHOTS / f"{tag}.png"))
    print(f"    sidecar {'present' if keep_sidecar else 'REMOVED':8}  "
          f"pages {len(tab._tiff_pages)}  patch boxes {boxes:4}  "
          f"split drawn: {drew}   {'saved '+tag+'.png' if ok else 'GRAB FAILED'}")

    # ...and a zoom, so the two colours in one patch can be seen
    if drew and tab._patch_boxes and tab._patch_boxes[0]:
        loc, r = sorted(tab._patch_boxes[0].items())[len(tab._patch_boxes[0]) // 2]
        tab._preview.set_patch_click_enabled(True, tab._patch_boxes)
        tab._preview.highlight_patch(0, r)
        for _ in range(3):
            if hasattr(tab._preview, "zoom_in"):
                tab._preview.zoom_in()
        pump(app, 1200)
        z = tab._preview.grab()
        if not z.isNull():
            z.save(str(SHOTS / f"{tag}-zoom-{loc}.png"))
            print(f"      zoomed on patch {loc} -> {tag}-zoom-{loc}.png")
    win.close()
    pump(app, 400)
    return 0 if (drew == keep_sidecar) else 1


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)
    print("\n  Nelson's 10 x 15 cm 600-patch chart, in the real Measure tab\n")
    bad = run(app, True, "01-as-ChromIQ-ships-it")
    bad += run(app, False, "02-with-the-sidecar-removed")
    print(f"\n  problems: {bad}\n  proof in {SHOTS}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
