"""X-Rite i1Pro 3: keep M0, M1 and M2 from every scan (Preferences > Beta,
2026-11-15), in the REAL vendored driver (native/instlib/i1pro3_imp.c).

* ArgyllCMS's own conversion of a patch, ``i1pro3_comp_refl_value``, asked
  for one condition (what ``-F n / 5 / u`` does today) and for all three at
  once (what the Beta does), on copies of the same samples: every number the
  same, bit for bit, and the three different from each other
  (native/chartread_helper/tests/i1pro3_conditions_test.c);
* the Beta's entry points do nothing unless the helper switched them on and
  armed a reading, never for the polariser, and a reading's record is gone
  before the next measurement starts;
* NOTHING ON THE WIRE: the new block calls no USB function, and its two calls
  in the measurement path sit where no request is made (the record is cleared
  before the trigger wait, filled after the last reading was converted).
  With the option off the i1Pro 3's fake-USB lives stay byte for byte those
  of ChromIQ 4.3.34's driver (tests/test_i1pro3_lights_modes.py, unchanged).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.test_i1pro3_lights_modes import _build_and_run

ROOT = Path(__file__).resolve().parent.parent
IMP = ROOT / "native" / "instlib" / "i1pro3_imp.c"


@pytest.fixture(scope="module")
def out(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1pro3_conditions_test")


def test_three_at_once_is_bit_for_bit_each_one_alone(out):
    lines = [ln for ln in out.splitlines() if ln.startswith("patch ")]
    assert len(lines) == 5
    for ln in lines:
        assert " BITS SAME " in ln, ln
        assert ln.endswith("distinct=1"), ln       # brighteners really at work
    assert "BITS ALL SAME" in out


def test_the_entry_points(out):
    want = [
        "off PTRS m0=main m1=null m2=null",
        "off TAKE 0",
        "on OPTIONS 1",
        "armed BEGIN 1",
        "armed PTRS m0=main m1=extra m2=extra",
        "armed TAKE_BEFORE_FINISH 0",
        "pol BEGIN 0",
        "disarmed BEGIN 0",
        "closed TAKE 0",
    ]
    got = [ln for ln in out.splitlines()
           if ln.split(" ", 1)[0] in ("off", "on", "armed", "pol",
                                      "disarmed", "closed")]
    assert got == want


def _block() -> str:
    text = IMP.read_text(encoding="utf-8", errors="replace")
    a = text.index('/* CHROMIQ PATCH: "X-Rite i1Pro 3: keep M0, M1 and M2')
    b = text.index("/* Parse the EEProm contents */", a)
    return text[a:b]


def test_the_block_sends_and_reads_nothing():
    block = _block()
    for needle in ("icom", "usb", "i1pro3_command", "do_measure",
                   "i1pro3_trigger", "i1pro3_readmeasurement",
                   "i1pro3_set", "i1pro3_get", "msec_sleep"):
        assert needle not in block, needle


def test_its_calls_sit_outside_any_request():
    text = IMP.read_text(encoding="utf-8", errors="replace")
    a = text.index("i1pro3_code i1pro3_imp_measure(")
    b = text.index("\n}\n", a)
    meas = text[a:b]
    begin = meas.index("i1pro3_cq_cond_begin(")
    finish = meas.index("i1pro3_cq_cond_finish(")
    # cleared before anything is asked of the instrument ...
    assert begin < meas.index("uicallback")
    # ... and filled after the last result was converted
    assert finish > meas.rindex("i1pro3_conv2XYZ(p, vals, nvals, specrd")
    # the pointer hook is right after -F's own choice, strip and spot
    assert len(re.findall(r"i1pro3_cq_cond_ptrs\(p, (?:i|0), &m0, &m1, &m2\);",
                          text)) == 2


def test_the_vendor_script_records_the_patch():
    v = (ROOT / "scripts" / "vendor_instlib.py").read_text(encoding="utf-8")
    assert "I1PRO3_IMP_C_COND" in v and "I1PRO3_IMP_H_COND" in v
    prov = (ROOT / "native" / "instlib" / "PROVENANCE.md").read_text(
        encoding="utf-8")
    assert "M0, M1 and M2 from one scan" in prov
