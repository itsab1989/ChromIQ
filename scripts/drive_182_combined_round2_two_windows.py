#!/usr/bin/env python3
"""Combined round 2: can the dated-verification protection be walked around?

§5 of `docs/design/measurement_report_limits.md` says the only saved report of
a dated verification is kept, because that verdict is the run's record of that
date. `_saved_delete_refusal` implements it by counting `_all_report_files`,
which is a SESSION-TIME list read when the window gathered its sources.

Seam 3 of this round measured that a report landing on disk while the window
sits open is never noticed. If the count can go stale downwards as well as
upwards, two windows open on the same date can each believe there is a spare.

So: give one dated verification TWO saved reports, open TWO windows on it,
delete one report in the second window, and then ask the first window — which
still believes there are two — to delete the other.

The date's own folder is read back off disk at the end. That, and not the
panel, is the evidence.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402
sys.path.insert(0, str(ROOT / "scripts"))
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

SOURCE = Path.home() / "ChromIQ" / "Demo-Switching"


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def combo(d):
    return [d._saved_combo.itemText(i) for i in range(d._saved_combo.count())]


def pick(d, name):
    for i in range(d._saved_combo.count()):
        data = d._saved_combo.itemData(i)
        if data and data[1] == name:
            d._saved_combo.setCurrentIndex(i)
            d._on_saved_chosen(i)
            return True
    return False


def main() -> int:                                   # noqa: C901
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    R: dict = {}
    crashes: list = []
    prev = sys.excepthook
    sys.excepthook = lambda t, e, tb: (
        crashes.append("".join(traceback.format_exception(t, e, tb))),
        prev(t, e, tb))

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))
    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-b20r2w-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    settings.set("restore_last_session", False)
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    R["locked_at_start"] = session_is_locked()

    proj = work / "Demo-Switching"
    shutil.copytree(SOURCE, proj, symlinks=True)
    date_dir = proj / "runs" / "run2" / "verifications" / "2026-06-24_164000"
    vti3 = date_dir / "Demo-Switching-verify.ti3"
    rdir = date_dir / "reports"
    first = rdir / "report_2026-06-24_16-40-00.json"
    assert first.is_file() and vti3.is_file()

    # THE MUTATION: a SECOND saved report of that same date, written and read
    # back before any window is opened.
    # THE SAME MEASUREMENT, A SECOND DOCUMENT ABOUT IT, which is what
    # `save_report` writes and what `_one_row_per_measurement` collapses: the
    # row's key is stamped from the MEASUREMENT, so a second report must keep
    # `created` and take the `_2` name. A first cut moved `created` an hour and
    # produced a second MEASUREMENT instead, which the refusal correctly
    # covered and which proved nothing.
    second = rdir / "report_2026-06-24_16-40-00_2.json"
    body = json.loads(first.read_text(encoding="utf-8"))
    second.write_text(json.dumps(body, indent=2), encoding="utf-8")
    on_disk = sorted(p.name for p in rdir.glob("report_*.json"))
    assert len(on_disk) == 2, on_disk
    R["reports_on_disk_at_start"] = on_disk

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))
    QMessageBox.exec = lambda self: QMessageBox.StandardButton.Ok  # type: ignore
    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    said: list = []
    MeasurementReportDialog._confirm = (                      # type: ignore
        lambda self, t, b: (said.append({"title": t, "body": b}), True)[1])
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    # TWO WINDOWS on the same dated verification, both opened before anything
    # is deleted — the ordinary way a person ends up with two: open one, then
    # open another from the other door.
    wa = MeasurementReportDialog(settings, None, initial_ti3=vti3)
    wa.resize(1400, 980)
    wa.move(60, 60)
    wa.show()
    pump(app, 3000)
    wb = MeasurementReportDialog(settings, None, initial_ti3=vti3)
    wb.resize(1400, 980)
    wb.move(140, 140)
    wb.show()
    pump(app, 3000)
    R["window_A_combo"] = combo(wa)
    R["window_B_combo"] = combo(wb)
    print(f"    A offers {len(R['window_A_combo'])}, "
          f"B offers {len(R['window_B_combo'])}", flush=True)
    ok, why = capture_window(wa, out / "W1-two-windows-A.png")
    R["capture_W1"] = {"ok": ok, "why": why}

    # A SELECTS THE REPORT IT WILL LATER DELETE, WHILE BOTH STILL EXIST.
    # This is the ordinary order: a person picks the document they want to
    # look at, reads it, and only then decides to remove it. It also fixes A's
    # idea of what exists at a moment when TWO reports really are on disk.
    assert pick(wa, first.name), "A cannot see the first report"
    pump(app, 1500)
    R["A_sees_before_B_deletes"] = combo(wa)
    R["A_delete_enabled_while_two_exist"] = wa._delete_report_btn.isEnabled()
    print(f"    A picked the first report while two exist; delete enabled: "
          f"{R['A_delete_enabled_while_two_exist']}", flush=True)

    # Window B deletes the SECOND report. Both windows now have one left on
    # disk, but only B knows it.
    assert pick(wb, second.name), "B cannot see the second report"
    pump(app, 1200)
    R["B_delete_enabled_on_the_spare"] = wb._delete_report_btn.isEnabled()
    wb._on_delete_report()
    pump(app, 2500)
    R["second_report_on_disk_after_B"] = second.is_file()
    R["on_disk_after_B"] = sorted(p.name for p in rdir.glob("report_*.json"))
    print(f"    after B deleted the spare, on disk: {R['on_disk_after_B']}",
          flush=True)
    ok, why = capture_window(wb, out / "W2-B-deleted-the-spare.png")
    R["capture_W2"] = {"ok": ok, "why": why}

    # Window A still believes there are two, AND IS NOT TOUCHED AGAIN. No
    # re-pick, because a re-pick is what re-reads the folder; a person who has
    # already chosen their report just presses Delete.
    R["A_delete_enabled_on_the_last_one"] = wa._delete_report_btn.isEnabled()
    R["A_refusal_note"] = wa._saved_note_full
    R["A_combo_when_asked"] = combo(wa)
    print(f"    A: delete enabled on the LAST report of a dated verification: "
          f"{R['A_delete_enabled_on_the_last_one']}  note="
          f"{R['A_refusal_note']!r}", flush=True)
    ok, why = capture_window(wa, out / "W3-A-on-the-last-report.png")
    R["capture_W3"] = {"ok": ok, "why": why}
    wa._on_delete_report()
    pump(app, 2500)

    # AND THE READER MUST BE ABLE TO SEE WHY. A refused delete that says
    # nothing is a button that does nothing.
    pump(app, 1500)
    R["A_delete_enabled_after_the_refusal"] = wa._delete_report_btn.isEnabled()
    R["A_note_after_the_refusal"] = wa._saved_note_full
    print(f"    after A pressed Delete: button enabled="
          f"{R['A_delete_enabled_after_the_refusal']}  note="
          f"{R['A_note_after_the_refusal']!r}", flush=True)

    # THE EVIDENCE IS THE FOLDER, NOT THE PANEL.
    left = sorted(p.name for p in rdir.glob("report_*.json"))
    R["reports_left_on_disk"] = left
    R["the_date_still_has_a_record"] = bool(left)
    R["confirmations_shown"] = said
    print(f"    reports left in the dated folder: {left}", flush=True)
    print(f"    THE DATE STILL HAS A RECORD: {R['the_date_still_has_a_record']}",
          flush=True)
    ok, why = capture_window(wa, out / "W4-after-A-tried.png")
    R["capture_W4"] = {"ok": ok, "why": why}

    wa.close(); wb.close()
    pump(app, 600)
    R["crashes"] = crashes
    (out / "two-windows-findings.json").write_text(
        json.dumps(R, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8")
    print(f"    crashes: {len(crashes)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
