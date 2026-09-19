#!/usr/bin/env python3
"""Adversary round 30: press every control beta 26 added, in a real window.

Beta 26 shipped three buttons that raised `NameError` on every press and looked
merely inert, past three green gates, because the guard READ THEIR SOURCE.  So
this drives the DOORS, and it carries the detector that would have caught it:

  **A RECORDING `sys.excepthook`.**  Measured by
  `adv30_what_happens_when_a_slot_raises.py`: PyQt6 6.11 does NOT call
  `qFatal()` for an exception in a slot.  It calls `sys.excepthook` and the app
  CARRIES ON.  So every press below is made with a hook that records, and a
  press that raises is a FAULT even when the window looks fine afterwards.

Scenes:
  1. Report limits: the three ISO buttons, end to end -- template written, file
     filled in, installed, read back in a REOPENED window, forgotten.
  2. Report limits: the new info icon -- opened, photographed, and its colour
     read off the widget.
  3. The ISO buttons' HEIGHT, measured off the widgets (Basti asked for 22 px).

Every file dialog is patched at the SPECIFIC helper the slot imports, never
`QDialog.exec`.  Every modal that appears is found on screen and its real
button is clicked.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-r30/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-r30/presets
    python scripts/adv30_press_every_new_control.py <out-dir> [de]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from PyQt6.QtCore import QTimer                                   # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog                 # noqa: E402
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

RAISED: list = []


def install_recorder() -> None:
    prev = sys.excepthook

    def hook(t, e, tb):
        RAISED.append({"type": t.__name__, "msg": str(e),
                       "where": "".join(traceback.format_tb(tb))[-700:]})
        prev(t, e, tb)

    sys.excepthook = hook


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _frames_match(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        if x.shape != y.shape:
            return False
        return bool((np.abs(x - y).sum(axis=2) > tol).sum() == 0)
    except Exception:                                       # noqa: BLE001
        return False


def photo(app, win, out: Path, tag: str) -> dict:
    ok = ok2 = False
    why = ""
    for _ in range(3):
        pump(app, 700)
        ok, why = capture_window(win, out / f"{tag}-1.png")
        pump(app, 700)
        ok2, why2 = capture_window(win, out / f"{tag}-2.png")
        why = why or why2
        if ok and ok2 and _frames_match(out / f"{tag}-1.png", out / f"{tag}-2.png"):
            return {"taken": True, "identical": True, "tag": tag}
    return {"taken": bool(ok and ok2), "identical": False, "why": why, "tag": tag}


def answer_the_modal(app, out: Path, tag: str, result: dict) -> None:
    """Find whatever modal the press opened, photograph it, press its button."""
    state = {"tries": 0}

    def _act():
        if state.get("done"):
            return
        dlg = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, QDialog) and w.isVisible()
                    and w.isModal() and w.objectName() != "thresholds"), None)
        if dlg is None:
            state["tries"] += 1
            if state["tries"] > 24:
                state["done"] = True
                result[tag] = {"appeared": False}
                return
            QTimer.singleShot(250, _act)
            return
        state["done"] = True
        texts = []
        from PyQt6.QtWidgets import QLabel, QPushButton
        for lab in dlg.findChildren(QLabel):
            t = (lab.text() or "").strip()
            if t:
                texts.append(t)
        result[tag] = {"appeared": True, "title": dlg.windowTitle(),
                       "texts": texts[:8],
                       "photo": photo(app, dlg, out, tag)}
        btns = [b for b in dlg.findChildren(QPushButton) if b.isVisible()]
        result[tag]["buttons"] = [b.text().replace("&", "") for b in btns]
        if btns:
            btns[-1].click()
        else:
            dlg.accept()

    QTimer.singleShot(350, _act)


def main() -> int:                                              # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"

    install_recorder()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import SPEC_GREEN, WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("appearance", "light")
    settings.set("language", lang)
    from core import i18n
    i18n.set_language(lang)
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")

    from workflow import compliance_sets as CS
    res: dict = {"lang": lang, "locked_at_start": session_is_locked(),
                 "compliance_dir": str(CS.user_values_path().parent)}
    # the sandbox must own the file we are about to write
    assert "/tmp/chromiq-r30" in res["compliance_dir"], res["compliance_dir"]
    if CS.user_values_path().is_file():
        CS.user_values_path().unlink()
    CS.reset_iso_cache()

    from ui.dialogs.thresholds_dialog import ThresholdsDialog

    def open_window():
        d = ThresholdsDialog(settings, None)
        d.resize(1100, 820)
        d.show(); d.raise_(); d.activateWindow()
        pump(app, 1800)
        return d

    dlg = open_window()
    res["window_visible"] = dlg.isVisible()
    res["photo_open"] = photo(app, dlg, out, f"S0-open-{lang}")

    # ---- the three buttons' geometry, measured off the widgets ----------
    res["button_heights"] = {
        "template": dlg._iso_template_btn.height(),
        "use": dlg._iso_use_btn.height(),
        "forget": dlg._iso_forget_btn.height(),
    }
    res["button_widths"] = {
        "template": dlg._iso_template_btn.width(),
        "use": dlg._iso_use_btn.width(),
        "forget": dlg._iso_forget_btn.width(),
    }
    res["button_texts"] = {
        "template": dlg._iso_template_btn.text(),
        "use": dlg._iso_use_btn.text(),
        "forget": dlg._iso_forget_btn.text(),
    }
    res["forget_enabled_with_no_file"] = dlg._iso_forget_btn.isEnabled()

    # the info icon, found by walking the row the three buttons sit in
    from ui.tooltip_button import TooltipButton
    icons = [w for w in dlg.findChildren(TooltipButton)]
    row_icon = None
    for w in icons:
        if abs(w.y() - dlg._iso_template_btn.y()) < 30 and \
           w.parent() is dlg._iso_template_btn.parent():
            row_icon = w
            break
    res["info_icon"] = {
        "found": row_icon is not None,
        "colour": getattr(row_icon, "_color", None) or getattr(
            row_icon, "color", None) if row_icon is not None else None,
        "spec_green": SPEC_GREEN,
        "size": [row_icon.width(), row_icon.height()] if row_icon else None,
    }
    res["info_icon"]["colour"] = str(res["info_icon"]["colour"])

    # =====================================================================
    # 1. "Save a file to fill in" -- pressed for real
    # =====================================================================
    work = Path(tempfile.mkdtemp(prefix="chromiq-r30-iso-"))
    target = work / "iso12647.json"
    import ui.widgets as W
    saved_save, saved_open = W.save_file_dialog, W.open_file_dialog
    calls: dict = {}

    W.save_file_dialog = lambda *a, **k: (calls.__setitem__("save", k),
                                          str(target))[1]
    answer_the_modal(app, out, "S1-said", res)
    RAISED.clear()
    dlg._iso_template_btn.click()
    pump(app, 3000)
    res["S1_template"] = {
        "raised": list(RAISED),
        "file_written": target.is_file(),
        "bytes": target.stat().st_size if target.is_file() else 0,
        "dialog_kwargs": {k: str(v) for k, v in (calls.get("save") or {}).items()},
    }
    if target.is_file():
        doc = json.loads(target.read_text(encoding="utf-8"))
        res["S1_template"]["sets"] = [k for k in doc if not k.startswith("_")]
        res["S1_template"]["row_count"] = sum(
            len(v) for k, v in doc.items()
            if not k.startswith("_") and isinstance(v, dict))

    # =====================================================================
    # 2. Fill the template in and press "Use a file I filled in"
    # =====================================================================
    if target.is_file():
        doc = json.loads(target.read_text(encoding="utf-8"))
        filled = 0
        for sid, cells in doc.items():
            if sid.startswith("_") or not isinstance(cells, dict):
                continue
            for rid in list(cells):
                cells[rid] = 2.5
                filled += 1
        target.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        res["S2_filled_cells"] = filled

    W.open_file_dialog = lambda *a, **k: (calls.__setitem__("open", k),
                                          str(target))[1]
    answer_the_modal(app, out, "S2-said", res)
    RAISED.clear()
    dlg._iso_use_btn.click()
    pump(app, 3000)
    installed = CS.user_values_path()
    res["S2_use"] = {
        "raised": list(RAISED),
        "installed_at": str(installed),
        "installed": installed.is_file(),
        "iso_data_path_text": CS.iso_data_path_text(),
        "forget_enabled_now": dlg._iso_forget_btn.isEnabled(),
    }

    # =====================================================================
    # 3. DOES A REOPENED WINDOW SHOW THE NUMBERS?  The window's own message
    #    tells the user to close and reopen it, so that promise is measured.
    # =====================================================================
    before_close = photo(app, dlg, out, f"S3-before-close-{lang}")
    dlg.close()
    pump(app, 800)
    RAISED.clear()
    dlg2 = open_window()
    res["S3_reopened"] = {
        "raised": list(RAISED),
        "visible": dlg2.isVisible(),
        "photo": photo(app, dlg2, out, f"S3-reopened-{lang}"),
        "before_close": before_close,
        "forget_enabled": dlg2._iso_forget_btn.isEnabled(),
    }
    # read the table: how many cells in the two ISO columns show a number now
    from PyQt6.QtWidgets import QLabel
    iso_cells = [(w.text() or "").strip() for w in dlg2.findChildren(QLabel)]
    res["S3_reopened"]["labels_with_2_5"] = sum(
        1 for t in iso_cells if t.startswith("2.5") or t == "2.5")
    res["S3_reopened"]["labels_with_question"] = sum(
        1 for t in iso_cells if t.strip() in ("?", "?"))
    res["S3_reopened"]["iso_trouble_shown"] = bool(dlg2._iso_file_trouble())
    res["S3_reopened"]["iso_trouble_text"] = dlg2._iso_file_trouble()[:300]

    # =====================================================================
    # 4. "Stop using it"
    # =====================================================================
    answer_the_modal(app, out, "S4-said", res)
    RAISED.clear()
    dlg2._iso_forget_btn.click()
    pump(app, 3000)
    res["S4_forget"] = {
        "raised": list(RAISED),
        "file_gone": not CS.user_values_path().is_file(),
        "forget_enabled_after": dlg2._iso_forget_btn.isEnabled(),
        "iso_data_path_text": CS.iso_data_path_text(),
    }

    # =====================================================================
    # 5. The info icon, pressed
    # =====================================================================
    if row_icon is not None:
        answer_the_modal(app, out, f"S5-icon-{lang}", res)
        RAISED.clear()
        row_icon.click()
        pump(app, 3000)
        res["S5_icon"] = {"raised": list(RAISED)}

    dlg2.close()
    pump(app, 500)
    res["raised_total"] = RAISED
    (out / f"iso-buttons-{lang}.json").write_text(json.dumps(res, indent=2,
                                                            default=str))
    W.save_file_dialog, W.open_file_dialog = saved_save, saved_open
    print(json.dumps(res, indent=2, default=str)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
