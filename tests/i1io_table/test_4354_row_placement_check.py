"""4.3.54: THE ROW PLACEMENT CHECK (workflow/i1io/table/placement.py), a veto beside the cut by
position, on rows shaped like the recorded ones (tests/i1io_table/placement_synth.py; the
recordings themselves are private and stay out of the repository).

| what the coordinator's brief asks                                         | here                    |
|---------------------------------------------------------------------------|-------------------------|
| a row off by 1-2.5 mm at 61-168 mm/s: the released cut accepts a wrong     | test_a_row_off_*        |
| patch (its dE00 named), the check refuses the row                          |                         |
| a correctly placed row, every patch length 8.9-16 mm, with and without     | test_a_correctly_*      |
| spacers, every speed ChromIQ can choose: accepted, values byte-identical    |                         |
| start +-5..40 ms, speed +-1..5 %: never a wrong patch accepted             | test_timing_errors_*    |
| "cannot confirm" cases refuse, never confirm by default                     | test_cannot_confirm_*   |
| the false-refusal rate on good rows, stated                                 | test_the_false_refusal_* |
| it only vetoes: values and the wire unchanged; the switch; the logs          | test_the_switch_*, ...  |

RED BEFORE: with ``placement.ROW_PLACEMENT_CHECK = False`` (the released 4.3.53 behaviour) the
offset and timing tests fail (the released cut accepts patches up to 13.6 dE00 off on these
rows); the work folder's red run holds the output.
"""
from __future__ import annotations

import inspect

import numpy as np
import pytest

from tests.i1io_table import placement_synth as S
from workflow.i1io.table import placement as pl
from workflow.i1io.table import scan as sc
from workflow.i1io.table import spot as sp
from workflow.i1io.table import strip as stp

#: a patch value further than this from its patch's true colour is WRONG (the cut tests' own)
DE_TOL = 0.5


def _plan_at(patch_mm, speed, spacer_mm=1.0):
    """The plan the job reads such a row with at *speed*: the rule's border, or (a speed the
    Row speed factor asked for) the border shrunk just enough to leave 3 clean readings."""
    p = S.plan(patch_mm, speed, spacer_mm)
    w = sc.windows(p, sc.MOTION_START_AFTER_LAMP_S, p.N, edge_mm=sc.strip_edge_mm(speed))
    if min(b - a for a, b in w) < sp.STRIP_MIN_READINGS:
        p.edge_mm = sc.shrunk_edge_mm(p, sp.STRIP_MIN_READINGS)
    return p


def _both(p, row, tmp_path, monkeypatch):
    """The released cut (the check off) and the cut with the check, on the same readings."""
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", False)
    off = S.write_and_cut(p, row, tmp_path / "off")
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", True)
    on = S.write_and_cut(p, row, tmp_path / "on")
    if on.ok:
        # a VETO only: an accepted row's values are the released cut's, to the last bit
        assert off.ok and on.patches == off.patches
    return off, on


def _worst(cut, row):
    return float(np.max(S.errors(cut, row))) if cut.ok else None


def _planner_speed(patch_mm, spacer_mm=1.0):
    for v in sp.speeds_to_try(patch_mm + spacer_mm):
        p = S.plan(patch_mm, v, spacer_mm)
        f = sp.strip_windows_ok(p)
        if f is not None and f >= sp.STRIP_MIN_READINGS and p.N <= sp.STRIP_N_MAX:
            return v
    return None


# ---- the switch, the logs ------------------------------------------------------------------------

def test_the_switch_is_one_constant_and_on():
    assert pl.ROW_PLACEMENT_CHECK is True
    # it applies at every speed and factor: strip.cut_row asks it on every row its own checks
    # accept, the dual row's lamp pass the same (dual_rows._placement)
    src = inspect.getsource(stp.cut_row)
    assert "pl.check_row(plan, rows, info[\"windows\"], wl)" in src
    from workflow.i1io.table import dual_rows as dl
    assert "pl.check_row(lamp, lamp_rows, windows, wavelengths)" in inspect.getsource(
        dl._placement)
    assert inspect.getsource(dl.cut_dual).count("_placement(") == 1
    assert inspect.getsource(dl.cut_lamp_only).count("_placement(") == 1


