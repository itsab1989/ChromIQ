"""The grey pair and the tone ramp of ChromIQ's own three limit sets (4.3.10).

Knut proposed new numbers on 2026-10-22 (agent 31 checked them against the
real sheets on this machine first) and Basti approved the parts that differ
from what shipped on 2026-10-23:

=====================================================  =====  =====  =====
row                                                    def.   tight  quick
=====================================================  =====  =====  =====
Average ΔCh, grey balance of the grey ramp             2.0    1.0    4.0
Maximum ΔCh, grey balance of the grey ramp             3.0    1.5    6.0
Maximum ΔL*, single-colour ramps 30 % to 70 %          3.0    1.5    6.0
=====================================================  =====  =====  =====

They were 1.5 / 1.0 / 3.0, 3.0 / 2.0 / 7.0 and "–" (no limit). Nothing else
moves: the five ΔE00 rows wait for Basti's talk with Knut, and the read-only
ISO and the Custom ISO columns keep what they had.

What existing data does (docs/design/measurement_report_limits.md §2):

* a saved report keeps the limits and verdicts it was saved with (§25.3);
* a Preferences row the user edited keeps the user's number, because an
  override is only stored where it differs from the factory number;
* a run an earlier ChromIQ bound (before beta 40) carries a copy of the old
  factory numbers; a new report of it takes the new ones where the copy still
  holds what ChromIQ shipped, and keeps any number the user chose
  (`refresh_bound_grey_tone`, the pattern of B8-1501's evenness rows).

Every test here is red on the code before this change.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from core.file_manager import Project                     # noqa: E402
from tests.helpers.legacy_run_meta import bind_run         # noqa: E402
from workflow import compliance_sets as cs                 # noqa: E402
from workflow.compliance_sets import (Limit, effective_limits,  # noqa: E402
                                      factory_limits, limits_from_json,
                                      limits_to_json)
from workflow.run_compliance import run_limits             # noqa: E402

AVG, MAX, RAMP = ("grey_balance_neutral_ramp_avg",
                  "grey_balance_neutral_ramp_max", "ramps_30_70_dl_max")
CHROMIQ = ("chromiq_default", "chromiq_tight", "chromiq_quick")

#: Basti's approval of 2026-10-23, typed in from the brief, not read from
#: the code under test.
APPROVED = {
    "chromiq_default": {AVG: 2.0, MAX: 3.0, RAMP: 3.0},
    "chromiq_tight": {AVG: 1.0, MAX: 1.5, RAMP: 1.5},
    "chromiq_quick": {AVG: 4.0, MAX: 6.0, RAMP: 6.0},
}
#: What shipped before. ``None`` is "–".
FORMER = {
    "chromiq_default": {AVG: 1.5, MAX: 3.0, RAMP: None},
    "chromiq_tight": {AVG: 1.0, MAX: 2.0, RAMP: None},
    "chromiq_quick": {AVG: 3.0, MAX: 7.0, RAMP: None},
}


# ---------------------------------------------------------------- the numbers
@pytest.mark.parametrize("set_id", CHROMIQ)
def test_the_three_rows_carry_the_approved_numbers(set_id):
    f = factory_limits(set_id)
    for rid, want in APPROVED[set_id].items():
        assert f[rid] == Limit.value(want), (set_id, rid, f[rid])


def test_the_de00_rows_did_not_move():
    """Basti: the ΔE00 rows stay as they are until he has talked to Knut."""
    want = {"chromiq_default": (2.0, 2.0, 2.0, 3.0, 3.0),
            "chromiq_tight": (1.0, 1.0, 1.0, 1.5, 1.5),
            "chromiq_quick": (4.0, 4.0, 4.0, 6.0, 6.0)}
    rows = ("all_de00_avg", "best95_de00_avg", "worst5_de00_avg",
            "all_de00_max", "all_de00_p95")
    for sid, nums in want.items():
        f = factory_limits(sid)
        assert tuple(f[r].number for r in rows) == nums, sid


def test_the_iso_and_custom_columns_did_not_move():
    """The Custom ISO columns take Knut's researched 1.5 / 3.0 / 2.0 on these
    rows, and the read-only columns what the shipped file gives them
    (ISO 12647-7 puts no limit on the ramp, ISO 12647-8 2.0)."""
    for sid in ("custom_iso_12647_7", "custom_iso_12647_8"):
        f = factory_limits(sid)
        assert (f[AVG].number, f[MAX].number, f[RAMP].number) == \
            (1.5, 3.0, 2.0), sid
    assert factory_limits("iso_12647_7")[RAMP].kind == "none"
    assert factory_limits("iso_12647_8")[RAMP] == Limit.value(2.0)


# ---------------------------------------------------------- Preferences rows
@pytest.mark.parametrize("set_id", CHROMIQ)
def test_a_preferences_row_the_user_edited_keeps_the_users_number(set_id):
    mine = {set_id: {AVG: 2.6, MAX: 4.4, RAMP: None}}
    got = effective_limits(set_id, mine)
    assert got[AVG] == Limit.value(2.6)
    assert got[MAX] == Limit.value(4.4)
    assert got[RAMP] == Limit.none(), "the user's '–' must stay a '–'"


# ------------------------------------------------- a run an earlier build bound
def _bound(tmp_path, set_id, cells: dict):
    """A run bound the way an earlier ChromIQ bound it, with *cells* as the
    copied numbers on the three rows (``None`` = "–", ``"absent"`` = a copy
    from a build that did not write the row)."""
    proj = Project.create(tmp_path / "P", "P")
    run = proj.current_run()
    run.ensure_dir()
    bind_run(run, set_id, None)
    meta = run.load_meta()
    lim = limits_from_json(meta.compliance_thresholds, set_id)
    for rid, v in cells.items():
        if v == "absent":
            lim.pop(rid, None)
        elif v is None:
            lim[rid] = Limit.none()
        elif isinstance(v, tuple):          # the bracketed form before 09-21
            lim[rid] = Limit.should(v[0])
        else:
            lim[rid] = Limit.value(v)
    meta.compliance_thresholds = limits_to_json(lim)
    run.save_meta(meta)
    return run


@pytest.mark.parametrize("set_id", CHROMIQ)
def test_a_copy_of_the_old_factory_numbers_takes_the_new_ones(tmp_path, set_id):
    run = _bound(tmp_path, set_id, FORMER[set_id])
    lim = run_limits(run, None)
    assert lim.bound
    for rid, want in APPROVED[set_id].items():
        assert lim.limits[rid] == Limit.value(want), (rid, lim.limits[rid])
    assert lim.edited is False, "nobody edited anything"


@pytest.mark.parametrize("set_id", CHROMIQ)
def test_the_old_bracketed_form_and_a_missing_row_take_the_new_ones(
        tmp_path, set_id):
    old = FORMER[set_id]
    run = _bound(tmp_path, set_id,
                 {AVG: (old[AVG],), MAX: (old[MAX],), RAMP: "absent"})
    assert RAMP not in run.load_meta().compliance_thresholds
    lim = run_limits(run, None)
    for rid, want in APPROVED[set_id].items():
        assert lim.limits[rid] == Limit.value(want), (rid, lim.limits[rid])
    assert lim.edited is False


def test_a_number_the_user_chose_on_the_run_stays_the_users(tmp_path):
    run = _bound(tmp_path, "chromiq_default", {AVG: 1.7, MAX: 2.5, RAMP: 4.0})
    lim = run_limits(run, None)
    assert (lim.limits[AVG], lim.limits[MAX], lim.limits[RAMP]) == (
        Limit.value(1.7), Limit.value(2.5), Limit.value(4.0))
    assert lim.edited is True


def test_one_row_the_user_chose_and_two_left_alone(tmp_path):
    run = _bound(tmp_path, "chromiq_quick", {AVG: 3.0, MAX: 5.0, RAMP: None})
    lim = run_limits(run, None)
    assert lim.limits[AVG] == Limit.value(4.0)        # was the factory 3.0
    assert lim.limits[MAX] == Limit.value(5.0)        # the user's own
    assert lim.limits[RAMP] == Limit.value(6.0)       # was the factory "–"


def test_a_copy_of_a_number_that_did_not_change_is_left_alone(tmp_path):
    """Default's grey maximum was 3.0 and is 3.0: nothing to do, and an
    edited row elsewhere in the copy is not touched either."""
    run = _bound(tmp_path, "chromiq_default", FORMER["chromiq_default"])
    meta = run.load_meta()
    meta.compliance_thresholds["all_de00_avg"] = 2.4
    run.save_meta(meta)
    lim = run_limits(run, None)
    assert lim.limits[MAX] == Limit.value(3.0)
    assert lim.limits["all_de00_avg"] == Limit.value(2.4)
    assert lim.edited is True


def test_a_custom_column_copy_is_not_refreshed(tmp_path):
    """The Custom ISO columns did not change, so their copies are not ours
    to touch on these rows, whatever they hold."""
    run = _bound(tmp_path, "custom_iso_12647_7", {AVG: 1.5, MAX: 7.0, RAMP: None})
    lim = run_limits(run, None)
    assert lim.limits[AVG] == Limit.value(1.5)
    assert lim.limits[MAX] == Limit.value(7.0)
    assert lim.limits[RAMP] == Limit.none()


def test_the_table_of_former_numbers_is_what_shipped():
    """`FORMER_GREY_TONE_FACTORY` against the numbers typed in above."""
    for sid, rows in FORMER.items():
        for rid, old in rows.items():
            assert cs.FORMER_GREY_TONE_FACTORY[sid][rid] == frozenset({old}), \
                (sid, rid)
    assert set(cs.FORMER_GREY_TONE_FACTORY) == set(CHROMIQ)


# ------------------------------------------------- the Report limits window
@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _settings(tmp_path):
    from PyQt6.QtCore import QSettings
    from core.settings import AppSettings
    s = AppSettings()
    s._qs = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return s


def test_the_window_shows_the_new_numbers_and_restore_brings_them_back(
        qapp, tmp_path):
    from ui.dialogs.thresholds_dialog import ThresholdsDialog
    s = _settings(tmp_path)
    s.set_compliance_overrides({sid: {AVG: 0.9, MAX: 0.9, RAMP: 0.9}
                                for sid in CHROMIQ})
    dlg = ThresholdsDialog(s, None)
    try:
        for sid in CHROMIQ:
            for rid in (AVG, MAX, RAMP):
                assert dlg._cells[(sid, rid)].value() == pytest.approx(0.9)
            btn = next(w for w in dlg._column_widgets[sid]
                       if w.__class__.__name__ == "QPushButton")
            btn.click()
            for rid, want in APPROVED[sid].items():
                assert dlg._cells[(sid, rid)].value() == pytest.approx(want), \
                    (sid, rid)
        assert s.get_compliance_overrides() == {}
    finally:
        dlg.deleteLater()
