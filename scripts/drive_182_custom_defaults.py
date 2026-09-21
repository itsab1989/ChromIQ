#!/usr/bin/env python3
"""B8-670: Knut's researched industry figures, in the REAL Report limits window.

Knut, #182, 2026-09-21::

    I have filled in the json file with the threshold limits I have manually
    set, based on findings from research online of industry practice and
    reasoned limits from the industry, which are independently set by various
    actors in the industry, companies or communities, not based on ISO
    standard values. I would like these to be set as default for the two
    Custom ISO 12647 columns.

Four things are photographed, all in a window the app opened:

1. the **Report limits** window with both Custom columns drawn, so the two
   columns can be read side by side and seen to differ;
2. the **masthead help**, which is where `_columns_paragraph` says where those
   numbers came from. That sentence is GENERATED from what is loaded, so the
   picture is of the sentence the code produced, not of one anybody typed;
3. the same window with a **user's own limit** already in the store, on one of
   the rows whose default moved, so the column shows the user's number beside
   ChromIQ's new ones;
4. the **Custom-columns tooltip** in the same window, the other place that
   used to say the numbers were ChromIQ's own.

TWO PIXEL-IDENTICAL FRAMES ARE TAKEN OF EVERY WINDOW, because another agent
may be driving the app on this machine at the same time: a frame that differs
from its own retake a second later is a frame something else walked through,
and it is reported as such rather than kept.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-cust/settings.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-cust/presets \\
    CHROMIQ_COMPLIANCE_ISO_FILE=<repo>/data/compliance_sets/iso12647.json \\
        python scripts/drive_182_custom_defaults.py <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import json
import os
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

from PyQt6.QtWidgets import QApplication, QMessageBox          # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                      # noqa: E402
from onscreen_capture import capture_window, session_is_locked  # noqa: E402

CUSTOM = ("custom_iso_12647_7", "custom_iso_12647_8")


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def twice(app, win, path: Path) -> "tuple[bool, str, float]":
    """Photograph *win* twice and require the CLIENT AREA to be identical.

    The window chrome is not the evidence and is the only thing that moves:
    macOS repaints the title bar and the two rounded bottom corners whenever
    focus changes, and another agent may be driving this machine.
    """
    from onscreen_capture import _difference
    other = path.with_name(path.stem + "__retake.png")
    ok1 = ok2 = False
    why1 = why2 = ""
    for _ in range(3):
        ok1, why1 = capture_window(win, path)
        if ok1:
            break
        pump(app, 900)
    if not ok1:
        return False, why1, -1.0
    pump(app, 1300)
    for _ in range(3):
        ok2, why2 = capture_window(win, other)
        if ok2:
            break
        pump(app, 900)
    if not ok2:
        return False, f"the retake failed: {why2}", -1.0
    d = _difference(path, other)
    if d <= 0.0:
        other.unlink(missing_ok=True)
        return True, "", d
    from PyQt6.QtGui import QImage
    a, b = QImage(str(path)), QImage(str(other))
    xs, ys, n = [], [], 0
    for y in range(0, a.height()):
        for x in range(0, a.width()):
            if a.pixel(x, y) != b.pixel(x, y):
                n += 1
                xs.append(x)
                ys.append(y)
    g, fg = win.geometry(), win.frameGeometry()
    r = win.devicePixelRatioF()
    top = int(round((g.y() - fg.y()) * r))
    left = int(round((g.x() - fg.x()) * r))
    right = a.width() - int(round((fg.right() - g.right()) * r))
    CHROME_BOTTOM = 24
    bottom = a.height() - CHROME_BOTTOM
    below = [(x, y) for x, y in zip(xs, ys)
             if top <= y < bottom and left <= x < right]
    ibox = ((min(x for x, _ in below), min(y for _, y in below),
             max(x for x, _ in below), max(y for _, y in below))
            if below else None)
    print(f"      the two frames differ in {n} pixels, frame "
          f"{a.width()}x{a.height()}, client area ({left},{top})-"
          f"({right},{bottom}), {len(below)} of them inside it, box {ibox}",
          flush=True)
    other.unlink(missing_ok=True)
    if below:
        return False, (f"the two frames differ in {len(below)} pixels INSIDE "
                       f"the client area, in box {ibox}"), d
    return True, (f"the client area is identical; {n} pixels of window chrome "
                  f"differ (the title bar and the rounded bottom corners, "
                  f"which macOS repaints on activation)"), d


def cell_text(td, set_id: str, rid: str) -> str:
    w = td._cells.get((set_id, rid))
    if w is None:
        return "<no cell>"
    if hasattr(w, "value"):
        return f"{w.value():.2f}"
    return w.text()


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    assert os.environ.get("CHROMIQ_COMPLIANCE_ISO_FILE"), \
        "FORCE THE REPOSITORY'S OWN ISO FILE: this machine holds a licence " \
        "holder's real values in Preferences and _iso_data_path prefers them"
    assert os.environ.get("QT_QPA_PLATFORM", "") != "offscreen", \
        "this is a driver, not a test"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    record: dict = {"frames": {}, "measured": {}}

    locked = session_is_locked()
    record["measured"]["screen was locked when the run started"] = locked
    print(f"    screen locked at start: {locked}", flush=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b670-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
    record["sandbox"] = str(work)

    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from ui.theme import apply_appearance
    from ui.dialogs.thresholds_dialog import (ThresholdsDialog,
                                              _columns_paragraph,
                                              _custom_columns_sentence)
    from ui.tooltip_button import _InfoDialog
    from workflow import compliance_sets as cs
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    cs.reset_iso_cache()
    record["measured"]["values file in use"] = cs.iso_data_path_text()
    record["measured"]["counts per column"] = {
        sid: cs.custom_default_counts(sid) for sid in CUSTOM}
    print(f"    values file: {cs.iso_data_path_text()}", flush=True)
    for sid in CUSTOM:
        print(f"      {sid}: {cs.custom_default_counts(sid)}", flush=True)

    # WHICH ROWS MOVED, measured here rather than typed, by putting the module
    # back to the one shared table it held before 2026-09-21.
    shipped = dict(cs._CUSTOM_INDUSTRY)
    moved: dict = {}
    for sid in CUSTOM:
        cs._CUSTOM_INDUSTRY = {}
        cs.reset_iso_cache()
        old = cs.factory_limits(sid)
        cs._CUSTOM_INDUSTRY = shipped
        cs.reset_iso_cache()
        new = cs.factory_limits(sid)
        moved[sid] = sorted(r for r in old if old[r] != new[r])
    record["measured"]["rows whose default moved"] = moved
    print(f"    moved: " + ", ".join(f"{k}={len(v)}" for k, v in moved.items()),
          flush=True)

    # ------------------------------------------------- 1. the window as it is
    td = ThresholdsDialog(settings, None)
    td.resize(1600, 1000)
    td.show()
    td.raise_()
    pump(app, 2000)
    print(f"    limits window on screen: {td.isVisible()} "
          f"{td.frameGeometry().width()}x{td.frameGeometry().height()}",
          flush=True)
    record["measured"]["the two Custom columns on screen"] = {
        sid: {rid: cell_text(td, sid, rid)
              for rid in cs.limit_bearing(cs.factory_limits(sid))}
        for sid in CUSTOM}
    differ = [rid for rid in cs.limit_bearing(cs.factory_limits(CUSTOM[0]))
              if cell_text(td, CUSTOM[0], rid) != cell_text(td, CUSTOM[1], rid)]
    record["measured"]["numbered rows the two columns draw differently"] = differ
    print(f"    the two columns draw {len(differ)} numbered rows differently: "
          f"{differ}", flush=True)

    ok, why, _ = twice(app, td, out / "01-limits-window.png")
    record["frames"]["01-limits-window.png"] = (
        "ok, the content is pixel-identical to its retake"
        + (f"; {why}" if why else "") if ok else f"REFUSED: {why}")
    print(f"    photo 01: {'ok' if ok else 'REFUSED: ' + why}", flush=True)

    # …AND THE ROWS THAT MOVED, which are below the fold.
    from PyQt6.QtWidgets import QScrollArea
    scroller = td.findChild(QScrollArea)
    anchor = td._cells.get((CUSTOM[0], "outer_gamut_226_de00_avg"))
    if scroller is not None and anchor is not None:
        scroller.ensureWidgetVisible(anchor, 0, 260)
        pump(app, 1000)
    okb, whyb, _ = twice(app, td, out / "01b-limits-window-moved-rows.png")
    record["frames"]["01b-limits-window-moved-rows.png"] = (
        "ok, the content is pixel-identical to its retake"
        + (f"; {whyb}" if whyb else "") if okb else f"REFUSED: {whyb}")
    print(f"    photo 01b: {'ok' if okb else 'REFUSED: ' + whyb}", flush=True)

    # ----------------------------------- 2. the masthead help, GENERATED text
    para = _columns_paragraph()
    record["measured"]["the generated columns paragraph"] = para
    record["measured"]["the generated custom sentence"] = \
        _custom_columns_sentence()
    print(f"    generated paragraph:\n      {para}", flush=True)
    # THE BODY THE WINDOW ITSELF HOLDS, not one this driver rebuilds: the
    # masthead's own TooltipButton is found and its stored text is what is
    # shown, so the picture is of what a user clicking that icon would read.
    from ui.tooltip_button import TooltipButton
    body = ""
    for b in td.findChildren(TooltipButton):
        if "Custom columns" in getattr(b, "_body", ""):
            body = b._body
            break
    assert body, "the masthead's help body could not be found in the window"
    record["measured"]["the masthead body is the generated paragraph"] = \
        para in body
    help_dlg = _InfoDialog("Report limits", body, td, 560)
    help_dlg.show()
    help_dlg.raise_()
    pump(app, 3000)
    ok2, why2, _ = twice(app, help_dlg, out / "02-masthead-help.png")
    record["frames"]["02-masthead-help.png"] = (
        "ok, the content is pixel-identical to its retake"
        + (f"; {why2}" if why2 else "") if ok2 else f"REFUSED: {why2}")
    print(f"    photo 02: {'ok' if ok2 else 'REFUSED: ' + why2}", flush=True)
    help_dlg.close()
    pump(app, 300)

    # ------------------------------------ 3. the Custom-columns tooltip below
    notes = td._notes_text() if hasattr(td, "_notes_text") else ""
    record["measured"]["the notes text names both sources"] = {
        "industry practice": "researched from industry practice" in notes,
        "ChromIQ's own numbers": "ChromIQ's own numbers" in notes,
        "says neither is the standard's":
            "Neither source is the published tolerances" in notes,
    }
    if notes:
        nd = _InfoDialog("What the columns hold", notes, td, 560)
        nd.show()
        nd.raise_()
        pump(app, 3000)
        ok3, why3, _ = twice(app, nd, out / "03-custom-columns-note.png")
        record["frames"]["03-custom-columns-note.png"] = (
            "ok, the content is pixel-identical to its retake"
            + (f"; {why3}" if why3 else "") if ok3 else f"REFUSED: {why3}")
        print(f"    photo 03: {'ok' if ok3 else 'REFUSED: ' + why3}", flush=True)
        nd.close()
        pump(app, 300)
    td.close()
    pump(app, 500)

    # ------------------------- 4. a user's own limit, beside the new defaults
    # WRITTEN AS THE USER'S, NOT AS OURS. The override blob is what the Report
    # limits window itself writes when somebody turns a spin box; seeding it
    # here is the same state as a user who set that row last month, and the
    # window is then opened fresh and photographed.
    from core.settings import store_compliance_overrides
    victim = moved[CUSTOM[0]][0]
    store_compliance_overrides(settings, {CUSTOM[0]: {victim: 1.23}})
    td2 = ThresholdsDialog(settings, None)
    td2.resize(1600, 1000)
    td2.show()
    td2.raise_()
    pump(app, 2000)
    mine = cell_text(td2, CUSTOM[0], victim)
    neighbours = {rid: cell_text(td2, CUSTOM[0], rid)
                  for rid in moved[CUSTOM[0]] if rid != victim}
    record["measured"]["the user's own row"] = {victim: mine}
    record["measured"]["the other moved rows beside it"] = neighbours
    print(f"    the user's row {victim} draws {mine!r}; the other moved rows "
          f"draw {neighbours}", flush=True)
    scroller2 = td2.findChild(QScrollArea)
    anchor2 = td2._cells.get((CUSTOM[0], victim))
    if scroller2 is not None and anchor2 is not None:
        scroller2.ensureWidgetVisible(anchor2, 0, 260)
        pump(app, 1000)
    ok4, why4, _ = twice(app, td2, out / "04-a-users-own-limit.png")
    record["frames"]["04-a-users-own-limit.png"] = (
        "ok, the content is pixel-identical to its retake"
        + (f"; {why4}" if why4 else "") if ok4 else f"REFUSED: {why4}")
    print(f"    photo 04: {'ok' if ok4 else 'REFUSED: ' + why4}", flush=True)
    td2.close()
    pump(app, 400)
    store_compliance_overrides(settings, {})

    (out / "measured.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    refused = [k for k, v in record["frames"].items() if v.startswith("REFUSED")]
    print(f"\n    {len(record['frames']) - len(refused)} of "
          f"{len(record['frames'])} frames kept", flush=True)
    for k in refused:
        print(f"      REFUSED {k}: {record['frames'][k]}", flush=True)
    return 1 if refused else 0


if __name__ == "__main__":
    raise SystemExit(main())
