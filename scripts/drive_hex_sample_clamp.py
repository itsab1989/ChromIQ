#!/usr/bin/env python3
"""Drive the REAL Scanner-profile dialog over a hexagonal chart and photograph
the Sample area control, so the cap can be seen rather than believed.

`scanin` reads a RECTANGLE inside each patch. Inside a hexagon that rectangle
runs out of room far sooner than inside a square, and the next hexagon is flush
against this one — so a box one percent too big reads the NEIGHBOUR, on every
patch at once. ChromIQ now works the ceiling out from the chart's own patch
proportions and applies it to the spinbox.

    python scripts/drive_hex_sample_clamp.py [patch_mm]

Two dialogs are opened on two real charts built by the engine — the same
patches, hexagonal and rectangular — and both are photographed, because the cap
is only right if the rectangular chart still gets its full 80 %.

Basti's preferences are copied to a throwaway .ini; nothing of his is touched.
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

from PyQt6.QtCore import QSettings                              # noqa: E402
from PyQt6.QtGui import QFontDatabase                           # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox           # noqa: E402

from core.resource_path import resource_path                    # noqa: E402

REAL_PLIST = Path.home() / "Library/Preferences/com.chromiq.ChromIQ.plist"


def pump(app, ms: int) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def build_chart(work: Path, name: str, w_mm: float, hexagonal: bool) -> Path:
    """A real engine chart, with the .channels.json sidecar the app writes —
    without that sidecar the dialog cannot know the chart is hexagonal and this
    script would quietly photograph the rectangular path twice."""
    from workflow.layout_engine import chart as le_chart
    folder = work / name
    folder.mkdir(parents=True, exist_ok=True)
    n = 150
    lines = ["CTI1", "", f'DESCRIPTOR "{name}"', 'ORIGINATOR "ChromIQ"',
             'KEYWORD "SAMPLE_LOC"', "NUMBER_OF_FIELDS 7", "BEGIN_DATA_FORMAT",
             "SAMPLE_ID RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z", "END_DATA_FORMAT",
             f"NUMBER_OF_SETS {n}", "BEGIN_DATA"]
    lines += [f"{i+1} {float((i * 37) % 101)} {float((i * 53) % 101)} "
              f"{float((i * 71) % 101)} 40.0 45.0 50.0" for i in range(n)]
    lines += ["END_DATA", ""]
    ti1 = folder / "probe.ti1"
    ti1.write_text("\n".join(lines), encoding="utf-8")
    stem = folder / name
    res = le_chart.build_chart(ti1, stem, instrument="SS", paper="A4",
                               hflag=hexagonal, pscale=w_mm / 7.0, border=6.0,
                               dpi=200, randomize=False)
    strips = json.loads(stem.with_suffix(".strips.json").read_text(encoding="utf-8"))
    patches = [p for p in strips["patches"] if p["page"] == 0]
    (folder / f"{name}.channels.json").write_text(json.dumps({
        "ink_channels": ["r", "g", "b"],
        "layout": {"engine": "chromiq", "engine_version": 1, "dpi": 200,
                   "paper_mm": [210.0, 297.0], "patches": strips["patches"],
                   "recipe": {"instrument": "SS", "hflag": hexagonal}}}), encoding="utf-8")
    pw = sorted(p["w"] for p in patches)[len(patches) // 2]
    ph = sorted(p["h"] for p in patches)[len(patches) // 2]
    print(f"{name}: {res.layout.total_patches} patches, "
          f"stored rect {pw:.2f} x {ph:.2f} px (h/w = {ph / pw:.3f})")
    return stem


def main() -> int:
    W = float(sys.argv[1]) if len(sys.argv) > 1 else 12.0
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    from ui.styles import APP_STYLESHEET
    app.setStyleSheet(APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_hexclamp_"))
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
    work = sandbox / "ChromIQ"
    settings.set("custom_output_path", str(work))
    settings.set("scanner_hex_charts", True)      # the beta opt-in, as a user sets it

    hexstem = build_chart(work, "HexChart", W, True)
    rectstem = build_chart(work, "SquareChart", W, False)

    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.argyll_runner import ArgyllRunner
    from ui.dialogs.scanin_dialog import ScannerProfileDialog
    runner = ArgyllRunner(settings)

    from workflow.scanin_runner import hex_max_sample_fraction
    ok = True
    for label, stem, hexagonal in (("hex", hexstem, True),
                                   ("rect", rectstem, False)):
        dlg = ScannerProfileDialog(runner, settings)
        dlg.resize(1180, 980)
        dlg.show()
        pump(app, 1200)
        dlg._set_chart(stem.with_suffix(".ti2"))
        pump(app, 1500)

        # What a user would do next: reach for the biggest number there is.
        dlg._sample_area.setValue(80)
        pump(app, 400)

        patches = [p for p in (dlg._layout or {}).get("patches", [])
                   if int(p.get("page", 0)) == 0]
        want = 80
        if hexagonal and patches:
            pw = sorted(p["w"] for p in patches)[len(patches) // 2]
            ph = sorted(p["h"] for p in patches)[len(patches) // 2]
            want = int(hex_max_sample_fraction(pw, ph) * 100)
        got_max, got_val = dlg._sample_area.maximum(), dlg._sample_area.value()
        good = got_max == want and got_val == want
        ok &= good
        print(f"{label:5s} hexagonal={hexagonal}  spinbox max={got_max}  "
              f"after asking for 80 -> {got_val}   expected {want}  "
              f"{'OK' if good else 'WRONG'}")
        print(f"      tooltip: {dlg._sample_area.toolTip()[:96] or '(none)'}")

        # Scroll the control into view — it lives below the fold, and a
        # screenshot of the part of the dialog that does not contain it proves
        # nothing at all.
        from PyQt6.QtWidgets import QScrollArea
        area = dlg._sample_area.parentWidget()
        while area is not None and not isinstance(area, QScrollArea):
            area = area.parentWidget()
        if area is not None:
            area.ensureWidgetVisible(dlg._sample_area, 0, 220)
        pump(app, 600)
        dlg.grab().save(str(shots / f"1_{label}_dialog.png"))

        tl = dlg._sa_label.mapTo(dlg, dlg._sa_label.rect().topLeft())
        top, bot = max(0, tl.y() - 44), min(dlg.height(), tl.y() + 60)
        crop = dlg.rect().adjusted(0, top, 0, bot - dlg.height())
        if crop.height() > 10:
            dlg.grab(crop).save(str(shots / f"2_{label}_sample_row.png"))
        dlg.close()
        pump(app, 300)

    print(f"\nshots: {shots}")
    print("VERDICT:", "as designed" if ok else "MISMATCH — see above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
