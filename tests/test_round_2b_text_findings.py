"""Round 2B (user-facing text, on screen), 2026-09-22: the behaviour behind
three of its findings, pinned.

#1 a saved report that records no type was LABELLED Full colour check while
   the page and the pulldown followed the run (§10), which on a profiling
   sheet is now the Printing record (K13);
#7 a window on a measurement outside any profile run greyed Generate with no
   reason, and the several-runs advice could not help it;
#8 a saved report of a type its kind no longer allows was asked about as
   "Nothing was changed", though Update would change its type.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from workflow.measurement_report import (REPORT_TYPE_FULL,      # noqa: E402
                                         REPORT_TYPE_RECORD)


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_an_untyped_saved_report_on_a_profiling_sheet_is_labelled_as_drawn(
        tmp_path, qapp):
    """#1. MUTATION: label with `report_type(rep)` again and this reads Full
    colour check: red."""
    from tests.test_import_measurement_module import (_cgats, _PATCHES,
                                                      _verify_env)
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    s, _fm, _ctl, run = _verify_env(tmp_path)
    ti3 = run.dir / "sheet.ti3"
    ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    try:
        r = dict(dlg._report, _origin_dir=str(run.dir), ti3="sheet.ti3")
        rep = {k: v for k, v in r.items() if k != "report_type"}
        assert dlg._type_a_file_renders_as(rep, r) == REPORT_TYPE_RECORD
        rep["report_type"] = REPORT_TYPE_FULL        # a file that DID choose
        assert dlg._type_a_file_renders_as(rep, r) == REPORT_TYPE_FULL
        # …AND THE LABEL ITSELF, from a real saved file that records no type
        from workflow.measurement_report import build_report, save_report
        saved = build_report(ti3)
        saved.pop("report_type", None)
        path = save_report(saved, run.dir)
        rr = dict(r, _report_file="")
        label = dlg._saved_report_label(rr, Path(path).name)
        assert "Printing record" in label, label
        assert "Full colour check" not in label, label
    finally:
        dlg.close()


def test_a_measurement_in_no_run_says_why_generate_is_grey(tmp_path, qapp):
    """#7. MUTATION: drop the `run is None` tooltip and it is empty: red."""
    from tests.test_report_window_limit_controls import (_colours, _dialog,
                                                         _ramp, _settings,
                                                         _write_ti3)
    dl = tmp_path / "Downloads"
    dl.mkdir()
    ti3 = _write_ti3(dl / "x.ti3", _ramp(16) + _colours())
    dlg = _dialog(_settings(tmp_path), ti3)
    try:
        assert not dlg._generate_btn.isEnabled()
        assert "not part of a profile run" in dlg._generate_btn.toolTip(), \
            dlg._generate_btn.toolTip()
    finally:
        dlg.deleteLater()


def test_a_saved_type_the_kind_no_longer_allows_is_a_change(tmp_path, qapp,
                                                            monkeypatch):
    """#8. A Printing record of a verification (legal on beta 34): shown as
    recorded, asked about under "Settings were modified", and Update writes a
    type a verification allows.

    MUTATION: drop the `_fit_to_kind(...) != _report_type_now()` half of
    `modified`, or the fit on the per-file `_tid`, and this goes red.
    NOT GUARDED, said out loud: the fit on `_tid_for_block`, which only a
    LEFTOVER member's re-stamp reads, and this fixture's older reports carry
    no document block to re-stamp (measured: the mutant stays green)."""
    from PyQt6.QtWidgets import QMessageBox
    from tests.test_generate_report_asks_what_to_do import (
        _a_real_document, _files, _pick_key, _press, _window)
    from tests.test_a_generated_report_is_one_document import _messy_project
    s, _fm, run, vs = _messy_project(tmp_path, dates=2)
    dlg = _window(s, vs[-1].measurement_ti3, qapp)
    try:
        key = _a_real_document(dlg, qapp, type_id=REPORT_TYPE_FULL,
                               every_measurement=True, detail=True)
        for f in _files(run):
            p = json.loads(f.read_text(encoding="utf-8"))
            doc = p.get("document") or {}
            if doc.get("id") == key.split(":", 1)[1]:
                doc["type"] = REPORT_TYPE_RECORD
                p["report_type"] = REPORT_TYPE_RECORD
                f.write_text(json.dumps(p), encoding="utf-8")
        # K19 (Knut, 2026-09-23): the list no longer OFFERS a type the run type
        # refuses, so a user cannot pick this document any more. The fit below is
        # still the safety net for any other door (a stored key, a document the
        # window opens on), so the entry is let through the filter here to reach
        # it; that the list itself hides it is `test_round_k19...`.
        dlg._entry_type = lambda e: REPORT_TYPE_FULL
        dlg._reload_sources()
        qapp.processEvents()
        # AWAY AND BACK, as a user reopening it: the window was still on this
        # document from the press that made it, and picking the entry it is
        # already on re-reads nothing.
        dlg._saved_combo.setCurrentIndex(0)
        qapp.processEvents()
        _pick_key(dlg, key, qapp)
        assert dlg._report_type_now() == REPORT_TYPE_RECORD, "not shown as recorded"
        del dlg._ask_update_or_create_new
        seen = []
        upd = _press("Update")

        def _exec(box):
            seen.append(box.text())
            return upd(box)
        monkeypatch.setattr(QMessageBox, "exec", _exec)
        dlg._on_generate_report()
        qapp.processEvents()
        assert seen == ["Settings were modified for the selected report"], seen
        for f in _files(run):
            doc = (json.loads(f.read_text(encoding="utf-8")).get("document")
                   or {})
            if doc.get("id") == key.split(":", 1)[1]:
                assert doc.get("type") != REPORT_TYPE_RECORD, (
                    "Update wrote a Printing record of a verification")
    finally:
        dlg.close()
