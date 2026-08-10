#!/usr/bin/env python3
"""Drive the Measure tab's IMPORT module in the real widgets, with real Argyll.

Stages a COPY of ``~/ChromIQ/printer-test`` (the original is never touched),
then, in the real TabMeasure with the app's real styling:

  1. checks the IMPORT mode button appears only for a verification run and
     that entering the module swaps the action row for Import Measurement,
  2. fabricates a measurement OUTSIDE the project with Argyll ``fakeread``
     (measurement data is never written by hand) — the file a user would get
     back from i1Profiler,
  3. presses the real Import Measurement button and lets the real handler
     convert, validate, snapshot and file it,
  4. verifies every artefact: the dated folder, the CHROMIQ_VERIFICATION
     keyword, the chart snapshot, the untouched original, value-identical
     colour data, and the measurement report built from the imported file,
  5. checks the two refusals on screen: importing onto a date that already
     holds a measurement, and a file that does not match the chart.

The i1Profiler ``.txt``/``.mxf`` conversion path is covered by the unit tests
and the real 550-patch round trip (2026-08-08); this drive uses the ``.ti3``
passthrough so every value on disk comes from Argyll.

Run on screen (the window appears and drives itself):

    .venv/bin/python scripts/drive_import_module_onscreen.py

or headless with QT_QPA_PLATFORM=offscreen — the checks are identical.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PyQt6.QtCore import QSettings, QTimer                  # noqa: E402
from PyQt6.QtGui import QFontDatabase                       # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from core.resource_path import resource_path                # noqa: E402

FAILURES: list[str] = []
ARGYLL = Path("/Applications/Argyll/bin")


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(what)


def pump(app, ms: int = 200) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


class ModalCloser:
    """Auto-close every modal the drive raises, recording its title."""

    def __init__(self, app) -> None:
        self.app = app
        self.titles: list[str] = []
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.timer.start(150)

    def _tick(self) -> None:
        w = self.app.activeModalWidget()
        if w is None:
            return
        # macOS ignores QMessageBox.setWindowTitle — read the text instead.
        got = w.windowTitle()
        if isinstance(w, QMessageBox):
            got = w.text() or got
        self.titles.append(got)
        if isinstance(w, (QDialog, QMessageBox)):
            w.reject()


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

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq_import_drive_"))
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
    fm = FileManager(settings)
    fm.set_target_name("printer-test")
    ctl = MeasurementTargetController(fm)
    tab = TabMeasure(ArgyllRunner(settings), settings)
    tab.set_target_controller(ctl)
    tab.resize(1500, 1100)
    tab.show()
    pump(app, 400)

    run = None
    print("\n-- the module appears only for a verification --")
    check("IMPORT hidden for a profiling target",
          not tab._import_btn.isVisible())
    ctl.set_profile_run("run1")
    ctl.set_run_type(RUN_TYPE_VERIFICATION)
    pump(app)
    run = resolve_run(fm.project(), ctl.target)
    if not run.has_verify_chart():
        print("the staged run has no verification chart — cannot continue")
        return 2
    check("IMPORT button appears", tab._import_btn.isVisible())
    tab._import_btn.click()
    pump(app, 300)
    check("stack shows the import panel", tab._stack.currentIndex() == 2)
    check("Import Measurement stands where Start stood",
          tab._import_go_btn.isVisible() and not tab._start_btn.isVisible())
    check("no file yet → button disabled with a reason",
          not tab._import_go_btn.isEnabled()
          and "folder button" in tab._import_go_btn.toolTip())
    body = tab._import_box_body.text()
    check("info box names the chart and the destination",
          run.verify_chart_ti2.name in body
          and str(run.verifications_dir) in body, body[:80])

    print("\n-- fakeread fabricates the 'i1Profiler' file, outside the project --")
    outside = sandbox / "from_i1profiler"
    outside.mkdir()
    # fakeread reads <base>.ti1 and writes <base>.ti3.
    shutil.copy2(run.verify_chart_ti1, outside / "printer-test-verify.ti1")
    shutil.copy2(run.verify_chart_ti2, outside / "printer-test-verify.ti2")
    r = subprocess.run(
        [str(ARGYLL / "fakeread"), str(run.built_profile_icc()),
         str(outside / "printer-test-verify")],
        cwd=str(outside), capture_output=True, text=True, timeout=120)
    src_ti3 = outside / "printer-test-verify.ti3"
    check("fakeread produced the measurement",
          r.returncode == 0 and src_ti3.exists(),
          (r.stderr or r.stdout).strip()[:80])
    if not src_ti3.exists():
        return 1
    original_bytes = src_ti3.read_bytes()

    print("\n-- the real button files it --")
    closer = ModalCloser(app)
    tab._import_path = src_ti3
    tab._update_import_panel()
    pump(app)
    check("button enabled once a file is chosen", tab._import_go_btn.isEnabled())
    tab._import_go_btn.click()
    pump(app, 800)
    vid = ctl.target.verification_id
    check("the bar moved to a new dated verification", bool(vid), vid)
    v = run.verification(vid) if vid else None
    dst = v.measurement_ti3 if v else None
    check("measurement filed in the dated folder",
          dst is not None and dst.exists(), str(dst))
    check("the done window was shown",
          any("imported" in t.lower() for t in closer.titles),
          "; ".join(closer.titles))
    if dst is None or not dst.exists():
        return 1
    text = dst.read_text()
    check("CHROMIQ_VERIFICATION keyword stamped",
          'CHROMIQ_VERIFICATION "true"' in text)
    from workflow.verify_chart_snapshot import has_snapshot
    check("chart snapshot stored with the date", has_snapshot(v))
    check("the user's original is untouched",
          src_ti3.read_bytes() == original_bytes)

    from workflow.ti3_analysis import parse_ti3
    import numpy as np
    a, b = parse_ti3(src_ti3), parse_ti3(dst)
    check("filed copy carries identical colour data",
          a.n_patches == b.n_patches
          and np.allclose(a.rgb, b.rgb) and np.allclose(a.xyz, b.xyz),
          f"{a.n_patches} patches")

    from workflow.measurement_report import build_report
    rep = build_report(dst)
    check("measurement report builds from the imported file",
          bool(rep.get("de00")), str(rep.get("reference_source")))
    if rep.get("reference_source") == "colorimetric":
        de = rep.get("de00") or {}
        check("fakeread round trip is near-perfect (sanity)",
              de.get("mean", 99) < 3.0, f"mean={de.get('mean')}")

    print("\n-- refusals: taken date, mismatching file --")
    closer.titles.clear()
    tab._import_go_btn.click()      # same date now holds a measurement
    pump(app, 500)
    check("importing onto the taken date is refused",
          any("already holds" in t.lower() for t in closer.titles),
          "; ".join(closer.titles))
    before = sorted(p.name for p in run.verifications_dir.iterdir())

    # A deliberately truncated file must be refused by the count check.
    lines = src_ti3.read_text().splitlines()
    cut = outside / "truncated.ti3"
    n_sets = next(i for i, ln in enumerate(lines) if "NUMBER_OF_SETS" in ln)
    end = next(i for i, ln in enumerate(lines) if ln.strip() == "END_DATA")
    kept = lines[:end - 5] + ["END_DATA"]
    kept[n_sets] = f"NUMBER_OF_SETS {int(lines[n_sets].split()[1]) - 5}"
    cut.write_text("\n".join(kept) + "\n")
    closer.titles.clear()
    ctl.set_verification_id("")     # "New verification" again
    pump(app)
    tab._import_path = cut
    tab._update_import_panel()
    tab._import_go_btn.click()
    pump(app, 500)
    check("a mismatching file is refused",
          any("does not match" in t.lower() for t in closer.titles),
          "; ".join(closer.titles))
    after = sorted(p.name for p in run.verifications_dir.iterdir())
    check("nothing was filed for the refused imports", before == after)

    closer.timer.stop()
    print(f"\n{'ALL CHECKS PASSED' if not FAILURES else f'{len(FAILURES)} FAILURES'}")
    print(f"sandbox kept for inspection: {sandbox}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())
