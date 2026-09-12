#!/usr/bin/env python3
"""ON SCREEN: is a hidden column remembered on a LOCKED run?

Knut, 2026-09-11: *"it is not remembered what I turned off some columns"*.
Round 1 (`2ec2f424`) fixed the door where the recalculation question threw the
tick away.  This asks the same question on the state most mature runs are in:
BOUND, with two dated verifications, therefore LOCKED.

Real MainWindow, real Measurement Report window, real Report limits window, real
tick box, clicked the way a person clicks it.  Sandbox the settings, the presets
and the working folder before running.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import QTimer                  # noqa: E402
from PyQt6.QtGui import QFontDatabase            # noqa: E402
from PyQt6.QtWidgets import QApplication         # noqa: E402

from onscreen_capture import capture_window, session_is_locked   # noqa: E402

_modals: list = []
_timers: list = []


def pump(app, ms: int = 300) -> None:
    end = time.time() + ms / 1000.0
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


def watchdog(app):
    """Nothing may block, and every window that opens is recorded."""
    def check():
        w = app.activeModalWidget()
        if w is None:
            return
        text = ""
        for attr in ("text", "informativeText"):
            f = getattr(w, attr, None)
            if callable(f):
                try:
                    text += str(f()) + "\n"
                except Exception:      # noqa: BLE001
                    pass
        _modals.append({"title": w.windowTitle(), "text": text[:600]})
        print("    !! modal:", w.windowTitle())
        try:
            w.reject()
        except Exception:              # noqa: BLE001
            w.close()
    t = QTimer()
    t.setInterval(250)
    t.timeout.connect(check)
    t.start()
    _timers.append(t)


def build_locked_run(root: Path):
    """A run that is BOUND and has two measured dates, which is LOCKED."""
    from core.file_manager import Project
    from workflow import measurement_report as mr
    from workflow import run_compliance as rc
    from workflow.ti3_analysis import mark_verification_ti3
    from test_report_judging import _colours, _ramp, _write_ti3

    proj = Project.create(root / "Adv2-Locked", "Adv2-Locked")
    run = proj.current_run()
    run.ensure_dir()
    first = None
    for i in range(2):
        v = run.new_verification(datetime(2026, 1, 1 + i, 10, 0, 0))
        v.ensure_dir()
        raw = v.dir / "Adv2-Locked.ti3"
        _write_ti3(raw, _ramp(16) + _colours(), verification=False)
        mark_verification_ti3(raw).rename(v.dir / f"{run.verify_stem}.ti3")
        target = v.dir / f"{run.verify_stem}.ti3"
        rep = mr.build_report(target)
        mr.stamp_verdict(rep, rc.run_limits(run, {}).limits,
                         set_id="chromiq_default",
                         set_label="ChromIQ default (recommended)")
        mr.save_report(rep, v.dir)
        first = first or target
    rc.bind_run(run, "chromiq_default", {})
    assert rc.is_bound(run) and rc.is_locked(run), "the fixture is not locked"
    return proj, run, first


def main() -> int:
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv \
        else Path("/tmp/chromiq-adv2-proof")
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else "run"
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)

    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    work = Path(os.environ["CHROMIQ_ADV2_WORK"])
    work.mkdir(parents=True, exist_ok=True)

    res: dict = {"tag": tag, "screen_locked": session_is_locked(),
                 "mode": "on screen (cocoa), real MainWindow + real windows",
                 "modals": _modals}
    print("00 screen locked:", res["screen_locked"])

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from core.resource_path import resource_path
    for fp in resource_path("assets/fonts").glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(fp))

    from core.settings import AppSettings
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    from ui import theme as ui_theme
    ui_theme.apply_appearance(app, None, "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    proj, run, ti3 = build_locked_run(work)
    from workflow import run_compliance as rc
    res["run"] = {"dir": str(run.dir), "bound": rc.is_bound(run),
                  "locked": rc.is_locked(run),
                  "dates": rc.measured_dates(run)}
    print("01 run:", res["run"])

    from ui.main_window import MainWindow
    win = MainWindow(settings)
    win.resize(1500, 980)
    win.show()
    pump(app, 1800)
    watchdog(app)

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(settings, win, initial_ti3=ti3)
    dlg.show()
    pump(app, 1600)
    ok, why = capture_window(dlg, shots / f"{tag}-10-report.png")
    res.setdefault("shots", {})["10-report"] = \
        f"{tag}-10-report.png" if ok else f"REFUSED: {why}"
    print("02 report window shot:", "ok" if ok else "REFUSED " + (why or ""))

    # The Report limits window, opened from the button a person presses.
    res["limits_button"] = dlg._limits_btn.text()
    print("03 the button reads:", res["limits_button"])

    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    td = ThresholdsDialog(settings, dlg, run=run,
                          run_editable=not dlg._locked_here(run))
    td.show()
    pump(app, 1200)
    res["run_editable_passed"] = not dlg._locked_here(run)
    boxes = {sid: (c.isChecked(), c.isEnabled())
             for sid, c in td._column_checks.items()}
    res["column_boxes_before"] = boxes
    print("04 column boxes:", boxes)
    ok, why = capture_window(td, shots / f"{tag}-11-limits.png")
    res.setdefault("shots", {})["11-limits"] = \
        f"{tag}-11-limits.png" if ok else f"REFUSED: {why}"

    # Untick "ChromIQ tight" the way a person does: click the box.
    target_sid = "chromiq_tight"
    box = td._column_checks[target_sid]
    before_meta = list(run.load_meta().compliance_columns or [])
    box.click()
    pump(app, 700)
    after_meta = list(run.load_meta().compliance_columns or [])
    res["untick"] = {"set": target_sid, "checked_now": box.isChecked(),
                     "column_hidden_in_window":
                         not td._column_visible(target_sid)
                         if hasattr(td, "_column_visible") else None,
                     "meta_before": before_meta, "meta_after": after_meta}
    print("05 after the click:", res["untick"])
    ok, why = capture_window(td, shots / f"{tag}-12-after-untick.png")
    res.setdefault("shots", {})["12-after-untick"] = \
        f"{tag}-12-after-untick.png" if ok else f"REFUSED: {why}"

    td.accept()
    pump(app, 600)
    td.deleteLater()
    pump(app, 400)

    # Reopen it, the way a person reopens it.
    td2 = ThresholdsDialog(settings, dlg, run=run,
                           run_editable=not dlg._locked_here(run))
    td2.show()
    pump(app, 1000)
    res["column_boxes_on_reopen"] = {
        sid: c.isChecked() for sid, c in td2._column_checks.items()}
    print("06 on reopen:", res["column_boxes_on_reopen"])
    ok, why = capture_window(td2, shots / f"{tag}-13-reopened.png")
    res.setdefault("shots", {})["13-reopened"] = \
        f"{tag}-13-reopened.png" if ok else f"REFUSED: {why}"

    remembered = res["column_boxes_on_reopen"].get(target_sid) is False
    res["verdict"] = ("the hidden column IS remembered" if remembered else
                      "THE HIDDEN COLUMN IS NOT REMEMBERED on a locked run: "
                      "the box came back ticked and nothing was written to "
                      "the run")
    print("07", res["verdict"])

    (out / f"{tag}-locked-columns.json").write_text(
        json.dumps(res, indent=2), encoding="utf-8")
    td2.reject()
    dlg.reject()
    win.close()
    pump(app, 400)
    return 0 if remembered else 1


if __name__ == "__main__":
    sys.exit(main())
