#!/usr/bin/env python3
"""Drive the pairing-3 batch in the real widgets, on screen, with real Argyll.

What it shows (each window pauses so it can be seen) and checks:

  1. The **"How was this sheet printed?"** window (M-HOW-PRINTED): a
     measurement is imported whose sheet ChromIQ did not print — the real
     import handler raises the question, the drive answers
     **With colour management**, and the print record on disk must say
     ``through-profile / external-cm / asked-at-measure`` with no
     ``printed_at`` claim.
  2. The **measurement report** built from that date must switch to the
     media-relative yardstick, and the report dialog must show the new
     "How the colours were judged" row and the external-cm wording.
  3. The **Welcome card** "Check a finished profile (verification run)"
     (rewritten — the old step 3 described a colour-management workflow the
     app deliberately prevents) and the **Dictionary** with its two new
     entries.
  4. The **Measurement info** tool placed deliberately too low must be
     nudged fully back on screen (the shared ``pin_min_height`` fix).

Stages a COPY of ``~/ChromIQ/printer-test`` — the original is never touched.

Run on screen (windows appear and drive themselves):

    .venv/bin/python scripts/drive_pairing3_onscreen.py

or headless with QT_QPA_PLATFORM=offscreen — the checks are identical, only
the pauses are skipped.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QSettings, QTimer                  # noqa: E402
from PyQt6.QtGui import QFontDatabase, QGuiApplication      # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,         # noqa: E402
                             QMessageBox)

from core.resource_path import resource_path                # noqa: E402

FAILURES: list[str] = []
ARGYLL = Path("/Applications/Argyll/bin")
ON_SCREEN = os.environ.get("QT_QPA_PLATFORM", "") != "offscreen"
# Optional: save a PNG of every window shown (CHROMIQ_SHOTS=<dir>).
SHOT_DIR = os.environ.get("CHROMIQ_SHOTS", "")
SHOT_N = [0]


def shot(widget, name: str) -> None:
    if not SHOT_DIR:
        return
    d = Path(SHOT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    SHOT_N[0] += 1
    out = d / f"{SHOT_N[0]:02d}-{name}.png"
    widget.grab().save(str(out))
    print(f"  shot {out.name}")


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(what)


def pump(app, ms: int = 200) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def pause(app, ms: int) -> None:
    """A LOOK-AT-THIS pause — skipped headless and in screenshot runs."""
    pump(app, ms if ON_SCREEN and not SHOT_DIR else 300)


class HowPrintedAnswerer:
    """Answer the modals of the import flow: the how-printed question gets
    **With colour management** (after a pause so it can be seen); every other
    modal is recorded and dismissed."""

    def __init__(self, app) -> None:
        self.app = app
        self.titles: list[str] = []
        self.answered_how_printed = False
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(150)

    def _tick(self) -> None:
        w = self.app.activeModalWidget()
        if w is None:
            return
        got = w.windowTitle()
        if isinstance(w, QMessageBox):
            got = w.text() or got
        if got in self.titles[-1:]:
            return                        # still the same box, keep waiting
        self.titles.append(got)
        if isinstance(w, QMessageBox) and "How was this sheet printed" in got:
            def _answer(box=w):
                shot(box, "how-was-this-sheet-printed")
                for b in box.buttons():
                    if "colour management" in b.text().lower():
                        self.answered_how_printed = True
                        b.click()
                        return
                box.reject()
            QTimer.singleShot(8000 if ON_SCREEN else 100, _answer)
        elif isinstance(w, (QDialog, QMessageBox)):
            def _dismiss(box=w):
                if isinstance(box, QMessageBox) \
                        and "imported" in (box.text() or "").lower():
                    shot(box, "measurement-imported")
                box.reject()
            QTimer.singleShot(
                3000 if ON_SCREEN and not SHOT_DIR else 400, _dismiss)


def main() -> int:
    if not (ARGYLL / "fakeread").exists():
        print("ArgyllCMS is required.")
        return 2
    src_project = Path.home() / "ChromIQ" / "printer-test"
    if not (src_project / "runs" / "run1" / "printer-test.icc").exists():
        print("~/ChromIQ/printer-test with a built profile is required.")
        return 2

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    try:
        for fp in Path(resource_path("assets/fonts")).glob("*.ttf"):
            QFontDatabase.addApplicationFont(str(fp))
    except Exception:      # noqa: BLE001
        pass
    from ui import styles
    app.setStyle(styles.WinButtonLayoutStyle("Fusion"))
    app.setPalette(styles.make_dark_palette())
    app.setStyleSheet(styles.APP_STYLESHEET)

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_pairing3_drive_"))
    work = sandbox / "working"
    work.mkdir()
    shutil.copytree(src_project, work / "printer-test")
    print(f"staged copy: {work / 'printer-test'}")

    from core.argyll_runner import ArgyllRunner
    from core.file_manager import FileManager
    from core.measurement_target import (RUN_TYPE_VERIFICATION, resolve_run)
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_measure import TabMeasure

    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "drive.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(work))
    settings.set("argyll_bin_path", str(ARGYLL))
    # Match the styling the drive forces: without this the sandbox is
    # "auto", which follows the SYSTEM theme — on a light-mode Mac the
    # trend charts rendered light inside the force-dark window.
    settings.set("appearance", "dark")
    fm = FileManager(settings)
    fm.set_target_name("printer-test")
    ctl = MeasurementTargetController(fm)
    tab = TabMeasure(ArgyllRunner(settings), settings)
    tab.set_target_controller(ctl)
    tab.resize(1500, 1100)
    tab.show()
    pump(app, 400)

    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app)
    run = resolve_run(fm.project(), ctl.target)
    if not run.has_verify_chart():
        print("the staged run has no verification chart — cannot continue")
        return 2

    print("\n== 1. the measure-time question (M-HOW-PRINTED) ==")
    tab._import_btn.click()
    pump(app, 300)
    outside = sandbox / "from_i1profiler"
    outside.mkdir()
    shutil.copy2(run.verify_chart_ti1, outside / "printer-test-verify.ti1")
    shutil.copy2(run.verify_chart_ti2, outside / "printer-test-verify.ti2")
    r = subprocess.run(
        [str(ARGYLL / "fakeread"), str(run.built_profile_icc()),
         str(outside / "printer-test-verify")],
        cwd=str(outside), capture_output=True, text=True, timeout=120)
    src_ti3 = outside / "printer-test-verify.ti3"
    check("fakeread produced the outside measurement",
          r.returncode == 0 and src_ti3.exists(),
          (r.stderr or r.stdout).strip()[:80])
    if not src_ti3.exists():
        return 1

    answerer = HowPrintedAnswerer(app)
    tab._import_path = src_ti3
    tab._update_import_panel()
    pump(app)
    tab._import_go_btn.click()
    pump(app, 800)
    # wait for the answer + the done window to pass
    t0 = time.time()
    while time.time() - t0 < 30 and app.activeModalWidget() is not None:
        pump(app, 200)
    check("the how-printed window appeared",
          any("How was this sheet printed" in t for t in answerer.titles),
          "; ".join(answerer.titles)[:120])
    check("it was answered 'With colour management'",
          answerer.answered_how_printed)
    answerer.timer.stop()

    vid = ctl.target.verification_id
    v = run.verification(vid) if vid else None
    dst = v.measurement_ti3 if v else None
    check("measurement filed in the dated folder",
          dst is not None and dst.exists(), str(dst))
    if dst is None or not dst.exists():
        return 1
    rec_path = dst.parent / f"{dst.stem}.print.json"
    check("print record written beside the dated measurement", rec_path.exists())
    rec = json.loads(rec_path.read_text()) if rec_path.exists() else {}
    check("record says through-profile via external colour management",
          rec.get("colour") == "through-profile"
          and rec.get("route") == "external-cm"
          and rec.get("intent") == "unknown", json.dumps(rec)[:100])
    check("record is marked as answered at measure time, with no printed_at",
          rec.get("recorded") == "asked-at-measure" and "printed_at" not in rec)

    print("\n== 2. the media-relative yardstick in the report ==")
    from workflow.measurement_report import build_report
    rep = build_report(dst)
    check("report picked the media-relative yardstick",
          rep.get("yardstick") == "media-relative", rep.get("yardstick"))
    pw = (rep.get("paper_white") or {}).get("lab") or [None]
    check("physical paper white stays as measured (absolute, not 100)",
          pw[0] is not None and 50.0 < float(pw[0]) < 99.5, str(pw))

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, None, initial_ti3=dst)
    dlg.show()
    pump(app, 600)
    html = dlg._printing_block_html(rep)
    check("report names the new 'How the colours were judged' row",
          "How the colours were judged" in html)
    check("report says the sheet came from another app with colour management",
          "another application with colour management" in html)
    label = dlg._run_row_label(rep)
    check("run row labels the method 'printed in another app …'",
          "another app with colour management" in label, label)
    shot(dlg, "measurement-report-media-relative")
    pause(app, 8000)
    dlg.close()

    print("\n== 3. the rewritten Welcome card + the two Dictionary entries ==")
    from ui.dialogs import welcome_dialog as wd
    card = next(w for w in wd.WORKFLOWS if w["key"] == "verify")
    steps = " ".join(s for _, s in card["steps"])
    check("card step 3 now names the Print Chart tab's Colour row",
          "“Colour” row" in steps and "colour management ON" not in steps)
    check("card no longer claims 'assign/convert in your print path'",
          "assign/convert" not in steps)
    check("card points at the exact Tools entry",
          "Measurement report (accuracy & drift)" in steps)
    terms = [t for t, _ in wd.GLOSSARY]
    check("Dictionary holds 'Which verification should I use?'",
          any("Which verification should I use" in t for t in terms))
    check("Dictionary holds the media-relative entry",
          any("media-relative" in t for t in terms))
    wdlg = wd.WelcomeDialog(settings)
    wdlg.show()
    pump(app, 300)
    wdlg._on_card_clicked("verify")
    pump(app, 300)
    shot(wdlg, "welcome-card-check-a-finished-profile")
    pause(app, 8000)
    wdlg._on_card_clicked("glossary")
    pump(app, 300)
    try:
        from PyQt6.QtWidgets import QLabel, QScrollArea
        target = next(l for l in wdlg.findChildren(QLabel)
                      if l.isVisible()
                      and "Which verification should I use" in l.text())
        sa, parent = None, target.parentWidget()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                sa = parent
                break
            parent = parent.parentWidget()
        if sa is not None:
            sa.ensureWidgetVisible(target, 0, 200)
            pump(app, 200)
    except StopIteration:
        pass
    shot(wdlg, "dictionary-which-verification-should-i-use")
    pause(app, 6000)
    wdlg.close()

    print("\n== 4. the Measurement info tool opens fully on screen ==")
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    runner = ArgyllRunner(settings)
    info = Ti3InfoDialog(runner, settings)
    area = (info.screen() or QGuiApplication.primaryScreen()).availableGeometry()
    info.move(area.left() + 60, area.bottom() - 120)   # bottom guaranteed out
    info.show()
    pump(app, 500)
    frame = info.frameGeometry()
    check("window bottom is on screen", frame.bottom() <= area.bottom(),
          f"bottom {frame.bottom()} vs screen {area.bottom()}")
    check("window top is on screen", frame.top() >= area.top())
    shot(info, "measurement-info-fully-on-screen")
    pause(app, 4000)
    info.close()
    tab.close()

    print(f"\n{'ALL OK' if not FAILURES else f'{len(FAILURES)} FAILURES'}")
    for f in FAILURES:
        print(f"  FAIL {f}")
    shutil.rmtree(sandbox, ignore_errors=True)
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
