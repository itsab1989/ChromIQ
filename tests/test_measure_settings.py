"""The Measure tab's per-target settings, and the guard that keeps them honest.

Knut put Measure in scope (#130: *"measure tab must be included"*) because two
of his own reports came from these controls — the ``-N`` that survived from an
earlier session and the resume tick that disagreed with itself.

`MEASURE_CONTROLS` is hand-written, which is the shape of mistake that has cost
this project several faults. The drift test below is therefore the important one
here: a `MeasureParams` field that nobody maps fails the suite instead of being
quietly absent from every target's stored settings.
"""
import dataclasses

import pytest

from workflow.measure_settings import (MEASURE_CONTROLS, NOT_A_SETTING, apply,
                                       snapshot)


class _Check:
    def __init__(self, on=False):
        self._on = on
    def isChecked(self):        return self._on
    def setChecked(self, v):    self._on = bool(v)


class _Combo:
    def __init__(self, data=("auto", "disable", "force"), current=0):
        self._data, self._i = list(data), current
    def currentData(self):      return self._data[self._i]
    def findData(self, v):      return self._data.index(v) if v in self._data else -1
    def setCurrentIndex(self, i): self._i = i


class _Opt:
    def __init__(self, key, on=False, widget=None):
        self.key, self.checkbox, self.widget = key, _Check(on), widget


class _Tab:
    def __init__(self):
        self._m_suppress_cb = _Check(True)
        self._m_nocal_cb    = _Check(False)
        self._m_pbp_cb      = _Check(False)
        self._m_resume_cb   = _Check(False)
        self._m_bidir_combo = _Combo()
        self._chartread_opts = [_Opt("tolerance", widget=_Combo(("0.5", "0.7"))),
                                _Opt("highres")]


def test_the_drift_guard_every_setting_is_mapped_or_explained():
    """The one that matters: a new MeasureParams field cannot go unnoticed."""
    from workflow.measure_manager import MeasureParams

    fields = {f.name for f in dataclasses.fields(MeasureParams)}
    mapped = set(MEASURE_CONTROLS) | set(NOT_A_SETTING)
    forgotten = fields - mapped
    assert not forgotten, (
        f"{sorted(forgotten)} are MeasureParams fields that are neither stored "
        f"per target nor listed in NOT_A_SETTING with a reason — so they would "
        f"silently not follow the run"
    )


def test_nothing_is_excluded_that_does_not_exist():
    """A stale exclusion hides a real gap just as well as a missing one."""
    from workflow.measure_manager import MeasureParams

    fields = {f.name for f in dataclasses.fields(MeasureParams)}
    stale = set(NOT_A_SETTING) - fields
    assert not stale, f"NOT_A_SETTING lists fields that are gone: {sorted(stale)}"


def test_it_reads_the_controls():
    tab = _Tab()
    snap = snapshot(tab)
    assert snap["suppress_warnings"] == {"enabled": True, "value": True}
    assert snap["disable_initial_cal"] == {"enabled": True, "value": False}
    assert snap["bidirectional"]["value"] == "auto"


def test_it_reads_every_chartread_option():
    tab = _Tab()
    snap = snapshot(tab)
    assert "chartread.tolerance" in snap and "chartread.highres" in snap
    assert snap["chartread.tolerance"]["value"] == "0.5"


def test_a_round_trip_restores_both_halves():
    tab = _Tab()
    tab._m_nocal_cb.setChecked(True)
    tab._m_bidir_combo.setCurrentIndex(2)
    tab._chartread_opts[0].checkbox.setChecked(True)
    snap = snapshot(tab)

    other = _Tab()
    assert apply(other, snap) == []
    assert other._m_nocal_cb.isChecked() is True
    assert other._m_bidir_combo.currentData() == "force"
    assert other._chartread_opts[0].checkbox.isChecked() is True


def test_the_N_flag_does_not_leak_between_targets():
    """His beta.148 report, as a test: -N must not survive into another run."""
    a = _Tab(); a._m_nocal_cb.setChecked(True)
    b = _Tab()
    apply(b, snapshot(b))                      # b keeps its own, untouched
    assert b._m_nocal_cb.isChecked() is False, (
        "skip-initial-calibration leaked from one target to another"
    )


def test_an_unknown_key_is_reported_not_raised():
    tab = _Tab()
    assert apply(tab, {"gone": {"enabled": True, "value": 1}}) == ["gone"]
    assert apply(tab, {"suppress_warnings": "not a dict"}) == ["suppress_warnings"]


def test_a_missing_control_is_skipped_not_crashed():
    """A tab part-built (or a mode where a row is absent) must not raise."""
    class Bare:
        _chartread_opts = []
    assert snapshot(Bare()) == {}
    assert apply(Bare(), {"suppress_warnings": {"enabled": True, "value": True}}) == []
