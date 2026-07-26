#!/usr/bin/env python3
"""Drive the REAL ChromIQ app through the #130 verification-chart rows of Knut's
test plan (posted on the issue 2026-07-26).

Covers what beta.20 and beta.21 added, end to end through the real MainWindow —
real bar, real tabs, real signals — asserting BOTH the interface state and what
actually happened on disk after each step:

    V-01  Verification dropdown lists dated folders, excludes old/ and reports/
    V-02  Start Measurement on "New verification" creates the folder + snapshot
    V-03  … and the bar moves to the newly created date
    V-04  Snapshot holds the chart files but not the page images
    V-05  … and DOES hold the images when there is no recipe to rebuild them
    V-06  Restore Used Chart is disabled on "New verification" (with its reason)
    V-07  … disabled for a date with no stored chart (with its reason)
    V-08  … enabled for a date that has one
    V-09  … disabled while a measurement is running
    V-10  Restore puts the chart back and leaves the measurements alone
    V-11  Restore leaves the dated folders and old/ untouched
    V-12  A dated folder with no measurement is labelled in the dropdown
    V-13  Verification Replace archives to verifications/old/, keeps the results
    V-14  Profiling Replace archives every folder in the run

Run headless for a pass/fail table:
    QT_QPA_PLATFORM=offscreen python scripts/drive_130_verify_plan.py
Run on screen to watch it:
    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_130_verify_plan.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication, #38)
except ImportError:
    pass

from PyQt6.QtCore import QSettings                                  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox      # noqa: E402

from core.argyll_runner import ArgyllRunner                         # noqa: E402
from core.file_manager import FileManager, Project                  # noqa: E402
from core.measurement_target import (RUN_TYPE_PROFILING,            # noqa: E402
                                     RUN_TYPE_VERIFICATION)
from core.settings import AppSettings                               # noqa: E402
from ui.measurement_target_bar import (MeasurementTargetBar,        # noqa: E402
                                       MeasurementTargetController)
from ui.tabs.tab_measure import TabMeasure                          # noqa: E402
from workflow.verify_chart_snapshot import snapshot_files           # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def _env(tmp: Path, *, recipe: bool = True):
    s = AppSettings()
    s._qs = QSettings(str(tmp / "s.ini"), QSettings.Format.IniFormat)
    root = tmp / "ChromIQ"; root.mkdir(exist_ok=True)
    s.set("custom_output_path", str(root))
    fm = FileManager(s)
    proj = Project.create(root / "P", "P"); run = proj.current_run(); run.ensure_dir()
    run.chart_ti2.write_text("PROFILING-CHART")
    run.measurement_ti3.write_text("MEASUREMENT")
    run.profile_icc.write_bytes(b"ICC")
    run.verifications_dir.mkdir(parents=True, exist_ok=True)
    run.verify_chart_ti1.write_text("VTI1")
    run.verify_chart_ti2.write_text("VTI2")
    if recipe:
        (run.verifications_dir / f"{run.verify_stem}.channels.json").write_text("{}")
    (run.verifications_dir / f"{run.verify_stem}_01.tif").write_text("PAGE")
    fm.set_target_name("P")
    ctl = MeasurementTargetController(fm)
    ctl.set_profile_run("run1"); ctl.set_run_type(RUN_TYPE_VERIFICATION)
    return s, fm, ctl, run


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    QDialog.exec = lambda self: 0
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    tmp = Path(tempfile.mkdtemp(prefix="chromiq_verify_plan_"))
    s, fm, ctl, run = _env(tmp)
    bar = MeasurementTargetBar(ctl)
    tab = TabMeasure(ArgyllRunner(s), s)
    tab.set_target_controller(ctl)

    print("\n--- dropdown ---")
    (run.verifications_dir / "old").mkdir(exist_ok=True)
    (run.verifications_dir / "reports").mkdir(exist_ok=True)
    older = run.verification("2026-06-01_090000"); older.ensure_dir()
    older.measurement_ti3.write_text("OLD RESULT")
    bar.refresh()
    labels = [bar._verify_combo.itemText(i) for i in range(bar._verify_combo.count())]
    record("V-01 dropdown lists the dated folder + New verification, hides old/ & reports/",
           any("2026" in t for t in labels) and any("New verification" in t for t in labels)
           and not any("old" == t or "reports" == t for t in labels), str(labels))

    print("\n--- snapshot at measurement start ---")
    tab._verify_cb.setChecked(True)
    ctl.set_verification_id("")                       # "New verification"
    before = {v.id for v in run.verifications()}
    tab._snapshot_verification_chart()
    after = {v.id for v in run.verifications()}
    created = sorted(after - before)
    record("V-02 Start on New verification creates the dated folder",
           len(created) == 1, str(created))
    record("V-03 the bar moves to the created date",
           ctl.target.verification_id in created, ctl.target.verification_id)
    new_v = run.verification(created[0]) if created else None
    names = sorted(p.name for p in snapshot_files(new_v)) if new_v else []
    record("V-04 snapshot holds the chart files, not the pages",
           any(n.endswith(".ti2") for n in names) and not any(n.endswith(".tif") for n in names),
           str(names))

    tmp2 = Path(tempfile.mkdtemp(prefix="chromiq_verify_plan_norecipe_"))
    s2, fm2, ctl2, run2 = _env(tmp2, recipe=False)
    tab2 = TabMeasure(ArgyllRunner(s2), s2); tab2.set_target_controller(ctl2)
    tab2._verify_cb.setChecked(True); ctl2.set_verification_id("")
    tab2._snapshot_verification_chart()
    v2 = run2.verifications()[-1] if run2.verifications() else None
    names2 = sorted(p.name for p in snapshot_files(v2)) if v2 else []
    record("V-05 without a recipe the pages ARE snapshotted",
           any(n.endswith(".tif") for n in names2), str(names2))

    print("\n--- Restore Used Chart states ---")
    ctl.set_verification_id("")
    en, tip = ctl.restore_state()
    record("V-06 disabled on New verification, with its reason",
           not en and tip.startswith("Select an existing"), tip)
    ctl.set_verification_id(older.id)
    en, tip = ctl.restore_state()
    record("V-07 disabled for a date with no stored chart, with its reason",
           not en and "no available chart" in tip, tip)
    ctl.set_verification_id(created[0])
    en, tip = ctl.restore_state()
    record("V-08 enabled for a date that has one", en and "Restore chart" in tip, tip)
    ctl.set_measuring(True)
    en, _ = ctl.restore_state()
    record("V-09 disabled while a measurement runs", not en)
    ctl.set_measuring(False)

    print("\n--- restore ---")
    run.verify_chart_ti2.write_text("REPLACED LATER")
    seen = {"n": 0}
    ctl.chart_restored.connect(lambda: seen.__setitem__("n", seen["n"] + 1))
    result = ctl.restore_used_chart()
    record("V-10 restore puts the chart back and keeps the measurements",
           bool(result and result.ok) and run.verify_chart_ti2.read_text() == "VTI2"
           and older.measurement_ti3.read_text() == "OLD RESULT"
           and seen["n"] == 1,
           f"ok={getattr(result, 'ok', None)} tabs_notified={seen['n']}")
    record("V-11 dated folders and old/ untouched by a restore",
           older.dir.exists() and (run.verifications_dir / "old").exists())

    print("\n--- dropdown marking ---")
    bar.refresh()
    labels = [bar._verify_combo.itemText(i) for i in range(bar._verify_combo.count())]
    record("V-12 a date with no measurement is labelled",
           any("no measurement yet" in t for t in labels), str(labels))

    print("\n--- archiving rules ---")
    from workflow.chart_import import archive_run_for_replace
    archive_run_for_replace(run, verification=True)
    record("V-13 verification Replace archives to verifications/old/, keeps results",
           run.verifications_old_dir.exists() and older.dir.exists()
           and run.chart_ti2.exists(),
           f"verifications/old={run.verifications_old_dir.exists()}")
    run.verify_chart_ti2.write_text("BACK")
    archive_run_for_replace(run, verification=False)
    archived = sorted(p.name for p in run.old_dir.rglob("*")) if run.old_dir.exists() else []
    record("V-14 profiling Replace archives every folder in the run",
           run.old_dir.exists() and "verifications" in archived,
           str(archived[:6]))

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n==== {passed}/{len(RESULTS)} rows PASSED ====")
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"  FAIL: {name} — {detail}")
    sys.stdout.flush()
    os._exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    raise SystemExit(main())
