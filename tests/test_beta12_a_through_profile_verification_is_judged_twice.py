"""Beta 12: a verification printed THROUGH its profile is judged twice (Knut,
#182 6045500910, answer 1, "OK" to question 1 of 6044584365).

* Colour fidelity against the TRUE source colour: the chart's colours
  through the source profile the print used (sRGB.icm), not the ``.ti2``'s
  design XYZ (ArgyllCMS targen's own model, black at L* 9), on the patches
  inside the profile's gamut only, the gamut tested in the print's intent.
* Profile accuracy: every patch against the profile's own prediction of the
  ink amounts that were really printed, judged with the same limits.
* Beyond the gamut: reported, never judged. A raw print: unchanged.

Basti's ET8550 run1 verification of 2026-10-06 (616 patches, relative,
sRGB.icm; FINDINGS G of the beta-12 diagnosis): before, 437 in gamut,
average 1.50, maximum 5.27 against the design; now 443 in gamut, 0.77 /
3.66 against sRGB.icm; profile accuracy 0.51 / 1.01 / 2.13.
"""
from __future__ import annotations

import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import pytest

from tests.argyll_env import argyll_bin_dir

DATA = Path(__file__).parent / "data" / "g_basti_et8550_run1_verify"
NAME = "ET8550_EpsPremSG_AdobeRGB_CM_Okt26"
DATE = "2026-10-06_154750"
BIN = argyll_bin_dir()

pytestmark = pytest.mark.skipif(
    BIN is None or not (BIN.parent / "ref" / "sRGB.icm").is_file()
    and not Path("/Applications/Argyll/ref/sRGB.icm").is_file(),
    reason="needs ArgyllCMS with ref/sRGB.icm")


def _sheet(tmp_path, **record) -> Path:
    """Basti's sheet in a project of its own; *record* overrides fields of
    its print record. The profile keeps the modification time the record
    names, as it did on his computer."""
    run = tmp_path / NAME / "runs" / "run1"
    day = run / "verifications" / DATE
    (day / "chart").mkdir(parents=True)
    icc = run / f"{NAME}.icc"
    shutil.copy2(DATA / f"{NAME}.icc", icc)
    ti3 = day / f"{NAME}-verify.ti3"
    shutil.copy2(DATA / ti3.name, ti3)
    shutil.copy2(DATA / f"{NAME}-verify.ti2", day / "chart" / f"{NAME}-verify.ti2")
    rec = json.loads((DATA / f"{NAME}-verify.print.json").read_text(
        encoding="utf-8"))
    rec.update(record)
    (day / "chart" / f"{NAME}-verify.print.json").write_text(
        json.dumps(rec), encoding="utf-8")
    when = datetime.fromisoformat(rec["profile_mtime"]).timestamp()
    os.utime(icc, (when, when))
    return ti3


def _report(ti3):
    from workflow import measurement_report as mr
    rep = mr.build_report(ti3, argyll_bin=str(BIN))
    mr.stamp_verdict(rep, 2.0, 3.0)
    return rep


def test_bastis_sheet_is_judged_against_srgb_and_against_its_profile(tmp_path):
    rep = _report(_sheet(tmp_path))
    assert rep["reference_source"] == "source"
    assert rep["source_reference"] == {"profile": "sRGB.icm",
                                       "intent": "relative"}
    assert rep["yardstick"] == "media-relative"
    gs = rep["gamut_split"]
    # the gamut tested in the print's intent: relative, 443 in, 173 out
    assert gs["intent"] == "relative"
    assert (gs["n_in"], gs["n_out"]) == (443, 173)
    assert gs["de00_in"]["avg_all"] == pytest.approx(0.766, abs=0.01)
    assert gs["de00_in"]["max_all"] == pytest.approx(3.659, abs=0.02)
    # the verdict still judges the within-gamut figures
    assert rep["verdict"]["source"] == "gamut_in"
    pa = rep["profile_accuracy"]
    assert pa["intent"] == "relative" and pa["profile"] == f"{NAME}.icc"
    assert pa["de00"]["n"] == 616
    assert pa["de00"]["avg_all"] == pytest.approx(0.515, abs=0.01)
    assert pa["de00"]["max_low95"] == pytest.approx(1.014, abs=0.01)
    assert pa["de00"]["max_all"] == pytest.approx(2.133, abs=0.02)
    v = rep["verdict"]["profile_accuracy"]
    assert v["all_pass"] is True
    assert {r["key"] for r in v["rows"]} == {
        "avg_all", "avg_low95", "avg_high5", "max_all", "max_low95"}
    assert all(r["word"] == "PASS" for r in v["rows"])


def test_beyond_the_gamut_never_fails_a_limit(tmp_path):
    rep = _report(_sheet(tmp_path))
    out = rep["gamut_split"]["de00_out"]
    assert out["max_all"] > 3.0               # far beyond any limit...
    judged = {r["row_id"]: r for r in rep["verdict"]["rows"]}
    # ...and the judged maximum is the within-gamut one, not that
    assert judged["all_de00_max"]["value"] == pytest.approx(
        rep["gamut_split"]["de00_in"]["max_all"])


def test_a_profile_changed_since_the_print_has_no_profile_accuracy(tmp_path):
    ti3 = _sheet(tmp_path)
    icc = ti3.parents[2] / f"{NAME}.icc"
    os.utime(icc, None)                       # rebuilt after the print
    rep = _report(ti3)
    assert rep["reference_source"] == "source"     # fidelity still judged
    pa = rep["profile_accuracy"]
    assert "de00" not in pa and "changed" in pa["reason"]
    assert "profile_accuracy" not in rep["verdict"]


def test_a_raw_print_keeps_its_reference(tmp_path):
    rep = _report(_sheet(tmp_path, colour="raw"))
    assert rep["reference_source"] == "design"
    assert "profile_accuracy" not in rep and "source_reference" not in rep
    assert "profile_accuracy" not in rep["verdict"]


def test_a_sheet_printed_elsewhere_keeps_the_design(tmp_path):
    rep = _report(_sheet(tmp_path, route="external-cm"))
    assert rep["reference_source"] == "design"
    assert "profile_accuracy" not in rep


def test_a_missing_source_profile_keeps_the_design(tmp_path):
    rep = _report(_sheet(tmp_path, source_profile="/nowhere/other.icm"))
    assert rep["reference_source"] == "design"


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_the_report_says_what_it_judged(tmp_path, qapp):
    from tests.test_calibration_reports import _settings
    from ui.dialogs.measurement_report_dialog import MeasurementReportDialog
    from workflow import measurement_messages as M
    ti3 = _sheet(tmp_path)
    rep = _report(ti3)
    dlg = MeasurementReportDialog(_settings(argyll_bin_path=str(BIN)), None,
                                  initial_ti3=ti3)
    try:
        produced = dlg._printing_block_html(rep)
        assert html.escape(M._REPORT_SOURCE_MEASURED) in produced
        assert "sRGB.icm" in produced
        table = dlg._profile_accuracy_html(rep)
        assert html.escape(M._REPORT_PROFILE_ACCURACY_HEADING) in table
        assert "0.52" in table and "2.13" in table and "PASS" in table
        detail = dlg._run_detail_html(rep)
        assert html.escape(M._REPORT_SOURCE_HEADING) in detail
        # and nothing of it on a sheet without it
        rep.pop("profile_accuracy")
        assert dlg._profile_accuracy_html(rep) == ""
    finally:
        dlg.close()
