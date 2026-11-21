"""The UV pass of a hand dual scan counts its readings over the WHOLE clean middle of each patch
(after 4.3.54, 2026-11-21; docs/design/i1pro2_dual_scan.md section 2a and section 17), AFTER it has
been lined up with the lamp pass (second fix round, the verification's V1: cut.estimate_offset /
chromiq_dualscan.c cq_dual_align, then the span less a quarter step).

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
           patches: int = 23, patch_steps: float = 20.0, noise: float = 0.002,
           aperture: float = 0.0):
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
    def level_at(x):
        k = patch_of(x)
        return np.where((k >= 0) & (k < patches), level[np.clip(k, 0, patches - 1)], 0.05)

    if aperture > 0:
        # what the aperture sees: the level averaged over +-aperture steps around the
        # reading (blurred patch edges, as on paper; the review's m6)
        off = np.linspace(-aperture, aperture, 41)
        sig = level_at(up_true[:, None] + off[None, :]).mean(axis=1)
        lamp_level = level_at(lp_true[:, None] + off[None, :]).mean(axis=1)
    else:
        sig = level_at(up_true)
        lamp_level = level_at(lp_true)
    # the lamp pass's own 380-400 nm readings, weighted by T / W as the helper does: what the
    # UV pass reads there (its first three bands: sig x 1.00 .. 1.02), with its own noise
    _strip.lamp_sig = lamp_level * 1.01 + noise * 0.5 * rng.standard_normal(lp_true.size)
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
    # fix round (review B1 / m6): blurred patch edges and the UV pass shifted, so the
    # averaging window's gate is reached in C too ("uv_pass_shifted")
    for seed in (1, 3):
        for d in (0.0, 2.0, 3.0):
            out.append((f"blur{seed}_{d:+.1f}", *_strip(seed, lamp_speed=1.5, uv_speed=1.5,
                                                         aperture=3.0, offset=0.85 + d)))
    # the exact boundaries: positions at lo + 0.25 and hi - 0.25 count, 0.24 / 7.76 do not
    lpb = np.arange(15, dtype=float) * 2.0
    upb = np.array([0.24, 0.25, 4.0, 7.75, 7.76, 10.25, 14.0, 17.75, 20.25, 24.0, 27.75, 27.8])
    out.append(("boundary", [(0, 5), (5, 5), (10, 5)], lpb, upb,
                np.tile((1.0 + 0.1 * np.arange(12))[:, None], (1, 36))))
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
            res[t[1]] = (t[2], float(t[3]), [int(v) for v in t[5:]],
                         [float(v) for v in vals.split()], float(t[4]))
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
    wflat = cut._flatness(spans, upa, np.asarray(uv, float), cut.TRIM, edge=cut.EDGE_STEPS)
    try:
        r = cut.cut_uv_pass(cells, lp, up, uv, edge=cut.EDGE_STEPS)   # the bare cut (C's twin)
        why = "ok"
        assert r.counts == counts
        np.testing.assert_allclose(r.uv[:, 0], firsts, rtol=0, atol=1e-13)
    except DualScanRefused as e:
        why = e.reason
    return why, flat, counts, firsts, wflat


def test_the_constants_are_the_same_in_c_and_python(c_out):
    _res, out = c_out
    line = next(ln for ln in out.splitlines() if ln.startswith("edge_steps "))
    t = line.split()
    assert float(t[1]) == cut.EDGE_STEPS == 0.25
    assert float(t[3]) == cut.TRIM == 0.2
    assert int(t[5]) == cut.MIN_UV_READINGS == 3
    assert float(t[7]) == cut.MAX_EDGE_FLATNESS == 0.001
    a = next(ln for ln in out.splitlines() if ln.startswith("align_consts ")).split()
    assert (float(a[1]), float(a[2]), int(a[3]), float(a[4]), float(a[5])) == (
        cut.ALIGN_SPAN, cut.ALIGN_STEP, cut.ALIGN_MIN_READINGS, cut.MAX_OFFSET, cut.MIN_RISE) == (
        6.5, 0.05, 20, 3.0, 1.15)


def test_c_and_python_cut_every_case_the_same(c_out):
    res, _out = c_out
    cases = _cases()
    assert len(res) == len(cases)
    verdicts = set()
    for name, cells, lp, up, uv in cases:
        why, flat, counts, firsts, wflat = _python(cells, lp, up, uv)
        cw, cflat, ccounts, cfirsts, cwflat = res[name]
        assert cw == why, (name, cw, why, counts)
        assert ccounts == counts, name
        for c_, p_ in ((cflat, flat), (cwflat, wflat)):
            if p_ == p_:
                assert c_ == pytest.approx(p_, rel=1e-9, abs=1e-15), name
            else:
                assert c_ != c_, name
        np.testing.assert_allclose(cfirsts, firsts, rtol=0, atol=1e-12)
        verdicts.add(why)
    # the cases reach every verdict the speed can give, and the gate
    assert {"ok", "uv_pass_too_fast", "uv_pass_misaligned", "uv_pass_shifted"} <= verdicts, verdicts
    assert res["boundary"][2] == [3, 3, 3]          # inclusive at lo + 0.25 / hi - 0.25, in C too


def test_a_uv_pass_at_the_lamp_pass_pace_is_accepted_where_4354_refused():
    """The tester's case: the UV pass about as fast as the lamp pass, over ArgyllCMS's narrow
    cells. 4.3.54's central 60 % held 2 readings in the worst patch; the whole span less half a
    step holds 3 or more."""
    cells, lp, up, uv = _strip(3, lamp_speed=1.5, uv_speed=1.7, patch_steps=19.0)
    r = cut.cut_uv_pass(cells, lp, up, uv, lamp_sig=_strip.lamp_sig)
    assert min(r.counts) >= cut.MIN_UV_READINGS
    old = []
    for s, n in cells:                  # what 4.3.54 counted on the same strip
        a, b = lp[s], lp[s + n - 1]
        lo, hi = min(a, b), max(a, b)
        w = hi - lo
        old.append(int(((up >= lo + 0.2 * w) & (up <= hi - 0.2 * w)).sum()))
    assert min(old) < cut.MIN_UV_READINGS
    assert cut.travel_verdict(old) == "uv_pass_too_fast"


def test_readings_within_a_quarter_step_of_the_span_end_are_left_out():
    cells = [(0, 5), (5, 5), (10, 5)]
    lp = np.arange(15, dtype=float) * 2.0          # spans 0-8, 10-18, 20-28
    uv_at = np.array([0.24, 0.25, 4.0, 7.75, 7.76, 10.25, 14.0, 17.75, 20.25, 24.0, 27.75, 27.8])
    ur = np.ones((uv_at.size, 36))
    r = cut.cut_uv_pass(cells, lp, uv_at, ur, edge=cut.EDGE_STEPS)
    assert r.counts == [3, 3, 3]                   # 0.24 and 7.76 / 27.8 are out
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


def _aligned_strip(seed, d, speed=1.5, noise=0.002):
    """the strip with blurred patch edges, its UV pass shifted d steps beyond the natural
    0.85, and the lamp pass's own 380-400 nm signal (what the helper lines it up by)"""
    c, lp, up, uv = _strip(seed, lamp_speed=1.5, uv_speed=speed, aperture=3.0, offset=0.85 + d,
                           noise=noise)
    return c, lp, up, uv, _strip.lamp_sig


