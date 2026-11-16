"""The margin tolerance's rule (native/chartread_helper/chromiq_margin.c, the
SAME C code the helper runs, through tests/margin_lib.py) on

* the three real i1Pro 2 sessions of one tester (2026-11-15; candidates
  reconstructed from the ruler diagnostics files by
  scripts/make_margin_fixtures.py, colours = the 3-band trace on the CIE Lab
  scale, expected colours = the accepted reading of the same strip, optionally
  with a design-colour stand-in noise);
* the expected CIE Lab of the reader review's 28 real .ti2 charts, with a
  simulated print.

The one property that matters most: ZERO wrong accepts. Every reading built
here that is not the expected row read in full (another row, a shift of one
or two patches at either end, a start one patch in with or without a white
end, a split or a back-and-forth in the middle, a stand-still inside the row)
must be refused. Full counts: the work notes' eval_margin.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tests import margin_lib as ml

DATA = Path(__file__).parent / "data"
pytestmark = pytest.mark.skipif(ml.lib() is None, reason="no C compiler here")

#: The refusals the rule rescues at noise 0, all correct (session, strip).
#: 9 of 31 since 2026-11-16b (10 before): strip S of the first session is now
#: refused because rule L's trailer must be within 3 dE of the lightest
#: segment, and in the 3-band trace (each band relative to its own maximum) a
#: light yellow patch there is "lighter" than the trailer. The two readings
#: of strip AL in the third session, real pulls back of 40 and 46 ruler steps,
#: were refused before and stay refused, now by the direction rule.
RESCUED = {("20261115-121759", "Z"),
           ("20261115-121759", "AG"), ("20261115-145807", "C"),
           ("20261115-145807", "V"), ("20261115-173446", "V"),
           ("20261115-173446", "Y"), ("20261115-173446", "AA"),
           ("20261115-173446", "AH"), ("20261115-173446", "AJ")}


def _fix():
    return json.loads((DATA / "margin_fixtures.json").read_text(encoding="utf-8"))


def _rows(sess):
    refs = {}
    for s in sess["strips"]:
        if s["verdict"] in ("accepted", "asked") and len(s["cut_values"]) == s["patches"]:
            v = np.array(s["cut_values"])
            refs.setdefault(s["strip"], (v[::-1] if s["reversed"] else v, s))
    return refs


def _perturb(R, sigma, rng):
    if sigma == 0:
        return R
    noise = rng.normal(0, sigma / 300.0, R.shape)
    gain = 1 + rng.normal(0, sigma / 400.0, (1, 3))
    return np.clip(R * gain + noise * np.sqrt(np.maximum(R, 0.02)), 0.003, 1.0)


def _correct(V, ref, s, acc):
    rev = None
    if s["ruler_sign"] and acc["ruler_sign"]:
        rev = acc["reversed"] ^ (s["ruler_sign"] != acc["ruler_sign"])
    for r in ((True, False) if rev is None else (rev,)):
        if np.abs(V - (ref[::-1] if r else ref)).max() <= 0.045:
            return True
    return False


def _ruler(s):
    """The recording's ruler as the helper hands it over: each candidate's
    position at its first reading, the net direction, the largest fall-back."""
    return {"p0": [c[6] for c in s["candidates"]],
            "net": float(s["ruler_sign"] or sum(c[2] for c in s["candidates"])),
            "back": s["ruler_back"]}


def _sessions(sigma, seed):
    """(outcomes of the real refusals, wrong accepts, constructed counts)."""
    rng = np.random.default_rng(seed)
    rescued, wrong, built = {}, [], {"refused": 0, "pos_ok": 0, "pos_refused": 0}
    for sess in _fix()["sessions"]:
        refs = _rows(sess)
        names = list(refs)
        REF = np.array([ml.band_lab(_perturb(refs[k][0], sigma, rng)) for k in names])
        for s in sess["strips"]:
            cands = s["candidates"]
            if len(cands) < 3 or s["strip"] not in names:
                continue
            V = np.array([c[3:6] for c in cands])
            lab = ml.band_lab(V)
            st = [c[2] for c in cands]
            no = [c[1] for c in cands]
            rul = _ruler(s)
            e = names.index(s["strip"])
            ref0, acc = refs[s["strip"]]
            why = ml.WHY.get(s["refused_because"], 1)
            if s["verdict"] == "refused":
                r = ml.decide(lab, st, no, REF, e, why, **rul)
                if r["accept"]:
                    ok = _correct(V[r["sel"]], ref0, s, acc)
                    rescued[(sess["session"], s["strip"])] = ok
                    if not ok:
                        wrong.append(("real", sess["session"], s["strip"]))
            for j in range(len(names)):
                if j != e and ml.decide(lab, st, no, REF, j, why, **rul)["accept"]:
                    wrong.append(("wrong row", sess["session"], s["strip"], names[j]))
            if s["verdict"] in ("accepted", "asked") and len(s["cut_values"]) == s["patches"]:
                U = ml.band_lab(np.array(s["cut_values"]))
                m = (lab[-1] if lab[-1][0] >= lab[0][0] else lab[0])[None]
                N = len(U)
                h = N // 2
                neg = [np.r_[m, U[1:]], np.r_[m, U[1:], m], np.r_[U[1:], m],
                       np.r_[m, U[:-1]], np.r_[U[:-1], m], np.r_[m, m, U[2:]],
                       np.r_[m, U[2:], m], np.r_[U[:-2], m, m],
                       np.r_[U[1:h], U[h - 1:h], U[h:]],
                       np.r_[m, U[:h], U[h - 1:h], U[h:]],
                       np.r_[m, U[:h + 1], U[h - 1:h + 1], U[h + 1:]]]
                pos = [(np.r_[m, U], U), (np.r_[U, m], U), (np.r_[m, U, m], U),
                       (np.r_[m, U[::-1]], U[::-1])]
                for form in ("M", "L"):
                    for C in neg:
                        full = np.r_[m, C, m] if form == "M" else np.r_[C, m]
                        for w in (1, 2, 3):
                            r = ml.decide(full, [17.0] * len(full), [20] * len(full), REF, e, w)
                            if r["accept"] and not (np.allclose(full[r["sel"]], U)
                                                    or np.allclose(full[r["sel"]], U[::-1])):
                                wrong.append(("constructed", sess["session"], s["strip"]))
                            else:
                                built["refused"] += 1
                    for C, want in pos:
                        full = np.r_[m, C, m] if form == "M" else np.r_[C, m]
                        r = ml.decide(full, [17.0] * len(full), [20] * len(full), REF, e, 2)
                        if r["accept"]:
                            if np.allclose(full[r["sel"]], want):
                                built["pos_ok"] += 1
                            else:
                                wrong.append(("positive misplaced", sess["session"], s["strip"]))
                        else:
                            built["pos_refused"] += 1
                # a stand-still INSIDE the row is refused, one after it is left out
                full = np.r_[m, U[:5], U[5:6], U[5:], m]
                stp = [17.0] * len(full)
                stp[6] = 0.0
                if ml.decide(full, stp, [20] * len(full), REF, e, 2)["accept"]:
                    wrong.append(("stand-still inside", sess["session"], s["strip"]))
    return rescued, wrong, built


def test_the_c_lab_matches_the_numpy_twin():
    import ctypes
    L = ml.lib()
    for xyz in ([96.42, 100.0, 82.49], [20.0, 10.0, 5.0], [0.1, 0.2, 0.05]):
        a = (ctypes.c_double * 3)(*xyz)
        b = (ctypes.c_double * 3)()
        L.cqm_xyz2lab(ctypes.byref(a), ctypes.byref(b))
        assert np.allclose(list(b), ml.xyz2lab(np.array(xyz)), atol=1e-9)


def test_real_sessions_rescue_exactly_the_expected_refusals_all_correct():
    rescued, wrong, built = _sessions(0, 1)
    assert wrong == []
    assert set(rescued) == RESCUED
    assert all(rescued.values())
    assert built["refused"] > 2000 and built["pos_ok"] > 500


@pytest.mark.parametrize("sigma", [8, 15, 25])
def test_with_design_colour_noise_there_is_still_no_wrong_accept(sigma):
    rescued, wrong, _ = _sessions(sigma, 2)
    assert wrong == []
    assert all(rescued.values())


def _sim(Lab, sigma, rng):
    out = Lab.copy()
    out[..., 0] = 0.93 * out[..., 0] + 2.5
    out[..., 1:] *= 0.85
    out[..., 2] += 2
    return out + rng.normal(0, sigma, out.shape)


@pytest.mark.parametrize("sigma", [0, 8])
def test_the_28_real_charts_never_accept_a_wrong_reading(sigma):
    charts = json.loads((DATA / "margin_charts.json").read_text(encoding="utf-8"))["charts"]
    assert len(charts) == 28
    wrong, ok, tries = [], 0, 0
    for name, rows in charts.items():
        REF = np.array(rows)
        R, N, _ = REF.shape
        white = REF.reshape(-1, 3)[np.argmax(REF.reshape(-1, 3)[:, 0])]
        rng = np.random.default_rng(7)
        M = _sim(REF, sigma, rng)
        paper = _sim(white[None], 0.5, rng)[0]
        m = paper[None]
        h = N // 2
        for e in range(R):
            U = M[e]
            neg = [np.r_[m, U[1:]], np.r_[m, U[1:], m], np.r_[U[1:], m],
                   np.r_[m, U[:-1]], np.r_[m, m, U[2:]], np.r_[m, U[2:], m],
                   np.r_[U[:-2], m, m], np.r_[U[1:h], U[h - 1:h], U[h:]],
                   np.r_[m, U[:h + 1], U[h - 1:h + 1], U[h + 1:]]]
            for form in ("M", "L"):
                for C in neg:
                    full = np.r_[m, C, m] if form == "M" else np.r_[C, m]
                    r = ml.decide(full, [17.0] * len(full), [20] * len(full), REF, e, 2)
                    tries += 1
                    if r["accept"] and not (np.allclose(full[r["sel"]], U)
                                            or np.allclose(full[r["sel"]], U[::-1])):
                        wrong.append((name, e))
                full = np.r_[m, m, U, m] if form == "M" else np.r_[U, m]
                r = ml.decide(full, [17.0] * len(full), [20] * len(full), REF, e, 2)
                ok += bool(r["accept"] and np.allclose(full[r["sel"]], U))
            full = np.r_[m, m, U, m]
            for j in range(R):
                if j != e:
                    tries += 1
                    if ml.decide(full, [17.0] * len(full), [20] * len(full), REF, j, 2)["accept"]:
                        wrong.append((name, e, j))
    assert wrong == []
    assert tries > 20000 and ok > 500


def test_a_flagged_candidate_is_never_used():
    rows = json.loads((DATA / "margin_charts.json").read_text(encoding="utf-8"))["charts"]
    REF = np.array(next(iter(rows.values())))
    U = _sim(REF, 0, np.random.default_rng(1))[0]
    m = np.array([[95.0, -0.5, 2.0]])
    full = np.r_[m, m, U, m]
    n = len(full)
    assert ml.decide(full, [17.0] * n, [20] * n, REF, 0, 2)["accept"]
    for flag in (1, 2, 4):
        flags = [0] * n
        flags[5] = flag
        assert not ml.decide(full, [17.0] * n, [20] * n, REF, 0, 2, flags=flags)["accept"]


def test_only_the_three_refusals_are_looked_at():
    rows = json.loads((DATA / "margin_charts.json").read_text(encoding="utf-8"))["charts"]
    REF = np.array(next(iter(rows.values())))
    U = _sim(REF, 0, np.random.default_rng(1))[0]
    m = np.array([[95.0, -0.5, 2.0]])
    full = np.r_[m, m, U, m]
    n = len(full)
    for why in (0, 4, 99):
        assert not ml.decide(full, [17.0] * n, [20] * n, REF, 0, why)["accept"]
