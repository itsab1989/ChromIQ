"""Beta 12 (review of build A): a sheet split by the profile's gamut with NO
patch inside it judges nothing, rather than judging every patch.

`verification_printing_and_target.md` B3d and `measurement_report_limits.md`
§26.4: the patches beyond the gamut are reported separately and never fail a
limit. `graded_de00` fell back to the all-patch block when the within-gamut
block was empty, so a sheet whose every colour lay beyond the gamut was
judged on exactly those colours and failed. Now the within-gamut rows read
N-A with the reason "no patch inside the gamut".
"""
from __future__ import annotations

import pytest

from workflow import measurement_report as mr


def _split_report(n_in: int, n_out: int) -> dict:
    """A verification whose all-patch figures fail any limit."""
    big = {"n": n_in + n_out, "avg_all": 9.0, "avg_low95": 8.0,
           "avg_high5": 20.0, "max_all": 25.0, "max_low95": 18.0}
    rep = {"is_verification": True, "sheet_kind": "verification",
           "reference_source": "source", "patches": n_in + n_out,
           "printing": {"colour": "through_profile", "route": "chromiq"},
           "de00": dict(big),
           "gamut_split": {"profile": "p.icc", "margin": 1.5,
                           "intent": "relative", "n_in": n_in,
                           "n_out": n_out, "de00_in": None,
                           "de00_out": dict(big)}}
    return rep


def test_zero_in_gamut_judges_nothing_beyond_the_gamut():
    rep = _split_report(0, 40)
    de, source = mr.graded_de00(rep)
    # NOT the all-patch block (the colours beyond the gamut)
    assert de == {} and source == mr.VERDICT_SOURCE_IN_GAMUT
    mr.stamp_verdict(rep, 2.0, 3.0)
    rows = {r["row_id"]: r for r in rep["verdict"]["rows"]}
    for rid in ("all_de00_avg", "all_de00_max"):
        assert rows[rid]["word"] != "FAIL", rows[rid]
        assert rows[rid]["value"] is None
        assert rows[rid]["reason"] == mr.REASON_NO_PATCH_IN_GAMUT
    assert not any(r["word"] == "FAIL" for r in rep["verdict"]["rows"])
    assert rep["verdict"]["all_pass"] is not False


def test_a_split_with_patches_inside_is_unchanged():
    rep = _split_report(10, 30)
    rep["gamut_split"]["de00_in"] = {"n": 10, "avg_all": 1.0,
                                     "avg_low95": 0.9, "avg_high5": 2.0,
                                     "max_all": 2.5, "max_low95": 2.0}
    assert not mr.no_patch_in_gamut(rep)
    de, source = mr.graded_de00(rep)
    assert source == mr.VERDICT_SOURCE_IN_GAMUT and de["max_all"] == 2.5


def test_no_split_still_judges_every_patch():
    rep = _split_report(0, 40)
    del rep["gamut_split"]
    assert not mr.no_patch_in_gamut(rep)
    de, source = mr.graded_de00(rep)
    assert source == mr.VERDICT_SOURCE_ALL and de["max_all"] == 25.0
    mr.stamp_verdict(rep, 2.0, 3.0)
    assert rep["verdict"]["all_pass"] is False   # MUTATION guard: still judged


def test_the_reason_has_a_sentence_and_is_a_measured_sheet_reason():
    assert mr.REASON_NO_PATCH_IN_GAMUT in mr.AFTER_PRINTING_REASONS
    import inspect
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    src = inspect.getsource(MeasurementReportDialog._reason_sentence)
    assert f'"{mr.REASON_NO_PATCH_IN_GAMUT}"' in src


@pytest.fixture()
def qapp():
    from PyQt6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def test_a_built_report_with_every_patch_beyond_the_gamut(
        qapp, tmp_path, monkeypatch):
    """Through `build_report` itself, the round trip stubbed to say every
    colour is beyond the gamut: the evenness rows judge nothing either."""
    from tests.test_gamut_split_report import _measured
    _s, _run, ti3 = _measured(tmp_path, monkeypatch,
                              lambda labs, *a, **kw: [False] * len(labs))
    rep = mr.build_report(ti3, argyll_bin="/x/bin")
    gs = rep["gamut_split"]
    assert gs["n_in"] == 0 and gs["n_out"] > 0
    mr.stamp_verdict(rep, 0.001, 0.001)       # any measured colour fails these
    rows = {r["row_id"]: r for r in rep["verdict"]["rows"]}
    assert rows["all_de00_avg"]["reason"] == mr.REASON_NO_PATCH_IN_GAMUT
    assert not any(r["word"] == "FAIL" for r in rep["verdict"]["rows"]), [
        (r["row_id"], r["value"]) for r in rep["verdict"]["rows"]
        if r["word"] == "FAIL"]
    for rid in mr.EVENNESS_ROWS:
        cell = mr.row_values(rep)[rid]
        assert cell["value"] is None
