"""The UV pass of a hand dual scan counts its readings over the WHOLE clean middle of each patch
(after 4.3.54, 2026-11-21; docs/design/i1pro2_dual_scan.md section 2a and section 17).

Until 4.3.54 the UV readings of a patch were those in the central 60 % of ArgyllCMS's lamp cell
(itself ArgyllCMS's clean middle 66 % of the patch), so the UV pass needed about 1.5 times slower
movement than the lamp pass (a tester: 27 of 87 UV passes refused as "too fast"). Now: the cell's
whole span (its first to its last lamp reading's ruler position) less half a ruler step at each end
(the ruler's count labels the same stripe edge one count apart in the two directions); at least 3
UV readings per patch, as before. The alignment gate keeps its own window (the central 60 %) and its
threshold, unchanged.

Pinned here: the C cut (chromiq_dualscan.c) and the Python twin (workflow/dual_scan/cut.py) give
the same counts, verdicts, alignment measure and patch values on invented strips of every speed;
the constants are the same; the new window's edges; the gate unchanged. INVENTED data only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from workflow.dual_scan import cut
from workflow.dual_scan.reasons import DualScanRefused

ROOT = Path(__file__).resolve().parent.parent


def _argyll_trim(ss: int, no: int) -> "tuple[int, int]":
    """ArgyllCMS's own trim of a found patch (i1pro_imp.c: 66 %, rounded down)."""
    nnn = (no * 2) // 3
    return ss + (no - nnn + 1) // 2, nnn


def _strip(seed: int, *, lamp_speed: float, uv_speed: float, offset: float = 0.85,
           patches: int = 23, patch_steps: float = 20.0, noise: float = 0.002):
    """An invented hand strip in ruler steps: the lamp pass runs DOWN the ruler at *lamp_speed*
    steps per reading (with a little wobble), the UV pass back UP at *uv_speed*, its positions
    *offset* steps high (the direction offset of the count). Returns cells (ArgyllCMS-trimmed),
    lamp positions, UV positions, UV readings [n, 36]."""
    rng = np.random.default_rng(seed)
    lead = 30.0
    length = lead * 2 + patches * patch_steps
    level = 0.2 + 0.6 * rng.random(patches)

    def pass_positions(speed, start, sign):
        pos, out = start, []
        while 0.0 <= pos <= length:
            out.append(pos)
            pos += sign * speed * (1.0 + 0.15 * np.sin(len(out) / 9.0))
        return np.array(out)

    lp_true = pass_positions(lamp_speed, length, -1)
    up_true = pass_positions(uv_speed, 0.0, +1)

    def patch_of(x):
        return np.floor((x - lead) / patch_steps).astype(int)

    cells = []
    pk = patch_of(lp_true)
    for k in reversed(range(patches)):      # the lamp pass meets the last patch first
        idx = np.flatnonzero(pk == k)
        # what ArgyllCMS finds: the readings well inside the patch (aperture blur at both ends)
        inner = idx[1:-1] if idx.size > 4 else idx
        cells.append(_argyll_trim(int(inner[0]), int(inner.size)))
    up_k = patch_of(up_true)
    sig = np.where((up_k >= 0) & (up_k < patches), level[np.clip(up_k, 0, patches - 1)], 0.05)
    wl = np.arange(36)
    uv = (sig[:, None] * (1.0 + 0.01 * wl[None, :])
          + noise * rng.standard_normal((up_true.size, 36)))
    return cells, lp_true, up_true + offset, uv


def _cases():
    out = []
    for i, (ls, us) in enumerate(((1.5, 1.5), (1.5, 2.0), (1.5, 2.3), (1.5, 2.6), (1.5, 3.0),
                                  (0.75, 0.75), (0.75, 1.5), (2.0, 2.0), (1.0, 3.5), (1.5, 1.0))):
        for off in (0.0, 0.85, -0.85, 1.45):
            out.append((f"s{i}_{off:+.2f}", *_strip(100 + i, lamp_speed=ls, uv_speed=us, offset=off)))
    # half a patch off: the alignment gate's case
    c, lp, up, uv = _strip(7, lamp_speed=1.5, uv_speed=1.5)
    out.append(("half_pitch", c, lp, up + 7.5, uv))
    return out


def _write(path: Path, cases) -> None:
    with path.open("w") as f:
        for name, cells, lp, up, uv in cases:
            f.write(f"cut {name} {len(cells)} {lp.size} {up.size}\n")
            f.write("C " + " ".join(f"{a} {b}" for a, b in cells) + "\n")
            f.write("P " + " ".join(f"{v:.17g}" for v in lp) + "\n")
            f.write("Q " + " ".join(f"{v:.17g}" for v in up) + "\n")
            for row in uv:
                f.write("U " + " ".join(f"{v:.17g}" for v in row) + "\n")


@pytest.fixture(scope="module")
def c_out(tmp_path_factory) -> "tuple[dict, str]":
    from tests.test_i1pro3_lights_modes import _build_and_run
    p = tmp_path_factory.mktemp("cutcases") / "cases.txt"
    _write(p, _cases())
    mp = pytest.MonkeyPatch()
    mp.setenv("CQ_DUAL_CUT_CASES", str(p))
    try:
        out = _build_and_run(tmp_path_factory, "i1pro2_dual_maths_test")
    finally:
        mp.undo()
    res = {}
    for ln in out.splitlines():
        if ln.startswith("cutcase "):
            head, vals = ln.split(" | ") if " | " in ln else (ln, "")
            t = head.split()
            res[t[1]] = (t[2], float(t[3]), [int(v) for v in t[4:]],
                         [float(v) for v in vals.split()])
    return res, out


