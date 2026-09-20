#!/usr/bin/env python3
"""Challenge round 31: the Reference values window, driven in a REAL window.

What round 30 could not see, and this exists to see:

* **its own message boxes.** `InfoDialog` takes its PARENT's title, so
  `window_id_for` matched both windows and `max(..., area)` picked the parent:
  every `*-said-*` picture of round 30 is a photograph of the greyed-out
  window BEHIND the sentence it is filed as. Fixed in `onscreen_capture`, and
  this driver photographs the box itself.
* **a set ChromIQ ships nothing for, given up.** "Stop using it" on FOGRA61
  used to say ChromIQ was back to a copy that has never existed.
* **the window with Fogra's WHOLE archive in it**, twenty-two sets, against
  the screen it has to fit on.
* **every control, twice, and in a silly order**, under a recording
  `sys.excepthook`.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-chal31/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-chal31/presets
    python scripts/chal31_the_reference_values_window.py <out-dir> [en|de] [width]
"""
from __future__ import annotations

import json
import os
import shutil
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

#: Fogra's own published archives, as downloaded.
PUB = Path.home() / "Desktop/ChromIQ-fogra-research/bench/C/fetch/published"

RAISED: list = []
BOXES: list = []
OUT = Path(".")
APP = None


def install_recorder() -> None:
    prev = sys.excepthook

    def hook(t, e, tb):
        RAISED.append({"type": t.__name__, "msg": str(e)[:300],
                       "tb": "".join(traceback.format_tb(tb))[-500:]})
        prev(t, e, tb)

    sys.excepthook = hook