def test_switched_off_it_confirms_nothing_and_changes_nothing(tmp_path, monkeypatch):
    p = _plan_at(10.0, 88)
    row = S.Row(p, dx_mm=2.5, seed=3)
    monkeypatch.setattr(pl, "ROW_PLACEMENT_CHECK", False)
    cut = S.write_and_cut(p, row, tmp_path)
    assert cut.ok and cut.info["placement"]["on"] is False        # 4.3.53's verdict
    assert _worst(cut, row) > DE_TOL                               # ... and its wrong patch


def test_the_session_header_and_the_app_log_say_it_is_on(monkeypatch, tmp_path):
    from workflow.i1io.table import job as J
    src = inspect.getsource(J.TableJob.__init__)
    assert '"row placement check: "' in src and "pl.ROW_PLACEMENT_CHECK" in src
    import ui.i1io_table_window as W
    assert W._row_placement_check() == "on"
    seen = {}
    import core.app_log as al
    monkeypatch.setattr(al, "line", lambda tag, /, **kv: seen.setdefault(tag, kv))

    class Win:
        _stamp = "20261121-120000"
        _run = None
        job = None
        _popups = False
    W._applog_table_opened(Win())
    assert seen["table session"]["row_placement_check"] == "on"
    # the window writes one app log line per checked row, with the job's numbers
    W.TableMeasureWindow._live_event(type("X", (), {})(), {
        "event": "row_placement", "row": 3, "confirmed": False,
        "reason": "window_outside_the_stable_run", "patch": "A7", "off_mm": 1.31,
        "what": "row placement check: NOT confirmed"})
    assert seen["table row placement"] == {
        "row": 3, "confirmed": "no", "reason": "window_outside_the_stable_run", "patch": "A7",
        "off_mm": 1.31, "what": "row placement check: NOT confirmed"}


def test_the_refused_row_has_a_true_sentence():
    import ui.i1io_table_window as W
    t = W.reason_text(stp.PLACEMENT_REASON)
    assert t == ("the readings did not confirm where the patches are in this row, so ChromIQ "
                 "did not use them")
    assert "—" not in t


def test_the_record_names_the_patch_and_the_millimetres(tmp_path, monkeypatch):
    p = _plan_at(10.0, 88)
    row = S.Row(p, dx_mm=2.5, seed=3)
    off, on = _both(p, row, tmp_path, monkeypatch)
    assert off.ok and not on.ok and on.reason == stp.PLACEMENT_REASON
    pc = on.info["placement"]
    assert pc["confirmed"] is False and pc["patch"] and pc["off_mm"] > 0.5
    line = pl.summary(pc)
    assert line.startswith("row placement check: NOT confirmed (")
    assert "the readings do not confirm where the patches are in this row" in line
    assert f"patch {pc['patch']}, by {pc['off_mm']:.2f} mm" in line
    assert "ms" in line and "%" in line


# ---- THE STUDY'S CASES: the aims or the print off by millimetres -------------------------------------

@pytest.mark.parametrize("speed", [61, 88, 110, 138, 168])
def test_a_row_off_by_millimetres_is_refused_where_the_released_cut_was_wrong(
        tmp_path, monkeypatch, speed):
    """ChromIQ's 10 mm patch + 1 mm spacer, read at *speed* (the rule's border, or at 110-168,
    reachable with the Row speed factor, the shrunk one), the whole row 1, 1.5, 2 or 2.5 mm
    off (either way, 3 seeds each). The released cut ACCEPTS rows with a wrong patch (the
    study: the aims and the print are millimetres off at any speed); with the check, every such
    row is refused and no accepted row holds a wrong patch."""
    wrong_released, refused_of_them, seen = 0, 0, []
    for dx in (1.0, 1.5, 2.0, 2.5):
        for sign in (1, -1):
            for seed in range(3):
                p = _plan_at(10.0, speed)
                row = S.Row(p, dx_mm=sign * dx, seed=seed + 10 * speed)
                off, on = _both(p, row, tmp_path / f"{dx}{sign}{seed}", monkeypatch)
                w_on = _worst(on, row)
                assert w_on is None or w_on <= DE_TOL, (speed, dx * sign, seed, w_on)
                w_off = _worst(off, row)
                if w_off is not None and w_off > DE_TOL:
                    wrong_released += 1
                    refused_of_them += not on.ok
                    seen.append((sign * dx, round(w_off, 2)))
    assert wrong_released > 0 and refused_of_them == wrong_released, (speed, seen)


