#!/usr/bin/env python3
"""ADVERSARY round 14 — the Measurement Report window's "wait for Generate".

Knut, 2026-09-14: *"It will also give a user a chance to undo a changed field,
if not wanting to regenerate the report."*

This drives the REAL window on screen and looks for a door that takes that
chance away, or leaves the red line lying.

Run::

    CHROMIQ_SETTINGS_FILE=/tmp/chromiq-adv14r.ini \
    CHROMIQ_PRESETS_DIR=/tmp/chromiq-adv14r-presets \
        python scripts/adv14_report_waits_attack.py <out-dir>
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import PyQt6.QtWebEngineWidgets  # noqa: F401
except ImportError:
    pass

from PyQt6.QtWidgets import QApplication, QMessageBox      # noqa: E402

from onscreen_capture import capture_window                # noqa: E402


def pump(app, ms=300):
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def main() -> int:
    assert os.environ.get("CHROMIQ_SETTINGS_FILE"), "SANDBOX THE SETTINGS FIRST"
    assert os.environ.get("CHROMIQ_PRESETS_DIR"), "SANDBOX THE PRESETS FIRST"
    out = Path(sys.argv[1]).resolve()
    out.mkdir(parents=True, exist_ok=True)

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("ChromIQ")
    from ui.styles import WinButtonLayoutStyle
    app.setStyle(WinButtonLayoutStyle("Fusion"))

    from core.settings import AppSettings
    work = Path(tempfile.mkdtemp(prefix="chromiq-adv14r-"))
    settings = AppSettings()
    settings.set("custom_output_path", str(work))
    settings.set("appearance", "dark")
    assert settings.get("custom_output_path", "") == str(work), "SANDBOX FAILED"

    for m in ("warning", "critical", "information"):
        setattr(QMessageBox, m, staticmethod(lambda *a, **k: 0))

    from ui.theme import apply_appearance
    apply_appearance(app, None, "dark")

    # the same fixture the suite uses, driven for real
    sys.path.insert(0, str(ROOT))
    from tests.test_import_measurement_module import _cgats, _PATCHES, _verify_env
    tmp = Path(tempfile.mkdtemp(prefix="chromiq-adv14r-proj-"))
    s, fm, _ctl, run = _verify_env(tmp)
    v = run.new_verification()
    v.ensure_dir()
    v.measurement_ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=v.measurement_ti3)
    dlg.resize(1500, 980)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    pump(app, 2500)
    print(f"    ON SCREEN: visible={dlg.isVisible()} "
          f"{dlg.frameGeometry().width()}x{dlg.frameGeometry().height()}",
          flush=True)

    def doc():
        return hashlib.sha1(dlg._view.toHtml().encode()).hexdigest()[:12]

    def state(tag):
        return {"where": tag, "doc": doc(),
                "banner": bool(dlg._stale_label.isVisible()),
                "generate_enabled": bool(dlg._generate_btn.isEnabled()),
                "sources": len(dlg._sources),
                "type": str(dlg._type_combo.currentData() or ""),
                "detail": bool(dlg._detail_check.isChecked())}

    log = [state("fresh window")]
    print(json.dumps(log[-1]), flush=True)

    # ---- A pending change, then a door that repaints at once ---------------
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 600)
    log.append(state("after ticking 'show detailed data' (PENDING)"))
    print(json.dumps(log[-1]), flush=True)
    capture_window(dlg, out / "report-banner-pending.png")

    pending_doc = doc()
    # a second measurement is added: a door the design says repaints AT ONCE
    run2 = fm.project().new_run()
    v2 = run2.new_verification()
    v2.ensure_dir()
    v2.measurement_ti3.write_text(
        _cgats("CTI3", [(r * 0.5, g, b) for (r, g, b) in _PATCHES]),
        encoding="utf-8")
    dlg._add_source(v2.measurement_ti3)
    pump(app, 900)
    log.append(state("after ADDING a measurement while the tick was pending"))
    print(json.dumps(log[-1]), flush=True)
    capture_window(dlg, out / "report-after-adding-a-measurement.png")
    adopted = (doc() != pending_doc and not dlg._stale_label.isVisible())
    print(f"    >>> the pending setting was ADOPTED without Generate: {adopted}",
          flush=True)

    # is the document really built WITH the pending setting? put the tick back
    # and see whether the window now claims the document is stale.
    dlg._detail_check.setChecked(not dlg._detail_check.isChecked())
    pump(app, 600)
    log.append(state("after putting the tick BACK (undo)"))
    print(json.dumps(log[-1]), flush=True)
    capture_window(dlg, out / "report-banner-vs-dead-generate.png")

    # ---- THE SAME PULLDOWN ON A MEASUREMENT THAT IS IN NO RUN --------------
    # `_on_type_chosen` has a `ctx is None` branch that calls `_refresh()`
    # outright, while `_on_set_chosen`'s identical branch defers. So the report
    # type still auto-generates for a .ti3 opened from outside a project, which
    # is the exact thing Knut reported.
    # HIDE THE FIRST WINDOW FIRST. Both are called "Measurement Report", and
    # the first photograph of this stage came back showing the OTHER one.
    dlg.hide()
    pump(app, 600)
    loose_dir = Path(tempfile.mkdtemp(prefix="chromiq-adv14r-loose-"))
    loose = loose_dir / "loose-measurement.ti3"
    loose.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg2 = MeasurementReportDialog(s, None, initial_ti3=loose)
    dlg2.resize(1500, 980)
    dlg2.show()
    dlg2.raise_()
    pump(app, 2000)

    def doc2():
        return hashlib.sha1(dlg2._view.toHtml().encode()).hexdigest()[:12]

    loose_log = [{"where": "fresh loose window", "doc": doc2(),
                  "banner": bool(dlg2._stale_label.isVisible()),
                  "run_ctx": repr(dlg2._run_ctx),
                  "type": str(dlg2._type_combo.currentData() or "")}]
    print(json.dumps(loose_log[-1]), flush=True)
    from workflow.measurement_report import report_type_is_built
    other = None
    for i in range(dlg2._type_combo.count()):
        tid = dlg2._type_combo.itemData(i)
        if tid and tid != dlg2._type_combo.currentData() and report_type_is_built(tid):
            other = (i, tid)
            break
    print(f"    another built type: {other}", flush=True)
    if other:
        before2 = doc2()
        dlg2._type_combo.setCurrentIndex(other[0])
        pump(app, 900)
        loose_log.append({"where": f"after choosing type {other[1]}",
                          "doc": doc2(),
                          "banner": bool(dlg2._stale_label.isVisible()),
                          "type": str(dlg2._type_combo.currentData() or ""),
                          "document_rebuilt_without_Generate":
                              doc2() != before2})
        print(json.dumps(loose_log[-1]), flush=True)
        print("    photo:", capture_window(
            dlg2, out / "report-loose-type-autogenerated.png"), flush=True)
        print("    title check:", dlg2.windowTitle(),
              "sources:", len(dlg2._sources), flush=True)
    # …and the SET pulldown in the very same window, which does defer
    setw = None
    for i in range(dlg2._set_combo.count()):
        sid = dlg2._set_combo.itemData(i)
        if sid and sid != dlg2._set_combo.currentData():
            setw = (i, sid)
            break
    if setw:
        before3 = doc2()
        dlg2._set_combo.setCurrentIndex(setw[0])
        pump(app, 900)
        loose_log.append({"where": f"after choosing SET {setw[1]} in the same window",
                          "doc": doc2(),
                          "banner": bool(dlg2._stale_label.isVisible()),
                          "document_rebuilt_without_Generate": doc2() != before3,
                          "generate_button_enabled":
                              bool(dlg2._generate_btn.isEnabled()),
                          "generate_button_text": dlg2._generate_btn.text()})
        print("    photo:", capture_window(
            dlg2, out / "report-loose-banner-points-at-a-dead-button.png"),
            flush=True)
        print(json.dumps(loose_log[-1]), flush=True)
    dlg2.close()

    (out / "report-findings.json").write_text(
        json.dumps({"log": log, "silently_adopted": adopted,
                    "loose_ti3": loose_log}, indent=2),
        encoding="utf-8")
    print("WROTE", out / "report-findings.json", flush=True)
    dlg.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
