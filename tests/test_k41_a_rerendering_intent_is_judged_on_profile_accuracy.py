"""k41 (Knut #182 6059912998, answer 2: "Check what is done in the industry
for same situation and do that").

A verification printed through its profile with the PERCEPTUAL or SATURATION
intent was judged against the relative-colorimetric source colour. Those two
intents change colour on purpose (ICC White Paper 9: "intended for
re-purposing"; White Paper 27: they "intentionally modify the output
colorimetry and hence cannot be completely evaluated using only objective
methods"), so the industry checks such a print on the profile's accuracy,
measurements against the profile's forward prediction (WP 27; ArgyllCMS
profcheck), and keeps source-match checks for the colorimetric intents.

So: through perceptual or saturation, the five colour-accuracy rows against
the source read INFO with a note naming the intent, and the Profile accuracy
table (k40) judges the sheet. Relative and absolute prints keep §58.
"""
from __future__ import annotations

import html

import pytest

from tests.test_beta12_a_through_profile_verification_is_judged_twice import (  # noqa: E501
    BIN, _sheet, pytestmark)  # noqa: F401  (the same Argyll skip)

FIVE = {"all_de00_avg", "best95_de00_avg", "worst5_de00_avg",
        "all_de00_max", "all_de00_p95"}


def _report(tmp_path, intent):
    from workflow import measurement_report as mr
    rep = mr.build_report(_sheet(tmp_path, intent=intent),
                          argyll_bin=str(BIN))
    mr.stamp_verdict(rep, 2.0, 3.0)
    return rep


@pytest.mark.parametrize("intent,note", [
    ("perceptual", "intent_perceptual_info"),
    ("saturation", "intent_saturation_info")])
def test_a_rerendered_sheet_shows_its_source_comparison_for_information(
        tmp_path, intent, note):
    rep = _report(tmp_path, intent)
    assert rep["source_reference"]["print_intent"] == intent
    rows = {r["row_id"]: r for r in rep["verdict"]["rows"]}
    for rid in FIVE:
        assert rows[rid]["word"] == "INFO", rid
        assert rows[rid]["value"] is not None
        assert note in rows[rid]["notes"]
    # the profile accuracy table is what judges it
    pa = rep["verdict"]["profile_accuracy"]
    assert {r["word"] for r in pa["rows"]} <= {"PASS", "FAIL"}
    assert rep["verdict"]["overall"] in ("PASS", "FAIL")


def test_a_rerendered_sheet_fails_on_its_profile_accuracy(tmp_path):
    import copy
    from workflow import measurement_report as mr
    rep = _report(tmp_path, "perceptual")
    bad = copy.deepcopy(rep)
    bad["profile_accuracy"]["de00"]["max_all"] = 9.0
    mr.stamp_verdict(bad, 2.0, 3.0)
    assert bad["verdict"]["overall"] == "FAIL"


def test_a_relative_sheet_is_judged_against_its_source_as_before(tmp_path):
    rep = _report(tmp_path, "relative")
    assert "print_intent" not in rep["source_reference"]
    rows = {r["row_id"]: r for r in rep["verdict"]["rows"]}
    assert {rows[rid]["word"] for rid in FIVE} <= {"PASS", "FAIL"}


def test_the_report_says_so(tmp_path, qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_messages as M
    rep = _report(tmp_path, "saturation")
    dlg = MeasurementReportDialog(_settings(argyll_bin_path=str(BIN)), None)
    try:
        produced = dlg._printing_block_html(rep)
        assert html.escape(M._REPORT_SOURCE_MEASURED_INFO) in produced
        first = M._REPORT_SOURCE_REFERENCE_INFO.split("{")[0]
        assert html.escape(first) in produced
        assert html.escape("is not judged") in produced
        assert dlg._note_sentence("intent_saturation_info") == \
            M._REPORT_INTENT_SATURATION_INFO
        assert dlg._note_sentence("intent_perceptual_info") == \
            M._REPORT_INTENT_PERCEPTUAL_INFO
    finally:
        dlg.close()
