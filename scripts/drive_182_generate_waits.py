#!/usr/bin/env python3
"""The Generate-report button, in the REAL Measurement Report window.

Knut, 2026-09-13, testing beta 12::

    The generate report button seems not to do much, as the report
    auto-generates whenever report type or judged against is changed.

and, 2026-09-14, after the change was put to him with its cost::

    This change give the user more feeling of control and understanding of when
    something should change, or when a change will result in a changed report,
    and will see that it does change or not when clicking "Generate report". It
    will also give a user a chance to undo a changed field, if not wanting to
    regenerate the report. Make the change.

This opens a real project's report window and, for each of the five settings he
named, does what a person does: move the control, look at the screen, put it
back, look again, then press the button. For every step it records

* the DOCUMENT the window is showing (a hash of the rendered HTML), so
  "nothing changed" is measured rather than assumed;
* whether the red line beside the button is on screen and what it says;
* and it photographs the window in the waiting state and again after the press.

The fifth setting, "Judged against", is driven only where the run's limit set
may still be changed; a locked run refuses it by design and the run's state is
recorded either way.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-gen.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-gen-presets \\
        python scripts/drive_182_generate_waits.py <pack> <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtCore import Qt                                      # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PROJECT = "Report-Limits-Report-Types"
RUN = "run1"


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def doc(dlg) -> str:
    """A fingerprint of the DOCUMENT on screen, not of the window's state."""
    return hashlib.sha256(dlg._view.toHtml().encode("utf-8")).hexdigest()[:16]