def _patch_errors(seed, d, speed=1.5):
    """(verdict, worst relative error of a patch's UV value) against the SAME strip at true
    alignment (offset 0), patch by patch"""
    c0, lp0, up0, uv0, ls0 = _aligned_strip(seed, -0.85, speed)
    ref = cut.cut_uv_pass(c0, lp0, up0, uv0, lamp_sig=ls0)
    c, lp, up, uv, ls = _aligned_strip(seed, d, speed)
    try:
        r = cut.cut_uv_pass(c, lp, up, uv, lamp_sig=ls)
    except DualScanRefused as e:
        return e.reason, None
    return "ok", float(np.max(np.abs(r.uv[:, 0] - ref.uv[:, 0]) / ref.uv[:, 0]))


@pytest.mark.parametrize("seed,speed", [(1, 1.5), (2, 1.5), (3, 1.8), (4, 1.2), (5, 1.5)])
def test_every_patch_stays_right_whatever_the_shift(seed, speed):
    """The verification's V1 as a test: the UV pass shifted -6 to +6 steps (both directions, by
    0.25) beyond its natural 0.85 is either refused or EVERY patch stays within 0.6 % of the same
    patch at true alignment (the noise of a few readings: 0.2 % per reading). Fails on the build
    before the second fix round: it had no alignment, a shifted pass leaked neighbour light at
    the patch ends (up to 14 % here)."""
    accepted = 0
    for d in np.round(np.arange(-6.0, 6.001, 0.25), 2):
        why, err = _patch_errors(seed, d, speed)
        if why == "ok":
            accepted += 1
            assert err <= 0.006, (seed, d, err)
        else:
            assert why == "uv_pass_shifted", (seed, d, why)
    # lined up, shifts within the largest offset taken (3 steps) are not refused
    assert accepted >= 20, accepted


