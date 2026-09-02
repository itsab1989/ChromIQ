"""colprof -l prefill from the measurement's TOTAL_INK_LIMIT (#72 Tier E).

The chart's ink limit rides targen's keyword through .ti1 → .ti2 → .ti3;
the profile build reads it back so chart time and profile time stay in sync
(hard problem 1). RGB measurements never carry the keyword — no-op there.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from workflow.profile_builder import ProfileBuilder, ProfileParams  # noqa: E402

_TI3_CMYK = """CTI3

COLOR_REP "CMYK_XYZ"
TOTAL_INK_LIMIT "280.0"

NUMBER_OF_FIELDS 8
BEGIN_DATA_FORMAT
SAMPLE_ID CMYK_C CMYK_M CMYK_Y CMYK_K XYZ_X XYZ_Y XYZ_Z
END_DATA_FORMAT
NUMBER_OF_SETS 1
BEGIN_DATA
1 0.0 0.0 0.0 0.0 96.4 100.0 82.5
END_DATA
"""


def _params(ti3: Path, extra: str = "") -> ProfileParams:
    return ProfileParams(ti3_path=ti3, description="t", extra_args=extra)


def test_ink_limit_prefilled_from_ti3(tmp_path):
    ti3 = tmp_path / "c.ti3"
    ti3.write_text(_TI3_CMYK, encoding="utf-8")
    args = ProfileBuilder(None)._build_args(_params(ti3))
    assert "-l280" in args


def test_user_l_flag_wins(tmp_path):
    ti3 = tmp_path / "c.ti3"
    ti3.write_text(_TI3_CMYK, encoding="utf-8")
    args = ProfileBuilder(None)._build_args(_params(ti3, extra="-l250"))
    assert "-l250" in args and "-l280" not in args
    # An explicit per-channel limit (-L) also suppresses the prefill.
    args = ProfileBuilder(None)._build_args(_params(ti3, extra="-L90"))
    assert "-L90" in args and "-l280" not in args


def test_rgb_ti3_stays_untouched(tmp_path):
    ti3 = tmp_path / "r.ti3"
    ti3.write_text(_TI3_CMYK.replace('COLOR_REP "CMYK_XYZ"\nTOTAL_INK_LIMIT "280.0"',
                                     'COLOR_REP "iRGB_XYZ"'), encoding="utf-8")
    args = ProfileBuilder(None)._build_args(_params(ti3))
    assert not any(a.startswith("-l") for a in args)


def test_missing_ti3_is_harmless(tmp_path):
    args = ProfileBuilder(None)._build_args(_params(tmp_path / "nope.ti3"))
    assert not any(a.startswith("-l") for a in args)
