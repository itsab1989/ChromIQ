"""The ruler check Beta (2026-11-14), on the wire: hand-held strip scans of an
i1Pro 2 and of the original i1Pro through the REAL vendored driver on a FAKE
USB layer (native/chartread_helper/tests/i1pro_ruler_scan_test.c).

With the option off, every scan's trace is byte for byte the base branch's
(tests/data/i1pro_ruler_base_trace.txt, made from 6de402163 by
scripts/make_ruler_base_fixtures.py): the same 0xD4 flags (0x0101), nothing
on 0x85. The ruler scenarios join this file with the driver part.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_i1pro3_lights_modes import _build_and_run

FIX = Path(__file__).resolve().parent / "data" / "i1pro_ruler_base_trace.txt"


@pytest.fixture(scope="module")
def trace(tmp_path_factory) -> str:
    return _build_and_run(tmp_path_factory, "i1pro_ruler_scan_test")


def _scn(text: str, scn: str) -> "list[str]":
    return [ln for ln in text.splitlines() if ln.startswith(scn + " ")]


@pytest.mark.parametrize("scn", ["off_i1pro2", "off_i1pro"])
def test_option_off_is_the_base_branch_byte_for_byte(trace, scn):
    base = FIX.read_text(encoding="utf-8")
    got = _scn(trace, scn)
    assert got, f"no {scn} lines"
    assert got == _scn(base, scn)


def test_off_never_touches_the_ruler_channel(trace):
    for ln in _scn(trace, "off_i1pro2") + _scn(trace, "off_i1pro"):
        assert " RD 85 " not in ln and " CANCEL" not in ln
    d4 = [ln for ln in _scn(trace, "off_i1pro2") if " CTL d4 " in ln]
    assert d4 and all(ln.split()[3].endswith("0101") for ln in d4)