@pytest.mark.parametrize("speed, dx, want_off", [(61, 2.0, 1.4), (88, 2.5, 3.0), (110, 2.5, 3.0),
                                                 (138, 2.0, 3.0), (168, 2.0, 3.0)])
def test_the_dE00_the_released_cut_accepted(tmp_path, monkeypatch, speed, dx, want_off):
    """One row per speed, named: the released cut's worst accepted patch (at least *want_off*
    dE00 off its true colour) and the check's refusal of that row."""
    p = _plan_at(10.0, speed)
    row = S.Row(p, dx_mm=dx, seed=1)
    off, on = _both(p, row, tmp_path, monkeypatch)
    assert off.ok and _worst(off, row) >= want_off, _worst(off, row)
    assert not on.ok and on.reason == stp.PLACEMENT_REASON


# ---- correctly placed rows: accepted, values byte-identical ---------------------------------------

PATCHES = (8.9, 10.0, 11.0, 12.0, 14.0, 16.0)


@pytest.mark.parametrize("spacer_mm", [1.0, 0.0], ids=["spacer", "no_spacer"])
@pytest.mark.parametrize("patch_mm", PATCHES)
def test_a_correctly_placed_row_is_accepted_with_the_released_values(
        tmp_path, monkeypatch, patch_mm, spacer_mm):
    """Every patch length a ChromIQ table chart can have, with ChromIQ's 1 mm contrast spacer
    and without, at the speed ChromIQ chooses and at the Row speed factors 0.5, 1.5 and 2.0:
    a row lying where the aims put it (clean print, the real arm's start and ripple, the
    recorded noise) is accepted, with the released cut's values to the last bit (_both)."""
    base = _planner_speed(patch_mm, spacer_mm)
    for f in (1.0, 0.5, 1.5, 2.0):
        v = sp.factored_speed(base, f)
        p = _plan_at(patch_mm, v, spacer_mm)
        for seed in range(2):
            row = S.Row(p, seed=seed + int(10 * patch_mm), spacer_mm=spacer_mm)
            off, on = _both(p, row, tmp_path / f"{f}-{seed}", monkeypatch)
            if not off.ok:
                continue                   # the released checks refuse it already
            assert _worst(off, row) <= DE_TOL
            assert on.ok, (patch_mm, spacer_mm, v, f, seed, on.info.get("placement"))


# ---- timing errors: never a wrong patch accepted ------------------------------------------------------

@pytest.mark.parametrize("patch_mm, factor", [(8.9, 1.0), (10.0, 1.0), (10.0, 2.0), (11.0, 1.0),
                                              (12.0, 1.5)])
def test_timing_errors_never_let_a_wrong_patch_through(tmp_path, monkeypatch, patch_mm, factor):
    """The motion start off by +-5, 10, 20, 40 ms, the speed off by +-1, 2, 5 %: with the check
    no accepted row holds a wrong patch (the released cut does accept some)."""
    v = sp.factored_speed(_planner_speed(patch_mm), factor)
    p = _plan_at(patch_mm, v)
    released_wrong = 0
    for kind, vals in (("dt", (-0.040, -0.020, -0.010, -0.005, 0.005, 0.010, 0.020, 0.040)),
                       ("eps", (-0.05, -0.02, -0.01, 0.01, 0.02, 0.05))):
        for i, x in enumerate(vals):
            kw = {"dt_s": x} if kind == "dt" else {"speed_err": x}
            row = S.Row(p, seed=100 * i + (7 if kind == "dt" else 8), print_sd=0.3, **kw)
            off, on = _both(p, row, tmp_path / f"{kind}{x}", monkeypatch)
            w = _worst(on, row)
            assert w is None or w <= DE_TOL, (patch_mm, v, kind, x, w)
            released_wrong += (_worst(off, row) or 0.0) > DE_TOL
    assert released_wrong > 0


