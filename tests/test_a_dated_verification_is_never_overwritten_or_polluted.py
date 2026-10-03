"""Review of f53874ca (4.3.3-beta.3): Refine / resume on a dated verification,
driven on screen on a copy of Knut's project (#182 5951427228) with the reader
simulated. Four faults, each pinned here through the real ending
(`_on_measure_done`) or the real file helpers:

1. "Measure anyway" on a measured date wrote the new reading over the date's
   measurement with no copy anywhere, although M-REPLACE-COMPLETE promises the
   old one "is moved to the run's 'old' folder ... nothing is deleted", and
   §2a of unified_measurement_management.md keeps a verification's copy in
   ``verifications/<date>/old/``.
2. The session guard of a resumed verification kept its copy in
   ``verifications/old/`` (the chart's archive) rather than the date's own
   ``old/`` (§2a).
3. After every verification read, "This chart already has a measurement" opened
   and the overlay was cleared: a settle during the read remembered the working
   file beside the chart as "the selection", and the dated file after it looked
   like another date being picked.
4. A copy left beside the shared chart by a killed session counted as CHART:
   the next date's ``chart/`` snapshot took one date's readings with it, and
   Restore Used Chart would stash and discard it.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402

from tests.test_a_dated_verification_offers_its_own_measurement import (  # noqa: E402
    TI3, _env, _pump)

NEW = TI3.replace("90.0 93.0", "91.5 94.5")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def quiet(monkeypatch):
    from ui.tabs.tab_measure import TabMeasure
    offers: list = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    monkeypatch.setattr(TabMeasure, "_maybe_offer_existing_overlay",
                        lambda self: offers.append("OFFER"))
    monkeypatch.setattr(TabMeasure, "_ask_how_printed", lambda self, t: None)
    monkeypatch.setattr(TabMeasure, "_show_verification_saved",
                        lambda self, d: None)
    monkeypatch.setattr(TabMeasure, "_maybe_save_measurement_report",
                        lambda self, d: None)
    return offers


def _read(tab, run, text, *, resume_session: bool):
    """What chartread leaves beside the chart, then the real ending."""
    beside = run.verify_chart_ti2.with_suffix(".ti3")
    if resume_session:
        tab._resume_cb.setChecked(True)
        assert tab._stage_verification_for_resume() == beside
        tab._begin_session_guard(beside)
    tab._session_live = True
    tab._ti3_mtime_before = beside.stat().st_mtime - 5 if beside.exists() else None
    beside.write_text(text, encoding="utf-8")
    tab._ti1_path = run.verify_chart_ti2
    tab._verify_run = True
    tab._all_done_shown = True
    tab._measure_failed = False
    tab._on_measure_done(0)
    return beside


def test_measure_anyway_keeps_the_dates_measurement_in_its_old(
        qapp, tmp_path, quiet):
    run, ctl, tab, measured, empty = _env(tmp_path)
    ctl.set_verification_id(measured.id)
    _pump()
    beside = _read(tab, run, NEW, resume_session=False)
    assert not beside.exists()
    assert "91.5" in measured.measurement_ti3.read_text(encoding="utf-8")
    kept = sorted((measured.dir / "old").glob("*/*.ti3"))
    assert kept, ("the date's previous measurement was overwritten with no "
                  "copy in verifications/<date>/old/")
    assert kept[0].read_text(encoding="utf-8") == TI3


def test_a_resumed_dates_guard_copy_is_in_the_dates_old(qapp, tmp_path, quiet):
    run, ctl, tab, measured, empty = _env(tmp_path)
    tab.show()
    ctl.set_verification_id(measured.id)
    _pump()
    _read(tab, run, NEW, resume_session=True)
    tab.hide()
    assert "91.5" in measured.measurement_ti3.read_text(encoding="utf-8")
    assert not run.verify_chart_ti2.with_suffix(".ti3").exists()
    in_date = sorted((measured.dir / "old").glob("*/*.ti3"))
    assert [p.read_text(encoding="utf-8") for p in in_date] == [TI3], (
        "exactly one copy of the pre-session measurement, in the date's old/")
    assert not list((run.verifications_dir / "old").glob("*/*.ti3"))


def test_no_existing_measurement_window_after_a_verification_read(
        qapp, tmp_path, quiet):
    run, ctl, tab, measured, empty = _env(tmp_path)
    tab.show()
    ctl.set_verification_id(measured.id)
    _pump()
    quiet.clear()
    tab._resume_cb.setChecked(True)
    tab._stage_verification_for_resume()
    tab._session_live = True
    tab._queue_selection_settle()          # something settles during the read
    _pump()
    _read(tab, run, NEW, resume_session=False)
    tab._queue_selection_settle()          # …and once it has ended
    _pump()
    tab.hide()
    assert quiet == [], ("'This chart already has a measurement' after the "
                         "date's own read")


def test_a_left_over_measurement_beside_the_chart_is_not_chart(
        qapp, tmp_path, quiet):
    from workflow.chart_slot import slot_for_verification
    from workflow.verify_chart_snapshot import (live_chart_files,
                                                snapshot_chart)
    run, ctl, tab, measured, empty = _env(tmp_path)
    beside = run.verify_chart_ti2.with_suffix(".ti3")
    beside.write_text(TI3, encoding="utf-8")         # a killed session's copy
    ref = run.verifications_dir / f"{run.verify_stem}-reference.ti3"
    ref.write_text(TI3, encoding="utf-8")            # this one IS chart
    names = {p.name for p in live_chart_files(run)}
    assert beside.name not in names and ref.name in names
    assert beside.name not in {
        p.name for p in slot_for_verification(empty).live_files()}
    snap = snapshot_chart(empty)
    assert not (snap / beside.name).exists(), \
        "one date's readings were copied into another date's chart snapshot"
    assert (snap / ref.name).exists()
