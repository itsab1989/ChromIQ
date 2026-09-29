#!/usr/bin/env python3
"""Adversary round 29: the re-laid-out Measurement Report window in GERMAN.

B8-460 claims the re-layout made the window's minimum width go DOWN, measured
at 1000 / 1200 / 1500 px.  Every one of those numbers was read off the ENGLISH
build, where "Generate report" is 16 characters and "Bericht erzeugen" is not
the widest thing in that new row of four buttons.

This opens the REAL window in both languages, at the same three widths, and
reads:

  * `minimumSizeHint().width()` of the window, which is the claim;
  * every button and label of the new "Report settings" group: its actual
    width against the width its own text wants, so a label that has been
    squeezed says so instead of being elided quietly;
  * whether any control is painted outside the group box that owns it.

Photographs the German window at the narrowest width, twice, through
`onscreen_capture.capture_window`.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-r29/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-r29/presets
    python scripts/adv29_the_german_window.py <project> <out>
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
from PyQt6.QtWidgets import QApplication                         # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402


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


def squeeze(dlg) -> list:
    """Every named control of the new layout: how wide it is, how wide it wants
    to be, and whether it is painted outside the box that owns it."""
    rows = []
    names = ["_saved_label", "_saved_combo", "_saved_help", "_type_blurb",
             "_settings_box", "_add_btn", "_list_label", "_profile_list",
             "_type_label", "_type_combo", "_judged_label", "_set_combo",
             "_limits_btn", "_generate_btn", "_delete_report_btn", "_pdf_btn",
             "_reveal_btn"]
    box = getattr(dlg, "_settings_box", None)
    for n in names:
        w = getattr(dlg, n, None)
        if w is None:
            continue
        want = w.sizeHint().width()
        have = w.width()
        p = w.mapTo(dlg, w.rect().topLeft())
        outside = ""
        if box is not None and w is not box and box.isAncestorOf(w):
            bp = box.mapTo(dlg, box.rect().topLeft())
            if p.x() < bp.x() or p.x() + have > bp.x() + box.width():
                outside = f"outside the group box ({bp.x()}..{bp.x()+box.width()})"
        rows.append({"name": n, "text": (w.text().replace("&", "")
                                         if hasattr(w, "text") else ""),
                     "have": have, "want": want,
                     "short_by": max(0, want - have),
                     "at": [p.x(), p.y()], "note": outside})
    return rows


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-r29-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "light")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    dest = work / src.name
    shutil.copytree(src, dest)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)

    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")
    from core.file_manager import FileManager
    fm = FileManager(settings); del fm

    ti3 = sorted((dest / "runs" / "run1" / "verifications"
                  / "2026-11-16_100000").glob("*.ti3"))[0]

    res: dict = {"project": str(src), "locked_at_start": session_is_locked(),
                 "languages": {}}
    for lang in ("en", "de"):
        settings.set("language", lang)
        import core.i18n as I
        I.set_language(lang)
        import importlib
        import ui.dialogs.measurement_report_dialog as MRD
        importlib.reload(MRD)
        per = {}
        for width in (1000, 1200, 1500):
            dlg = MRD.MeasurementReportDialog(settings, None, initial_ti3=ti3)
            dlg.resize(width, 900)
            dlg.show(); dlg.raise_()
            pump(app, 2500)
            mw = dlg.minimumSizeHint().width()
            rows = squeeze(dlg)
            per[str(width)] = {
                "minimum_width": mw,
                "actual_width": dlg.width(),
                "generate_text": dlg._generate_btn.text().replace("&", ""),
                "squeezed": [r for r in rows if r["short_by"] > 0],
                "outside": [r for r in rows if r["note"]],
                "all": rows,
            }
            print(f"  {lang} @{width}: minimum={mw}  actual={dlg.width()}  "
                  f"squeezed={[ (r['name'], r['short_by']) for r in rows if r['short_by']>0 ]}",
                  flush=True)
            if width == 1000:
                ok, why, tries, same = capture_settled(
                    app, dlg, out / f"{lang}-1000-1.png",
                    out / f"{lang}-1000-2.png")
                per[str(width)]["photo"] = {"taken": ok, "why": why,
                                            "identical": same}
                print(f"      photograph: {ok} {why}; identical: {same}/{tries}",
                      flush=True)
            dlg.close()
            pump(app, 500)
        res["languages"][lang] = per

    res["locked_at_end"] = session_is_locked()
    (out / "result.json").write_text(json.dumps(res, indent=2, default=str),
                                     encoding="utf-8")
    print(f"    wrote {out / 'result.json'}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:                                      # noqa: BLE001
        traceback.print_exc()
        raise SystemExit(2)
