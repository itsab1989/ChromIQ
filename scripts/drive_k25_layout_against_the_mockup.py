#!/usr/bin/env python3
"""Knut's beta-25 mockup, measured, and the real window measured beside it.

Opens the Measurement Report on his own demo project in a REAL window, reads
every control's rectangle, and writes them next to the positions read off
`mockup-report-window-layout.png` so the two can be compared row by row. Also
stamps the measurements onto a copy of the mockup.

    CHROMIQ_SETTINGS_FILE=… CHROMIQ_PRESETS_DIR=… \\
        python scripts/drive_k25_layout_against_the_mockup.py <project> <out>
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
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

#: read off `~/Desktop/ChromIQ-knut-beta25-batch/mockup-report-window-layout.png`
#: (2324 x 2698, a 2x picture of a 1162 px window) with the crop measured at
#: 0.6885 x / 0.6897 y. Logical px from the window's left/top edge.
MOCKUP = {
    "intro":          (22, 144),
    "saved_label":    (22, 177),
    "saved_combo":    (165, 177),
    "saved_help":     (753, 177),
    "already":        (165, 211),
    "settings_box":   (22, 237),
    "add_btn":        (37, 275),
    "list_label":     (37, 310),
    "profile_list":   (37, 330),
    "type_label":     (37, 409),
    "type_combo":     (188, 409),
    "judged_label":   (37, 460),
    "set_combo":      (188, 460),
    "limits_btn":     (508, 460),
    "generate_btn":   (22, 520),
}


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        if x.shape != y.shape:
            return False
        return bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                      # noqa: BLE001
        return False


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def capture_settled(app, win, first: Path, second: Path, tries: int = 4):
    ok = ok2 = False
    why = ""
    for n in range(1, tries + 1):
        pump(app, 800)
        ok, why = capture_window(win, first)
        pump(app, 800)
        ok2, why2 = capture_window(win, second)
        why = why or why2
        if ok and ok2 and _frames_match(first, second):
            return True, why, n, True
    return bool(ok and ok2), why, tries, False


def main() -> int:                                          # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-k25d-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "light")
    settings.set("language", "en")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    fm = FileManager(settings); del fm

    ti3 = sorted((dest / "runs" / "run1" / "verifications"
                  / "2026-11-16_100000").glob("*.ti3"))[0]
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    # HIS MOCKUP IS A 1162 px WINDOW. Measured at the same width, so the two
    # sets of numbers are comparable without scaling.
    dlg.resize(1162, 1040)
    dlg.show(); dlg.raise_(); dlg.activateWindow()
    pump(app, 3000)
    print(f"    window on screen: {dlg.isVisible()}  "
          f"{dlg.width()}x{dlg.height()}", flush=True)

    names = {
        "intro": None, "saved_label": dlg._saved_label,
        "saved_combo": dlg._saved_combo, "saved_help": dlg._saved_help,
        "already": dlg._type_blurb, "settings_box": dlg._settings_box,
        "add_btn": dlg._add_btn, "list_label": dlg._list_label,
        "profile_list": dlg._profile_list, "type_label": dlg._type_label,
        "type_combo": dlg._type_combo, "judged_label": dlg._judged_label,
        "set_combo": dlg._set_combo, "limits_btn": dlg._limits_btn,
        "generate_btn": dlg._generate_btn,
    }
    rows = []
    for key, w in names.items():
        if w is None:
            continue
        p = w.mapTo(dlg, w.rect().topLeft())
        mx, my = MOCKUP[key]
        rows.append({"element": key, "mockup": [mx, my],
                     "window": [p.x(), p.y()],
                     "dx": p.x() - mx, "dy": p.y() - my,
                     "size": [w.width(), w.height()]})
        print(f"      {key:15s} mockup=({mx:4d},{my:4d})  "
              f"window=({p.x():4d},{p.y():4d})  dx={p.x()-mx:+4d} "
              f"dy={p.y()-my:+4d}", flush=True)

    res = {"window": [dlg.width(), dlg.height()], "rows": rows}
    ok, why, tries, same = capture_settled(
        app, dlg, out / "L-at-mockup-width-1.png",
        out / "L-at-mockup-width-2.png")
    print(f"    photograph: {ok} {why}; identical: {same}/{tries}", flush=True)
    res["photo"] = {"taken": ok, "why": why, "identical": same}
    json.dump(res, (out / "layout.json").open("w", encoding="utf-8"), indent=2)

    # --- stamp the measurements onto a copy of his mockup ------------------
    try:
        from PIL import Image, ImageDraw
        mk = Path(os.path.expanduser(
            "~/Desktop/ChromIQ-knut-beta25-batch/mockup-report-window-layout.png"))
        im = Image.open(mk).convert("RGB")
        d = ImageDraw.Draw(im)
        for r in rows:
            mx, my = r["mockup"]
            x, y = mx * 2, my * 2                 # his image is 2x
            d.line([(x - 26, y), (x + 26, y)], fill=(220, 0, 120), width=3)
            d.line([(x, y - 26), (x, y + 26)], fill=(220, 0, 120), width=3)
            d.text((x + 32, y - 22),
                   f"{r['element']} ({mx},{my}) -> ({r['window'][0]},"
                   f"{r['window'][1]})  d=({r['dx']:+d},{r['dy']:+d})",
                   fill=(180, 0, 90))
        im.save(out / "mockup-with-measurements.png")
        print("    wrote mockup-with-measurements.png", flush=True)
    except Exception as exc:                               # noqa: BLE001
        print(f"    could not annotate the mockup: {exc}", flush=True)

    dlg.close()
    pump(app, 400)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                      # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
