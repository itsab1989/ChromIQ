"""The i1Pro 2 dual scan: the instrument path's pairing check (C) is the Python one.

Safety review 2026-11-18, MUST M1: a UV pass over the neighbouring row (or set down one patch
further) passes every ruler gate, so only the pairing check tells it from the strip's own pass.
The record path (workflow/dual_scan/record.py) runs ``pairing.check_pairing``; the instrument path
(native/chartread_helper/chromiq_dualdev.c, ``cq_dd_strip``) now runs its C twin
``cq_dual_pairing`` (chromiq_dualscan.c) right after the cut. This file holds the two to the same
rule, the same thresholds and the same "not judged" cases, on invented strips shaped like the
reviewer's (tests/test_i1pro2_dual_scan_wrong_row_needs_the_pairing_check.py) and on random ones.
The recorded strips of both instruments are compared the same way in the private proof (work
folder, never in the repository).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from workflow.dual_scan import pairing
from workflow.dual_scan.cut import cut_uv_pass
from workflow.dual_scan.model import WAVELENGTHS, DualCalibration
from workflow.dual_scan.pairing import check_pairing
from workflow.dual_scan.reasons import REASONS, DualScanRefused

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "native" / "chartread_helper"
NB = WAVELENGTHS.size


def _code(path: Path) -> str:
    return re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8", errors="replace"), flags=re.S)


# ----------------------------------------------------------------- the two sides

def python_verdict(L, U, cal: DualCalibration) -> "tuple":
    """(reason or 'ok', checked, usable, corr, err) of pairing.check_pairing."""
    try:
        ev = check_pairing(L, U, cal)
        return "ok", int(ev.checked), ev.usable, ev.correlation, ev.median_ratio_error
    except DualScanRefused as e:
        return e.reason, None, None, None, None


def write_cases(path: Path, cases) -> None:
    """cases: [(name, L[n][36], U[n][36], W[36], T[36], E[36])] in the maths test's format."""
    def vec(tag, v):
        return tag + " " + " ".join(repr(float(x)) for x in np.asarray(v, dtype=float).ravel()) + "\n"
    with path.open("w", encoding="utf-8") as f:
        for name, L, U, W, T, E in cases:
            L = np.atleast_2d(L)
            U = np.atleast_2d(U)
            f.write(f"case {name} {L.shape[0]}\n")
            f.write(vec("W", W) + vec("T", T) + vec("E", E))
            for row in L:
                f.write(vec("L", row))
            for row in U:
                f.write(vec("U", row))


def c_verdicts(stdout: str) -> "dict[str, tuple]":
    out = {}
    for ln in stdout.splitlines():
        if not ln.startswith("pairing "):
            continue
        t = ln.split()
        if len(t) == 3:
            out[t[1]] = (t[2], None, None, None, None)
            continue
        why = t[2]
        out[t[1]] = (why, int(t[3]), int(t[4]), float(t[6]), float(t[7]))
    return out


def agree(py: tuple, c: tuple, *, tol: float = 1e-9) -> bool:
    """Same verdict; when accepted, the same checked flag, usable count and numbers."""
    if py[0] != c[0]:
        return False
    if py[0] != "ok":
        return True
    if py[1] != c[1] or py[2] != c[2]:
        return False
    for a, b in ((py[3], c[3]), (py[4], c[4])):
        if (a != a) != (b != b):
            return False
        if a == a and abs(a - b) > tol:
            return False
    return True


# ----------------------------------------------------------------- the cases

def _cal(lift: float = 1.0):
    w = np.full(NB, 0.9)
    t = np.where(WAVELENGTHS <= 410, 0.2, 0.02) * lift
    e = np.full(NB, 1000.0)
    return w, t, e


def _row(levels, glow=0.08, noise=0.0, seed=0, lift=1.0):
    w, t, _e = _cal(lift)
    rng = np.random.default_rng(seed)
    L = np.array([np.full(NB, v) for v in levels]) * (1.0 + 0.02 * rng.standard_normal((len(levels), NB)))
    U = L * (t / w)[None, :] + glow * ((WAVELENGTHS >= 420) & (WAVELENGTHS <= 500))[None, :] * L
    if noise:
        U = U * (1.0 + noise * rng.standard_normal(U.shape))
    return L, U


