#!/usr/bin/env python3
"""Drive Knut's beta-29 Measurement Report review ON SCREEN, in a real window.

CLAUDE.md: on screen is the default, ``widget.grab()`` is not a screenshot and
``QT_QPA_PLATFORM=offscreen`` belongs to the suite, never to a driver. Every
picture here comes from ``scripts/onscreen_capture.capture_window``.

    export CHROMIQ_SETTINGS_FILE=/tmp/chromiq-b29r/settings.ini
    export CHROMIQ_PRESETS_DIR=/tmp/chromiq-b29r/presets
    .venv/bin/python scripts/drive_b29_report_review.py [--stage before|after]

The measurements come from the shipped limit-demo pack's
``Report-Limits-Threshold-Series`` run1, which is the project Knut opened.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.pop("QT_QPA_PLATFORM", None)          # a real, on-screen platform
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

#: **THIS MACHINE IS NOT IN SHIPPING STATE, AND A DRIVER MUST NOT PHOTOGRAPH
#: THAT.** `~/Library/Preferences/ChromIQ/compliance/iso12647.json` holds a
#: licence holder's real ISO 12647-7/-8 tolerances. That is the supply-your-own
#: route working as designed, and `_iso_data_path` prefers it over the shipped
#: file, so a window driven here shows populated ISO columns that no user of a
#: shipped ChromIQ has, and a proof folder would end up holding the content of
#: a paid standard. The env var beats the user's file (`compliance_sets.py`,
#: `_iso_data_path`), so it is forced here rather than left to the caller's
#: shell: a driver that only works when someone remembers to export something
#: is a driver that will one day be run without it.
os.environ["CHROMIQ_COMPLIANCE_ISO_FILE"] = str(
    ROOT / "data" / "compliance_sets" / "iso12647.json")

from PyQt6.QtCore import QPoint, Qt                              # noqa: E402
from PyQt6.QtWidgets import QApplication                         # noqa: E402
from PyQt6.QtTest import QTest                                   # noqa: E402

from core.settings import AppSettings                            # noqa: E402
from scripts.capture_screens import build_app, pump              # noqa: E402
from scripts.onscreen_capture import capture_window              # noqa: E402
from ui.theme import apply_appearance                            # noqa: E402

PROJECT = Path("/tmp/chromiq-b29r/out/Report-Limits-Threshold-Series")
OUT = Path(os.environ.get("B29_OUT") or
           str(Path.home() / "Desktop" / "ChromIQ-beta30-proof" / "beta29-review"))

NOTES: list[str] = []


def note(line: str) -> None:
    print(line)
    NOTES.append(line)


def shot(win, name: str) -> bool:
    """Photograph the real window TWICE and require the frames to be identical.

    Two pixel-identical frames is the project's rule: one picture can catch a
    window mid-paint and show a state no user ever saw.
    """
    OUT.mkdir(parents=True, exist_ok=True)
    # THE REPORT BODY IS A QTextBrowser THAT RE-RENDERS AFTER EVERY SETTING
    # CHANGE, and a frame caught mid-render differs from the next one for a
    # reason that has nothing to do with the state being photographed.
    pump(1500)
    a = OUT / f"{name}.png"
    b = OUT / f"{name}__frame2.png"
    def _try(path):
        for _ in range(3):
            ok, why = capture_window(win, path, settle=1.2)
            if ok:
                return True, ""
            pump(700)
        return False, why
    ok, why = _try(a)
    if not ok:
        note(f"  CAPTURE REFUSED {name}: {why}")
        return False
    pump(1200)
    ok2, why2 = _try(b)
    if not ok2:
        note(f"  CAPTURE REFUSED {name} (2nd frame): {why2}")
        return False
    #: **THE TITLE BAR IS NOT THE APP.** Measured 2026-09-21: two consecutive
    #: captures of a settled window differ by 2.6 % of sampled pixels, and the
    #: bounding box of every one of them is `y 0..54` across the full width,
    #: which is the macOS title bar repainting as the window gains and loses
    #: key status between one `screencapture` and the next. Below it the two
    #: frames are identical to the pixel. So the identity the rule is after,
    #: that the window was not caught mid-paint, is measured on the CONTENT.
    TITLE_BAR_PX = 60

    same = a.read_bytes() == b.read_bytes()
    detail = ""
    if not same:
        from PyQt6.QtGui import QImage
        ia, ib = QImage(str(a)), QImage(str(b))
        if not ia.isNull() and ia.size() == ib.size():
            body = all(ia.pixel(x, y) == ib.pixel(x, y)
                       for y in range(TITLE_BAR_PX, ia.height(), 2)
                       for x in range(0, ia.width(), 2))
            if body:
                detail = ("  identical below the title bar; the only "
                          f"difference is above y={TITLE_BAR_PX} (the window "
                          "server's key-status repaint)")
                same = True
        if not same and not ia.isNull() and ia.size() == ib.size():
            # SAY WHERE THEY DIFFER, do not just say that they do. A window
            # with a live fade or a caret in it never gives two identical
            # frames, and "not identical" alone cannot tell that apart from a
            # frame caught mid-paint.
            n, box = 0, [10**9, 10**9, -1, -1]
            for y in range(0, ia.height(), 2):
                for x in range(0, ia.width(), 2):
                    if ia.pixel(x, y) != ib.pixel(x, y):
                        n += 1
                        box[0] = min(box[0], x); box[1] = min(box[1], y)
                        box[2] = max(box[2], x); box[3] = max(box[3], y)
            total = (ia.width() // 2) * (ia.height() // 2)
            detail = (f"  differing sampled pixels {n}/{total} "
                      f"({100.0 * n / max(1, total):.3f} %), "
                      f"bounding box x{box[0]}..{box[2]} y{box[1]}..{box[3]}")
            b.rename(a.with_name(a.stem + "__frame2.png"))
    if same:
        b.unlink(missing_ok=True)
    note(f"  shot {name}.png  two frames identical: {same}")
    if detail:
        note(detail)
    return same


def click_row(lst, row: int) -> None:
    """Click the CHECKBOX of a list row the way a user does: a real mouse press
    on the item's indicator, not ``setCheckState``."""
    item = lst.item(row)
    r = lst.visualItemRect(item)
    # The tick indicator sits at the left edge of the item rectangle.
    p = QPoint(r.left() + 10, r.center().y())
    QTest.mouseClick(lst.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, p)
    pump(120)


