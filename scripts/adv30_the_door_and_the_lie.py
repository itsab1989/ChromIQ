#!/usr/bin/env python3
"""Adversary round 30: through the REAL door, and what the grey line then says.

`adv30_the_reference_values_window.py` drove the new window directly. This
drives the route a person takes: Report limits -> "Reference values…" -> supply
a file -> Close -> read the grey line the door now carries. That line is the
ONLY thing in the Report limits window that says which numbers are in force,
and it is written by `_sync_iso_buttons`, which asks
`iso_data_path_text()` -- "is there a file?" -- and not "could it be read?".

Also measures, in whichever language is asked for:
  * the door's text against its own width, and the grey line against its own
  * the new window at a 1000 px main window, which is the size Basti works at
  * the state line in both windows at every step

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-r30/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-r30/presets
    python scripts/adv30_the_door_and_the_lie.py <out> [en|de] [width]
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
from PyQt6.QtWidgets import (QApplication, QLabel,                # noqa: E402
                             QPushButton)
from onscreen_capture import capture_window, session_is_locked    # noqa: E402

RAISED: list = []
BOXES: list = []
OUT = Path(".")
WANT: dict = {"tag": None}


def rec_hook() -> None:
    prev = sys.excepthook

    def hook(t, e, tb):
        RAISED.append({"type": t.__name__, "msg": str(e),
                       "tb": "".join(traceback.format_tb(tb))[-500:]})
        prev(t, e, tb)
    sys.excepthook = hook


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _same(a, b, tol=8):
    try:
        import numpy as np
        from PIL import Image
        x = np.asarray(Image.open(a).convert("RGB")).astype(int)
        y = np.asarray(Image.open(b).convert("RGB")).astype(int)
        return x.shape == y.shape and bool((np.abs(x - y).sum(2) > tol).sum() == 0)
    except Exception:                                       # noqa: BLE001
        return False


def photo(app, win, tag):
    for _ in range(3):
        pump(app, 650)
        ok, why = capture_window(win, OUT / f"{tag}-1.png")
        pump(app, 650)
        ok2, why2 = capture_window(win, OUT / f"{tag}-2.png")
        if ok and ok2 and _same(OUT / f"{tag}-1.png", OUT / f"{tag}-2.png"):
            return {"taken": True, "identical": True}
    return {"taken": False, "identical": False, "why": why or why2}


class Boxes:
    """Standing watcher for the app's own InfoDialog."""

    def __init__(self, app):
        self.app = app
        self.busy = False
        self.t = QTimer(); self.t.setInterval(140)
        self.t.timeout.connect(self.tick); self.t.start()

    def tick(self):
        if self.busy:
            return
        self.busy = True
        try:
            self._tick()
        finally:
            self.busy = False

    def _tick(self):
        from ui.tooltip_button import InfoDialog
        box = next((w for w in QApplication.topLevelWidgets()
                    if isinstance(w, InfoDialog) and w.isVisible()), None)
        if box is None:
            return
        rec = {"texts": [t for t in
                         ((l.text() or "").strip() for l in box.findChildren(QLabel))
                         if t][:4]}
        if WANT.get("tag"):
            tag = WANT.pop("tag"); WANT["tag"] = None
            rec["photo"] = photo(self.app, box, tag)
        for b in box.findChildren(QPushButton):
            if b.isVisible():
                b.click(); break
        else:
            box.accept()
        BOXES.append(rec)

    def stop(self):
        self.t.stop(); self.t.timeout.disconnect()