# ---- the cases the check cannot confirm: it says so ------------------------------------------------

def _windows(p, n, edge=0.0):
    return sc.windows(p, sc.MOTION_START_AFTER_LAMP_S, n, edge_mm=edge)


def test_cannot_confirm_without_readings_or_with_broken_ones():
    p = S.plan(10.0, 88)
    w = _windows(p, p.N)
    assert pl.check_row(p, [], w)["reason"] == "no_readings"
    assert pl.check_row(p, [[0.5] * 36] * 30, w)["reason"] == "too_few_readings_for_the_check"
    row = S.Row(p, seed=2)
    bad = row.readings.copy()
    bad[100, 7] = float("nan")
    r = pl.check_row(p, bad.tolist(), w)
    assert r["confirmed"] is False and r["reason"] == "readings_not_finite"
    r = pl.check_row(p, row.readings.tolist(), w[:-1])
    assert r["confirmed"] is False


def test_cannot_confirm_when_the_check_itself_fails(monkeypatch):
    p = S.plan(10.0, 88)
    row = S.Row(p, seed=2)

    def boom(*a, **k):
        raise ZeroDivisionError("planted")
    monkeypatch.setattr(pl, "_check", boom)
    r = pl.check_row(p, row.readings.tolist(), _windows(p, p.N, 1.58))
    assert r["confirmed"] is False and r["reason"] == "check_failed" and "planted" in r["error"]


@pytest.mark.parametrize("patch_mm, speed", [(6.0, 88), (7.0, 110), (7.0, 138), (8.0, 168)])
def test_very_short_patches_are_not_confirmed(patch_mm, speed):
    """Patches too short for 3 clean readings at that speed: not confirmed even when the cut is
    given every reading (no border at all)."""
    p = S.plan(patch_mm, speed)
    for seed in range(3):
        row = S.Row(p, seed=seed)
        r = pl.check_row(p, row.readings.tolist(), _windows(p, p.N, 0.0))
        assert r["confirmed"] is False, (patch_mm, speed, seed)


def test_a_whole_pitch_aim_error_is_beyond_the_check_documented(tmp_path, monkeypatch):
    """THE CHECK'S LIMIT, pinned so that nobody believes otherwise: a sheet that lies a WHOLE
    PITCH off (the aims made on the neighbouring patch, 11 mm) puts every window on the
    neighbour's clean middle. The timing's own bound is +-(12 ms + 3 mm / V), so the readings
    fit "as timed" and the row is confirmed with every value its neighbour's. That is an aiming
    error, not a placement error: reading patch by patch would read the same wrong patches.
    It is named in the safety brief as what slips through."""
    p = _plan_at(10.0, 88)
    row = S.Row(p, dx_mm=11.0, seed=4)
    off, on = _both(p, row, tmp_path, monkeypatch)
    assert off.ok and on.ok and _worst(on, row) > DE_TOL


@pytest.mark.parametrize("speed", [110, 138, 168])
def test_low_contrast_neighbours_without_spacers_are_refused_or_right(tmp_path, monkeypatch,
                                                                      speed):
    """No spacer, every patch a slight variant of one colour (0.5-1 dE00 apart): the runs merge;
    accepted only with every value right (the window stays inside its own patch), else refused."""
    rng = np.random.default_rng(speed)
    base = S.PALETTE[3]
    for seed in range(3):
        p = _plan_at(10.0, speed, spacer_mm=0.0)
        cols = np.array([np.clip(base * (1 + rng.normal(0, 0.01)), 0.01, 1) for _ in range(24)])
        row = S.Row(p, seed=seed, spacer_mm=0.0, colours=cols)
        off, on = _both(p, row, tmp_path / str(seed), monkeypatch)
        w = _worst(on, row)
        assert w is None or w <= DE_TOL


def test_few_readings_per_patch_are_not_confirmed_by_default():
    """8.9 mm patches at 168 mm/s (2 to 3 readings on a patch's clean part): the check refuses
    rather than confirm from edge readings."""
    p = S.plan(8.9, 168, 1.0)
    refused = 0
    for seed in range(5):
        row = S.Row(p, seed=seed, print_sd=0.45, dx_mm=0.8)
        r = pl.check_row(p, row.readings.tolist(), _windows(p, p.N, 0.0))
        refused += not r["confirmed"]
    assert refused >= 3


