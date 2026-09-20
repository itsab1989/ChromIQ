#!/usr/bin/env python3
"""Adversary round 30: the Reference values window, pressed on screen.

Beta 26 shipped three buttons that raised `NameError` on every press and looked
merely inert, past three green gates, because the guard READ THEIR SOURCE.
Those three buttons became ONE DOOR and THIS WINDOW, uncommitted, in one pass,
hours later.  A brand-new window written in one pass is the same risk again, so
every control in it is pressed here, in a real window, with the detector the
last round lacked:

  **A RECORDING `sys.excepthook`.**  Measured by
  `adv30_what_happens_when_a_slot_raises.py`: PyQt6 6.11 does NOT call
  `qFatal()` for an exception raised in a slot.  It calls `sys.excepthook` and
  the app CARRIES ON, so a press that raises leaves the window looking fine.
  Every press below is made with a hook that records, and a press that raises
  is a fault whatever the window looks like afterwards.

Scenes
  A  the door in Report limits: its height, its text, its state line
  B  Save a file to fill in -- CANCELLED, then for real
  C  Use a file I filled in -- CANCELLED; not JSON; JSON of the WRONG SHAPE;
     then the real thing
  D  Stop using it, and the state line in BOTH windows after each action
  E  the window opened a second time, and after an install
  F  Stop using it while the ENVIRONMENT VARIABLE is what supplies the values
  G  can the two windows disagree about what is in use?

Every modal is the app's real `InfoDialog`, found on screen by a STANDING
watcher that photographs it and clicks its real Close button; never
`QDialog.exec = lambda self: 1`.  The watcher logs every box it closed, so a
scene that must raise NO box is measured by an empty delta rather than by hope.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-r30/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-r30/presets
    python scripts/adv30_the_reference_values_window.py <out-dir> [en|de] [width]
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
from PyQt6.QtWidgets import (QApplication, QDialog, QLabel,       # noqa: E402
                             QPushButton)
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

RAISED: list = []
BOXES: list = []
OUT = Path(".")
WANT_PHOTO: dict = {"tag": None}


def install_recorder() -> None:
    prev = sys.excepthook

    def hook(t, e, tb):
        RAISED.append({"type": t.__name__, "msg": str(e),
                       "tb": "".join(traceback.format_tb(tb))[-600:]})
        prev(t, e, tb)

    sys.excepthook = hook


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _same(a: Path, b: Path, tol: int = 8) -> bool:
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        return x.shape == y.shape and bool((np.abs(x - y).sum(2) > tol).sum() == 0)
    except Exception:                                       # noqa: BLE001
        return False


def photo(app, win, tag: str) -> dict:
    ok = ok2 = False
    why = ""
    for _ in range(3):
        pump(app, 650)
        ok, why = capture_window(win, OUT / f"{tag}-1.png")
        pump(app, 650)
        ok2, why2 = capture_window(win, OUT / f"{tag}-2.png")
        why = why or why2
        if ok and ok2 and _same(OUT / f"{tag}-1.png", OUT / f"{tag}-2.png"):
            return {"taken": True, "identical": True}
    return {"taken": bool(ok and ok2), "identical": False, "why": why}


class BoxWatcher:
    """Standing watcher: close every InfoDialog that appears, and say what it
    said. A one-shot handler hung the previous driver for nine minutes inside
    `QDialog::exec`; this cannot, and its log is the evidence for a scene that
    must raise NO box at all."""

    def __init__(self, app):
        self.app = app
        self.t = QTimer()
        self.t.setInterval(140)
        self.t.timeout.connect(self.tick)
        self.t.start()

    def tick(self) -> None:
        from ui.tooltip_button import InfoDialog
        box = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, InfoDialog) and w.isVisible()), None)
        if box is None:
            return
        texts = [(l.text() or "").strip() for l in box.findChildren(QLabel)]
        rec = {"title": box.windowTitle(),
               "texts": [t for t in texts if t][:6]}
        tag = WANT_PHOTO.get("tag")
        if tag:
            WANT_PHOTO["tag"] = None
            rec["photo"] = photo(self.app, box, tag)
        for b in box.findChildren(QPushButton):
            if b.isVisible():
                b.click()
                break
        else:
            box.accept()
        BOXES.append(rec)

    def stop(self) -> None:
        self.t.stop()
        self.t.timeout.disconnect()


def boxes_since(n: int) -> list:
    return BOXES[n:]


def main() -> int:                                              # noqa: C901
    global OUT
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    OUT = Path(sys.argv[1]).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1240

    install_recorder()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
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
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    import ui.widgets as W

    comp = CS.user_values_path()
    assert "/tmp/chromiq-r30" in str(comp), str(comp)
    if comp.is_file():
        comp.unlink()
    CS.reset_iso_cache()

    res: dict = {"lang": lang, "width": width,
                 "locked_at_start": session_is_locked(),
                 "compliance_file": str(comp)}
    watcher = BoxWatcher(app)
    work = Path(tempfile.mkdtemp(prefix="chromiq-r30-rv-"))

    saved_save, saved_open = W.save_file_dialog, W.open_file_dialog
    answer: dict = {"save": "", "open": "", "save_kw": {}, "open_kw": {}}
    W.save_file_dialog = lambda *a, **k: (answer.__setitem__("save_kw", k),
                                          answer["save"])[1]
    W.open_file_dialog = lambda *a, **k: (answer.__setitem__("open_kw", k),
                                          answer["open"])[1]

    def open_rv(tag):
        d = ReferenceValuesDialog(None)
        d.resize(width, d.sizeHint().height())
        d.show(); d.raise_(); d.activateWindow()
        pump(app, 1400)
        return d

    def state_of(d):
        return [lbl.text() for _s, lbl, _f in d._rows]

    def forget_enabled(d):
        return [f.isEnabled() for _s, _l, f in d._rows]

    # =====================================================================
    # A. THE DOOR in Report limits
    # =====================================================================
    th = ThresholdsDialog(settings, None)
    th.resize(width, 820)
    th.show(); th.raise_(); th.activateWindow()
    pump(app, 1800)
    res["A_door"] = {
        "window_visible": th.isVisible(),
        "button_text": th._iso_values_btn.text(),
        "button_height": th._iso_values_btn.height(),
        "button_width": th._iso_values_btn.width(),
        "button_hint_w": th._iso_values_btn.sizeHint().width(),
        "text_fits": th._iso_values_btn.width() >= th._iso_values_btn.sizeHint().width(),
        "state_line": th._iso_state_lbl.text(),
        "state_w": th._iso_state_lbl.width(),
        "state_hint_w": th._iso_state_lbl.sizeHint().width(),
        "state_elided": th._iso_state_lbl.width() < th._iso_state_lbl.sizeHint().width(),
        "trouble_panel": th._iso_file_trouble(),
        "photo": photo(app, th, f"A-report-limits-{lang}-{width}"),
    }

    rv = open_rv("B")
    res["B_open"] = {
        "visible": rv.isVisible(),
        "title": rv.windowTitle(),
        "sections": len(rv._rows),
        "state": state_of(rv),
        "forget_enabled_with_nothing_supplied": forget_enabled(rv),
        "button_heights": [b.height() for b in rv.findChildren(QPushButton)],
        "button_texts": [b.text() for b in rv.findChildren(QPushButton)],
        "size": [rv.width(), rv.height()],
        "raised": list(RAISED),
        "photo": photo(app, rv, f"B-reference-values-{lang}-{width}"),
    }

    # =====================================================================
    # B. Save a file to fill in -- CANCELLED
    # =====================================================================
    n = len(BOXES); RAISED.clear()
    answer["save"] = ""
    rv.findChildren(QPushButton)[0].click()
    pump(app, 1600)
    res["B_template_cancelled"] = {
        "raised": list(RAISED), "boxes": boxes_since(n),
        "must_be_silent": len(boxes_since(n)) == 0,
        "dialog_kwargs": {k: str(v) for k, v in answer["save_kw"].items()},
    }

    # ... and for real
    target = work / "iso12647.json"
    n = len(BOXES); RAISED.clear()
    answer["save"] = str(target)
    WANT_PHOTO["tag"] = f"B-template-said-{lang}"
    rv.findChildren(QPushButton)[0].click()
    pump(app, 2400)
    res["B_template"] = {
        "raised": list(RAISED), "boxes": boxes_since(n),
        "file_written": target.is_file(),
        "bytes": target.stat().st_size if target.is_file() else 0,
        "dialog_kwargs": {k: str(v) for k, v in answer["save_kw"].items()},
        "state_after": state_of(rv),
    }

    # =====================================================================
    # C. Use a file I filled in
    # =====================================================================
    use_btn = rv.findChildren(QPushButton)[1]
    n = len(BOXES); RAISED.clear()
    answer["open"] = ""
    use_btn.click(); pump(app, 1600)
    res["C_use_cancelled"] = {
        "raised": list(RAISED), "boxes": boxes_since(n),
        "must_be_silent": len(boxes_since(n)) == 0,
        "installed": comp.is_file(),
        "dialog_kwargs": {k: str(v) for k, v in answer["open_kw"].items()},
    }

    bad = work / "not-json.json"
    bad.write_text("{ this is not json,,, }", encoding="utf-8")
    n = len(BOXES); RAISED.clear()
    answer["open"] = str(bad)
    WANT_PHOTO["tag"] = f"C-not-json-{lang}"
    use_btn.click(); pump(app, 2400)
    res["C_not_json"] = {
        "raised": list(RAISED), "boxes": boxes_since(n),
        "installed": comp.is_file(), "state": state_of(rv),
    }

    # JSON THAT PARSES, WRONG SHAPE -- two of them, and the second is the one
    # a user is most likely to make: ChromIQ's OWN meta.json cell shape.
    shape1 = work / "a-list.json"
    shape1.write_text("[1, 2, 3]", encoding="utf-8")
    n = len(BOXES); RAISED.clear()
    answer["open"] = str(shape1)
    WANT_PHOTO["tag"] = f"C-wrong-shape-list-{lang}"
    use_btn.click(); pump(app, 2400)
    res["C_wrong_shape_list"] = {
        "raised": list(RAISED), "boxes": boxes_since(n),
        "installed": comp.is_file(),
        "state_in_this_window": state_of(rv),
        "iso_problems": CS.iso_problems() if hasattr(CS, "iso_problems") else "n/a",
    }

    if target.is_file():
        doc = json.loads(target.read_text(encoding="utf-8"))
        shaped = {}
        cells = 0
        for sid, v in doc.items():
            if sid.startswith("_") or not isinstance(v, dict):
                shaped[sid] = v
                continue
            shaped[sid] = {rid: {"kind": "value", "number": 2.5} for rid in v}
            cells += len(v)
        shape2 = work / "meta-shape.json"
        shape2.write_text(json.dumps(shaped, indent=2), encoding="utf-8")
        n = len(BOXES); RAISED.clear()
        answer["open"] = str(shape2)
        WANT_PHOTO["tag"] = f"C-wrong-shape-meta-{lang}"
        use_btn.click(); pump(app, 2400)
        res["C_wrong_shape_meta"] = {
            "cells": cells,
            "raised": list(RAISED), "boxes": boxes_since(n),
            "installed": comp.is_file(),
            "state_in_this_window": state_of(rv),
            "report_limits_state_line_now": th._iso_state_lbl.text(),
            "report_limits_trouble_panel_now": th._iso_file_trouble()[:400],
            "photo": photo(app, rv, f"C-after-wrong-shape-{lang}"),
        }

    # the properly filled file
    if target.is_file():
        doc = json.loads(target.read_text(encoding="utf-8"))
        filled = 0
        for sid, v in doc.items():
            if sid.startswith("_") or not isinstance(v, dict):
                continue
            for rid in list(v):
                v[rid] = 2.5
                filled += 1
        good = work / "filled.json"
        good.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        n = len(BOXES); RAISED.clear()
        answer["open"] = str(good)
        WANT_PHOTO["tag"] = f"C-good-said-{lang}"
        use_btn.click(); pump(app, 2400)
        res["C_good"] = {
            "filled_cells": filled,
            "raised": list(RAISED), "boxes": boxes_since(n),
            "installed": comp.is_file(),
            "state": state_of(rv),
            "forget_enabled": forget_enabled(rv),
            "iso_data_path_text": CS.iso_data_path_text(),
            "photo": photo(app, rv, f"C-good-{lang}"),
        }

    # =====================================================================
    # G. DO THE TWO WINDOWS AGREE?  The Report limits window is still open
    #    and was never told.  Its state line only re-reads when its own door
    #    closes, so this is what a reader actually sees.
    # =====================================================================
    res["G_disagreement"] = {
        "reference_values_says": state_of(rv),
        "report_limits_state_line": th._iso_state_lbl.text(),
        "report_limits_trouble_panel": th._iso_file_trouble()[:300],
        "note": "the Report limits window here was opened BEFORE the install "
                "and has not been through _on_reference_values",
    }

    # =====================================================================
    # E. OPEN THE WINDOW A SECOND TIME, with a file installed
    # =====================================================================
    rv.close(); pump(app, 700)
    RAISED.clear()
    rv2 = open_rv("E")
    res["E_second_open"] = {
        "raised": list(RAISED),
        "state": state_of(rv2),
        "forget_enabled": forget_enabled(rv2),
        "photo": photo(app, rv2, f"E-second-open-{lang}"),
    }

    # =====================================================================
    # D. Stop using it
    # =====================================================================
    forget_btn = rv2.findChildren(QPushButton)[2]
    n = len(BOXES); RAISED.clear()
    WANT_PHOTO["tag"] = f"D-forget-said-{lang}"
    forget_btn.click(); pump(app, 2400)
    res["D_forget"] = {
        "raised": list(RAISED), "boxes": boxes_since(n),
        "file_gone": not comp.is_file(),
        "state": state_of(rv2),
        "forget_enabled_after": forget_enabled(rv2),
        "iso_data_path_text": CS.iso_data_path_text(),
    }
    # pressing it again, with nothing installed -- the button should be dead
    n = len(BOXES); RAISED.clear()
    forget_btn.click(); pump(app, 1400)
    res["D_forget_again"] = {
        "button_enabled": forget_btn.isEnabled(),
        "raised": list(RAISED), "boxes": boxes_since(n),
    }
    rv2.close(); pump(app, 500)

    # =====================================================================
    # F. THE ENVIRONMENT VARIABLE.  `iso_data_path_text` returns the env path,
    #    so the state line says "in use" and Forget is ENABLED -- but
    #    `forget_user_values` only ever removes ChromIQ's OWN copy. Measure
    #    what the press does.
    # =====================================================================
    envfile = work / "env-values.json"
    envfile.write_text(json.dumps({"iso12647_7": {}}), encoding="utf-8")
    os.environ[CS.ISO_DATA_ENV] = str(envfile)
    CS.reset_iso_cache()
    RAISED.clear()
    rv3 = open_rv("F")
    fb = rv3.findChildren(QPushButton)[2]
    n = len(BOXES)
    before = state_of(rv3)
    fb.click(); pump(app, 2200)
    res["F_env_var"] = {
        "env": CS.ISO_DATA_ENV, "env_path": str(envfile),
        "state_before": before,
        "forget_enabled": fb.isEnabled(),
        "raised": list(RAISED),
        "boxes_after_press": boxes_since(n),
        "state_after": state_of(rv3),
        "env_file_still_there": envfile.is_file(),
        "anything_happened": bool(boxes_since(n)) or before != state_of(rv3),
        "photo": photo(app, rv3, f"F-env-var-{lang}"),
    }
    rv3.close(); pump(app, 400)
    os.environ.pop(CS.ISO_DATA_ENV, None)
    CS.reset_iso_cache()

    th.close(); pump(app, 400)
    watcher.stop()
    res["raised_total"] = RAISED
    res["boxes_total"] = len(BOXES)
    W.save_file_dialog, W.open_file_dialog = saved_save, saved_open
    (OUT / f"reference-values-{lang}-{width}.json").write_text(
        json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
