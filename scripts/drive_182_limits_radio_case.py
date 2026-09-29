#!/usr/bin/env python3
"""Knut's beta 12 report: the Edit-limits radios, in the REAL windows.

Knut, 2026-09-13, on `Report-Limits-Report-Types` run 5::

    The Judged against is set to "ChromIQ tight", but when opening "Edit
    Limits" window the "ChromIQ default" was enabled. Manually clicking any of
    the 5 radio-buttons to select a limit set did nothing (had no effect.) even
    though the Judge against field was open for editing (Unlock this run's
    limits was ON). The radio-buttons should be locked if "Unlock this run's
    limits" is OFF, and set to same value as in the Judge against field.

This opens the project, the report window and the limits window, and records
what each control actually says and does: the run's bound set, the "Judged
against" pulldown, the row the radios sit on and its LABEL, which radio is
checked, whether the run is unlocked, and what clicking a radio changes.

It photographs both windows so the labels can be read rather than inferred.

Run it::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-lr.ini \\
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-lr-presets \\
        python scripts/drive_182_limits_radio_case.py <pack> <out-dir>

Never set QT_QPA_PLATFORM=offscreen for this. It is a driver, not a test.
"""
from __future__ import annotations

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

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox   # noqa: E402

sys.path.insert(0, str(ROOT / "scripts"))                        # noqa: E402
from onscreen_capture import capture_window, session_is_locked   # noqa: E402

PROJECT = "Report-Limits-Report-Types"
RUN = "run5"