# ---- the false-refusal rate, stated ---------------------------------------------------------------

#: MEASURED with this test's own rows (work folder scripts/false_refusals.py ->
#: synthetic_result.txt): realistic GOOD rows (the released cut accepts them and every patch is
#: within DE_TOL; start +-6 ms, the row +-0.4 mm, the aim grid 0.5 % long), ChromIQ's own speed
#: for each patch length, its 1 mm spacer: clean print 1 of 60 refused (1.7 %, two places fitting
#: equally well); vendor-like print (edges +-0.45 mm) 5 of 59 (8.5 %), and 4 of those 5 had a
#: window that really took in edge readings (outside the truth's clean part). Over a wider set
#: (explore.py "realistic": both prints, both spacer forms, factors 1.0 / 1.5 / 2.0) 54 of 675
#: good rows (8 %), 16 of them (2.4 %) with every window truly clean.
FALSE_REFUSALS_MAX = {"clean": 0.03, "vendor-like": 0.12}


@pytest.mark.parametrize("print_sd, label", [(0.15, "clean"), (0.45, "vendor-like")])
def test_the_false_refusal_rate_on_good_rows(tmp_path, monkeypatch, print_sd, label):
    rng = np.random.default_rng(5)
    good = refused = 0
    for patch_mm in PATCHES:
        v = _planner_speed(patch_mm)
        p = _plan_at(patch_mm, v)
        for seed in range(10):
            row = S.Row(p, seed=seed * 7 + int(patch_mm * 10) + v, print_sd=print_sd,
                        dt_s=rng.uniform(-0.006, 0.006),
                        dx_mm=float(np.clip(rng.normal(0, 0.4), -1.5, 1.5)),
                        scale=rng.normal(0.005, 0.003))
            off, on = _both(p, row, tmp_path / f"{patch_mm}-{seed}", monkeypatch)
            if off.ok and _worst(off, row) <= DE_TOL:
                good += 1
                refused += not on.ok
    assert good >= 50
    assert refused / good <= FALSE_REFUSALS_MAX[label], (label, refused, good)


# ---- speed ----------------------------------------------------------------------------------------

def test_a_rows_check_takes_well_under_100_ms():
    """The slowest ChromIQ case: the longest row at the lowest strip speed (54 mm/s, 16 mm
    patches: about 1,450 readings), and a typical one (10 mm at 88)."""
    import time
    for patch_mm, v in ((16.0, 54), (10.0, 88)):
        p = S.plan(patch_mm, v)
        row = S.Row(p, seed=1)
        w = _windows(p, p.N, sc.strip_edge_mm(v))
        pl.check_row(p, row.readings.tolist(), w)           # imports, first use
        t0 = time.perf_counter()
        r = pl.check_row(p, row.readings.tolist(), w)
        ms = (time.perf_counter() - t0) * 1000.0
        assert r["confirmed"], r
        assert ms < 100.0, (patch_mm, v, ms)


def test_longest_run_is_the_studys_run():
    """The fast run search gives the study prototype's greedy result (every start grown, the
    first longest kept) on random segments."""
    rng = np.random.default_rng(3)

    def proto(seg):
        best = (0, None)
        for a in range(len(seg)):
            b = a
            while b + 1 < len(seg):
                cand = seg[a:b + 2]
                med = np.median(cand, 0)
                d = pl._de00(cand, np.repeat(med[None], len(cand), 0)).max()
                if d > pl._limit(med[0]):
                    break
                b += 1
            if b - a + 1 > best[0]:
                best = (b - a + 1, a)
        return best[1], best[0]
    for k in range(40):
        n = int(rng.integers(1, 40))
        steps = rng.integers(0, 4, n).cumsum() // 3
        seg = np.stack([50 + 8 * steps + rng.normal(0, 0.3, n), rng.normal(0, 0.4, n),
                        rng.normal(0, 0.4, n)], 1)
        if k % 4 == 0:
            seg[:, 0] -= 30                               # dark
        assert pl.longest_run(seg, int(rng.integers(0, n))) == proto(seg), k