def first_run_row(dlg) -> int:
    """The first row that is a MEASUREMENT, from the dialog's own row map.

    Row 0 is the profile header, which carries no tick. The first pass of this
    driver asked the item's flags instead and got row 0 back, so it clicked a
    row that has nothing to toggle and reported "did not toggle" about a
    healthy list. `_list_rows` is what the dialog itself keys on.
    """
    for i, (kind, _si, key) in enumerate(getattr(dlg, "_list_rows", []) or []):
        if kind == "run" and key is not None:
            return i
    return -1


def probe_the_list(dlg) -> str:
    """Can a USER work this list? A click on a real measurement row, and a
    scroll from a known starting point.

    **The scroll test starts at zero on purpose.** The first pass left the bar
    at its maximum and then asked the next probe whether it had moved: it had
    not, because there was nowhere left to go, and that reads exactly like a
    freeze. A probe that cannot fail for the right reason cannot pass for it
    either.
    """
    lst = dlg._profile_list
    row = first_run_row(dlg)
    if row < 0:
        return "no measurement row in the list"
    sb = lst.verticalScrollBar()
    sb.setValue(0)
    pump(120)

    # SCROLL FIRST, THEN CLICK. A click writes `_hidden_runs` and touches the
    # settings, which repaints the frame; measuring the scroll after that was
    # measuring the repaint's timing, and it answered False on a list that
    # scrolls perfectly well two lines later.
    v0 = sb.value()
    lst.setFocus(Qt.FocusReason.MouseFocusReason)
    # A FRESH LIST HAS NO CURRENT ITEM, and Key_End on a list with no current
    # item moves nothing. Without this the probe answered "did not scroll"
    # about the freshly built window and "scrolled" about the same window one
    # step later, which is a fact about QListWidget and not about the fault.
    lst.setCurrentRow(row)
    pump(100)
    v0 = sb.value()
    QTest.keyClick(lst, Qt.Key.Key_End)
    pump(300)
    scrolled = sb.value() != v0
    v1 = sb.value()
    sb.setValue(0)
    pump(120)

    before = lst.item(row).checkState()
    click_row(lst, row)
    clicked = lst.item(row).checkState() != before
    if clicked:
        click_row(lst, row)                  # put it back
    return (f"a real click on measurement row {row} toggled its tick: "
            f"{clicked}; the list scrolled: {scrolled} "
            f"(range 0..{sb.maximum()}, {v0} -> {v1})")