ROW_A = [0.85, 0.20, 0.55, 0.10, 0.70, 0.35, 0.90, 0.15]
ROW_B = [0.30, 0.80, 0.12, 0.65, 0.25, 0.90, 0.40, 0.60]


def _pass(cells_uv: np.ndarray, per_cell: int = 6):
    n = cells_uv.shape[0]
    cells = [(10 * k, 10) for k in range(n)]
    lamp_pos = np.arange(10 * n, dtype=float)
    up, ur = [], []
    for k in reversed(range(n)):
        for i in range(per_cell):
            up.append(10 * k + 3.0 + 3.0 * i / (per_cell - 1))
            ur.append(cells_uv[k])
    return cells, lamp_pos, np.array(up), np.array(ur)


def _cases():
    w, t, e = _cal()
    LA, UA = _row(ROW_A)
    LB, UB = _row(ROW_B, seed=1)
    cases = {
        "own_row": (LA, cut_uv_pass(*_pass(UA)).uv),
        "next_row": (LA, cut_uv_pass(*_pass(UB)).uv),          # the reviewer's M1 case
        "reversed": (LA, UA[::-1]),
        "shifted_one_patch": (LA[1:], UA[:-1]),
        "half_from_another_row": (LA, np.vstack([UA[:4], UB[4:]])),
        "one_colour": _row([0.5] * 8, noise=0.01),              # spread too small: ratio only
        "one_colour_wrong_level": (_row([0.5] * 8)[0], _row([0.5] * 8)[1] * 1.3),
        "dark_strip_own": _row([0.02, 0.03, 0.025, 0.035, 0.02, 0.03], noise=0.05),
        "dark_strips_crossed": (_row([0.02, 0.03, 0.025, 0.035])[0],
                                _row([0.035, 0.02, 0.03, 0.025], seed=3)[1]),
        "dark_lamp_bright_uv": (_row([0.02, 0.03, 0.025, 0.035])[0], _row([0.8, 0.2, 0.6, 0.4])[1]),
        "bright_lamp_dark_uv": (_row([0.8, 0.2, 0.6, 0.4])[0], _row([0.02, 0.03, 0.025, 0.035])[1]),
        "uv_led_off": (_row([0.8, 0.2, 0.6, 0.4])[0], np.full((4, NB), 1e-4)),
        "black_patch_in_strip": (np.vstack([np.zeros(NB), _row([0.5, 0.6, 0.4, 0.7])[0]]),
                                 np.vstack([np.zeros(NB), _row([0.5, 0.6, 0.4, 0.7])[1]])),
        "two_usable_only": (_row([0.6, 0.02, 0.5, 0.01])[0], _row([0.6, 0.02, 0.5, 0.01])[1]),
        "nan_value": (np.vstack([np.full(NB, np.nan), _row([0.5, 0.6])[0]]),
                      np.vstack([np.zeros(NB), _row([0.5, 0.6])[1]])),
    }
    rng = np.random.default_rng(20261118)
    for i in range(120):      # random strips, own and wrong, noisy and not
        n = int(rng.integers(2, 30))
        lev = rng.uniform(0.005, 0.95, n)
        L, U = _row(lev, noise=float(rng.choice([0.0, 0.02, 0.08])), seed=i)
        if i % 3 == 1:
            U = U[rng.permutation(n)]
        elif i % 3 == 2:
            U = U * float(rng.uniform(0.5, 1.5))
        cases[f"random_{i}"] = (L, U)
    return [(name, L, U, w, t, e) for name, (L, U) in cases.items()]


