"""Under a black ink limit (-L) Maximum accuracy's black stays deep and neutral.

Research finding agent5-02 (2026-09-29), re-validated by agent 7 (T3,
2026-10-03): the accurate inversion's active-set guard in
``b2a._gauss_newton`` called a channel pinned only at 1.0, never at its own
ceiling. Under ``-L70`` the K channel sat at 0.70 with an outward step, stayed
in the total-ink face constraint, received ink the clip removed again, and
C/M/Y never got the budget: on the battery's CMYK printer S3 the black
printed L* 21.3 with a colour cast (colprof 15.5), on a Clapper-Yule printer
a saturated green. Pinned at the ceiling, the black prints about L* 14.3,
neutral, with the total ink limit used.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from benchmarks.iccread import IccProfile
from benchmarks.synthetic import PRINTERS, make_chart, measure, write_ti3
from workflow.profile_engine import BuildSettings, build_profile

_TS = datetime(2026, 10, 3, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def s3_klimited(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("klimit")
    printer = PRINTERS["S3"]
    chart = make_chart(printer, 400)
    xyz, refl, _ = measure(printer, chart)
    ti3 = write_ti3(tmp / "S3.ti3", printer, chart, xyz, refl)
    out = {}
    for name, klim in (("free", None), ("L70", 70.0)):
        icc = tmp / f"{name}.icc"
        build_profile(ti3, icc, BuildSettings(
            quality="l", gammap_mode="accurate", ink_limit=printer.tac,
            black_ink_limit=klim, timestamp=_TS))
        dev = IccProfile(icc).b2a_device(np.array([[0.0, 0.0, 0.0]]),
                                         "B2A1")[0]
        out[name] = (dev, printer.lab_relative_true(dev[None])[0])
    return printer, out


def test_the_k_limited_black_uses_the_total_ink_budget(s3_klimited):
    printer, out = s3_klimited
    dev, _lab = out["L70"]
    assert dev[3] <= 0.70 + 1e-3, dev
    # The capped K hands its share to C, M and Y: the total ink limit is
    # reached (was 2.19 of 2.80 before the fix).
    assert dev.sum() >= printer.tac / 100.0 - 0.06, dev


def test_the_k_limited_black_is_deep_and_neutral(s3_klimited):
    _printer, out = s3_klimited
    _dev, lab = out["L70"]
    _dev_free, lab_free = out["free"]
    # Within a few L* of the unlimited black (S3: about 10 vs 14 with E6,
    # 21 without), and without a colour cast.
    assert lab[0] <= lab_free[0] + 5.5, (lab, lab_free)
    assert np.hypot(lab[1], lab[2]) < 4.0, lab