def test_without_the_alignment_a_shift_damages_patch_ends():
    """the same strips cut without lining them up: the damage the alignment removes"""
    worst = 0.0
    for d in (1.0, 1.5, 2.0, -2.5, -3.0):
        c, lp, up, uv, _ls = _aligned_strip(1, d)
        c0, lp0, up0, uv0, ls0 = _aligned_strip(1, -0.85)
        ref = cut.cut_uv_pass(c0, lp0, up0, uv0, lamp_sig=ls0)
        try:
            r = cut.cut_uv_pass(c, lp, up, uv, edge=cut.EDGE_STEPS)   # narrow, NOT lined up
        except DualScanRefused:
            continue
        worst = max(worst, float(np.max(np.abs(r.uv[:, 0] - ref.uv[:, 0]) / ref.uv[:, 0])))
    assert worst > 0.01, worst


def _align_cases():
    out = []
    for seed in (1, 2, 3):
        for d in (-3.5, -1.0, 0.0, 1.3, 2.9, 4.0):
            c, lp, up, uv, ls = _aligned_strip(seed, d)
            ends = [x for s_, n in c for x in (lp[s_], lp[s_ + n - 1])]
            out.append((f"a{seed}_{d:+.1f}", lp, ls, up, uv[:, :3].mean(axis=1), min(ends), max(ends)))
    # a strip with no patch edges to line up by: not lined up (4.3.54's window), not refused
    c, lp, up, uv, ls = _aligned_strip(4, 0.0)
    ends = [x for s_, n in c for x in (lp[s_], lp[s_ + n - 1])]
    out.append(("flat", lp, np.full(lp.size, 0.5), up, np.full(up.size, 0.5) + 0.001 * np.sin(up),
                min(ends), max(ends)))
    return out


@pytest.fixture(scope="module")
def c_align(tmp_path_factory):
    from tests.test_i1pro3_lights_modes import _build_and_run
    p = tmp_path_factory.mktemp("aligncases") / "cases.txt"
    with p.open("w") as f:
        for name, lp, ls, up, us, lo, hi in _align_cases():
            f.write(f"align {name} {lp.size} {up.size} {lo:.17g} {hi:.17g}\n")
            for tag, v in (("P", lp), ("S", ls), ("Q", up), ("V", us)):
                f.write(tag + " " + " ".join(f"{x:.17g}" for x in v) + "\n")
    mp = pytest.MonkeyPatch()
    mp.setenv("CQ_DUAL_ALIGN_CASES", str(p))
    try:
        out = _build_and_run(tmp_path_factory, "i1pro2_dual_maths_test")
    finally:
        mp.undo()
    return {ln.split()[1]: (ln.split()[2], float(ln.split()[3]), float(ln.split()[4]))
            for ln in out.splitlines() if ln.startswith("aligncase ")}


