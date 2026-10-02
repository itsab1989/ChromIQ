"""#182 (a), the two silent-write doors the challenge found in Generate.

Knut, 2026-10-01: *"Any change in the settings must ask … never update the
existing report selected without any warning."* K4 (§13.8, CONFIRMED
2026-09-23): with a report selected in "Report shown", Generate never writes a
new report without asking. K65 (§54.1, CONFIRMED): nothing on the page changes
before Generate.

Two doors still wrote without the question (EVIDENCE.md A6 3 and 4):

* GAP 3: the loaded id EMPTY (not "New report…") skipped the guard altogether.
  The tests reach that state by clearing ``_loaded_doc_id`` on a window that
  shows a saved report, which is what an early return of
  ``_adopt_visible_document`` leaves behind.
* GAP 4: the loaded report no longer in the list made the window reload what
  the list named; on "New report…" that was ``_start_new_report()``, which put
  the DEFAULTS back, so the user's moved setting was thrown away and a report
  of the defaults written. The tests take the loaded report out of the list
  the way the list itself does (``_saved_documents`` no longer yields it).

No new message text: the existing three-button question is asked.

MUTATIONS, each proved red (MUTATIONS.md of H_impl_182):
* restore the old guard ``if updating is None and loaded and loaded !=
  NEW_REPORT_KEY:`` with ``_load_what_the_list_names(force=True)``: GAP 3 and
  GAP 4 tests red;
* drop ``self._hold_as_loaded(named)`` / ``updating = named``: the GAP 3 and
  GAP 4b tests red.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _dates(tmp_path, qapp, n=1):
    """A run with *n* dated verifications, each with its automatic report."""
    from tests.test_import_measurement_module import _PATCHES, _cgats
    from tests.test_the_measurement_report_defaults_are_knuts import (
        _a_measured_run, _measure_tab)
    s, _fm, _ctl, run, v = _a_measured_run(tmp_path)
    dates = [v]
    tab = _measure_tab(s, qapp)
    try:
        tab._maybe_save_measurement_report(v.measurement_ti3)
        for _ in range(n - 1):
            time.sleep(1.1)
            w = run.new_verification()
            w.ensure_dir()
            w.measurement_ti3.write_text(_cgats("CTI3", _PATCHES),
                                         encoding="utf-8")
            tab._maybe_save_measurement_report(w.measurement_ti3)
            dates.append(w)
    finally:
        tab.deleteLater()
    return s, run, dates


def _window(s, ti3, qapp):
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    dlg = MeasurementReportDialog(s, None, initial_ti3=ti3)
    qapp.processEvents()
    asked: list = []
    dlg._ask_update_or_create_new = (
        lambda: (asked.append(dlg._loaded_doc_id), "cancel")[1])
    return dlg, asked


def _move_the_set(dlg, qapp) -> str:
    combo = dlg._set_combo
    for i in range(combo.count()):
        if combo.itemData(i) and combo.itemData(i) != combo.currentData():
            combo.setCurrentIndex(i)
            qapp.processEvents()
            return str(combo.itemData(i))
    raise AssertionError("no other limit set to choose")


def _all_reports(run) -> "dict[Path, bytes]":
    return {p: p.read_bytes() for p in Path(run.dir).rglob("report_*.json")
            if "old" not in p.parts}


def _drop_from_the_list(dlg, monkeypatch, key: str) -> None:
    real = type(dlg)._saved_documents

    def _without(self, run):
        return [d for d in real(self, run) if d["key"] != key]
    monkeypatch.setattr(type(dlg), "_saved_documents", _without)


# --------------------------------------------------------------------------
# GAP 3: an empty loaded id
# --------------------------------------------------------------------------
def test_gap3_an_empty_loaded_id_under_a_saved_report_asks(tmp_path, qapp):
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, run, (v,) = _dates(tmp_path, qapp)
    dlg, asked = _window(s, v.measurement_ti3, qapp)
    try:
        shown = str(dlg._saved_combo.currentData() or "")
        assert shown and shown != NEW_REPORT_KEY, "the window opened on New report…"
        _move_the_set(dlg, qapp)
        dlg._loaded_doc_id = ""
        before = _all_reports(run)
        dlg._on_generate_report()
        qapp.processEvents()
        assert asked == [shown], (
            "Generate under a saved report wrote without asking", asked)
        assert _all_reports(run) == before, "Cancel wrote a report"
    finally:
        dlg.close()


def test_gap3_create_new_keeps_the_users_setting(tmp_path, qapp):
    s, run, (v,) = _dates(tmp_path, qapp)
    dlg, asked = _window(s, v.measurement_ti3, qapp)
    dlg._ask_update_or_create_new = lambda: (asked.append(1), "new")[1]
    try:
        chosen = _move_the_set(dlg, qapp)
        dlg._loaded_doc_id = ""
        before = _all_reports(run)
        dlg._on_generate_report()
        qapp.processEvents()
        assert asked == [1]
        after = _all_reports(run)
        new = set(after) - set(before)
        assert len(new) == 1, new
        assert all(after[p] == b for p, b in before.items())
        rep = json.loads(new.pop().read_text(encoding="utf-8"))
        assert rep["compliance"]["set_id"] == chosen
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# GAP 4: the loaded report gone from the list
# --------------------------------------------------------------------------
def test_gap4_a_vanished_report_never_throws_the_users_setting_away(
        tmp_path, qapp, monkeypatch):
    """The loaded report drops out of the list and the list, refilled, lands
    on "New report…": the press writes a NEW report (nothing existing is
    touched) judged against the set the user chose, never the defaults that
    `_start_new_report` put back."""
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, run, (v,) = _dates(tmp_path, qapp)
    dlg, asked = _window(s, v.measurement_ti3, qapp)
    try:
        loaded = dlg._loaded_doc_id
        chosen = _move_the_set(dlg, qapp)
        _drop_from_the_list(dlg, monkeypatch, loaded)
        combo = dlg._saved_combo
        combo.blockSignals(True)
        combo.setCurrentIndex(combo.findData(NEW_REPORT_KEY))
        combo.blockSignals(False)
        before = _all_reports(run)
        dlg._on_generate_report()
        qapp.processEvents()
        assert dlg._set_combo.currentData() == chosen, (
            "the press put the list's settings back over the user's")
        after = _all_reports(run)
        assert all(after[p] == b for p, b in before.items()), \
            "a saved report was rewritten"
        new = set(after) - set(before)
        assert len(new) == 1, new
        rep = json.loads(new.pop().read_text(encoding="utf-8"))
        assert rep["compliance"]["set_id"] == chosen, (
            "the new report was not judged against the set on screen")
    finally:
        dlg.close()


def test_gap4b_a_list_naming_another_saved_report_asks_about_it(
        tmp_path, qapp, monkeypatch):
    """The loaded report drops out of the list and the list names another
    saved report: the press asks about THAT one, and the setting on screen
    is still the user's when it asks."""
    s, run, (v1, v2) = _dates(tmp_path, qapp, n=2)
    dlg, asked = _window(s, v2.measurement_ti3, qapp)
    try:
        loaded = dlg._loaded_doc_id
        chosen = _move_the_set(dlg, qapp)
        combo = dlg._saved_combo
        other = next(str(combo.itemData(i)) for i in range(combo.count())
                     if combo.itemData(i) and combo.itemData(i) != loaded
                     and str(combo.itemData(i)).startswith("id:"))
        _drop_from_the_list(dlg, monkeypatch, loaded)
        combo.blockSignals(True)
        combo.setCurrentIndex(combo.findData(other))
        combo.blockSignals(False)
        seen = {}
        dlg._ask_update_or_create_new = lambda: (
            asked.append(dlg._loaded_doc_id),
            seen.setdefault("set", dlg._set_combo.currentData()), "cancel")[2]
        before = _all_reports(run)
        dlg._on_generate_report()
        qapp.processEvents()
        assert asked == [other], asked
        assert seen["set"] == chosen, "the user's setting was replaced first"
        assert _all_reports(run) == before
    finally:
        dlg.close()