def _python(cells, lp, up, uv):
    """(verdict, flatness, counts, first band per patch) as the Python twin says."""
    lpa, upa = np.asarray(lp, float), np.asarray(up, float)
    counts, firsts, spans = [], [], []
    for s, n in cells:
        a, b = lpa[s], lpa[s + n - 1]
        lo, hi = min(a, b), max(a, b)
        spans.append((lo, hi))
        m = (upa >= lo + cut.EDGE_STEPS) & (upa <= hi - cut.EDGE_STEPS)
        counts.append(int(m.sum()))
        firsts.append(float(uv[m, 0].mean()) if m.any() else 0.0)
    flat = cut._flatness(spans, upa, np.asarray(uv, float), cut.TRIM)
    try:
        r = cut.cut_uv_pass(cells, lp, up, uv)
        why = "ok"
        assert r.counts == counts
        np.testing.assert_allclose(r.uv[:, 0], firsts, rtol=0, atol=1e-13)
    except DualScanRefused as e:
        why = e.reason
    return why, flat, counts, firsts


def test_the_constants_are_the_same_in_c_and_python(c_out):
    _res, out = c_out
    line = next(ln for ln in out.splitlines() if ln.startswith("edge_steps "))
    t = line.split()
    assert float(t[1]) == cut.EDGE_STEPS == 0.5
    assert float(t[3]) == cut.TRIM == 0.2
    assert int(t[5]) == cut.MIN_UV_READINGS == 3


def test_c_and_python_cut_every_case_the_same(c_out):
    res, _out = c_out
    cases = _cases()
    assert len(res) == len(cases)
    verdicts = set()
    for name, cells, lp, up, uv in cases:
        why, flat, counts, firsts = _python(cells, lp, up, uv)
        cw, cflat, ccounts, cfirsts = res[name]
        assert cw == why, (name, cw, why, counts)
        assert ccounts == counts, name
        if flat == flat:
            assert cflat == pytest.approx(flat, rel=1e-9, abs=1e-15), name
        else:
            assert cflat != cflat, name
        np.testing.assert_allclose(cfirsts, firsts, rtol=0, atol=1e-12)
        verdicts.add(why)
    # the cases reach every verdict the speed can give, and the gate
    assert {"ok", "uv_pass_too_fast", "uv_pass_misaligned"} <= verdicts, verdicts


def test_a_uv_pass_at_the_lamp_pass_pace_is_accepted_where_4354_refused():
    """The tester's case: the UV pass about as fast as the lamp pass, over ArgyllCMS's narrow
    cells. 4.3.54's central 60 % held 2 readings in the worst patch; the whole span less half a
    step holds 3 or more."""
    cells, lp, up, uv = _strip(3, lamp_speed=1.5, uv_speed=1.7, patch_steps=19.0)
    r = cut.cut_uv_pass(cells, lp, up, uv)
    assert min(r.counts) >= cut.MIN_UV_READINGS
    old = []
    for s, n in cells:                  # what 4.3.54 counted on the same strip
        a, b = lp[s], lp[s + n - 1]
        lo, hi = min(a, b), max(a, b)
        w = hi - lo
        old.append(int(((up >= lo + 0.2 * w) & (up <= hi - 0.2 * w)).sum()))
    assert min(old) < cut.MIN_UV_READINGS
    assert cut.travel_verdict(old) == "uv_pass_too_fast"


def test_readings_within_half_a_step_of_the_span_end_are_left_out():
    cells = [(0, 5), (5, 5), (10, 5)]
    lp = np.arange(15, dtype=float) * 2.0          # spans 0-8, 10-18, 20-28
    uv_at = np.array([0.49, 0.5, 4.0, 7.5, 7.51, 10.5, 14.0, 17.5, 20.5, 24.0, 27.5, 27.6])
    ur = np.ones((uv_at.size, 36))
    r = cut.cut_uv_pass(cells, lp, uv_at, ur)
    assert r.counts == [3, 3, 3]                   # 0.49 and 7.51 / 27.6 are out
    with pytest.raises(DualScanRefused) as e:
        cut.cut_uv_pass(cells, lp, uv_at, ur, edge=1.0)
    assert e.value.reason == "uv_pass_too_fast"


def test_the_alignment_gate_keeps_its_own_window():
    """The gate is computed on the central 60 % of each span (TRIM) as before; the new window is
    only the UV readings' one. Same strip, same flatness number as the 4.3.54 formula."""
    cells, lp, up, uv = _strip(11, lamp_speed=1.5, uv_speed=1.2)
    r = cut.cut_uv_pass(cells, lp, up, uv)
    spans = [tuple(sorted((lp[s], lp[s + n - 1]))) for s, n in cells]
    assert r.flatness == cut._flatness(spans, up, uv, 0.2)
    assert r.flatness < cut.MAX_FLATNESS
    with pytest.raises(DualScanRefused) as e:
        cut.cut_uv_pass(cells, lp, up + 7.5, uv)    # half a patch off
    assert e.value.reason == "uv_pass_misaligned"


def test_the_helper_calls_the_cut_with_the_edge():
    src = (ROOT / "native" / "chartread_helper" / "chromiq_dualdev.c").read_text(encoding="utf-8")
    assert "CQ_DUAL_TRIM, CQ_DUAL_MIN_UV,\n\t\t\t\t                  CQ_DUAL_EDGE_STEPS, cutv, counts)" in src
    h = (ROOT / "native" / "chartread_helper" / "chromiq_dualscan.h").read_text(encoding="utf-8")
    assert "#define CQ_DUAL_EDGE_STEPS 0.5" in h and "#define CQ_DUAL_MIN_UV 3" in h


if __name__ == "__main__":      # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