def main() -> int:                                              # noqa: C901
    global OUT
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    OUT = Path(sys.argv[1]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1000

    rec_hook()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("appearance", "light"); settings.set("language", lang)
    from core import i18n
    i18n.set_language(lang)
    from ui.theme import apply_appearance
    apply_appearance(app, None, "light")

    from workflow import compliance_sets as CS
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    import ui.widgets as W

    comp = CS.user_values_path()
    assert "/tmp/chromiq-r30" in str(comp)
    if comp.is_file():
        comp.unlink()
    CS.reset_iso_cache()

    work = Path(tempfile.mkdtemp(prefix="chromiq-r30-door-"))
    res = {"lang": lang, "width": width, "locked": session_is_locked()}
    _watcher = Boxes(app)          # KEEP THE NAME: an unbound watcher is collected

    # a file that PARSES and is the WRONG SHAPE: ChromIQ's own meta.json cell
    # shape, which is the one a user is most likely to copy.
    tmpl = json.loads(CS.iso_values_template())
    wrong = {sid: {rid: {"kind": "value", "number": 2.5} for rid in cells}
             for sid, cells in tmpl.items()
             if not sid.startswith("_") and isinstance(cells, dict)}
    wrong_file = work / "wrong-shape.json"
    wrong_file.write_text(json.dumps(wrong, indent=2), encoding="utf-8", encoding='utf-8')

    saved_open = W.open_file_dialog
    W.open_file_dialog = lambda *a, **k: str(wrong_file)

    th = ThresholdsDialog(settings, None)
    th.resize(width, 780)
    th.show(); th.raise_(); th.activateWindow()
    pump(app, 1800)
    res["before"] = {
        "door_text": th._iso_values_btn.text(),
        "door_w": th._iso_values_btn.width(),
        "door_hint_w": th._iso_values_btn.sizeHint().width(),
        "door_h": th._iso_values_btn.height(),
        "door_text_fits": th._iso_values_btn.width() >= th._iso_values_btn.sizeHint().width(),
        "state_line": th._iso_state_lbl.text(),
        "state_w": th._iso_state_lbl.width(),
        "state_hint_w": th._iso_state_lbl.sizeHint().width(),
        "state_fits": th._iso_state_lbl.width() >= th._iso_state_lbl.sizeHint().width(),
        "trouble_panel_text": th._iso_file_trouble(),
        "window_w": th.width(),
        "photo": photo(app, th, f"L1-before-{lang}-{width}"),
    }

    # ---- press the REAL door, act inside the modal, then Close it ----------
    inside: dict = {"tries": 0}

    def act():
        if inside.get("done"):
            return
        rv = next((w for w in QApplication.topLevelWidgets()
                   if isinstance(w, ReferenceValuesDialog) and w.isVisible()), None)
        if rv is None:
            inside["tries"] += 1
            if inside["tries"] > 30:
                inside["done"] = True
                inside["why"] = "the door opened no window in 9 s"
                return
            QTimer.singleShot(300, act)
            return
        inside["done"] = True
        inside["opened"] = True
        inside["size"] = [rv.width(), rv.height()]
        inside["state_before"] = [l.text() for _s, l, _f in rv._rows]
        btns = rv.findChildren(QPushButton)
        inside["buttons"] = [(b.text(), b.width(), b.sizeHint().width(),
                              b.height(),
                              b.width() >= b.sizeHint().width()) for b in btns]
        inside["photo"] = photo(app, rv, f"L2-window-{lang}-{width}")
        WANT["tag"] = f"L3-said-{lang}-{width}"
        btns[1].click()                       # "Use a file I filled in…"
        pump(app, 2200)
        inside["state_after"] = [l.text() for _s, l, _f in rv._rows]
        inside["photo_after"] = photo(app, rv, f"L4-after-{lang}-{width}")
        rv.accept()

    QTimer.singleShot(400, act)
    RAISED.clear()
    th._iso_values_btn.click()
    pump(app, 3000)
    res["inside_the_window"] = inside
    res["raised_in_the_door"] = list(RAISED)

    res["after"] = {
        "state_line": th._iso_state_lbl.text(),
        "installed": comp.is_file(),
        "iso_data_path_text": CS.iso_data_path_text(),
        "trouble_panel_says": th._iso_file_trouble()[:400],
        "trouble_panel_on_screen": bool([
            w for w in th.findChildren(QLabel)
            if w.objectName() == "isoFileTrouble"]),
        "photo": photo(app, th, f"L5-report-limits-after-{lang}-{width}"),
    }
    # ... and the SAME window reopened, which is what the message told the user
    th.close(); pump(app, 700)
    th2 = ThresholdsDialog(settings, None)
    th2.resize(width, 780); th2.show(); th2.raise_(); th2.activateWindow()
    pump(app, 1800)
    res["reopened"] = {
        "state_line": th2._iso_state_lbl.text(),
        "trouble_panel_on_screen": bool([
            w for w in th2.findChildren(QLabel)
            if w.objectName() == "isoFileTrouble"]),
        "trouble_panel_says": th2._iso_file_trouble()[:300],
        "photo": photo(app, th2, f"L6-reopened-{lang}-{width}"),
    }
    th2.close(); pump(app, 400)

    W.open_file_dialog = saved_open
    if comp.is_file():
        comp.unlink()
    CS.reset_iso_cache()
    res["boxes"] = BOXES
    res["raised_total"] = RAISED
    (OUT / f"door-and-lie-{lang}-{width}.json").write_text(
        json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
