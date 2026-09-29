#!/usr/bin/env python3
"""Adversary 23d — the Report type and Judged against help, read on screen.

Opens the real Measurement Report window, clicks the two ⓘ buttons, photographs
the popups, and then checks the help's own claims against what the SAME window
offers: which types are greyed, what the line under the pulldown says, which
rows each type keeps, and which sets exist.

Run once per language.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,            # noqa: E402
                             QMessageBox, QLabel)
from onscreen_capture import capture_window                    # noqa: E402


def pump(app, ms=250):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def plain(html):
    return " ".join(re.sub("<[^>]+>", " ", html or "").split())


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("QT_QPA_PLATFORM") != "offscreen", "ON SCREEN ONLY"
    lang = sys.argv[1]
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv23d-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("language", lang)
    from core import i18n
    i18n.set_language(lang)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    QDialog.exec = lambda self: 1                 # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.theme import apply_appearance
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    apply_appearance(app, None, "dark")

    # A REAL project with real verifications, from the suite's own demo cache.
    cache = Path(os.environ["CHROMIQ_DEMO_SRC"])
    shutil.copytree(cache, work / cache.name, dirs_exist_ok=True)
    ti3s = sorted((work / cache.name).glob("runs/*/verifications/*/*.ti3"))
    assert ti3s, "no verification measurement staged"
    from core.file_manager import FileManager
    fm = FileManager(settings)
    fm.set_target_name(cache.name)

    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3s[0])
    dlg.resize(1500, 1000)
    dlg.show()
    dlg.raise_()
    pump(app, 1800)
    rec = {"language": lang, "window_on_screen": dlg.isVisible()}
    print(f"[{lang}] window on screen:", dlg.isVisible(), flush=True)

    # --- the pulldown as the window really offers it
    combo = dlg._type_combo
    model = combo.model()
    types = []
    for i in range(combo.count()):
        it = model.item(i)
        types.append({"text": combo.itemText(i),
                      "data": combo.itemData(i),
                      "enabled": (bool(it.flags()
                                       & Qt.ItemFlag.ItemIsEnabled)
                                  if it else None),
                      "tooltip": combo.itemData(i, 3) or (it.toolTip() if it
                                                          else "")})
    rec["types"] = types
    print(f"[{lang}] pulldown:", json.dumps(
        [(t["text"], t["enabled"]) for t in types], ensure_ascii=False),
        flush=True)

    # --- the line under the pulldown for a greyed entry
    greyed = [t for t in types if t["data"] and not t["enabled"]]
    rec["greyed_line"] = {}
    for t in greyed:
        idx = [combo.itemData(n) for n in range(combo.count())].index(t["data"])
        try:
            dlg._show_type_blurb(t["data"])
        except Exception:                                    # noqa: BLE001
            pass
        try:
            combo.setCurrentIndex(idx)
        except Exception:                                    # noqa: BLE001
            pass
        pump(app, 250)
        rec["greyed_line"][t["text"]] = {
            "blurb": dlg._type_blurb.text(),
            "blurb_tooltip": dlg._type_blurb.toolTip(),
            "combo_settled_on": combo.currentText(),
        }
    print(f"[{lang}] greyed:", json.dumps(rec["greyed_line"],
                                          ensure_ascii=False)[:400], flush=True)

    # --- the two help buttons, on screen
    from ui.tooltip_button import TooltipButton, _InfoDialog
    btns = dlg.findChildren(TooltipButton)
    rec["tooltip_buttons"] = len(btns)
    texts = []
    for n, b in enumerate(btns):
        texts.append(str(b.dialog_body()))
    rec["help_texts"] = texts
    # photograph the two that carry the new paragraphs
    shots = 0
    # THE TWO THE CHANGE SET TOUCHED, found by the paragraph it appended and
    # not by length: the window's own "What this tool does" help is longer.
    from ui.dialogs.measurement_report_dialog import _PAIRING_HELP
    from core.i18n import tr as _tr
    _key = _tr(_PAIRING_HELP)[:40]
    order = [i for i, t in enumerate(texts) if _key in t]
    for n in order:
        b = btns[n]
        body = texts[n]
        # `QDialog.exec` is neutered so nothing blocks, so the SAME dialog
        # the click builds is built here and SHOWN instead.
        pop = _InfoDialog(b._title, b.dialog_body(), dlg, b._min_width)
        pop.show()
        pop.raise_()
        pump(app, 1200)
        ok, why = capture_window(pop, out / f"D-{lang}-help-{n}.png")
        shots += 1
        print(f"[{lang}] help {n}: photographed {ok} {why} "
              f"({len(body)} chars)", flush=True)
        pop.close()
        pump(app, 400)

    # --- the sets the window really offers, and what each type does with them
    setc = getattr(dlg, "_set_combo", None)
    if setc is not None:
        rec["sets"] = [(setc.itemText(i), setc.itemData(i))
                       for i in range(setc.count())]
    runs = dlg._runs_for_report()
    rec["claims"] = {}
    if runs and setc is not None:
        r0 = runs[0]
        tids = [combo.itemData(n) for n in range(combo.count())]
        for ti in range(combo.count()):
            tid = combo.itemData(ti)
            if not tid or not model.item(ti) or not (
                    model.item(ti).flags() & Qt.ItemFlag.ItemIsEnabled):
                continue
            combo.setCurrentIndex(ti)
            pump(app, 200)
            per_set = {}
            for si in range(setc.count()):
                setc.setCurrentIndex(si)
                pump(app, 200)
                rows, _rec = dlg._verdict_rows(r0)
                per_set[setc.itemText(si)] = {
                    "set_combo_enabled": setc.isEnabled(),
                    "words": {(x.get("row_id") or x.get("key")): x.get("word")
                              for x in rows},
                    "note": dlg._mismatch_text(),
                }
            rec["claims"][combo.itemText(ti)] = per_set
    (out / f"adv23d-{lang}.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
    ok, why = capture_window(dlg, out / f"D-{lang}-window.png")
    print(f"[{lang}] window photographed: {ok} {why}", flush=True)
    dlg.close()
    pump(app, 300)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
