#!/usr/bin/env python3
"""Walk the demo package's own steps in the REAL app and check each one.

Knut, #130 2026-08-04: *"perform the exact tests in the demo project package,
step-by-step, via on-screen control of chromIQ app and verify that every step is
described to correctly work according to the test description readme.md."*

So this drives the real ``MainWindow`` — real fonts, real styling, real event
loop — against a copy of the built package, performs the action each step
describes, and compares the window that actually appears with the message ID
the step promises. The steps are read from ``make_demo_package.CASES``, which is
what generates the README, so the two cannot describe different tests.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_demo_package.py [package-dir]

Every step is isolated: one failure never stops the walk, and the run ends with
a PASS/FAIL table.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ONSCREEN = bool(os.environ.get("CHROMIQ_DRIVE_ONSCREEN"))
if not ONSCREEN:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401  (before QApplication)
except ImportError:
    pass

from PyQt6.QtCore import QSettings, QTimer                     # noqa: E402
from PyQt6.QtGui import QFontDatabase                          # noqa: E402
from PyQt6.QtWidgets import (QApplication, QDialog,            # noqa: E402
                             QMessageBox)

RESULTS: "list[tuple[str, bool, str]]" = []


#: Steps the package documents that this driver does not check. Kept separate
#: from RESULTS so they can never be counted as passing.
NOT_DRIVEN: "list[tuple[str, bool]]" = []


def record(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   — {detail}" if detail else ""))


def pump(app, ms: int = 250) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def build_app():
    from core.resource_path import resource_path
    from ui.styles import WinButtonLayoutStyle
    from ui.widgets import ButtonFontFilter, GroupBoxSurfaceFilter
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("ChromIQ")
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    app.installEventFilter(ButtonFontFilter(app))
    app.installEventFilter(GroupBoxSurfaceFilter(app))
    return app


# ---------------------------------------------------------------------------
# Catching the window a step raises, without answering for the user by accident
# ---------------------------------------------------------------------------
class Caught:
    """The windows raised since the last :meth:`reset`."""

    def __init__(self) -> None:
        self.titles: list[str] = []
        self.texts: list[str] = []
        self.answer = "reject"          # "accept" presses the go-ahead button

    def reset(self, answer: str = "reject") -> None:
        self.titles.clear()
        self.texts.clear()
        self.answer = answer

    def install(self) -> None:
        caught = self

        def _msg_exec(box):
            caught.titles.append(box.windowTitle() or box.text())
            caught.texts.append((box.text() or "") + "\n"
                                + (box.informativeText() or ""))
            for b in box.buttons():
                role = box.buttonRole(b).name
                want = "AcceptRole" if caught.answer == "accept" else "RejectRole"
                if role == want:
                    box.setClickedButtonForTest(b) if hasattr(
                        box, "setClickedButtonForTest") else None
                    return 0
            return 0

        def _dlg_exec(dlg):
            caught.titles.append(dlg.windowTitle())
            from PyQt6.QtWidgets import QLabel
            caught.texts.append("\n".join(
                lbl.text() for lbl in dlg.findChildren(QLabel)))
            return int(QDialog.DialogCode.Accepted if caught.answer == "accept"
                       else QDialog.DialogCode.Rejected)

        QMessageBox.exec = _msg_exec            # type: ignore[assignment]
        QDialog.exec = _dlg_exec                # type: ignore[assignment]
        for m in ("warning", "critical", "information", "question"):
            setattr(QMessageBox, m, staticmethod(
                lambda *a, **k: caught.titles.append(str(a[1]) if len(a) > 1 else "")
                or 0))

    def saw(self, headline: str) -> bool:
        needle = headline.lower()[:48]
        return any(needle in (t or "").lower() for t in self.titles + self.texts)


CAUGHT = Caught()


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "demo-package"
    if not src.exists():
        print(f"No package at {src}; run scripts/make_demo_package.py first")
        return 2

    sys.path.insert(0, str(ROOT / "scripts"))
    from make_demo_package import CASES                        # noqa: E402
    from workflow import measurement_messages as M             # noqa: E402

    sandbox = Path(tempfile.mkdtemp(prefix="chromiq-demo-drive-"))
    work = sandbox / "ChromIQ"
    shutil.copytree(src, work)
    print(f"Sandbox: {work}\n")

    app = build_app()
    CAUGHT.install()
    from core.settings import AppSettings
    settings = AppSettings()
    settings._qs = QSettings(str(sandbox / "s.ini"), QSettings.Format.IniFormat)
    settings.set("custom_output_path", str(work))
    settings.set("show_welcome_dialog", False)
    settings.set("chartread_engine", "argyll")     # Knut's setting for the tests

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    if ONSCREEN:
        win.show(); win.raise_(); win.activateWindow()
    pump(app, 600)

    fm = win._file_mgr
    tab_chart, tab_measure = win._tab_chart, win._tab_measure
    ctl = getattr(tab_measure, "_target_ctl", None)
    from core.measurement_target import (RUN_TYPE_PROFILING,
                                         RUN_TYPE_VERIFICATION)

    for case in CASES:
        name = case["name"]
        if not (work / name).exists():
            continue
        print(f"\n=== {name} ===")
        fm.set_target_name(name)
        if ctl is not None:
            ctl.set_profile_run("run1")
            ctl.set_run_type(RUN_TYPE_PROFILING)
        pump(app, 300)

        # Each project starts from a clean slate: a chart left loaded from the
        # previous one made every window describe the wrong run.
        tab_measure.clear_chart_file()
        run1_ti2 = work / name / "runs" / "run1" / f"{name}.ti2"
        if run1_ti2.exists():
            tab_measure.set_ti1_path(run1_ti2)
        pump(app, 200)

        for i, step in enumerate(case["steps"], 1):
            ids = re.findall(r"\[\[(M-[A-Z0-9-]+)\]\]", step)
            plain = re.sub(r"\s*\[\[[^\]]+\]\]", "", step)
            first = ids[0] if ids else None
            msg = M.CATALOGUE.get(first) if first else None
            label = f"{name} step {i}"

            # --- perform what the step describes ------------------------
            CAUGHT.reset("reject")
            try:
                lowered = plain.lower()
                # "Set Profile run = run 3" — the step says which run it works
                # on, so the driver must follow it or every window describes
                # run 1.
                m = (re.search(r"profile run = \*{0,2}run ?(\d+)", lowered)
                     or re.search(r"switch to \*{0,2}run ?(\d+)", lowered)
                     or re.search(r"^\*{0,2}run ?(\d+)\*{0,2} ?—", lowered)
                     or re.search(r"^in \*{0,2}run ?(\d+)", lowered)
                     or re.search(r"^still in run ?(\d+)", lowered))
                if m and ctl is not None:
                    rid = f"run{m.group(1)}"
                    ctl.set_profile_run(rid)
                    pump(app, 200)
                    cand = work / name / "runs" / rid / f"{name}.ti2"
                    tab_measure.clear_chart_file()
                    if cand.exists():
                        tab_measure.set_ti1_path(cand)
                    pump(app, 200)
                if "run type = **verification**" in lowered and ctl is not None:
                    ctl.set_run_type(RUN_TYPE_VERIFICATION)
                    pump(app, 250)
                if "generate chart" in lowered and "press" in lowered:
                    # NOTHING IS ALIGNED HERE ON PURPOSE.
                    #
                    # The first version of this driver called
                    # _align_current_run_to_target() before asking, which made
                    # every step pass while the app itself warned about whatever
                    # run happened to be "current" — the fault Knut then found by
                    # hand on Demo-08. A driver that helps the app along tests
                    # the help, not the app. The guard resolves the bar's run
                    # itself since beta.133.
                    tab_chart._confirm_displacing_results()
                elif "start measurement" in lowered and "greyed" in lowered:
                    win._tabs.setCurrentWidget(tab_measure)
                    pump(app, 250)
                    enabled = tab_measure._start_btn.isEnabled()
                    tip = tab_measure._start_btn.toolTip()
                    ok = (not enabled) and (msg is None or msg.title.lower()[:40]
                                            in tip.lower())
                    record(label, ok,
                           f"enabled={enabled} tooltip={'yes' if tip else 'EMPTY'}")
                    continue
                elif "start measurement" in lowered:
                    win._tabs.setCurrentWidget(tab_measure)
                    pump(app, 250)
                    # "Tick Refine / resume … and press Start Measurement" —
                    # the tick is part of the step, and it is what decides
                    # whether the window appears at all.
                    if "tick **refine" in lowered or "tick refine" in lowered:
                        for cb in (tab_measure._resume_cb,
                                   tab_measure._m_resume_cb):
                            if cb is not None:
                                cb.setChecked(True)
                    elif "untick" in lowered:
                        for cb in (tab_measure._resume_cb,
                                   tab_measure._m_resume_cb):
                            if cb is not None:
                                cb.setChecked(False)
                    pump(app, 150)
                    tab_measure._confirm_replacing_measurement()
                elif "auto-update preview" in lowered:
                    # The preview declines to re-draw a run that holds work.
                    win._tabs.setCurrentWidget(tab_chart)
                    pump(app, 200)
                    try:
                        tab_chart._align_current_run_to_target()
                    except Exception:      # noqa: BLE001
                        pass
                    tab_chart._said_auto_update_paused = False   # freshly switched on
                    tab_chart._say_preview_is_paused()
                elif "build profile" in lowered and "load" in lowered \
                        and "different run" in lowered:
                    # The step deliberately loads ANOTHER run's measurement and
                    # presses Build Profile — the state that used to build into
                    # the wrong run without a word.
                    win._tabs.setCurrentWidget(win._tab_profile)
                    prof = win._tab_profile
                    other = work / name / "runs" / "run6" / f"{name}.ti3"
                    if other.exists():
                        prof.set_ti3_path(other, propagate=False)
                    pump(app, 250)
                    prof._confirm_building_outside_the_selected_run()
                elif "build profile" in lowered:
                    win._tabs.setCurrentWidget(win._tab_profile)
                    prof = win._tab_profile
                    # §6 keys off the measurement the build would use, so the
                    # tab has to be holding it — which is what pressing
                    # "Build Profile" on a run means.
                    rid = getattr(ctl, "target", None)
                    rid = rid.profile_run if rid is not None else "run1"
                    ti3 = work / name / "runs" / (rid or "run1") / f"{name}.ti3"
                    if ti3.exists():
                        prof.set_ti3_path(ti3, propagate=False)
                    pump(app, 250)
                    # The tick lives INSIDE the window — silencing before the
                    # call would suppress the very window the step is about.
                    prof._confirm_rebuild_over_verifications()
                pump(app, 200)
            except Exception as exc:                      # noqa: BLE001
                record(label, False, f"{type(exc).__name__}: {exc}")
                continue

            # --- and check what the step promised -----------------------
            if msg is not None:
                record(label, CAUGHT.saw(msg.title),
                       f"expected {first}; saw {CAUGHT.titles or 'nothing'}")
            elif "no window" in plain.lower() or "no warning" in plain.lower():
                record(label, not CAUGHT.titles,
                       f"saw {CAUGHT.titles}" if CAUGHT.titles else "silent")
            else:
                # NOT VERIFIED — AND IT MUST NOT COUNT AS PASSED.
                #
                # This used to `record(label, True, "no message promised")`,
                # so every step that promises no message ID was reported as
                # passing without anything being checked — and the summary line
                # then claimed all of them "behave as the package describes".
                # The Restore Used Chart steps are all in this group, which is
                # how the package could read as fully verified while the step
                # Knut could not perform was never driven at all.
                #
                # A test that reports success for work it did not do is worse
                # than no test, because it is read as evidence.
                NOT_DRIVEN.append((label, "Expected" in plain))

    # ------------------------------------------------------------------
    # The Restore steps, checked from the DATA rather than left undriven
    # ------------------------------------------------------------------
    # Every "Restore Used Chart" step in the package promises no message ID, so
    # all of them sat in NOT_DRIVEN — the group that used to be counted as
    # passing. This closes the most important part of that gap: a Restore step
    # cannot possibly be performed unless the target it names ships a stored
    # chart, which is precisely what Knut found missing.
    #
    # Read from a PRISTINE copy: by this point the walk above has generated
    # charts and archived others, so the live tree reflects the driver's own
    # history rather than the package as shipped.
    print("\n=== every documented Restore step has something to restore ===")
    import tempfile as _tf

    from core.file_manager import Project as _Project
    from workflow.chart_slot import (slot_for_calibration, slot_for_run,
                                     slot_for_verification)
    from workflow.verify_chart_snapshot import slot_has_snapshot

    for case in CASES:
        nm = case["name"]
        if not (src / nm).is_dir():
            continue
        steps = " ".join(case.get("steps") or [])
        if "Restore Used Chart" not in steps:
            continue
        fresh = Path(_tf.mkdtemp()) / nm
        shutil.copytree(src / nm, fresh)
        try:
            pr = _Project.load(fresh)
            for r in pr.all_runs():
                record(f"{nm}: {r.id} has a stored chart",
                       slot_has_snapshot(slot_for_run(r)))
                for v in r.verifications():
                    record(f"{nm}: {r.id}/{v.id} has a stored chart",
                           slot_has_snapshot(slot_for_verification(v)))
            if pr.calibration.dir.is_dir():
                record(f"{nm}: the calibration has a stored chart",
                       slot_has_snapshot(slot_for_calibration(pr.calibration)))
        except Exception as exc:            # noqa: BLE001
            record(f"{nm}: could not be read for the Restore check", False, str(exc))
        finally:
            shutil.rmtree(fresh.parent, ignore_errors=True)

    bad = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} driven steps behave as "
          f"the package describes")
    for name, _ok, detail in bad:
        print(f"  ✗ {name}: {detail}")
    if NOT_DRIVEN:
        # Said out loud, every run: the reader has to know the difference
        # between "verified" and "not looked at".
        #
        # Grouped, and with the dedicated drivers named, because one flat
        # number overstates the gap as badly as the old code understated it —
        # most of these belong to Demo-09, which `drive_demo_09.py` walks in
        # detail. Trading one misleading number for another would waste the
        # point of reporting it at all.
        DEDICATED = {"Demo-09-Run-Descriptions": "scripts/drive_demo_09.py"}
        by_project: "dict[str, list[tuple[str, bool]]]" = {}
        for label, has_expectation in NOT_DRIVEN:
            by_project.setdefault(label.rsplit(" step ", 1)[0], []).append(
                (label, has_expectation))
        # A step that states no "Expected:" is a SETUP step — "set Profile run
        # = run 1" — which the driver does perform; the expectation belongs to
        # the step after it, and that one IS checked. Counting those as
        # unverified overstates the gap as badly as the old code understated
        # it, and a number nobody trusts is no better than a wrong one.
        real_gap = [l for l, exp in NOT_DRIVEN
                    if exp and l.rsplit(" step ", 1)[0] not in DEDICATED]
        print(f"\n{len(NOT_DRIVEN)} step(s) promise no message ID, so THIS "
              f"driver does not assert on them. Of those, "
              f"{len(real_gap)} are a real coverage gap:")
        for project in sorted(by_project):
            steps = by_project[project]
            n_exp = sum(1 for _l, e in steps if e)
            if project in DEDICATED:
                note = f"covered by {DEDICATED[project]}"
            elif n_exp == 0:
                note = "all setup steps — performed, nothing of their own to assert"
            else:
                note = f"{n_exp} state an expectation and are NOT checked"
            print(f"  ·  {project}: {len(steps)} step(s) — {note}")
        for label in real_gap:
            print(f"       ✗ not checked: {label}")
    win.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