def banner(dlg) -> "str | None":
    lbl = getattr(dlg, "_stale_label", None)
    if lbl is None or not lbl.isVisible():
        return None
    return lbl.text()


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    pack = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-gen-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"
    print(f"    sandbox: {work}", flush=True)

    src = pack / PROJECT
    assert src.is_dir(), f"no {PROJECT} in {pack}"
    dst = work / src.name
    shutil.copytree(src, dst)

    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from ui.theme import apply_appearance
    from workflow.run_compliance import is_locked
    # The recalculate question, answered YES, so a limit-set change is not
    # silently declined and reported as "nothing happened".
    _asked: list = []
    MeasurementReportDialog._confirm = (               # type: ignore[method-assign]
        lambda self, title, text: (_asked.append(title), True)[1])
    apply_appearance(app, None, "dark")
    fm = FileManager(settings)
    del fm

    ti3s = sorted((dst / "runs" / RUN / "verifications").glob("*/*.ti3"))
    assert ti3s, f"no dated verification in {RUN}"
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3s[0])
    dlg.resize(1500, 1000)
    dlg.show()
    dlg.raise_()
    pump(app, 2200)
    print(f"    report window on screen: {dlg.isVisible()} "
          f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}",
          flush=True)
    ctx = dlg._run_ctx
    steps: list = []

    def record(name, note=""):
        steps.append({"step": name, "doc": doc(dlg), "banner": banner(dlg),
                      "note": note})
        print(f"    {name:<44} doc={steps[-1]['doc']} "
              f"banner={'YES' if steps[-1]['banner'] else 'no'}", flush=True)

    record("00 opened")
    opened = steps[-1]["doc"]
    assert steps[-1]["banner"] is None, "a fresh window already warns"

    photos: dict = {}

    def shoot(tag):
        p = out / f"{tag}.png"
        ok, why = capture_window(dlg, p)
        photos[tag] = p.name if ok else f"REFUSED: {why}"
        print(f"      photo {tag}: {'ok' if ok else 'REFUSED: ' + str(why)}",
              flush=True)

    # ---------------------------------------------------- 1. Report type
    combo = dlg._type_combo
    was = combo.currentIndex()
    other = next((i for i in range(combo.count())
                  if combo.itemData(i) and i != was
                  and combo.model().item(i).isEnabled()), None)
    assert other is not None, "the type pulldown offers nothing else"
    combo.setCurrentIndex(other)
    pump(app, 900)
    record("01 report type moved", combo.itemText(other))
    shoot("01-type-moved-and-the-document-waits")
    combo.setCurrentIndex(was)
    pump(app, 900)
    record("02 report type put back")
    combo.setCurrentIndex(other)
    pump(app, 900)
    record("03 report type moved again")
    dlg._on_generate_report()
    pump(app, 1200)
    record("04 Generate pressed")
    shoot("02-after-generate")
    generated = steps[-1]["doc"]

    # ------------------------------------------- 2. Show all measurement runs
    dlg._all_runs_check.setChecked(not dlg._all_runs_check.isChecked())
    pump(app, 800)
    record("05 show-all toggled")
    dlg._all_runs_check.setChecked(not dlg._all_runs_check.isChecked())
    pump(app, 800)
    record("06 show-all put back")

    # ------------------------------------------------- 3. Show detailed data
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 800)
    record("07 detail toggled")
    dlg._on_generate_report()
    pump(app, 1200)
    record("08 Generate pressed")
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 800)
    record("09 detail toggled back")
    dlg._on_generate_report()
    pump(app, 1200)
    record("10 Generate pressed")

    # ---------------------------------------------- 4. the measurements ticked
    rows = [i for i, (kind, _si, key) in enumerate(dlg._list_rows)
            if kind == "run" and key]
    if rows:
        item = dlg._profile_list.item(rows[0])
        item.setCheckState(Qt.CheckState.Unchecked)
        pump(app, 800)
        record("11 a measurement unticked")
        item.setCheckState(Qt.CheckState.Checked)
        pump(app, 800)
        record("12 ticked again")
    else:
        record("11 no run row to untick", "SKIPPED")

    # ------------------------------------------------------ 5. Judged against
    sc = dlg._set_combo
    locked = bool(ctx and is_locked(ctx.run))
    if sc.isEnabled() and sc.count() > 1:
        w2 = sc.currentIndex()
        o2 = next(i for i in range(sc.count()) if i != w2)
        sc.setCurrentIndex(o2)
        pump(app, 1200)
        record("13 judged-against moved", f"{sc.itemText(o2)}; locked={locked}")
        shoot("03-set-moved-and-the-document-waits")
        dlg._on_generate_report()
        pump(app, 1200)
        record("14 Generate pressed")
    else:
        record("13 judged-against not offered",
               f"enabled={sc.isEnabled()} locked={locked}")

    # ------------------------------- 6. AND WHERE THERE IS NOTHING TO PRESS
    # A second profile loaded disables "Generate report", because a report is
    # written into ONE run. The five settings must then repaint at once rather
    # than point at a dead button, which is what an adversary round found them
    # doing.
    others = sorted(p for p in pack.iterdir()
                    if p.is_dir() and p.name != PROJECT)
    if others:
        src2 = others[0]
        dst2 = work / src2.name
        shutil.copytree(src2, dst2)
        more = sorted(dst2.glob("runs/*/verifications/*/*.ti3"))
        if more:
            dlg._add_source(more[0])
            pump(app, 1500)
            record("15 a second profile loaded",
                   f"generate_enabled={dlg._generate_btn.isEnabled()}")
            shoot("04-two-profiles-loaded")
            _doc_before = doc(dlg)
            dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
            pump(app, 1200)
            record("16 detail toggled with Generate dead",
                   f"generate_enabled={dlg._generate_btn.isEnabled()} "
                   f"document_rebuilt={doc(dlg) != _doc_before}")
            steps[-1]["rebuilt"] = doc(dlg) != _doc_before
            steps[-1]["generate_enabled"] = dlg._generate_btn.isEnabled()
            shoot("05-dead-button-repaints-at-once")

    by = {s["step"]: s for s in steps}
    verdicts = {
        "a fresh window shows no banner": by["00 opened"]["banner"] is None,
        "moving a setting leaves the document alone": all(
            by[s]["doc"] == prev for s, prev in (
                ("01 report type moved", opened),
                ("05 show-all toggled", generated),
                ("07 detail toggled", generated))),
        "moving a setting puts the red line up": all(
            by[s]["banner"] for s in
            ("01 report type moved", "05 show-all toggled",
             "07 detail toggled")),
        "putting it back takes the red line away": all(
            by[s]["banner"] is None for s in
            ("02 report type put back", "06 show-all put back")),
        "Generate rebuilds the document": (
            by["04 Generate pressed"]["doc"] != opened
            and by["08 Generate pressed"]["doc"]
            != by["07 detail toggled"]["doc"]),
        "Generate clears the red line": all(
            by[s]["banner"] is None for s in
            ("04 Generate pressed", "08 Generate pressed",
             "10 Generate pressed")),
    }
    if "11 a measurement unticked" in by:
        verdicts["unticking a measurement waits too"] = bool(
            by["11 a measurement unticked"]["banner"])
        verdicts["ticking it back clears the line"] = (
            by["12 ticked again"]["banner"] is None)
    if "16 detail toggled with Generate dead" in by:
        _d = by["16 detail toggled with Generate dead"]
        verdicts["a dead Generate button means the setting repaints at once"] = (
            bool(_d.get("rebuilt")) and not _d.get("generate_enabled"))
        verdicts["and no red line points at a button that cannot be pressed"] = (
            _d["banner"] is None)
    if "13 judged-against moved" in by:
        verdicts["judged-against waits too"] = bool(
            by["13 judged-against moved"]["banner"])
        verdicts["and Generate clears it"] = (
            by["14 Generate pressed"]["banner"] is None)

    (out / "generate-waits.json").write_text(
        json.dumps({"project": PROJECT, "run": RUN, "photos": photos,
                    "recalculate_questions": _asked,
                    "steps": steps, "verdicts": verdicts}, indent=2),
        encoding="utf-8")
    print(json.dumps(verdicts, indent=2), flush=True)
    print(f"    screen locked at start: {session_is_locked()}", flush=True)
    dlg.close()
    pump(app, 400)
    return 0 if all(verdicts.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