def test_c_and_python_line_up_the_same(c_align):
    cases = _align_cases()
    assert len(c_align) == len(cases)
    seen = set()
    for name, lp, ls, up, us, lo, hi in cases:
        why, off, rise = cut.estimate_offset(lp, ls, up, us, lo, hi)
        cw, coff, crise = c_align[name]
        assert cw == (why or "ok"), (name, cw, why, off, rise)
        assert coff == pytest.approx(off, abs=1e-12), name
        if rise == rise and rise != float("inf"):
            assert crise == pytest.approx(rise, rel=1e-9), name
        seen.add(why or "ok")
        if name.startswith("a"):
            true = 0.85 + float(name.split("_")[1])       # the offset the strip was made with
            assert off == pytest.approx(true, abs=0.15), name
            assert (why is None) == (abs(true) <= cut.MAX_OFFSET), name
    assert seen == {"ok", "uv_pass_shifted", "not_lined_up"}
    assert c_align["flat"][0] == "not_lined_up"             # nothing to line up by


def test_a_strip_with_nothing_to_line_up_by_keeps_4354s_window():
    """Patches alike at 380-400 nm (no clear edges to line up by): not refused (that would loop
    for ever), cut uncorrected with 4.3.54's central 60 %, which the replay showed to hold up to
    about 2 steps of offset."""
    c, lp, up, uv, ls = _aligned_strip(4, 0.0)
    r = cut.cut_uv_pass(c, lp, up, uv, lamp_sig=np.full(lp.size, 0.5))
    assert r.lined_up == "not_lined_up" and r.offset == 0.0
    old = []
    for s_, n in c:
        lo, hi = sorted((lp[s_], lp[s_ + n - 1]))
        old.append(int(((up >= lo + 0.2 * (hi - lo)) & (up <= hi - 0.2 * (hi - lo))).sum()))
    assert r.counts == old


def _central_counts(c, lp, up):
    out = []
    for s_, n in c:
        lo, hi = sorted((lp[s_], lp[s_ + n - 1]))
        out.append(int(((up >= lo + 0.2 * (hi - lo)) & (up <= hi - 0.2 * (hi - lo))).sum()))
    return out


def test_without_the_lamp_readings_the_cut_keeps_4354s_window():
    """Third round, S1: no lamp readings to line up with (the helper's "not_measured": a lamp
    pass over 4000 readings, a failed allocation) never reaches the narrow window on positions
    nobody lined up: 4.3.54's central 60 % instead, as for "nothing clear to line up by"."""
    c, lp, up, uv, _ls = _aligned_strip(2, 0.0)
    r = cut.cut_uv_pass(c, lp, up, uv)
    assert r.lined_up == "not_measured" and r.counts == _central_counts(c, lp, up)
    assert r.window_flatness != r.window_flatness          # the narrow window's gate not asked


def _jump_strip(seed, jump, at=0.5):
    """the UV pass's offset jumps by *jump* steps part way through the pass (a lost or added
    ruler count, a hand reversal)"""
    c, lp, up, uv, ls = _aligned_strip(seed, 0.0)
    up = up.copy()
    k = int(up.size * at)
    up[k:] += jump
    return c, lp, up, uv, ls


@pytest.mark.parametrize("jump", [0.5, 1.0, -1.0])
def test_an_offset_changing_by_up_to_one_step_mid_pass_stays_right(jump):
    """the verification: a step of up to 1 step (a hand reversal flips the count's label by about
    1) is lined up to the larger part and every patch stays within 1.5 % (its replay: at most
    0.14 dE00 M2)"""
    c0, lp0, up0, uv0, ls0 = _aligned_strip(1, -0.85)
    ref = cut.cut_uv_pass(c0, lp0, up0, uv0, lamp_sig=ls0)
    c, lp, up, uv, ls = _jump_strip(1, jump)
    r = cut.cut_uv_pass(c, lp, up, uv, lamp_sig=ls)
    assert r.lined_up == "lined_up"
    assert float(np.max(np.abs(r.uv[:, 0] - ref.uv[:, 0]) / ref.uv[:, 0])) <= 0.015


