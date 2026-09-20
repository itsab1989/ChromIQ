#!/usr/bin/env python3
"""B8-547 and B8-548 on screen: the window fits, and the ISO half says a sentence.

Round 31 measured the fault by LOOKING at a photograph, after every per-widget
number said the window was clean. So this driver photographs, and it also
measures the two things a photograph cannot be argued with about: the window's
height against the screen's, and whether any two rows overlap.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b29/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-b29/presets
    python scripts/drive_beta29_the_window_fits.py <out> [en|de]
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from PyQt6.QtWidgets import (QApplication, QLabel,              # noqa: E402
                             QPushButton)
from onscreen_capture import capture_window, session_is_locked  # noqa: E402

ARCHIVE = Path("/Users/Basti/.claude/jobs/c4ec4e71/tmp/fogra/"
               "Fogra Characterisation Data/FOGRA39_to_FOGRA60_v2.zip")
RAISED: list = []
OUT = Path(".")


def rec_hook() -> None:
    prev = sys.excepthook

    def hook(t, e, tb):
        RAISED.append({"type": t.__name__, "msg": str(e),
                       "tb": "".join(traceback.format_tb(tb))[-400:]})
        prev(t, e, tb)
    sys.excepthook = hook


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _same(a, b, tol=8):
    import numpy as np
    from PIL import Image
    x = np.asarray(Image.open(a).convert("RGB")).astype(int)
    y = np.asarray(Image.open(b).convert("RGB")).astype(int)
    return x.shape == y.shape and bool((np.abs(x - y).sum(2) > tol).sum() == 0)


def photo(app, win, tag):
    why = ""
    for _ in range(3):
        pump(app, 650)
        ok, why = capture_window(win, OUT / f"{tag}-1.png")
        pump(app, 650)
        ok2, why2 = capture_window(win, OUT / f"{tag}-2.png")
        if ok and ok2 and _same(OUT / f"{tag}-1.png", OUT / f"{tag}-2.png"):
            return {"taken": True, "identical": True}
        why = why or why2
    return {"taken": False, "identical": False, "why": why}


def overlaps(dlg) -> int:
    """Rows whose painted rectangles intersect, in GLOBAL coordinates.

    Round 31 counted 231 of these once macOS clamped the window. A row that
    overlaps its neighbour is unreadable whatever its own geometry says.
    """
    boxes = []
    for _src, _key, lbl, _btn in dlg._rows:
        if not lbl.isVisible():
            continue
        tl = lbl.mapToGlobal(lbl.rect().topLeft())
        boxes.append((tl.y(), tl.y() + lbl.height()))
    n = 0
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i][0] < boxes[j][1] and boxes[j][0] < boxes[i][1]:
                n += 1
    return n


def main() -> int:
    global OUT
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    OUT = Path(sys.argv[1]).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"

    rec_hook()
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

    from workflow import reference_sets as rs
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    import ui.widgets as W

    assert "/tmp/chromiq-b29" in str(rs.user_dir()), rs.user_dir()
    res = {"lang": lang, "locked_at_start": session_is_locked(),
           "user_dir": str(rs.user_dir())}

    # ---- 1. as ChromIQ ships ------------------------------------------
    d1 = ReferenceValuesDialog(None)
    d1.show(); d1.raise_(); d1.activateWindow()
    pump(app, 1600)
    screen = d1.screen() or QApplication.primaryScreen()
    room = screen.availableGeometry().height()
    res["shipped"] = {
        "sets": len(d1._rows), "height": d1.height(), "screen": room,
        "fits": d1.height() <= room,
        "scroll_needed": d1._scroll.verticalScrollBar().maximum(),
        "overlapping_pairs": overlaps(d1),
        "photo": photo(app, d1, f"A-shipped-{lang}"),
    }
    d1.close(); pump(app, 500)

    # ---- 2. Fogra's whole published archive ---------------------------
    res["archive"] = {"path": str(ARCHIVE), "exists": ARCHIVE.is_file()}
    if ARCHIVE.is_file():
        res["archive"]["installed"] = rs.install_user_file(ARCHIVE)
    d2 = ReferenceValuesDialog(None)
    d2.show(); d2.raise_(); d2.activateWindow()
    pump(app, 2000)
    bar = d2._scroll.verticalScrollBar()
    res["with_archive"] = {
        "sets": len(d2._rows), "height": d2.height(), "screen": room,
        "fits": d2.height() <= room,
        "scroll_max": bar.maximum(),
        "every_row_reachable": bar.maximum() > 0,
        "overlapping_pairs": overlaps(d2),
        "close_button_on_screen":
            d2._close.mapToGlobal(d2._close.rect().bottomLeft()).y() <= room,
        "photo_top": photo(app, d2, f"B-archive-top-{lang}"),
    }
    bar.setValue(bar.maximum())
    pump(app, 800)
    res["with_archive"]["photo_bottom"] = photo(app, d2, f"C-archive-end-{lang}")
    res["with_archive"]["overlapping_after_scroll"] = overlaps(d2)
    d2.close(); pump(app, 500)

    # ---- 3. B8-548: the ISO half refuses a zip with a SENTENCE ---------
    from ui.tooltip_button import InfoDialog
    said: list = []
    saved_open = W.open_file_dialog
    W.open_file_dialog = lambda *a, **k: str(ARCHIVE)
    d3 = ReferenceValuesDialog(None)
    d3.show(); d3.raise_(); d3.activateWindow()
    pump(app, 1200)
    iso_btn = None
    for b in d3.findChildren(QPushButton):
        if "fill" in b.text().lower() or "ausgef" in b.text().lower():
            iso_btn = b
    res["iso_button"] = iso_btn.text() if iso_btn else None
    if iso_btn is not None:
        from PyQt6.QtCore import QTimer

        def grab():
            box = next((w for w in QApplication.topLevelWidgets()
                        if isinstance(w, InfoDialog) and w.isVisible()), None)
            if box is None:
                QTimer.singleShot(250, grab)
                return
            said.append([t for t in ((l.text() or "").strip()
                                     for l in box.findChildren(QLabel)) if t])
            photo(app, box, f"D-iso-refusal-{lang}")
            for b in box.findChildren(QPushButton):
                if b.isVisible():
                    b.click()
                    return
            box.accept()

        QTimer.singleShot(400, grab)
        iso_btn.click()
        pump(app, 4000)
    res["iso_refusal_said"] = said
    res["iso_refusal_is_a_sentence"] = bool(
        said and not any("codec" in t or "Traceback" in t
                         for group in said for t in group))
    W.open_file_dialog = saved_open
    d3.close(); pump(app, 400)

    for sid in list(rs.user_record()):
        rs.forget_user_set(sid)
    res["raised"] = RAISED
    (OUT / f"window-fits-{lang}.json").write_text(
        json.dumps(res, indent=2, default=str), encoding="utf-8")
    print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
