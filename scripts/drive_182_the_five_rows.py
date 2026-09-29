#!/usr/bin/env python3
"""B8-397: the five limit rows that had no detection, in the REAL windows.

Knut, 2026-09-18, approving the three proposals of S2w::

    Implement the proposals. I have already proposed to change the heading from
    'Selected patches of the standard's chart' to 'Selected patches of the
    chart'. The help text can explain, as for all the other metrics, what the
    detection method is and how it is used, and if there are any requirements
    to the charts etc.

Three things are photographed, all of them in a window the app opened:

1. the **Report limits** window, showing the changed group heading and the five
   rows now carrying a limit in the two Custom columns rather than a ``?``;
2. the **info icon** of each of the five rows, which is where the new detection
   method and the new lever are read;
3. the **Measurement Report** window on two real measurements of the demo pack,
   one whose chart declares no control strip and one whose chart declares a
   strip of seven, so the two new reasons are read as sentences rather than as
   codes.

TWO PIXEL-IDENTICAL FRAMES ARE TAKEN OF EVERY WINDOW, because another agent is
driving the app on this machine at the same time: a frame that differs from its
own retake a second later is a frame something else walked through, and it is
reported as such rather than kept.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b397.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-b397-presets \\
        python scripts/drive_182_the_five_rows.py <pack> <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
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

PROJECT = "Report-Limits-Custom-Columns"
#: The five rows B8-397 gave a detection method.
FIVE = ("control_strip_de00_avg", "control_strip_de00_max",
        "control_strip_de00_p95", "surface_gamut_de00_avg",
        "outer_gamut_226_de00_avg")


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def twice(app, win, path: Path) -> "tuple[bool, str, float]":
    """Photograph *win* twice and require the two frames to be identical.

    Returns (ok, why, difference %). A window another process walked over
    between the two frames differs from itself, and that is reported rather
    than filed as evidence.
    """
    from onscreen_capture import _difference
    other = path.with_name(path.stem + "__retake.png")
    # THREE TRIES EACH. Another agent is driving this machine, and a capture
    # that loses the race comes back as "screencapture refused the window's
    # rectangle" rather than as a wrong picture. Retrying a refusal is not the
    # same as accepting one: a refusal that survives three attempts is still
    # reported and the file is still not kept.
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
    # SAY WHERE, NOT ONLY HOW MUCH. A percentage cannot tell a blinking caret
    # from another process's window landing on top, and the two need different
    # answers. The bounding box of the differing pixels does.
    from PyQt6.QtGui import QImage
    a, b = QImage(str(path)), QImage(str(other))
    xs, ys, n = [], [], 0
    for y in range(0, a.height()):
        for x in range(0, a.width()):
            if a.pixel(x, y) != b.pixel(x, y):
                n += 1
                xs.append(x)
                ys.append(y)
    box = (min(xs), min(ys), max(xs), max(ys)) if n else None
    # THE WINDOW CHROME IS NOT THE EVIDENCE, AND IT IS THE ONLY THING THAT
    # MOVES. Measured on every refused frame of four runs: the differing pixels
    # are a band across the top of the picture ending at y = 55 on a 2x screen,
    # which is macOS repainting the TITLE BAR, plus exactly 28 pixels in the
    # last 24 rows, which is the rounded bottom corner and its shadow. Both are
    # redrawn when the window goes active or inactive, and another agent is
    # driving this machine at the same time, so focus moves. The window's
    # CLIENT AREA is what the frame is evidence of, and that is required to be
    # identical, pixel for pixel.
    g, fg = win.geometry(), win.frameGeometry()
    r = win.devicePixelRatioF()
    top = int(round((g.y() - fg.y()) * r))
    left = int(round((g.x() - fg.x()) * r))
    right = a.width() - int(round((fg.right() - g.right()) * r))
    # Qt reports NO bottom frame on macOS, so the client rect runs to the last
    # row of the picture and the rounded bottom corners fall inside it.
    # Measured on eight refused frames across four runs: exactly 28 pixels,
    # always in the last 24 rows and always at the two ends of them, which is
    # the antialiasing of those two corners. Excluded by name, at the measured
    # size, and not by widening a tolerance until the run went quiet.
    CHROME_BOTTOM = 24
    bottom = a.height() - CHROME_BOTTOM
    strip = top
    below = [(x, y) for x, y in zip(xs, ys)
             if top <= y < bottom and left <= x < right]
    inside = len(below)
    ibox = ((min(x for x, _ in below), min(y for _, y in below),
             max(x for x, _ in below), max(y for _, y in below))
            if below else None)
    print(f"      the two frames differ in {n} pixels, box {box}, "
          f"frame {a.width()}x{a.height()}, client area "
          f"({left},{top})-({right},{bottom}), {inside} of them inside it, "
          f"box {ibox}", flush=True)
    other.unlink(missing_ok=True)
    if inside:
        return False, (f"the two frames differ in {inside} pixels INSIDE the "
                       f"client area, in box {ibox} of a "
                       f"{a.width()}x{a.height()} frame"), d
    return True, (f"the client area is identical; {n} pixels of window "
                  f"chrome differ (the title bar and the two rounded bottom "
                  f"corners, which macOS repaints on activation)"), d


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    record: dict = {"frames": {}, "measured": {}}

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b397-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)
    record["sandbox"] = str(work)

    src = pack / PROJECT
    assert src.is_dir(), f"no {PROJECT} in {pack}"
    proj = work / src.name
    shutil.copytree(src, proj)
    # A SECOND COPY, UNTOUCHED, which is the rule-1 frame: a project exactly as
    # the demo pack delivers it, opened by this build.
    kept = work / (src.name + "-as-delivered")
    shutil.copytree(src, kept)

    # THE WINDOW OPENS A SAVED REPORT WHEN THERE IS ONE, and every measurement
    # in this pack has one, written by an older build that had no control-strip
    # block. That is rule 1 working and it is photographed as frame 09; to see
    # the NEW state the report has to be BUILT, so the saved reports are
    # removed from the working copy. A measurement whose report has not been
    # generated yet is exactly this state.
    for r in sorted(proj.rglob("reports")):
        if r.is_dir():
            shutil.rmtree(r)

    # THE RUNS ARE UNBOUND HERE, ON PURPOSE AND SAID OUT LOUD. Both were bound
    # before this release, so their stored copy holds "?" on the five rows and
    # the window would show exactly what it showed yesterday, which is rule 1
    # of this change working. To photograph the NEW state the run has to be
    # bound by THIS build, so the stored copy is removed and the window binds
    # the run itself, through `ensure_bound`, exactly as it does at a run's
    # first verification.
    for run in ("run1", "run2"):
        meta = proj / "runs" / run / "meta.json"
        d = json.loads(meta.read_text(encoding="utf-8"))
        d.pop("compliance_thresholds", None)
        meta.write_text(json.dumps(d, indent=2), encoding="utf-8")

    # …and run2's chart is given a control strip of SEVEN, which is one short.
    from workflow.ti3_analysis import parse_ti3
    chart2 = proj / "runs" / "run2" / f"{PROJECT}.ti2"
    ids = parse_ti3(chart2).sample_ids[:7]
    (chart2.parent / f"{chart2.stem}.control-strip.json").write_text(
        json.dumps({"name": "Demo strip of seven", "sample_ids": list(ids)}),
        encoding="utf-8")
    print(f"    run2's chart now declares a strip of {len(ids)}: "
          f"{' '.join(ids)}", flush=True)
    record["declared_strip"] = list(ids)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from core.i18n import tr
    from ui.theme import apply_appearance
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    from ui.tooltip_button import _InfoDialog
    from workflow import compliance_sets as cs
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    # ---------------------------------------------------------- 1. the window
    td = ThresholdsDialog(settings, None)
    td.resize(1500, 1000)
    td.show()
    td.raise_()
    pump(app, 1800)
    print(f"    limits window on screen: {td.isVisible()} "
          f"{td.frameGeometry().width()}x{td.frameGeometry().height()}",
          flush=True)
    heading = tr(cs.GROUP_LABELS["selected"])
    on_screen = [w.text() for w in td.findChildren(type(td.findChild(
        __import__("PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel)))
        if hasattr(w, "text")]
    record["measured"]["the heading on screen"] = heading
    record["measured"]["the heading is in the window"] = heading in on_screen
    cells = {}
    for rid in FIVE:
        w = td._cells.get(("custom_iso_12647_7", rid))
        cells[rid] = (type(w).__name__,
                      f"{w.value():.2f}" if hasattr(w, "value") else w.text())
    record["measured"]["Custom ISO 12647-7 cells"] = cells
    print(f"    heading: {heading!r} (in the window: "
          f"{heading in on_screen})", flush=True)
    for rid, v in cells.items():
        print(f"      {rid:26s} {v[0]:22s} {v[1]}", flush=True)

    ok, why, diff = twice(app, td, out / "01-limits-window.png")

    record["frames"]["01-limits-window.png"] = (
        f"ok, the content is pixel-identical to its retake"
        + (f"; {why}" if why else "") if ok else f"REFUSED: {why}")
    print(f"    photo 01: {'ok' if ok else 'REFUSED: ' + why}", flush=True)

    # …AND THE GROUP THE HEADING BELONGS TO, WHICH IS BELOW THE FOLD. The
    # first frame of this window showed the top of the table, so the one
    # heading Knut changed was not in the picture at all. The scroll area is
    # moved to the row itself rather than by a guessed number of pixels.
    scroller = None
    from PyQt6.QtWidgets import QScrollArea
    for sa in td.findChildren(QScrollArea):
        if sa.widget() is not None and td._grid.parent() in (sa.widget(),
                                                             sa.widget().parent()):
            scroller = sa
            break
    if scroller is None:
        scroller = td.findChild(QScrollArea)
    cell = td._cells.get(("custom_iso_12647_7", "surface_gamut_de00_avg"))
    if scroller is not None and cell is not None:
        scroller.ensureWidgetVisible(cell, 0, 260)
        pump(app, 900)
    okb, whyb, _ = twice(app, td, out / "01b-limits-window-selected-group.png")
    record["frames"]["01b-limits-window-selected-group.png"] = (
        "ok, the content is pixel-identical to its retake"
        + (f"; {whyb}" if whyb else "") if okb else f"REFUSED: {whyb}")
    print(f"    photo 01b: {'ok' if okb else 'REFUSED: ' + whyb}", flush=True)

    # ---------------------------------------------- 2. the five help dialogs
    for n, rid in enumerate(FIVE, start=2):
        row = cs.ROW_BY_ID[rid]
        d = _InfoDialog(tr(row.label), td._row_help(row), td, 460)
        d.show()
        d.raise_()
        # LONG ENOUGH FOR THE SCROLL BAR TO FINISH FADING. `ui/fade_scroll.py`
        # fades the bar out after the content settles, and two frames taken
        # across that fade differ by 0.06 % of the pixels: a thin strip down
        # the right edge, on exactly the dialogs whose help text is long enough
        # to scroll. Measured by diffing two frames of the same dialog with
        # nothing else on the machine: zero differing pixels once it has
        # settled. That is the only thing the retake was catching here, and it
        # is not another process walking through the window.
        pump(app, 3000)
        name = f"{n:02d}-help-{rid}.png"
        ok2, why2, diff2 = twice(app, d, out / name)
        record["frames"][name] = (
            "ok, the content is pixel-identical to its retake"
            + (f"; {why2}" if why2 else "") if ok2 else f"REFUSED: {why2}")
        print(f"    photo {name}: {'ok' if ok2 else 'REFUSED: ' + why2}",
              flush=True)
        d.close()
        pump(app, 250)
    td.close()
    pump(app, 400)

    # ------------------------------------------ 3. the reasons in the report
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    import html as _html
    import re as _re
    for n, (base, run, expect) in enumerate(
            ((proj, "run1", "no_control_strip"),
             (proj, "run2", "control_strip_too_small"),
             (kept, "run1", "as-delivered-saved-report")), start=7):
        ti3 = sorted((base / "runs" / run / "verifications")
                     .glob("*/*-verify.ti3"))[0]
        dlg = MeasurementReportDialog(settings, None, initial_ti3=str(ti3))
        dlg.resize(1400, 1000)
        dlg.show()
        dlg.raise_()
        pump(app, 2200)
        rep = dlg._report
        lim = dlg._limits_for(rep)
        rows = {r.get("row_id") or r.get("key"): r
                for r in dlg._verdict_rows(rep)[0]}
        missing = dict(dlg._not_computed(rep))
        text = _html.unescape(_re.sub(
            "<[^>]+>", " ", dlg._report_results_html(dlg._runs_for_report())))
        text = " ".join(text.split())
        run = f"{base.name}/{run}"
        record["measured"][f"{run} set"] = f"{lim.set_id} (bound={lim.bound})"
        record["measured"][f"{run} strip block"] = rep.get("control_strip")
        record["measured"][f"{run} rows"] = {
            rid: {"word": rows.get(rid, {}).get("word"),
                  "value": rows.get(rid, {}).get("value"),
                  "reason": rows.get(rid, {}).get("reason")}
            for rid in FIVE}
        sentences = {lbl: why for lbl, why in missing.items()
                     if any(tr(cs.ROW_BY_ID[r].label) == lbl for r in FIVE)}
        record["measured"][f"{run} sentences"] = sentences
        record["measured"][f"{run} the sentence is on the page"] = {
            lbl: (s[:40] in text) for lbl, s in sentences.items()}
        print(f"    {run}: set {lim.set_id}, expected {expect}", flush=True)
        for lbl, s in sentences.items():
            print(f"      {lbl}: {s}", flush=True)
        # SCROLL THE BODY TO THE SENTENCE. The mismatch strip above the results
        # names the rows and keeps the reasons in its tooltip; the sentences
        # themselves are printed under the results table, which is below the
        # fold on a window this size. A frame of a document nobody scrolled is
        # a frame of a heading.
        find = tr("Not computed on this chart:")
        moved = dlg._view.find(find)
        if not moved:
            from PyQt6.QtGui import QTextCursor
            dlg._view.moveCursor(QTextCursor.MoveOperation.Start)
            moved = dlg._view.find(find)
        bar = dlg._view.verticalScrollBar()
        if not moved:
            bar.setValue(bar.maximum())
        else:
            # …AND PAST IT. `find` puts the match on the LAST visible line, so
            # the sentence it introduces is still below the fold. Measured on
            # the first frame: the note's own heading was the bottom row of
            # the picture and not one word of the reason was in it.
            # …BY ONE VIEWPORT LESS A LINE, so the heading lands at the TOP of
            # the band and the sentence under it is what fills the picture.
            # `find` leaves the match on the last visible line and a fixed
            # nudge of 420 overshot the whole note; the page step is the only
            # number that is right at any window size.
            bar.setValue(min(bar.maximum(),
                             bar.value() + bar.pageStep() - 40))
        print(f"      scrolled to {find!r}: found={moved}, "
              f"scroll {bar.value()} of {bar.maximum()}", flush=True)
        record["measured"][f"{run} scrolled to the note"] = bool(moved)
        pump(app, 900)
        name = f"{n:02d}-report-{run.split("/")[-1]}-{expect}.png"
        ok3, why3, diff3 = twice(app, dlg, out / name)
        record["frames"][name] = (
            "ok, the content is pixel-identical to its retake"
            + (f"; {why3}" if why3 else "") if ok3 else f"REFUSED: {why3}")
        print(f"    photo {name}: {'ok' if ok3 else 'REFUSED: ' + why3}",
              flush=True)
        dlg.close()
        pump(app, 400)

    verdicts = {
        "the heading no longer names a standard":
            "standard" not in heading.lower(),
        "all five rows carry a limit in Custom ISO 12647-7":
            all(v[0] != "QLabel" for v in cells.values()),
        "every frame was taken, and each frame's CONTENT is identical to "
        "its own retake a second later":
            all(v.startswith("ok") for v in record["frames"].values()),
        "the run with no declaration says no_control_strip":
            record["measured"][f"{PROJECT}/run1 rows"]
            ["control_strip_de00_avg"]["reason"] == "no_control_strip",
        "the run with seven says control_strip_too_small":
            record["measured"][f"{PROJECT}/run2 rows"]
            ["control_strip_de00_avg"]["reason"] == "control_strip_too_small",
        "both gamut rows were computed on a real 210-patch chart":
            record["measured"][f"{PROJECT}/run1 rows"]
            ["surface_gamut_de00_avg"]["value"] is not None
            and record["measured"][f"{PROJECT}/run1 rows"]
            ["outer_gamut_226_de00_avg"]["value"] is not None,
        "every withheld row reached the page as a sentence":
            all(record["measured"][f"{PROJECT}/run1 the sentence is on the "
                                   f"page"].values())
            and all(record["measured"][f"{PROJECT}/run2 the sentence is on "
                                       f"the page"].values()),
        # RULE 1, ON SCREEN: a project exactly as it sits on a disk today,
        # opened by this build, shows the report it showed before. Its saved
        # verdict names none of the five rows, because the build that wrote it
        # could not judge them.
        "a saved report still says exactly what it said":
            all(v["word"] is None for v in
                record["measured"][f"{PROJECT}-as-delivered/run1 rows"]
                .values()),
    }
    record["verdicts"] = verdicts
    record["screen locked at start"] = session_is_locked()
    (out / "the-five-rows.json").write_text(json.dumps(record, indent=2),
                                            encoding="utf-8")
    print(json.dumps(verdicts, indent=2), flush=True)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
