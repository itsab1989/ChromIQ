"""Beta-12 review: a sheet whose print record names its source profile at a
path of ANOTHER computer (C:/Argyll/ref/sRGB.icm, or another account's
Argyll folder) is judged against this computer's profile of the same name,
and the profile's prediction of the sheet uses the same rule.

Found in review: the report took the same-name sRGB.icm for its source
reference, while the Profile accuracy block (the live check's chain) said
"the sRGB source profile of the conversion is missing", so one report both
used the source and said it was not there.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_beta12_a_through_profile_verification_is_judged_twice import (
    BIN, _report, _sheet, pytestmark)  # noqa: F401  (the same skip)
from workflow.verification_print import (recorded_source_profile,
                                         source_profile_path)


@pytest.mark.parametrize("recorded", [
    "C:\\Argyll\\ref\\sRGB.icm",
    "/Users/user/Argyll_V3.5.0/ref/sRGB.icm",
])
def test_report_and_prediction_agree_on_a_source_recorded_elsewhere(
        tmp_path, recorded):
    rep = _report(_sheet(tmp_path, source_profile=recorded))
    assert rep["reference_source"] == "source"
    pa = rep["profile_accuracy"]
    assert "reason" not in pa, pa
    assert pa["de00"]["avg_all"] == pytest.approx(0.515, abs=0.01)


def test_a_source_of_another_name_is_not_taken_for_srgb(tmp_path):
    assert recorded_source_profile("/nowhere/AdobeRGB1998.icc", str(BIN)) == ""
    rep = _report(_sheet(tmp_path, source_profile="/nowhere/other.icm"))
    assert rep["reference_source"] == "design"


def test_the_rule():
    here = source_profile_path(str(BIN))
    assert recorded_source_profile(here, str(BIN)) == here
    assert recorded_source_profile("", str(BIN)) == here
    assert recorded_source_profile("D:\\x\\sRGB.icm", str(BIN)) == here
    assert Path(recorded_source_profile("/gone/sRGB.icm", str(BIN))).is_file()