def pump(app, ms: int = 300) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


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
    work = Path(tempfile.mkdtemp(prefix="chromiq-lr-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    src = pack / PROJECT
    assert src.is_dir(), f"no {PROJECT} in {pack}"
    dst = work / src.name
    shutil.copytree(src, dst)
    print(f"    driving the COPY at {dst}", flush=True)

    # A DIALOG THAT BLOCKS IS A DIALOG BASTI CLICKS. The limits window is
    # opened by hand below, so `exec` must return rather than sit there.
    QDialog.exec = lambda self: 1                     # type: ignore[assignment]
    for m in ("warning", "critical", "information", "question"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from core.file_manager import FileManager
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    # THE RECALCULATE QUESTION, ANSWERED YES. Changing a bound run's set asks
    # before rewriting its saved reports, and `_confirm` exists so a driver can
    # answer it ("One method, so a driver can answer it"). The blanket
    # QMessageBox stub answers 0, which is a refusal, so the first run of this
    # driver recorded the pick, declined its own question and reported the
    # rebind as not happening.
    _asked: list = []
    MeasurementReportDialog._confirm = (                    # type: ignore[method-assign]
        lambda self, title, text: (_asked.append(title), True)[1])
    from workflow.run_compliance import is_locked, run_limits
    fm = FileManager(settings)
    del fm

    ti3s = sorted((dst / "runs" / RUN / "verifications").glob("*/*.ti3"))
    assert ti3s, f"no dated verification in {RUN}"
    dlg = MeasurementReportDialog(settings, None, initial_ti3=ti3s[0])
    dlg.show()
    dlg.raise_()
    pump(app, 1800)
    print(f"    report window on screen: {dlg.isVisible()} "
          f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}", flush=True)

    ctx = dlg._run_ctx
    facts: dict = {
        "run": RUN,
        "judged_against_combo": (dlg._limits_combo.currentText()
                                 if getattr(dlg, "_limits_combo", None) else None),
        "judged_against_data": (dlg._limits_combo.currentData()
                                if getattr(dlg, "_limits_combo", None) else None),
        "unlock_checked": (dlg._unlock_check.isChecked()
                           if getattr(dlg, "_unlock_check", None) else None),
        "run_is_locked": bool(ctx and is_locked(ctx.run)),
    }
    if ctx is not None:
        rec = run_limits(ctx.run, {})
        facts["run_bound_set_id"] = rec.set_id
        facts["run_bound_label"] = rec.label_en
    shot = out / "01-report-window.png"
    ok, why = capture_window(dlg, shot)
    facts["report_photo"] = shot.name if ok else f"REFUSED: {why}"

    # ---------------------------------------------------------- the limits window
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    td = ThresholdsDialog(settings, dlg, run=ctx.run if ctx else None,
                          run_editable=bool(ctx and not dlg._locked_here(ctx.run)))
    td.show()
    td.raise_()
    pump(app, 1500)
    print(f"    limits window on screen: {td.isVisible()} "
          f"{td.frameGeometry().width()}x{td.frameGeometry().height()}", flush=True)

    from PyQt6.QtWidgets import QLabel, QRadioButton
    radios = {}
    for col, rb in getattr(td, "_default_radios", {}).items():
        radios[col] = {"checked": rb.isChecked(), "enabled": rb.isEnabled(),
                       "tooltip": rb.toolTip()}
    facts["radios"] = radios
    facts["radio_row_label"] = None
    for lbl in td.findChildren(QLabel):
        t = (lbl.text() or "").strip()
        if "default" in t.lower() and "run" in t.lower():
            facts["radio_row_label"] = t
            break
    facts["default_set_before"] = td._default_set
    facts["read_only_here"] = td._read_only_here()

    shot2 = out / "02-limits-window.png"
    ok2, why2 = capture_window(td, shot2)
    facts["limits_photo"] = shot2.name if ok2 else f"REFUSED: {why2}"

    # THE NEW ROW: which set does it say this run uses, and can it be changed?
    run_radios = {c: {"checked": rb.isChecked(), "enabled": rb.isEnabled()}
                  for c, rb in getattr(td, "_run_set_radios", {}).items()}
    facts["run_set_radios"] = run_radios
    facts["run_radio_checked"] = next(
        (c for c, v in run_radios.items() if v["checked"]), None)
    facts["run_radio_matches_binding"] = (
        facts["run_radio_checked"] == facts.get("run_bound_set_id"))

    # CLICK THE "Default for new runs" ONE, the way he did, and see what moves.
    target = next((c for c in radios if c != facts.get("run_bound_set_id")), None)
    if target:
        td._default_radios[target].setChecked(True)
        pump(app, 400)
        facts["clicked_default_radio"] = target
        facts["default_set_after"] = td._default_set
        if ctx is not None:
            facts["run_bound_set_after_default_click"] = run_limits(ctx.run, {}).set_id

    # NOW THE NEW ROW, which is the one he expected to work.
    pick = next((c for c in run_radios
                 if c != facts.get("run_bound_set_id")), None)
    if pick:
        td._run_set_radios[pick].setChecked(True)
        pump(app, 400)
        facts["clicked_run_radio"] = pick
        facts["dialog_recorded"] = td.run_set_chosen
        # …and the report window applies it on close, through the pulldown.
        td.close()
        pump(app, 400)
        dlg._on_open_limits.__wrapped__ if False else None
        # Simulate the close path the button takes: the window reads the pick.
        _i = dlg._set_combo.findData(pick)
        if _i >= 0 and dlg._set_combo.currentIndex() != _i:
            dlg._set_combo.setCurrentIndex(_i)
        pump(app, 900)
        if ctx is not None:
            facts["run_bound_set_after_run_click"] = run_limits(ctx.run, {}).set_id
        facts["judged_against_after"] = dlg._set_combo.currentText()
        facts["questions_asked"] = list(_asked)
    else:
        td.close()
    pump(app, 300)
    # ------------------------------- K-C: does the report TEXT follow the set?
    # Knut: *"When I changed the Judged against option to another limit set,
    # the report scope and report text did not update to specify correct limit
    # set. The same happened if I changed the report type."*
    import re as _re

    def _prose(html_str: str) -> str:
        t = _re.sub(r"<[^>]+>", " ", html_str or "")
        t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
        return _re.sub(r"\s+", " ", t)

    try:
        reps = dlg._runs_for_report()
        body_now = _prose(dlg._report_body_html(reps, for_pdf=True))
        facts["text_names_new_set"] = "ChromIQ default" in body_now
        facts["text_still_names_old_set"] = "ChromIQ tight" in body_now
        facts["view_names_new_set"] = "ChromIQ default" in _prose(
            dlg._view.toHtml() if getattr(dlg, "_view", None) else "")
        facts["view_names_old_set"] = "ChromIQ tight" in _prose(
            dlg._view.toHtml() if getattr(dlg, "_view", None) else "")
        (out / "report-body-after-set-change.txt").write_text(
            body_now, encoding="utf-8")
    except Exception as exc:                                # noqa: BLE001
        facts["text_check_failed"] = repr(exc)

    # …and the same question for the report TYPE.
    try:
        from workflow.measurement_report import REPORT_TYPE_GREY
        _ti = dlg._type_combo.findData(REPORT_TYPE_GREY)
        if _ti >= 0:
            dlg._type_combo.setCurrentIndex(_ti)
            pump(app, 900)
            reps2 = dlg._runs_for_report()
            body2 = _prose(dlg._report_body_html(reps2, for_pdf=True))
            view2 = _prose(dlg._view.toHtml() if getattr(dlg, "_view", None) else "")
            facts["after_type_change_body_names_grey"] = "Grey and tone" in body2
            facts["after_type_change_view_names_grey"] = "Grey and tone" in view2
            facts["type_combo_now"] = dlg._type_combo.currentText()
            (out / "report-body-after-type-change.txt").write_text(
                body2, encoding="utf-8")
    except Exception as exc:                                # noqa: BLE001
        facts["type_check_failed"] = repr(exc)

    shot3 = out / "03-report-after.png"
    ok3, why3 = capture_window(dlg, shot3)
    facts["after_photo"] = shot3.name if ok3 else f"REFUSED: {why3}"
    dlg.close()
    pump(app, 300)

    # ------------------------------------------------- and now a LOCKED run
    # His other half: *"The radio-buttons should be locked if 'Unlock this
    # run's limits' is OFF."* `Report-Limits-Set-Compare` run 2 is locked in
    # the shipped pack, so it is driven rather than simulated.
    locked_facts: dict = {}
    lsrc = pack / "Report-Limits-Set-Compare"
    if lsrc.is_dir():
        ldst = work / lsrc.name
        if not ldst.exists():
            shutil.copytree(lsrc, ldst)
        lti3 = sorted((ldst / "runs" / "run2" / "verifications").glob("*/*.ti3"))
        if lti3:
            ldlg = MeasurementReportDialog(settings, None, initial_ti3=lti3[0])
            ldlg.show()
            ldlg.raise_()
            pump(app, 1500)
            lctx = ldlg._run_ctx
            locked_facts["run_is_locked"] = bool(lctx and is_locked(lctx.run))
            locked_facts["editable_here"] = bool(
                lctx and not ldlg._locked_here(lctx.run))
            ltd = ThresholdsDialog(settings, ldlg, run=lctx.run if lctx else None,
                                   run_editable=locked_facts["editable_here"])
            ltd.show()
            ltd.raise_()
            pump(app, 1200)
            locked_facts["run_set_radios"] = {
                c: {"checked": rb.isChecked(), "enabled": rb.isEnabled()}
                for c, rb in getattr(ltd, "_run_set_radios", {}).items()}
            locked_facts["any_enabled"] = any(
                v["enabled"] for v in locked_facts["run_set_radios"].values())
            locked_facts["checked"] = next(
                (c for c, v in locked_facts["run_set_radios"].items()
                 if v["checked"]), None)
            if lctx is not None:
                locked_facts["bound_set"] = run_limits(lctx.run, {}).set_id
            lshot = out / "04-locked-run-limits.png"
            lok, lwhy = capture_window(ltd, lshot)
            locked_facts["photo"] = lshot.name if lok else f"REFUSED: {lwhy}"
            # A click must not record anything on a locked run.
            _pick = next((c for c in locked_facts["run_set_radios"]
                          if c != locked_facts.get("bound_set")), None)
            if _pick:
                ltd._run_set_radios[_pick].setChecked(True)
                pump(app, 300)
                locked_facts["recorded_after_click"] = ltd.run_set_chosen
            ltd.close()
            pump(app, 200)
            ldlg.close()
            pump(app, 200)
    facts["locked_run"] = locked_facts
    print("\n    LOCKED RUN:", flush=True)
    for k in ("run_is_locked", "editable_here", "any_enabled", "checked",
              "bound_set", "recorded_after_click", "photo"):
        print(f"      {k}: {locked_facts.get(k)}", flush=True)

    (out / "limits-radio.json").write_text(
        json.dumps({"screen_locked": session_is_locked(),
                    "qt_qpa_platform": os.environ.get("QT_QPA_PLATFORM", "<unset>"),
                    "facts": facts}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    for k in ("run_bound_set_id", "run_bound_label",
              "unlock_checked", "run_is_locked", "read_only_here",
              "radio_row_label", "run_radio_checked",
              "run_radio_matches_binding", "default_set_before",
              "clicked_default_radio", "default_set_after",
              "run_bound_set_after_default_click", "clicked_run_radio",
              "dialog_recorded", "run_bound_set_after_run_click",
              "judged_against_after", "questions_asked",
              "text_names_new_set", "text_still_names_old_set",
              "view_names_new_set", "view_names_old_set",
              "type_combo_now", "after_type_change_body_names_grey",
              "after_type_change_view_names_grey"):
        print(f"      {k}: {facts.get(k)}", flush=True)
    print(f"      default radios: {json.dumps(radios)}", flush=True)
    print(f"      run radios: {json.dumps(run_radios)}", flush=True)
    print(f"\n    written {out / 'limits-radio.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