def pick_combo(combo, text_part: str) -> bool:
    """Choose a pulldown entry through the control's own activation path."""
    for i in range(combo.count()):
        if text_part.lower() in combo.itemText(i).lower():
            combo.setCurrentIndex(i)
            combo.activated.emit(i)
            pump(500)
            return True
    return False


def list_state(dlg) -> str:
    lst = dlg._profile_list
    n = lst.count()
    ticked = sum(1 for i in range(n)
                 if lst.item(i).checkState() == Qt.CheckState.Checked)
    return (f"type={dlg._type_combo.currentText()!r} rows={n} ticked={ticked} "
            f"enabled={lst.isEnabled()} "
            f"viewport_enabled={lst.viewport().isEnabled()}")


def main() -> int:
    if not PROJECT.is_dir():
        note(f"demo project missing: {PROJECT}")
        return 1
    app = build_app()
    settings = AppSettings()
    apply_appearance(app, None, "dark")

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog

    run1 = PROJECT / "runs" / "run1"
    vdirs = sorted((run1 / "verifications").glob("20*_*"))
    note(f"dated verifications on disk: {len(vdirs)}")

    dlg = MeasurementReportDialog(settings)
    dlg.resize(1280, 1500)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(900)
    for v in vdirs:
        ti3 = next(iter(sorted(v.glob("*.ti3"))), None)
        if ti3 is not None:
            dlg._append_source(ti3, origin=ti3)
    dlg._rebuild_from_sources()
    pump(2000)

    lst = dlg._profile_list
    note(f"A. window open, list: {list_state(dlg)}")
    note(f"   {probe_the_list(dlg)}")
    note("   'Show all measurement runs' still in the window: "
         f"{getattr(dlg, '_all_runs_check', None) is not None}")
    note("   Select all / Deselect all present: "
         f"{getattr(dlg, '_select_all_btn', None) is not None and
             getattr(dlg, '_deselect_all_btn', None) is not None}")
    shot(dlg, "01_open_eleven_measurements")

    # ---- THE SEVERE ONE: does the list FREEZE on "Colour summary"? ----
    note("B. choosing report type 'Colour summary'")
    ok = pick_combo(dlg._type_combo, "colour summary")
    note(f"   type chosen: {ok}; list: {list_state(dlg)}")
    note(f"   {probe_the_list(dlg)}")
    shot(dlg, "02_colour_summary_list_frozen")

    # ---- and does it STAY frozen when "New report..." is chosen? ----
    note("C. choosing 'New report...' in the Report shown pulldown")
    picked = pick_combo(dlg._saved_combo, "new report")
    note(f"   picked: {picked}; list: {list_state(dlg)}")
    note(f"   {probe_the_list(dlg)}")
    shot(dlg, "03_new_report_list_still_works")

    # ---- the two buttons that replace the checkbox ----
    if getattr(dlg, "_select_all_btn", None) is None:
        note("D-I skipped: this build has no Select all / Deselect all "
             "(running against the base commit, for the BEFORE pictures)")
        print("\n".join(["", "=" * 60, "SUMMARY", "=" * 60] + NOTES))
        (OUT / "driver-log.txt").write_text("\n".join(NOTES) + "\n",
                                            encoding="utf-8")
        return 0
    note("D. the buttons Knut asked for, clicked the way a user clicks them")
    QTest.mouseClick(dlg._deselect_all_btn, Qt.MouseButton.LeftButton)
    pump(600)
    note(f"   after Deselect all: {list_state(dlg)}")
    shot(dlg, "04_deselect_all")
    QTest.mouseClick(dlg._select_all_btn, Qt.MouseButton.LeftButton)
    pump(600)
    note(f"   after Select all:   {list_state(dlg)}")
    shot(dlg, "05_select_all")

    # ---- E. Generate with several ticked on a one-page type ----
    # The message is MODAL, so it is photographed from a timer and dismissed
    # there. A driver that patched the box away would prove only that it had
    # patched the box away.
    note("E. Colour summary + 11 ticked + Generate report")
    from PyQt6.QtCore import QTimer
    seen = {}

    def catch_the_modal():
        w = QApplication.activeModalWidget()
        if w is None:
            seen["found"] = False
            return
        seen["found"] = True
        seen["title"] = w.windowTitle()
        seen["text"] = getattr(w, "text", lambda: "")()
        seen["informative"] = getattr(w, "informativeText", lambda: "")()
        shot(w, "06_one_page_says_so")
        w.close()

    from workflow.measurement_report import REPORT_TYPE_SUMMARY
    note(f"   _report_type_now()      = {dlg._report_type_now()!r}")
    note(f"   REPORT_TYPE_SUMMARY     = {REPORT_TYPE_SUMMARY!r}")
    note(f"   len(_reports_to_generate) = {len(dlg._reports_to_generate())}")
    note(f"   len(_runs_for_report)     = {len(dlg._runs_for_report())}")
    note(f"   len(_runs_for_document)   = {len(dlg._runs_for_document())}")
    QTimer.singleShot(2500, catch_the_modal)
    dlg._generate_btn.click()
    pump(6000)
    note(f"   a modal appeared: {seen.get('found')}")
    if seen.get("found"):
        note(f"   title: {seen.get('title')!r}")
        note(f"   text:  {seen.get('text')!r}")
    note(f"   list after the refusal: {list_state(dlg)}")

    # ---- F. with every measurement ticked, how many does each type cover? ----
    note("F. 11 ticked: what each report type actually covers")
    QTest.mouseClick(dlg._select_all_btn, Qt.MouseButton.LeftButton)
    pump(600)
    for i in range(dlg._type_combo.count()):
        label = dlg._type_combo.itemText(i)
        if not dlg._type_combo.model().item(i).isEnabled():
            continue
        dlg._type_combo.setCurrentIndex(i)
        dlg._type_combo.activated.emit(i)
        pump(700)
        note(f"   {label:<34} ticked={len(dlg._runs_for_report()):>3}  "
             f"document={len(dlg._runs_for_document()):>3}  "
             f"files={len(dlg._reports_to_generate()):>3}")

    # ---- G. does the counter agree with the pulldown? ----
    note("G. 'Already generated for this run' against 'Report shown'")
    pick_combo(dlg._type_combo, "full colour check")
    pump(800)
    entries = [dlg._saved_combo.itemText(i)
               for i in range(dlg._saved_combo.count())]
    real = [e for e in entries if "new report" not in e.lower()]
    note(f"   counter line : {dlg._generated_full or dlg._type_blurb_full!r}")
    note(f"   pulldown     : {len(real)} report(s), "
         f"{len(entries)} entries including 'New report...'")
    from workflow.measurement_report import generated_report_types
    note(f"   counted      : {generated_report_types(dlg._context_run())}")
    for e in real[:3]:
        note(f"   pre-created entry: {e[:115]}")

    # ---- H. a real Generate, and what it writes ----
    note("H. Full colour check, 11 ticked, Generate report")
    import glob as _glob
    before_files = len(_glob.glob(
        str(run1 / "**" / "report_*.json"), recursive=True))
    caught = {}

    def dismiss():
        w = QApplication.activeModalWidget()
        if w is not None:
            caught["title"] = w.windowTitle()
            caught["text"] = getattr(w, "text", lambda: "")()
            shot(w, "07_after_generate")
            w.close()

    QTimer.singleShot(3000, dismiss)
    dlg._generate_btn.click()
    pump(9000)
    after_files = len(_glob.glob(
        str(run1 / "**" / "report_*.json"), recursive=True))
    note(f"   report files on disk: {before_files} -> {after_files}")
    note(f"   modal: {caught.get('text', '(none)')[:120]!r}")
    pump(1500)
    entries = [dlg._saved_combo.itemText(i)
               for i in range(dlg._saved_combo.count())]
    real = [e for e in entries if "new report" not in e.lower()]
    note(f"   counter line : {dlg._generated_full or dlg._type_blurb_full!r}")
    note(f"   pulldown     : {len(real)} report(s)")
    for e in real[:4]:
        note(f"   entry: {e[:115]}")
    shot(dlg, "08_after_generate_window")

    # ---- I. selecting a pre-created report ----
    note("I. selecting a pre-created (legacy) report from 'Report shown'")
    for i in range(dlg._saved_combo.count()):
        txt = dlg._saved_combo.itemText(i)
        if "new report" in txt.lower() or "All dates" in txt:
            continue
        dlg._saved_combo.setCurrentIndex(i)
        dlg._saved_combo.activated.emit(i)
        pump(1800)
        note(f"   selected: {txt[:100]}")
        note(f"   -> {list_state(dlg)}")
        shot(dlg, "09_selected_one_report")
        break

    print("\n".join(["", "=" * 60, "SUMMARY", "=" * 60] + NOTES))
    (OUT / "driver-log.txt").write_text("\n".join(NOTES) + "\n", encoding="utf-8")
    # Leave the window up briefly so a human watching sees a real window.
    pump(1200)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