# --------------------------------------------------------------------------
# normal: New report… still writes a new report, as it always has
# --------------------------------------------------------------------------
def test_a1_new_report_loaded_under_a_saved_report_asks(tmp_path, qapp):
    """#182 A1 (Knut 5943085974): the window shows the one saved report in
    "Report shown"; whatever the loaded id says, Generate asks about it.
    The state the gap-3 guard still let through: loaded id "New report…"
    while the list names the saved report. (Knut's on-screen sequence asks;
    L_impl_knut_rulings/k3_done, k3_tools.) MUTATION: drop the A1 block in
    `_generate_once`: red."""
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, run, (v,) = _dates(tmp_path, qapp)
    dlg, asked = _window(s, v.measurement_ti3, qapp)
    try:
        shown = str(dlg._saved_combo.currentData() or "")
        assert shown and shown != NEW_REPORT_KEY
        _move_the_set(dlg, qapp)
        dlg._loaded_doc_id = NEW_REPORT_KEY
        before = _all_reports(run)
        dlg._on_generate_report()
        qapp.processEvents()
        assert asked == [shown], (
            "Generate under a saved report wrote without asking", asked)
        assert _all_reports(run) == before, "Cancel wrote a report"
    finally:
        dlg.close()


def test_new_report_still_writes_without_the_question(tmp_path, qapp):
    from ui.dialogs.measurement_report_dialog import NEW_REPORT_KEY
    s, run, (v,) = _dates(tmp_path, qapp)
    dlg, asked = _window(s, v.measurement_ti3, qapp)
    try:
        combo = dlg._saved_combo
        combo.setCurrentIndex(combo.findData(NEW_REPORT_KEY))
        qapp.processEvents()
        assert dlg._loaded_doc_id == NEW_REPORT_KEY
        before = _all_reports(run)
        dlg._on_generate_report()
        qapp.processEvents()
        assert asked == []
        assert len(set(_all_reports(run)) - set(before)) == 1
    finally:
        dlg.close()
