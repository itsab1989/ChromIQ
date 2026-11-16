"""The margin tolerance's driver patch (native/instlib/i1pro_imp.c, the
CHROMIQ PATCH "margin tolerance", 2026-11-16), pinned on its source:

* the block makes no USB call and sends nothing (no usb_*, no icom, no
  i1pro_command / control message, no thread);
* every hook returns at once unless the helper switched it on for a session
  whose ruler check is in use, on an i1Pro 2, and only while an armed strip's
  record is open (cq_ruler_recording);
* the recogniser hook only copies; ArgyllCMS's refusal and every accepted
  value are untouched (the refusal is still returned, the success path has no
  hook);
* the lights' timing is unchanged: the trigger call is only timed;
* the vendor script records the patch and re-vendoring reproduces the tree
  (scripts/vendor_instlib.py, PROVENANCE.md).

The wire itself with the option off is pinned by the unchanged fake-USB
traces (tests/test_ruler_scan_trace.py, tests/test_i1pro2_lights_*.py): the
driver code added here is never reached there, because nothing arms it.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "native" / "instlib" / "i1pro_imp.c").read_text(encoding="utf-8")


def _block() -> str:
    a = SRC.index("/* CHROMIQ PATCH: the margin tolerance (Preferences > Beta, 2026-11-16).")
    b = SRC.index("int i1pro2_cq_trigger_wait_ms(void *pp) {", a)
    b = SRC.index("\n}\n", b) + 3
    return SRC[a:b]


def _fn(name: str) -> str:
    blk = _block()
    a = blk.index(name + "(")
    a = blk.index("{", a)
    b = blk.index("\n}\n", a)
    return blk[a:b]


def test_the_block_never_touches_usb():
    blk = _block()
    for bad in ("usb_", "icom", "i1pro_command", "control_msg", "new_athread",
                "i1pro2_indLEDseq", "msec_sleep", "i1pro_trigger"):
        assert bad not in blk, bad


def test_every_entry_returns_at_once_unless_armed():
    for name in ("i1pro2_cq_tol_segments", "i1pro2_cq_tol_candidates",
                 "i1pro2_cq_tol_values"):
        body = _fn(name)
        first_if = body[body.index("if ("):body.index(")", body.index("if (")) + 1]
        assert "!m->cq_tol_on" in first_if, name
    for name in ("i1pro2_cq_tol_segments", "i1pro2_cq_tol_candidates"):
        assert "cq_ruler_recording" in _fn(name), name


def test_it_needs_the_ruler_and_an_i1pro2():
    body = _fn("i1pro2_cq_tol_options")
    assert "m->cq_ruler_on" in body and "instI1Pro2" in body


def test_only_the_three_refusals_are_looked_at():
    body = _block()
    assert re.search(r"I1PRO_RD_NOTENOUGHPATCHES\s*\|\|\s*ev == I1PRO_RD_TOOMANYPATCHES"
                     r"\s*\|\|\s*ev == I1PRO_RD_LEADTRAILINCONS", body)


def test_the_hooks_sit_only_on_the_refusal_paths():
    # the recogniser: one copy right after the threshold, nothing on success
    assert SRC.count("i1pro2_cq_tol_segments(p, pat, npat);") == 1
    a = SRC.index("i1pro_code i1pro_extract_patches_multimeas(")
    b = SRC.index("\n}\n", a)
    rec = SRC[a:b]
    assert rec.index("i1pro2_cq_tol_segments(") < rec.index("if (npat < (tnpatch + 2))")
    # read_patches_2: inside the failure branch of the recogniser call
    i = SRC.index("i1pro2_cq_tol_candidates(p, ev, multimes")
    assert "if (ev != I1PRO_OK) {" in SRC[i - 200:i]
    # imp_measure: inside the failure branch after read_patches_2
    i = SRC.index("i1pro2_cq_tol_values(p, ev, (int)clamp);")
    assert "if (ev != I1PRO_OK) {" in SRC[i - 60:i]
    assert "failed at i1pro_read_patches_2" in SRC[i:i + 400]


def test_the_lights_trigger_is_only_timed():
    a = SRC.index("unsigned int cq_t0 = msec_time();\t/* CHROMIQ PATCH 2026-11-16")
    b = SRC.index("m->cq_lights_wait_ms = (int)(msec_time() - cq_t0);")
    seg = SRC[a:b]
    # between the two time stamps only the unchanged lights call and the
    # unchanged sanity check
    assert seg.count("i1pro2_cq_lights_trigger(p);") == 1
    assert "msec_sleep" not in seg and "usb" not in seg
    # the quiet time itself is the one 4.3.37 set
    assert "#define CQ_LIGHTS_QUIET_MS   2100" in SRC


def test_the_candidates_are_computed_as_argyll_computes_a_patch():
    body = _fn("i1pro2_cq_tol_candidates")
    for piece in ("nnn = (no * 2 + 0)/3;", "trim = (no - nnn + 1)/2;",
                  "PATCH_CONS_THR * m->scan_toll_ratio",
                  "patch_cons_thr *= sqrt(0.012308/inttime);",
                  "i1pro_absraw_to_abswav(p, m->highres, s->reflective, n,",
                  "i1pro_scale_specrd(p, m->cq_tol_spec, n, m->cq_tol_spec);"):
        assert piece in body, piece
    assert "i1pro_conv2XYZ(p, vals, n, m->cq_tol_spec, (instClamping)clamp)" in \
        _fn("i1pro2_cq_tol_values")


def test_the_vendor_script_records_the_patch():
    v = (ROOT / "scripts" / "vendor_instlib.py").read_text(encoding="utf-8")
    assert "I1PRO_IMP_C_TOL" in v and "I1PRO_IMP_H_TOL" in v
    assert "I1PRO_IMP_C_LIGHTS + I1PRO_IMP_C_RULER + I1PRO_IMP_C_TOL" in v
    prov = (ROOT / "native" / "instlib" / "PROVENANCE.md").read_text(encoding="utf-8")
    assert "the margin tolerance" in prov
