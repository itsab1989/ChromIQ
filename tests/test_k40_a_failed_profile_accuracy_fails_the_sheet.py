"""k40 (Knut #182 6059912998, answer 1): a FAILED Profile accuracy table on a
verification printed through its profile fails the sheet's overall word.

Knut named the five metrics: "Average ΔE00, all patches", "Average ΔE00,
lowest 95 %", "Average ΔE00, highest 5 %", "Maximum ΔE00, all patches" and
"Maximum ΔE00, lowest 95 % (95th percentile)". Those are exactly the rows of
the Profile accuracy table (`ACCURACY_METRICS`), checked here first.

The sheet is Basti's ET8550 run1 verification (beta 12). Its own figures all
pass, so the table is made to fail by raising the profile-accuracy figures
on the built report and judging it again.
"""
from __future__ import annotations

import copy

import pytest

from tests.test_beta12_a_through_profile_verification_is_judged_twice import (  # noqa: E501
    BIN, _sheet, pytestmark)  # noqa: F401  (the same Argyll skip)


def test_the_table_is_the_five_metrics_knut_named(qapp):
    from workflow.measurement_report import (ACCURACY_METRICS,
                                             PROFILE_ACCURACY_ROW_IDS)
    from workflow.compliance_sets import ROWS
    keys = [k for k, _w in ACCURACY_METRICS]
    assert keys == ["avg_all", "avg_low95", "avg_high5", "max_all",
                    "max_low95"]
    by_key = {r.metric_key: r.id for r in ROWS if r.metric_key in keys}
    assert set(by_key.values()) == set(PROFILE_ACCURACY_ROW_IDS)
    from ui.dialogs.measurement_report_dialog import _METRIC_LABELS
    names = {_METRIC_LABELS[k]() for k in keys}
    assert names == {"Average ΔE00, all patches", "Average ΔE00, lowest 95 %",
                     "Average ΔE00, highest 5 %", "Maximum ΔE00, all patches",
                     "Maximum ΔE00, lowest 95 % (95th percentile)"}


def _lenient():
    """The default set with every numeric limit but the five colour-accuracy
    rows opened wide, and those at 3.0 (averages) and 6.0 (maxima): the
    sheet's own figures all pass."""
    from workflow.compliance_sets import Limit
    from workflow.measurement_report import limits_from_pair
    lim = limits_from_pair(3.0, 6.0)
    for rid, l in list(lim.items()):
        if l.is_numeric and rid not in (
                "all_de00_avg", "best95_de00_avg", "worst5_de00_avg",
                "all_de00_max", "all_de00_p95"):
            lim[rid] = Limit.value(1000.0)
    return lim


def _failing(tmp_path):
    from workflow import measurement_report as mr
    rep = mr.build_report(_sheet(tmp_path), argyll_bin=str(BIN))
    mr.stamp_verdict(rep, _lenient())             # colour fidelity passes
    assert rep["verdict"]["overall"] == "PASS"
    assert rep["verdict"]["profile_accuracy"]["all_pass"] is True
    bad = copy.deepcopy(rep)
    bad["profile_accuracy"]["de00"]["avg_all"] = 4.0   # over the 3.0
    bad["profile_accuracy"]["de00"]["max_all"] = 9.0   # over the 6.0
    mr.stamp_verdict(bad, _lenient())
    return rep, bad


def test_a_failed_table_fails_the_overall_word(tmp_path):
    good, bad = _failing(tmp_path)
    v = bad["verdict"]
    assert v["profile_accuracy"]["all_pass"] is False
    # the colour-fidelity rows themselves are unchanged and pass
    assert [r["word"] for r in v["rows"]] == [
        r["word"] for r in good["verdict"]["rows"]]
    assert v["overall"] == "FAIL"
    assert v["all_pass"] is False
    assert v["summary"]["failed"] == 2
    # the five table values are counted as values checked
    assert v["summary"]["checked"] == good["verdict"]["summary"]["checked"]
    assert good["verdict"]["summary"]["checked"] >= 5


def test_the_report_window_says_fail_too(tmp_path, qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    good, bad = _failing(tmp_path)
    dlg = MeasurementReportDialog(_settings(argyll_bin_path=str(BIN)), None)
    try:
        # the window's own judgement, from a report without a saved verdict
        for rep in (good, bad):
            rep.pop("verdict", None)
        dlg._limits_for = lambda r: type("L", (), {
            "limits": _lenient(), "set_id": "chromiq_default"})()
        assert dlg._column_summary(good).word == "PASS"
        assert dlg._column_summary(bad).word == "FAIL"
    finally:
        dlg.close()


def test_a_type_without_the_colour_rows_is_not_failed_by_the_table():
    from workflow.measurement_report import profile_accuracy_pairs
    rep = {"profile_accuracy": {"de00": {"avg_all": 9.0, "max_all": 9.0}}}
    grey_only = [{"row_id": "grey_ramp_steps", "word": "PASS"}]
    assert profile_accuracy_pairs(rep, grey_only, {}) == []


def test_a_report_saved_before_k40_keeps_the_note_that_was_true_of_it(
        tmp_path, qapp):
    """Review of beta 15: a report SAVED by beta 12 to 14 is shown with the
    Overall word it was saved with (§53), which did not count the table. Its
    note must not claim that a FAIL in the table failed the sheet; a report
    judged by beta 15 says that it does."""
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_messages as M
    from workflow.measurement_report import (PROFILE_ACCURACY_COUNTED_KEY,
                                             saved_before_k40)
    _good, bad = _failing(tmp_path)
    assert bad["verdict"]["profile_accuracy"][PROFILE_ACCURACY_COUNTED_KEY]
    assert not saved_before_k40(bad["verdict"])
    old = copy.deepcopy(bad)
    old["verdict"]["profile_accuracy"].pop(PROFILE_ACCURACY_COUNTED_KEY)
    assert saved_before_k40(old["verdict"])
    dlg = MeasurementReportDialog(_settings(argyll_bin_path=str(BIN)), None)
    try:
        dlg._type_changes_the_document = lambda: False
        assert dlg._shows_a_pre_k40_word(old)
        assert not dlg._shows_a_pre_k40_word(bad)
        dlg._type_changes_the_document = lambda: True    # recomputed: k40
        assert not dlg._shows_a_pre_k40_word(old)
    finally:
        dlg.close()
    assert "do not change the sheet's verdict" in \
        M._REPORT_PROFILE_ACCURACY_NOTE_BEFORE_K40