def test_a_jump_of_several_steps_mid_pass_falls_back_or_is_refused():
    """The stated limit (design section 17): a jump of 3 steps or more in mid pass leaves no
    single offset that fits; the strip is not lined up and gets 4.3.54's window (its exposure:
    the replay showed up to 3.9 dE00 there), or it is refused; it is never cut narrow."""
    for jump in (4.0, -4.0, 5.0):
        c, lp, up, uv, ls = _jump_strip(3, jump)
        try:
            r = cut.cut_uv_pass(c, lp, up, uv, lamp_sig=ls)
        except DualScanRefused as e:
            assert e.reason in ("uv_pass_shifted", "uv_pass_misaligned", "uv_pass_too_fast",
                                "uv_pass_stalled", "uv_pass_short"), e.reason
            continue
        assert r.lined_up in ("not_lined_up", "lined_up")
        if r.lined_up == "not_lined_up":
            assert r.counts == _central_counts(c, lp, up - 0.0)


def _low_contrast(c, lp, up, uv, ls, k, seed=0):
    """the 380-400 nm band only (what the alignment reads) squeezed to k x its contrast, the
    reading noise kept: an OBA paper where every patch is dark there"""
    rng = np.random.default_rng(seed)
    uv = uv.copy()
    m = uv[:, :3].mean()
    uv[:, :3] = m + k * (uv[:, :3] - m) + rng.normal(0, 0.002, (uv.shape[0], 3))
    lm = ls.mean()
    return lm + k * (ls - lm) + rng.normal(0, 0.002, ls.size), uv


def test_a_strip_with_low_380_400_contrast_is_lined_up_while_its_edges_are_clear():
    """The tester's 480-patch chart on an OBA paper has about 0.4 x the 380-400 nm patch-to-patch
    contrast of the recorded strips (work folder proof4): at that contrast the strip still lines
    up (and every patch stays right); only far below it does it fall back to 4.3.54's window."""
    c, lp, up, uv, ls = _aligned_strip(5, 0.0)
    ls4, uv4 = _low_contrast(c, lp, up, uv, ls, 0.4)
    r = cut.cut_uv_pass(c, lp, up, uv4, lamp_sig=ls4)
    assert r.lined_up == "lined_up" and r.offset == pytest.approx(0.85, abs=0.15)
    ls0, uv0 = _low_contrast(c, lp, up, uv, ls, 0.01)
    r0 = cut.cut_uv_pass(c, lp, up, uv0, lamp_sig=ls0)
    assert r0.lined_up == "not_lined_up" and r0.counts == _central_counts(c, lp, up)


def test_the_helper_calls_the_cut_with_the_edge():
    src = (ROOT / "native" / "chartread_helper" / "chromiq_dualdev.c").read_text(encoding="utf-8")
    assert "cq_dd_edge(align_state), cutv, counts);" in src
    j = src.index("static double cq_dd_edge(")
    edge_fn = src[j:src.index("\n}\n", j)]
    # the narrow window ONLY on lined-up positions (third round, S1)
    assert 'strcmp(align_state, "lined_up") == 0 ? CQ_DUAL_EDGE_STEPS : -1.0' in edge_fn
    h = (ROOT / "native" / "chartread_helper" / "chromiq_dualscan.h").read_text(encoding="utf-8")
    assert "#define CQ_DUAL_EDGE_STEPS 0.25" in h and "#define CQ_DUAL_MIN_UV 3" in h
    i = src.index("static void cq_dd_strip(")
    body = src[i:src.index("\n}\n", i)]
    a = body.index("why = cq_dd_align(")
    assert a < body.index("why = cq_dual_cut(")                # lined up first, then cut


if __name__ == "__main__":      # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
