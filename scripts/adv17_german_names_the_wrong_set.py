#!/usr/bin/env python3
"""Adversary 17: the German help sends a German reader to a set that is not there.

The German pairing paragraph says *"Die beiden ISO-Typen gehören zum passenden
Custom-ISO-Satz"*. The German "Judged against" pulldown does not offer any
"Custom ISO": `data/i18n/de.json` translates the two sets as
"Eigene ISO 12647-7" and "Eigene ISO 12647-8".

This opens the REAL Measurement Report window with the UI language set to
German, photographs the "Judged against" pulldown open, and lists every item in
it beside what the help tells the reader to look for.
"""
from __future__ import annotations

import json
import os
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
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PROJECT = "Report-Limits-Custom-Columns"      # its run is on a Custom ISO set


def pump(app, ms=250):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv17de-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", "de")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    # THE LANGUAGE IS LOADED ONCE AT STARTUP, so load it here the same way.
    from core import i18n
    i18n.set_language("de")
    from core.i18n import tr
    assert tr("Report limits") == "Berichtsgrenzwerte", tr("Report limits")

    QDialog.exec = lambda self: 1                 # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from ui.theme import apply_appearance
    from ui.dialogs.measurement_report_dialog import (MeasurementReportDialog,
                                                      _PAIRING_HELP)
    from ui.tooltip_button import TooltipButton, _InfoDialog
    apply_appearance(app, None, "dark")

    shutil.copytree(pack / PROJECT, work / PROJECT)
    fm = FileManager(settings)
    fm.set_target_name(PROJECT)
    ti3 = sorted((work / PROJECT).glob("runs/*/verifications/*/*.ti3"))[0]

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3)
    dlg.resize(1500, 1000)
    dlg.show()
    dlg.raise_()
    pump(app, 2500)
    print(f"    window on screen: {dlg.isVisible()}", flush=True)

    combo = getattr(dlg, "_set_combo", None) or getattr(dlg, "_limits_combo", None)
    if combo is None:
        # find the pulldown that holds the set names
        from PyQt6.QtWidgets import QComboBox
        for c in dlg.findChildren(QComboBox):
            items = [c.itemText(i) for i in range(c.count())]
            if any("ISO 12647-7" in t for t in items):
                combo = c
                break
    items = [combo.itemText(i) for i in range(combo.count())] if combo else []
    print("    Judged against items:", items, flush=True)

    ok, why = capture_window(dlg, out / "01-de-report-window.png")
    print(f"    photo window: {'ok' if ok else 'REFUSED ' + str(why)}", flush=True)
    if combo is not None:
        combo.showPopup()
        pump(app, 1200)
        ok2, why2 = capture_window(dlg, out / "02-de-judged-against-open.png")
        print(f"    photo popup: {'ok' if ok2 else 'REFUSED ' + str(why2)}",
              flush=True)
        combo.hidePopup()
        pump(app, 300)

    # the German help, as the window builds it
    body_de = ""
    for btn in dlg.findChildren(TooltipButton):
        if btn._title == tr("Judged against"):
            body_de = btn._body
            d = _InfoDialog(btn._title, btn._body, dlg, btn._min_width)
            d.resize(max(560, btn._min_width + 120), 900)
            d.show(); d.raise_(); pump(app, 1200)
            ok3, why3 = capture_window(d, out / "03-de-help-judged-against.png")
            print(f"    photo help: {'ok' if ok3 else 'REFUSED ' + str(why3)}",
                  flush=True)
            d.close(); pump(app, 250)
            break

    facts = {
        "ui language": settings.get("language", ""),
        "Judged against pulldown items": items,
        "the pulldown offers a 'Custom ISO'":
            any("Custom ISO" in t for t in items),
        "the pulldown offers 'Eigene ISO'":
            any("Eigene ISO" in t for t in items),
        "the German help says 'Custom-ISO'": "Custom-ISO" in body_de,
        "the German help says 'Eigene ISO'": "Eigene ISO" in body_de,
        "German set label for 12647-7": tr("Custom ISO 12647-7"),
        "German set label for 12647-8": tr("Custom ISO 12647-8"),
        "help sentence": [s for s in body_de.split(". ")
                          if "ISO" in s][:4],
        "screen locked at start": session_is_locked(),
    }
    (out / "german-names-the-wrong-set.json").write_text(
        json.dumps(facts, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(facts, indent=2, ensure_ascii=False))
    dlg.close(); pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