@pytest.fixture(scope="module")
def c_out(tmp_path_factory) -> "dict[str, tuple]":
    from tests.test_i1pro3_lights_modes import _build_and_run
    p = tmp_path_factory.mktemp("pairing") / "cases.txt"
    write_cases(p, _cases())
    mp = pytest.MonkeyPatch()
    mp.setenv("CQ_DUAL_PAIRING_CASES", str(p))
    try:
        out = _build_and_run(tmp_path_factory, "i1pro2_dual_maths_test")
    finally:
        mp.undo()
    return c_verdicts(out)


def test_c_and_python_give_the_same_verdict_on_every_case(c_out):
    cases = _cases()
    assert len(c_out) == len(cases)
    bad = []
    for name, L, U, w, t, e in cases:
        py = python_verdict(L, U, DualCalibration(w, t, e))
        if not agree(py, c_out[name]):
            bad.append((name, py, c_out[name]))
    assert not bad, bad


def test_the_cases_cover_every_outcome(c_out):
    """Not a vacuous agreement: accepted, accepted unchecked, and every refusal occur."""
    v = {k: x[0] for k, x in c_out.items()}
    assert v["own_row"] == "ok" and c_out["own_row"][1] == 1
    for k in ("next_row", "reversed", "shifted_one_patch", "half_from_another_row",
              "one_colour_wrong_level", "dark_lamp_bright_uv"):
        assert v[k] == "uv_pass_wrong_strip", (k, c_out[k])
    for k in ("bright_lamp_dark_uv", "uv_led_off"):
        assert v[k] == "uv_pass_no_uv_light", (k, c_out[k])
    for k in ("dark_strip_own", "dark_strips_crossed"):
        assert v[k] == "ok" and c_out[k][1] == 0, (k, c_out[k])     # not judged: too dark
    assert v["black_patch_in_strip"] == "ok" and c_out["black_patch_in_strip"][1] == 1
    assert v["one_colour"] == "ok" and c_out["one_colour"][3] != c_out["one_colour"][3]   # corr not asked
    assert v["two_usable_only"] == "ok" and c_out["two_usable_only"][2] == 2
    assert v["nan_value"] == "bad_values"
    rnd = [x[0] for k, x in c_out.items() if k.startswith("random_")]
    assert "ok" in rnd and "uv_pass_wrong_strip" in rnd


def test_the_c_thresholds_are_the_python_ones():
    h = (HELPER / "chromiq_dualscan.h").read_text(encoding="utf-8")

    def c(name):
        return float(re.search(r"#define CQ_DUAL_PAIR_" + name + r"\s+([0-9.]+)", h).group(1))
    assert (c("LO"), c("HI")) == tuple(float(x) for x in pairing.LED_BANDS_NM)
    assert c("MIN_CORRELATION") == pairing.MIN_CORRELATION
    assert c("MAX_RATIO_ERROR") == pairing.MAX_MEDIAN_RATIO_ERROR
    assert c("MIN_SPREAD") == pairing.MIN_SPREAD
    assert c("LEVEL_FLOOR") == pairing.LEVEL_FLOOR
    assert c("MIN_USABLE") == pairing.MIN_USABLE
    assert c("MIN_FOR_CORRELATION") == pairing.MIN_FOR_CORRELATION
    assert c("MIN_LIGHT_RATIO") == pairing.MIN_LIGHT_RATIO


def test_the_hand_strip_runs_the_pairing_check_between_the_cut_and_the_formula():
    src = _code(HELPER / "chromiq_dualdev.c")
    i = src.index("static void cq_dd_strip(")
    body = src[i:src.index("\n}\n", i)]
    cut, pair, comp = (body.index("cq_dual_cut("), body.index("cq_dual_pairing("),
                       body.index("cq_dd_compute("))
    assert cut < pair < comp
    # a refusal is a failure of the pass (the strip is read again), not of the session
    j = src.index("static int cq_dd_pass_level(")
    lvl = src[j:src.index("\n}\n", j)]
    for w in ("uv_pass_wrong_strip", "uv_pass_no_uv_light"):
        assert f'"{w}"' in lvl and w in REASONS
    # and the event says whether the pairing could be judged (the note pairing_not_checked)
    assert "pairing_not_checked" in body or "\\\"pairing\\\"" in src
