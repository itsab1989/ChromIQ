"""The ruler check's driver patches (scripts/vendor_instlib.py, 2026-11-14):
what they may send and read, pinned in the source.

* i1Pro 2: the only new things on the wire are the two ruler bits in the
  existing 0xD4 measure command and reads of bulk IN 0x85; never 0xD7 (stop
  ruler, ChromIQ's rule of 2026-11-14), never a control request of its own;
* i1Pro 3: nothing at all (no USB call in its block);
* every entry the drivers call is a no-op until the helper switched the ruler
  on and armed a strip.
"""
from __future__ import annotations

import re

from tests.test_i1pro2_lights_driver import _vendor


def _code(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_i1pro2_block_reads_only_0x85_and_sends_nothing():
    b = _code(_vendor()["I1PRO_IMP_C_RULER_BLOCK"])
    assert b.count("usb_read(") == 1 and "0x85" in b
    for never in ("usb_control(", "usb_write(", "0xD7", "0xd7", "stop_ruler",
                  "EEProm", "update_log"):
        assert never not in b, never
    # a ruler read never times out while the instrument is in use: only the
    # close ends a pending read (review item 2, 2026-11-14)
    assert "CQ_RULER_READ_TOUT    86400.0" in _vendor()["I1PRO_IMP_C_RULER_BLOCK"]
    assert "CQ_RULER_READ_TOUT);" in b
    # ...and the close is bounded (review item 3)
    assert "CQ_RULER_CLOSE_MS     2000" in _vendor()["I1PRO_IMP_C_RULER_BLOCK"]


def test_i1pro2_bits_only_for_an_armed_lit_scan_of_a_real_i1pro2():
    b = _code(_vendor()["I1PRO_IMP_C_RULER_BLOCK"])
    i = b.index("int i1pro2_cq_ruler_bits(")
    body = b[i:b.index("\n}\n", i)]
    for cond in ("p->dtype == instI1Pro2", "m->cq_ruler_on", "m->cq_ruler_armed",
                 "!m->cq_ruler_given_up", "mmodif == i1p_norm", "s->scan",
                 "s->reflective", "!m->uv_en"):
        assert cond in body, cond
    assert "I1PRO2_MMF_RULER_START | I1PRO2_MMF_RULER_END" in body


def test_i1pro2_options_need_the_ruler_sensor():
    b = _code(_vendor()["I1PRO_IMP_C_RULER_BLOCK"])
    i = b.index("int i1pro2_cq_ruler_options(")
    assert "I1PRO_CAP2_ZEB_RUL" in b[i:b.index("\n}\n", i)]


def test_i1pro3_block_sends_and_reads_nothing():
    b = _code(_vendor()["I1PRO3_IMP_C_RULER_BLOCK"])
    for never in ("usb_read(", "usb_control(", "usb_write(", "icom->"):
        assert never not in b, never


def test_every_hook_line_names_the_ruler_and_changes_no_argyll_variable():
    v = _vendor()
    for name in ("I1PRO_IMP_C_RULER", "I1PRO3_IMP_C_RULER"):
        for old, new in v[name]:
            o = set(old.splitlines())
            added = [ln for ln in new.splitlines() if ln not in o]
            if any("RULER_BLOCK" in ln for ln in added) or len(added) > 40:
                continue          # the block itself
            for ln in _code("\n".join(added)).splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                assert "cq_ruler" in ln or ln in ("}", "return ev;"), ln
