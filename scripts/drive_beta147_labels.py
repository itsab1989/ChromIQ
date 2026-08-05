#!/usr/bin/env python3
"""On-screen check of Knut's beta.144 report: the two label rules and the help card.

Drives the REAL Create Chart tab and the REAL help card with the app's own
styling, screenshots each state, and prints what the window actually says.

    CHROMIQ_DRIVE_ONSCREEN=1 python scripts/drive_beta147_labels.py

**It always stops itself.** A hard-kill timer is armed before the first window
appears, because a GUI driver that hangs takes the developer's screen with it.
"""
from __future__ import annotations

import os
import signal
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

HARD_STOP_S = 60


def _arm_hard_stop() -> None:
    """Kill this process outright if anything blocks — before Qt is imported,
    so a modal window cannot outlive it."""
    def _die() -> None:
        print(f"\n!! hard stop after {HARD_STOP_S}s — something blocked", flush=True)
        os.kill(os.getpid(), signal.SIGKILL)
    t = threading.Timer(HARD_STOP_S, _die)
    t.daemon = True
    t.start()


_arm_hard_stop()

if not os.environ.get("CHROMIQ_DRIVE_ONSCREEN"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile                                            # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel           # noqa: E402
from PyQt6.QtGui import QFontMetrics                       # noqa: E402

from core.argyll_runner import ArgyllRunner                # noqa: E402
from core.file_manager import FileManager                  # noqa: E402
from core.measurement_target import (                      # noqa: E402
    RUN_TYPE_CALIBRATION, RUN_TYPE_PROFILING, RUN_TYPE_VERIFICATION,
)
from core.settings import DEFAULTS                         # noqa: E402


class _Settings:
    def __init__(self, tmp: Path, **over):
        self.d = dict(DEFAULTS)
        self.d["custom_output_path"] = str(tmp)
        self.d.update(over)

    def get(self, key, default=None):
        return self.d.get(key, default)

    def set(self, key, value):
        self.d[key] = value


def _apply_real_styling(app: QApplication, settings) -> None:
    """Mirror main.py: the fonts and theme the user actually sees."""
    try:
        from ui.theme import apply_appearance
        apply_appearance(app, None, settings.get("appearance", "auto"))
    except Exception as exc:                                # noqa: BLE001
        print(f"   (theme not applied: {exc})")
    try:
        from ui.fonts import load_app_fonts
        load_app_fonts()
    except Exception:                                       # noqa: BLE001
        pass


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="chromiq-drive-labels-"))
    settings = _Settings(tmp, calibration_mode=True)
    app = QApplication(sys.argv)
    _apply_real_styling(app, settings)

    from ui.measurement_target_bar import MeasurementTargetController
    from ui.tabs.tab_chart import TabChart

    fm = FileManager(settings)
    fm.set_target_name("Knut-Label-Check")
    project = fm.project()
    while project._next_run_index() <= 3:
        project.new_run()

    tab = TabChart(ArgyllRunner(settings), fm, settings)
    ctl = MeasurementTargetController(fm)
    ctl.set_calibration_allowed(True)
    tab.set_target_controller(ctl)
    tab.resize(1180, 900)
    tab.show()
    app.processEvents()

    shots = ROOT / "docs" / "design" / "mockups" / "run_description_labels"
    shots.mkdir(parents=True, exist_ok=True)

    cases = [
        ("run3-profiling",    "run3", RUN_TYPE_PROFILING,
         ("Run 3 Description:", "Run 3 Chart Notes:")),
        ("newrun-profiling",  "",     RUN_TYPE_PROFILING,
         ("Run 4 Description:", "Run 4 Chart Notes:")),
        ("run2-verification", "run2", RUN_TYPE_VERIFICATION,
         ("Run 2 Description:", "Verification Chart Notes:")),
        ("newrun-verification", "",   RUN_TYPE_VERIFICATION,
         ("Run 4 Description:", "Verification Chart Notes:")),
        ("calibration",       "run1", RUN_TYPE_CALIBRATION,
         ("Calibration Description:", "Calibration Chart Notes:")),
    ]

    failures = []
    print("\n=== the labels, as the window shows them ===")
    for name, run, run_type, expect in cases:
        ctl.set_profile_run(run)
        ctl.set_run_type(run_type)
        app.processEvents()
        got = (tab._manual_run_desc_lbl.text(), tab._manual_chart_notes_lbl.text())
        ok = got == expect
        print(f"  {'OK ' if ok else 'BAD'}  {name:22s} {got[0]:28s} | {got[1]}")
        if not ok:
            failures.append(f"{name}: expected {expect}, window shows {got}")
        # Grab the frame the two rows live in, not the whole tab: the rows sit
        # in Manual's Output group and are what this is about.
        frame = tab._manual_chart_notes_lbl.parentWidget()
        for _ in range(3):                      # up to the enclosing group box
            if frame is not None and frame.parentWidget() is not None:
                frame = frame.parentWidget()
        (frame or tab).grab().save(str(shots / f"{name}.png"))
        # …and the folder line must name the same run.
        print(f"        location: {ctl.location_being_edited()}")

    # ---- the help card Knut named ---------------------------------------
    print("\n=== the -T help card ===")
    from ui.tooltip_button import _InfoDialog
    import inspect, re
    from ui.tabs.tab_measure import TabMeasure

    src = inspect.getsource(TabMeasure)
    raw = re.search(r'tooltip_title=tr\("Patch consistency tolerance \(-T\)"\),\s*'
                    r'tooltip_body=\(\s*(tr\(.*?\))\s*\),', src, re.S).group(1)
    body = eval(raw, {"tr": lambda s: s})                   # noqa: S307
    dlg = _InfoDialog("Patch consistency tolerance (-T)", body, None, 420)
    dlg.show()
    app.processEvents()
    label = dlg.findChildren(QLabel)[1]
    fm_ = QFontMetrics(label.font())
    widest = max(fm_.horizontalAdvance(ln) for ln in body.split("\n") if ln.strip())
    fill = widest / label.width()
    print(f"  window {dlg.width()} px, body {label.width()} px, "
          f"longest written line {widest} px  →  fill {fill:.0%}")
    dlg.grab().save(str(shots / "help-card-tolerance.png"))
    if fill <= 0.9:
        failures.append(f"the -T card fills only {fill:.0%} of its body width")
    if widest > label.width():
        failures.append("the -T card still re-wraps its own lines")
    dlg.close()

    print(f"\nscreenshots: {shots}")
    if failures:
        print("\nFAILURES:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nall on-screen checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
