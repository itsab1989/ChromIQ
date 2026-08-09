#!/usr/bin/env python3
"""T10 — drive the real Print Chart tab through feature A, end to end on disk.

Builds a real project with a verification chart (a real RGB TIFF page), gives
the run a real RGB profile (Argyll's sRGB.icm standing in for a printer
profile — cctiff happily converts RGB→RGB), selects Run type = Verification,
and presses BOTH print buttons. The submission to CUPS is captured at
``CupsRawPrinter.print_job_ps`` — nothing reaches a printer — but everything
before that is real: the real widgets, the real state machine, the real
``cctiff`` from the configured ArgyllCMS install, real files.

Checks, all on disk:
  1. both buttons funnel through the conversion (T4),
  2. the converted sheets land in ``verifications/cache/`` and differ from the
     sources (T2),
  3. the print record beside the chart says through-profile · intent · route
     (A15–A18),
  4. raw selected → the untouched pages are submitted and the record says raw,
  5. a chart with a colorimetric reference forces Raw on the real widgets (T11).

Run with the app's own venv:

    QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/drive_verification_print_a.py

Drop the offscreen platform to watch it happen on screen — the checks are the
same either way.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FAILURES: list[str] = []


def check(what: str, ok: bool, detail: str = "") -> None:
    print(f"  {'OK  ' if ok else 'FAIL'} {what}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(what)


def main() -> int:
    from PIL import Image
    from PyQt6.QtCore import QSettings
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])

    from core.file_manager import FileManager, Project
    from core.measurement_target import RUN_TYPE_VERIFICATION
    from core.settings import AppSettings
    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_print import TabPrint
    from workflow import verification_print as vp
    from workflow.cups_printer import CupsRawPrinter

    bin_dir = Path("/Applications/Argyll/bin")
    srgb = bin_dir.parent / "ref" / "sRGB.icm"
    if not (bin_dir / "cctiff").exists() or not srgb.exists():
        print("ArgyllCMS with cctiff + ref/sRGB.icm is required for this drive.")
        return 2

    td = Path(tempfile.mkdtemp(prefix="chromiq-drive-a-"))
    try:
        s = AppSettings()
        s._qs = QSettings(str(td / "s.ini"), QSettings.Format.IniFormat)
        s.set("custom_output_path", str(td))
        s.set("argyll_bin_path", str(bin_dir))
        s.set("use_native_print_dialog", False)
        fm = FileManager(s)
        Project.create(td / "Drive-A", "Drive-A").current_run().ensure_dir()
        fm.set_target_name("Drive-A")
        ctl = MeasurementTargetController(fm)

        run = fm.project().run("run1")
        run.verifications_dir.mkdir(parents=True, exist_ok=True)
        ti2 = run.verify_chart_ti2
        ti2.write_text("CTI2\n")
        # A real RGB page with saturated colours, so the conversion has work.
        page = run.verifications_dir / f"{run.verify_stem}_01.tif"
        img = Image.new("RGB", (300, 200))
        for x in range(300):
            for y in range(200):
                img.putpixel((x, y), (x * 255 // 299, y * 255 // 199, 128))
        img.save(page, format="TIFF")
        shutil.copyfile(srgb, run.profile_icc)   # the "printer" profile

        ctl.set_profile_run("run1")
        ctl.set_run_type(RUN_TYPE_VERIFICATION)

        tab = TabPrint(s)
        tab.set_target_controller(ctl)
        tab._current_ti2 = ti2
        tab.load_tiffs([page])
        tab._preview._pages = [(page, 0)]
        tab._preview._current = 0

        submitted: list[Path] = []
        tab._printer.print_job_ps = (           # capture the CUPS hand-off
            lambda path, config, on_finish=None, **kw: (
                submitted.append(Path(path)),
                on_finish and on_finish(0)))
        # Pre-send checks would talk to real CUPS — neutralise them, keep the
        # geometry/preflight path itself.
        tab._printer.is_printer_reachable = lambda p: True
        tab._module.get_stuck_jobs = lambda p: []
        tab._module.detect_printers = lambda: ["DrivePrinter"]
        tab._module.query_options = lambda p: {}
        tab._module.build_config = lambda printer, options: {"printer": printer}
        tab._printer_combo.addItem("DrivePrinter", "DrivePrinter")
        s.set("confirm_before_printing", False)

        print("\n-- through the profile, both buttons --")
        check("the Colour row offers both options",
              tab._cm_through_rb.isEnabled() and tab._cm_raw_rb.isEnabled())
        check("default is through the profile (no history)",
              tab._cm_through_rb.isChecked())

        tab._on_print_current()
        cache = run.verifications_dir / "cache"
        conv = cache / page.name
        check("converted sheet exists in verifications/cache/", conv.exists())
        check("converted sheet differs from the source",
              conv.exists() and conv.read_bytes() != page.read_bytes())
        check("the CUPS path received the CONVERTED sheet",
              submitted == [conv], str(submitted))

        submitted.clear()
        tab._on_print_all()
        check("Print All converts too (T4)", submitted == [conv])

        rec = json.loads(vp.print_record_path(ti2).read_text())
        check("record: colour through-profile", rec["colour"] == "through-profile")
        check("record: intent relative", rec["intent"] == "relative")
        check("record: route chromiq", rec["route"] == "chromiq")
        check("record: profile + mtime recorded",
              rec.get("profile") == run.profile_icc.name and rec.get("profile_mtime"))

        print("\n-- raw, deliberately --")
        submitted.clear()
        tab._cm_raw_rb.setChecked(True)
        tab._on_print_current()
        check("raw submits the untouched page", submitted == [page])
        rec = json.loads(vp.print_record_path(ti2).read_text())
        check("record now says raw, no intent",
              rec["colour"] == "raw" and rec["intent"] == "")

        print("\n-- a chart that is already converted (§3.1a) --")
        vp.colorimetric_reference_for(ti2).write_text("CTI3\n")
        tab._update_colour_row_visible()
        check("through is DISABLED, not merely deselected",
              not tab._cm_through_rb.isEnabled())
        check("raw is selected and the print would go raw",
              tab._cm_selected_colour() == "raw")

        print()
        if FAILURES:
            print(f"{len(FAILURES)} check(s) FAILED")
            return 1
        print("all checks passed — files verified on disk at " + str(td))
        return 0
    finally:
        shutil.rmtree(td, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