def pump(ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        APP.processEvents()
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


def photo(win, tag: str) -> dict:
    """TWO PIXEL-IDENTICAL FRAMES OR IT IS NOT A PHOTOGRAPH."""
    ok = ok2 = False
    why = ""
    for _ in range(3):
        pump(600)
        ok, why = capture_window(win, OUT / f"{tag}-1.png")
        pump(600)
        ok2, why2 = capture_window(win, OUT / f"{tag}-2.png")
        why = why or why2
        if ok and ok2 and _same(OUT / f"{tag}-1.png", OUT / f"{tag}-2.png"):
            from PyQt6.QtGui import QImage
            im = QImage(str(OUT / f"{tag}-1.png"))
            return {"taken": True, "identical": True, "file": f"{tag}-1.png",
                    "px": [im.width(), im.height()],
                    "window_says": [win.width(), win.height()]}
    return {"taken": bool(ok and ok2), "identical": False, "why": why}


class BoxWatcher:
    """Close every InfoDialog that appears, say what it said, and PHOTOGRAPH
    it when asked. Standing, not one-shot: a one-shot handler hung an earlier
    driver for nine minutes inside `QDialog::exec`."""

    def __init__(self):
        from PyQt6.QtCore import QTimer
        self.want = None
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
        texts = [(x.text() or "").strip() for x in box.findChildren(QLabel)]
        rec = {"title": box.windowTitle(), "texts": [t for t in texts if t][:6]}
        if self.want:
            tag, self.want = self.want, None
            rec["photo"] = photo(box, tag)
            # AND PROVE IT IS THE BOX AND NOT THE PARENT: the box is smaller,
            # so a picture the size of the window behind it is the round-30
            # fault coming back.
            rec["box_size"] = [box.width(), box.height()]
        for b in box.findChildren(QPushButton):
            if b.isVisible():
                b.click()
                break
        else:
            box.accept()
        BOXES.append(rec)

    def stop(self) -> None:
        self.t.stop()


def overlaps(dlg) -> list:
    """Rows drawn ON TOP of one another.

    **THE DETECTOR THIS ROUND DID NOT HAVE, AND THE PHOTOGRAPH DID.** A label
    given two lines' worth of minimum height inside a row the layout still
    sizes for one is not CLIPPED: it paints both lines, over whatever is below
    it. Every per-widget check came back clean while the German window drew
    "und ist datiert auf May 2015." across the FOGRA47 line.
    """
    boxes = []
    for _s, key, lbl, _b in dlg._rows:
        g = lbl.geometry()
        p = lbl.mapTo(dlg, g.topLeft() - lbl.pos())
        boxes.append((key, p.y(), p.y() + lbl.height()))
    bad = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            if a[1] < b[2] and b[1] < a[2]:
                bad.append({"rows": [a[0], b[0]], "a": a[1:], "b": b[1:]})
    return bad


def clipped(w) -> list:
    """Every visible label or button narrower than the text it holds."""
    bad = []
    for c in w.findChildren((QLabel, QPushButton)):
        if not c.isVisible() or not (c.text() or "").strip():
            continue
        hint = c.sizeHint()
        if isinstance(c, QLabel) and c.wordWrap():
            need = c.heightForWidth(c.width())
            if need > c.height() + 1:
                bad.append({"what": c.text()[:60], "h": c.height(),
                            "needs": need, "kind": "wrapped label too short"})
            continue
        if hint.width() > c.width() + 1:
            bad.append({"what": c.text()[:60], "w": c.width(),
                        "needs": hint.width(), "kind": type(c).__name__})
        if hint.height() > c.height() + 1:
            bad.append({"what": c.text()[:60], "h": c.height(),
                        "needs": hint.height(), "kind": type(c).__name__})
    return bad


def main() -> int:                                              # noqa: C901
    global OUT, APP
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
    assert not os.environ.get("QT_QPA_PLATFORM"), "this DRIVER opens a window"
    OUT = Path(sys.argv[1]).resolve(); OUT.mkdir(parents=True, exist_ok=True)
    lang = sys.argv[2] if len(sys.argv) > 2 else "en"
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 820

    install_recorder()
    APP = QApplication.instance() or QApplication(sys.argv[:1])
    APP.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    APP.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    s = AppSettings(); s.set("appearance", "light"); s.set("language", lang)
    from core import i18n
    i18n.set_language(lang)
    # THE APP'S OWN STYLESHEET, OR EVERY SIZE HERE IS FICTION.
    from ui.theme import apply_appearance
    apply_appearance(APP, None, "light")

    from workflow import reference_sets as rs
    from workflow import compliance_sets as cs
    from ui.dialogs.reference_values_dialog import ReferenceValuesDialog
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    import ui.widgets as W

    assert "/tmp/chromiq-chal31" in str(rs.user_dir()), rs.user_dir()
    shutil.rmtree(rs.user_dir(), ignore_errors=True)
    if cs.user_values_path().is_file():
        cs.user_values_path().unlink()
    rs.reset_cache(); cs.reset_iso_cache()

    scr = APP.primaryScreen().availableGeometry()
    res: dict = {"lang": lang, "opened_at_width": width,
                 "locked_at_start": session_is_locked(),
                 "screen": [scr.width(), scr.height()],
                 "user_dir": str(rs.user_dir()),
                 "archives_are_fogras_own": PUB.is_dir()}
    watcher = BoxWatcher()

    answer = {"open": "", "save": ""}
    W.open_file_dialog = lambda *a, **k: answer["open"]
    W.save_file_dialog = lambda *a, **k: answer["save"]

    def rows(dlg, key):
        dlg._refresh(); pump(120)
        return [r for r in dlg._rows if r[0].key == key]

    def press_install(dlg, path, tag=None):
        src = next(x for x in dlg._sources if x.key == "fogra")
        n = len(BOXES); RAISED.clear(); answer["open"] = str(path)
        if tag:
            watcher.want = tag
        btn = next(b for b in dlg.findChildren(QPushButton)
                   if b.text() == src.install_label)
        btn.click(); pump(2600)
        return {"raised": list(RAISED), "boxes": BOXES[n:]}

    def press_stop(dlg, set_id, tag=None):
        r = next((x for x in rows(dlg, "fogra") if x[1] == set_id), None)
        if r is None:
            return {"error": f"no row for {set_id}"}
        n = len(BOXES); RAISED.clear()
        if tag:
            watcher.want = tag
        vis, en = r[3].isVisible(), r[3].isEnabled()
        r[3].click(); pump(2600)
        return {"was_visible": vis, "was_enabled": en,
                "raised": list(RAISED), "boxes": BOXES[n:]}

    # -- A: the door in Report limits, under the app's own stylesheet --------
    th = ThresholdsDialog(s); th.resize(width + 200, 700); th.show(); pump(900)
    doors = [b for b in th.findChildren(QPushButton)
             if "…" in b.text() and ("Reference" in b.text()
                                     or "Referenz" in b.text())]
    res["A_door"] = {"visible": th.isVisible(), "count": len(doors),
                     "labels": [b.text() for b in doors],
                     "height": doors[0].height() if doors else None,
                     "photo": photo(th, f"A-door-{lang}")}
    th.close(); pump(200)

    dlg = ReferenceValuesDialog(); dlg.resize(width, dlg.height())
    dlg.show(); pump(900)

    def snap(tag, extra=None):
        d = {"w": dlg.width(), "h": dlg.height(),
             "fits_screen": dlg.height() <= scr.height()
             and dlg.width() <= scr.width(),
             "fogra_lines": [r[2].text() for r in rows(dlg, "fogra")],
             "stops_enabled": [r[3].isEnabled() for r in rows(dlg, "fogra")],
             "stops_visible": [r[3].isVisible() for r in rows(dlg, "fogra")],
             "clipped": clipped(dlg),
             "overlapping_rows": overlaps(dlg),
             "photo": photo(dlg, f"{tag}-{lang}")}
        if extra:
            d.update(extra)
        return d

    res["B_first_open"] = snap("B-first-open")

    # -- C: a newer file for a set that SHIPS -------------------------------
    f51 = PUB / "MK3_Subsets_FOGRA39_until_FOGRA60.zip"
    work = Path("/tmp/chal31/onscreen"); work.mkdir(parents=True, exist_ok=True)
    import zipfile
    with zipfile.ZipFile(f51) as z:
        (work / "FOGRA51_MW3_Subset.txt").write_bytes(
            z.read("FOGRA51_MW3_Subset.txt"))
    res["C_newer_51"] = {"install": press_install(dlg, work / "FOGRA51_MW3_Subset.txt",
                                                  tag=f"C-said-{lang}")}
    res["C_newer_51"]["after"] = snap("C-fogra51-yours")

    # -- D: a set that ships NOWHERE, Fogra's real FOGRA61 beta shape -------
    f61 = work / "FOGRA61_beta.txt"
    f61.write_bytes(("\r\n".join([
        "ISO28178", 'FILE_DESCRIPTOR\t"3D-DesignRGB_FOGRA61(beta)"',
        'ORIGINATOR\t"Fogra, www.fogra.org"', 'CREATED\t"31-Jul-2024"',
        "NUMBER_OF_FIELDS\t7", "BEGIN_DATA_FORMAT",
        "SAMPLE_ID\tRGB_R\tRGB_G\tRGB_B\tLAB_L\tLAB_A\tLAB_B",
        "END_DATA_FORMAT", "NUMBER_OF_SETS\t2", "BEGIN_DATA",
        "1\t0\t0\t0\t11\t0\t0", "2\t255\t255\t255\t91\t-1\t4",
        "END_DATA", ""])).encode("utf-8"))
    res["D_fogra61"] = {"install": press_install(dlg, f61)}
    res["D_fogra61"]["after"] = snap("D-fogra61-arrived")

    # -- E: stop the set that ships NOWHERE. THE SENTENCE UNDER TEST. -------
    res["E_stop_61"] = press_stop(dlg, "FOGRA61", tag=f"E-stop61-said-{lang}")
    res["E_stop_61"]["after"] = snap("E-fogra61-gone")
    res["E_stop_61"]["still_offered"] = rs.by_id("FOGRA61") is not None

    # -- F: stop the set that DOES ship -------------------------------------
    res["F_stop_51"] = press_stop(dlg, "FOGRA51", tag=f"F-stop51-said-{lang}")
    res["F_stop_51"]["after"] = snap("F-back-to-shipped")

    # -- G: rubbish, and the sentence the user gets -------------------------
    bad = work / "holiday-notes.txt"
    bad.write_text("Dear Fogra,\r\nplease send the data.\r\n", encoding="utf-8")
    res["G_rubbish"] = press_install(dlg, bad, tag=f"G-refusal-{lang}")
    res["G_rubbish"]["nothing_written"] = \
        not list(rs.user_dir().glob("*.txt"))

    # -- H: FOGRA'S WHOLE ARCHIVE. twenty-two sets, against the screen. -----
    res["H_whole_archive"] = press_install(
        dlg, PUB / "FOGRA39_to_FOGRA60_v2.zip", tag=f"H-zip-said-{lang}")
    res["H_whole_archive"]["after"] = snap("H-whole-archive")

    # -- I: EVERY CONTROL, TWICE, IN A SILLY ORDER --------------------------
    RAISED.clear()
    n = len(BOXES)
    seq = []
    for _round in range(2):
        labels = []
        for b in list(dlg.findChildren(QPushButton)):
            try:
                if b.isVisible() and b.text() != "Close":
                    labels.append(b.text())
            except RuntimeError:
                pass
        # backwards the second time round, because "in a silly order" means
        # pressing Stop before Use and the last row before the first
        for label in (labels if _round == 0 else list(reversed(labels))):
            try:
                b = next((x for x in dlg.findChildren(QPushButton)
                          if x.text() == label and x.isVisible()), None)
            except RuntimeError:
                b = None
            if b is None:
                seq.append(f"<gone: {label}>")
                continue
            seq.append(label)
            try:
                b.click()
            except RuntimeError as exc:
                seq.append(f"<deleted mid-press: {exc}>")
            pump(500)
    # ...and the ISO half, which this change could have broken
    iso = next(x for x in dlg._sources if x.key == "iso12647")
    answer["save"] = str(work / "iso-template.json")
    answer["open"] = str(work / "iso-template.json")
    for label in (getattr(iso.template, "label", ""), iso.install_label,
                  iso.forget_label):
        for _ in range(2):
            # RE-QUERY EVERY TIME. `_fill_items` destroys the row widgets, so a
            # QPushButton held across one press is a deleted C++ object on the
            # next -- which this driver hit for real on its first run.
            try:
                b = next((x for x in dlg.findChildren(QPushButton)
                          if x.text() == label and x.isVisible()
                          and x.isEnabled()), None)
            except RuntimeError:
                b = None
            if b is None:
                seq.append(f"<no live button: {label}>")
                continue
            seq.append(label)
            b.click(); pump(700)
    res["I_every_control_twice"] = {
        "pressed": seq, "raised": list(RAISED), "boxes": len(BOXES) - n,
        "iso_template_written": (work / "iso-template.json").is_file(),
        "after": snap("I-after-mashing"),
    }

    # -- J: narrow. the window at its own minimum, on a small main window ---
    dlg.resize(dlg.minimumWidth(), dlg.height()); pump(700)
    res["J_narrow"] = snap("J-narrow", {"min_width": dlg.minimumWidth()})

    res["boxes_all"] = BOXES
    res["raised_total"] = RAISED
    watcher.stop()
    dlg.close(); pump(200)
    res["locked_at_end"] = session_is_locked()
    (OUT / f"result-{lang}.json").write_text(json.dumps(res, indent=1),
                                             encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items()
                      if k not in ("boxes_all",)}, indent=1)[:9000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
