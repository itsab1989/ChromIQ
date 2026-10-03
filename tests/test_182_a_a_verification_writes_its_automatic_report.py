"""#182 (a): a VERIFICATION writes its automatic report, and the window opens on it.

Knut, 2026-10-01: Generate in the Measurement Report window wrote a report
without asking, right after a verification. The question logic was not at
fault: a verification never emits ``measure_finished``, which was the only
thing that wrote the automatic report, so the dated folder held no saved report
and the window opened on "New report…", where Generate writes a new one by
design. K13 (§13.10 of ``docs/design/measurement_report_limits.md``, CONFIRMED
2026-09-23) says the automatic report follows a verification measurement as it
follows a profiling one, and the Measure tab's tick box promises
``verifications/<date>/reports``.

EVERY TEST GOES THROUGH THE REAL ENDING: the chartread-exit handler
(``_on_measure_done``) and the real import (``_on_import_measurement``). The
tests that existed called ``_maybe_save_measurement_report`` directly, which is
exactly why nothing noticed the wiring was missing.

MUTATIONS, each proved red (MUTATIONS.md of H_impl_182):
* delete the ``self._maybe_save_measurement_report(dst)`` call in
  ``_finalize_verification``: the guided tests go red;
* delete it in ``_import_into_verification``: the import test goes red;
* emit ``measure_finished`` instead of calling the saver: the
  never-emits assertion goes red.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

from tests.test_import_measurement_module import (_PATCHES, _cgats,  # noqa: E402
                                                  _measurement, _tab,
                                                  _verify_env)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _reports_of(folder: Path) -> "list[Path]":
    return sorted((Path(folder) / "reports").glob("report_*.json"))


def _measured_by_chartread(run) -> Path:
    """What chartread leaves behind for a verification read: ``<stem>.ti3``
    beside the verify chart the tab loaded."""
    ti3 = run.verify_chart_ti2.with_suffix(".ti3")
    ti3.write_text(_cgats("CTI3", _PATCHES), encoding="utf-8")
    return ti3


def _guided_ending(tab, run, monkeypatch, *, saved=None) -> None:
    """Drive the real chartread-exit handler for a successful verification
    read. The two windows at its end are recorded, not shown; the how-printed
    question is answered "Not sure" by not being asked."""
    monkeypatch.setattr(tab, "_ask_how_printed", lambda ti3: None)
    if saved is not None:
        monkeypatch.setattr(tab, "_show_verification_saved",
                            lambda dst: saved.append(dst))
    _measured_by_chartread(run)
    tab._ti1_path = run.verify_chart_ti2
    tab._verify_run = True
    tab._ti3_mtime_before = None
    tab._all_done_shown = True
    tab._measure_failed = False
    tab._on_measure_done(0)


def _setup(tmp_path, qapp, *, tick: bool = True):
    s, fm, ctl, run = _verify_env(tmp_path)
    tab = _tab(s, fm, ctl)
    tab._save_report_cb.setChecked(tick)
    qapp.processEvents()
    return s, fm, ctl, run, tab


# --------------------------------------------------------------------------
# normal
# --------------------------------------------------------------------------
def test_a_guided_verification_writes_one_report_in_its_dated_folder(
        tmp_path, qapp, monkeypatch):
    from workflow.measurement_report import (REPORT_TYPE_RECORD,
                                             SCOPE_ONE_DATE, recorded_document)
    s, fm, ctl, run, tab = _setup(tmp_path, qapp)
    emitted, saved = [], []
    tab.measure_finished.connect(emitted.append)
    try:
        _guided_ending(tab, run, monkeypatch, saved=saved)
    finally:
        tab.deleteLater()
    assert len(saved) == 1, "the verification-saved window was not reached"
    dst = saved[0]
    assert dst.parent.parent == run.verifications_dir
    reports = _reports_of(dst.parent)
    assert len(reports) == 1, (
        "a guided verification wrote no automatic report into its dated "
        f"folder's reports/: {list(dst.parent.rglob('*'))}")
    doc = recorded_document(json.loads(reports[0].read_text(encoding="utf-8")))
    assert doc is not None, "the automatic report carries no document block"
    assert doc["scope"] == SCOPE_ONE_DATE
    # K13: a verification's automatic report is Preferences' default type,
    # never the Printing record.
    assert doc["type"] != REPORT_TYPE_RECORD, doc["type"]
    assert [m["ti3"] for m in doc["measurements"]] == [dst.name]
    # Nothing in the run's own reports/ and nothing in verifications/reports/.
    assert not _reports_of(run.dir)
    assert not _reports_of(run.verifications_dir)
    # And still never advanced to Build Profile.
    assert emitted == [], "a verification emitted measure_finished"
    assert "Measurement report saved" in tab._log.toPlainText()


def test_a_verification_import_writes_one_report_in_its_dated_folder(
        tmp_path, qapp, monkeypatch):
    from workflow.measurement_report import (REPORT_TYPE_RECORD,
                                             SCOPE_ONE_DATE, recorded_document)
    s, fm, ctl, run, tab = _setup(tmp_path, qapp)
    tab._switch_mode("import")
    tab._import_path = _measurement(tmp_path)
    done, emitted = [], []
    monkeypatch.setattr(tab, "_show_import_done",
                        lambda verification, dst: done.append(dst))
    monkeypatch.setattr(tab, "_ask_how_printed", lambda ti3: None)
    tab.measure_finished.connect(emitted.append)
    try:
        tab._on_import_measurement()
    finally:
        tab.deleteLater()
    assert len(done) == 1, "the import did not finish"
    reports = _reports_of(done[0].parent)
    assert len(reports) == 1, (
        "a verification import wrote no automatic report: "
        f"{list(done[0].parent.rglob('*'))}")
    doc = recorded_document(json.loads(reports[0].read_text(encoding="utf-8")))
    assert doc is not None and doc["scope"] == SCOPE_ONE_DATE
    assert doc["type"] != REPORT_TYPE_RECORD
    assert emitted == []


# --------------------------------------------------------------------------
# boundary: the tick box off, a date measured again
# --------------------------------------------------------------------------
def test_with_the_tick_box_off_a_verification_writes_no_report(
        tmp_path, qapp, monkeypatch):
    s, fm, ctl, run, tab = _setup(tmp_path, qapp, tick=False)
    saved = []
    try:
        _guided_ending(tab, run, monkeypatch, saved=saved)
    finally:
        tab.deleteLater()
    assert len(saved) == 1 and saved[0].exists()
    assert not list(run.dir.rglob("report_*.json"))
    assert not (saved[0].parent / "reports").exists(), \
        "an empty reports/ folder was made with the tick box off"


def test_with_the_tick_box_off_an_import_writes_no_report(
        tmp_path, qapp, monkeypatch):
    s, fm, ctl, run, tab = _setup(tmp_path, qapp, tick=False)
    tab._switch_mode("import")
    tab._import_path = _measurement(tmp_path)
    done = []
    monkeypatch.setattr(tab, "_show_import_done",
                        lambda verification, dst: done.append(dst))
    monkeypatch.setattr(tab, "_ask_how_printed", lambda ti3: None)
    try:
        tab._on_import_measurement()
    finally:
        tab.deleteLater()
    assert len(done) == 1
    assert not list(run.dir.rglob("report_*.json"))


def test_measuring_a_date_again_leaves_its_old_reports_byte_identical(
        tmp_path, qapp, monkeypatch):
    """The bar's target names an existing date: the measurement is replaced
    (as before) and the date gains exactly ONE new report beside the old ones,
    which are not touched byte for byte. And the window then opens on the
    NEW one (P.10, the latest created)."""
    import time
    s, fm, ctl, run, tab = _setup(tmp_path, qapp)
    saved = []
    try:
        _guided_ending(tab, run, monkeypatch, saved=saved)
        first = saved[0]
        vid = first.parent.name
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in _reports_of(first.parent)}
        assert len(before) == 1
        ctl.set_verification_id(vid)
        assert ctl.target.verification_id == vid
        time.sleep(1.1)              # a new stamp, as a real second read has
        _guided_ending(tab, run, monkeypatch, saved=saved)
    finally:
        tab.deleteLater()
    assert len(saved) == 2 and saved[1] == first, saved
    after = _reports_of(first.parent)
    assert len(after) == 2, after
    for p, (data, mtime) in before.items():
        assert p.read_bytes() == data, f"{p.name} was rewritten"
        assert p.stat().st_mtime_ns == mtime
    new = (set(after) - set(before)).pop()

    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=first)
    try:
        qapp.processEvents()
        entry = next(d for d in dlg._saved_documents(
            dlg._run_ctx.run if dlg._run_ctx else None)
            if d["key"] == dlg._loaded_doc_id)
        names = [n for _r, n in entry["members"]]
        assert names == [new.name], (names, new.name)
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# the window it opens: on the saved report, and Generate after a change asks
# --------------------------------------------------------------------------
def test_open_measurement_report_lands_on_the_saved_report_and_generate_asks(
        tmp_path, qapp, monkeypatch):
    """Knut's sequence of 2026-10-01, through the real windows: verification
    read -> "Open measurement report" in the saved window -> the window shows
    the automatic report (not "New report…") -> Judged against changed ->
    Generate asks Create New / Update / Cancel, and Cancel writes nothing."""
    from ui.dialogs.measurement_report_dialog import (NEW_REPORT_KEY,
                                                      MeasurementReportDialog)
    s, fm, ctl, run, tab = _setup(tmp_path, qapp)
    seen: dict = {}
    real_exec = QDialog.exec

    def _exec(self):
        if isinstance(self, MeasurementReportDialog):
            qapp.processEvents()
            seen["loaded"] = self._loaded_doc_id
            seen["shown"] = str(self._saved_combo.currentData() or "")
            folder = Path(seen["dst"]).parent
            seen["before"] = {p: p.read_bytes() for p in _reports_of(folder)}
            asked = []
            self._ask_update_or_create_new = (
                lambda: (asked.append(self._loaded_doc_id), "cancel")[1])
            combo = self._set_combo
            for i in range(combo.count()):
                if combo.itemData(i) and combo.itemData(i) != combo.currentData():
                    combo.setCurrentIndex(i)
                    break
            qapp.processEvents()
            seen["red"] = self._settings_were_modified()
            self._on_generate_report()
            qapp.processEvents()
            seen["asked"] = asked
            seen["after"] = {p: p.read_bytes() for p in _reports_of(folder)}
            return 0
        # the verification-saved window: press its "Open measurement report"
        for b in self.findChildren(QPushButton):
            if b.objectName() == "primary":
                b.click()
                return 1
        return real_exec(self)

    monkeypatch.setattr(QDialog, "exec", _exec)
    monkeypatch.setattr(tab, "_ask_how_printed", lambda ti3: None)
    orig = tab._maybe_save_measurement_report

    def _spy(ti3):
        seen["dst"] = ti3
        orig(ti3)
    monkeypatch.setattr(tab, "_maybe_save_measurement_report", _spy)
    try:
        _measured_by_chartread(run)
        tab._ti1_path = run.verify_chart_ti2
        tab._verify_run = True
        tab._ti3_mtime_before = None
        tab._all_done_shown = True
        tab._measure_failed = False
        tab._on_measure_done(0)
    finally:
        tab.deleteLater()
    assert "loaded" in seen, "the Measurement Report window was not opened"
    assert seen["loaded"] and seen["loaded"] != NEW_REPORT_KEY, (
        "the window opened on 'New report…', not on the automatic report")
    assert seen["shown"] == seen["loaded"]
    assert len(seen["before"]) == 1
    assert seen["red"], "changing Judged against raised no red line"
    assert seen["asked"] == [seen["loaded"]], (
        "Generate after a changed setting wrote without asking")
    assert seen["after"] == seen["before"], "Cancel wrote a report"
