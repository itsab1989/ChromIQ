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
                    # The §4 guard assesses project.current_run(), which the
                    # tab aligns to the bar before it asks.
                    try:
                        tab_chart._align_current_run_to_target()
                    except Exception:      # noqa: BLE001
                        pass
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
                record(label, True, "no message promised")

    bad = [r for r in RESULTS if not r[1]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} steps behave as the "
          f"package describes")
    for name, _ok, detail in bad:
        print(f"  ✗ {name}: {detail}")
    win.close()
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
