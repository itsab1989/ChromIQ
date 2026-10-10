"""The neighbour check (#182): the rule on its own, on synthetic charts and
replayed on the real profiling sheets the beta 10 analysis measured.

Beta 17 (Knut #182 6071673457, adopted in 6078174421; 6082015002,
6085694445): Knut's four steps. For each neighbour its error (ΔE*ab between
reading and expected colour), their median, the patch's own error, and red
when own minus median is MORE than the neighbour limit. The neighbours are the
2 to 4 read patches nearest in expected colour within the colour-neighbour
radius, from ANY strip. Beta 15's first test ("buffer": readings further apart
than the expected colours) is gone.

The real sheets are in ``tests/data/neighbour_check/`` (location, device RGB,
expected XYZ, measured XYZ per patch). Their counts below are re-measured with
the beta 17 rule; beta 15's are kept beside them.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

import pytest

from workflow import neighbour_check as N
from workflow.neighbour_check import NeighbourCheck, engine_lab

DATA = Path(__file__).resolve().parent / "data" / "neighbour_check"


def strip_of(loc: str) -> str:
    return "".join(c for c in str(loc) if c.isalpha()).upper()


def sheet(name):
    return json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))["patches"]


def check_of(patches, limit=N.LIMIT_DE, radius=N.RADIUS_DE):
    nc = NeighbourCheck(limit=limit, radius=radius)
    for loc, _rgb, exp, meas in patches:
        nc.set_reading(loc, exp, meas, strip_of(loc))
    nc.evaluate()
    return nc


# ---- the rule's numbers are the ruling's -----------------------------------
def test_the_numbers_are_the_approved_ones():
    assert N.RADIUS_DE == 15.0
    assert N.MAX_COMPARED == 4
    assert N.MIN_COMPARED == 2              # B2+, beta 15 (was 3)
    assert N.LIMIT_DE == 10.0
    from workflow import misread_settings as MS
    # Knut 6078174421 / 6082015002 / 6085694445
    assert MS.NEIGHBOUR_LIMIT_DEFAULTS == {"estimated": 10.0, "accurate": 5.0,
                                           "verification": 3.0,
                                           "calibration": 10.0}
    assert MS.NEIGHBOUR_RADIUS_DEFAULTS == {"estimated": 15.0,
                                            "accurate": 30.0,
                                            "verification": 30.0,
                                            "calibration": 30.0}


def test_lab_is_the_engines():
    """The same L*a*b* as workflow.measurement_report._engine_lab."""
    from workflow.measurement_report import _engine_lab
    for xyz in ((96.42, 100.0, 82.49), (20.0, 10.0, 5.0), (0.3, 0.2, 0.4)):
        assert engine_lab(xyz) == pytest.approx(_engine_lab(xyz), abs=1e-9)


# ---- synthetic charts ------------------------------------------------------
def _grid(strips=6, per=12, step=4.0, shift=(0.0, 0.0, 0.0)):
    """Patches on a lattice in L*a*b*: strip s, position p. Neighbouring
    lattice points of OTHER strips are within ΔE 15. The 'printer' reads every
    patch off by the same *shift*, as a rough estimate does."""
    rows = []
    for s in range(strips):
        letter = chr(ord("A") + s)
        for p in range(per):
            exp = (40.0 + step * s, -20.0 + step * p, 5.0)
            meas = tuple(e + d for e, d in zip(exp, shift))
            rows.append((f"{letter}{p + 1}", exp, meas, letter))
    return rows


def _check_lab(rows, **kw):
    nc = NeighbourCheck(**kw)
    for loc, exp, meas, strip in rows:
        nc.set_reading_lab(loc, exp, meas, strip)
    nc.evaluate()
    return nc


def test_a_clean_chart_has_no_suspect_even_far_off_its_estimate():
    """Every patch ΔE 30 from its rough estimate, the same way: that is the
    estimate, not a misread."""
    nc = _check_lab(_grid(shift=(-20.0, 15.0, 15.0)))
    assert nc.suspects() == []
    assert nc.checked_count() == len(nc)


def test_a_misread_in_the_middle_of_the_colour_space_is_suspected():
    rows = _grid()
    i = next(k for k, r in enumerate(rows) if r[0] == "C6")
    loc, exp, meas, strip = rows[i]
    rows[i] = (loc, exp, (meas[0] - 20.0, meas[1] + 8.0, meas[2]), strip)
    nc = _check_lab(rows)
    assert nc.suspects() == ["C6"]
    f = nc.finding("C6")
    assert f.suspect and len(f.compared) == 4
    # Knut's step 4: own error minus the median of theirs, over the limit
    assert f.further == pytest.approx(f.own_de - f.median_de)
    assert f.further > N.LIMIT_DE
    # Its neighbours are not dragged in: the median keeps one bad partner out.
    for other in f.compared:
        assert not nc.is_suspect(other)


def test_the_limit_is_strict():
    """Over the neighbour limit, not at it."""
    rows = [("A1", (50, 0, 0), (50, 0, 0), "A"),
            ("B1", (50, 1, 0), (50, 1, 0), "B"),
            ("C1", (50, 2, 0), (50, 2, 0), "C"),
            ("D1", (50, 3, 0), (50, 3, 0), "D"),
            ("E1", (60, 0, 0), (60, 0, 0), "E")]
    nc = _check_lab(rows)
    assert nc.suspects() == []
    # A1 read 12 lower: its own error 12, its neighbours' 0.
    rows[0] = ("A1", (50, 0, 0), (38, 0, 0), "A")
    f = _check_lab(rows).finding("A1")
    assert f.compared[0] == "B1"
    assert f.further == pytest.approx(12.0)
    nc = _check_lab(rows, limit=f.further)
    assert not nc.is_suspect("A1")
    # At one decimal (Knut, #182 6094941512): ON the limit is not over it,
    # 0.1 above it is; a few thousandths either side of the limit read as
    # the limit itself.
    nc = _check_lab(rows, limit=f.further - 0.1)
    assert nc.is_suspect("A1")
    for limit in (f.further - 0.04, f.further + 0.04):
        assert not _check_lab(rows, limit=limit).is_suspect("A1")


@pytest.mark.parametrize("own, suspect", [(3.0, False), (3.04, False),
                                          (3.06, True), (3.1, True),
                                          (2.96, False)])
def test_knuts_b3_on_the_limit_is_not_over_it(own, suspect):
    """Knut, #182 6094941512: B3 turned red at ΔE 3.0 with the neighbour
    limit at 3.0. Compared at one decimal as the card prints it: 3.0 is
    not flagged, 3.1 is. 3.04 prints 3.0 and is not; 3.06 prints 3.1 and
    is."""
    rows = [("A1", (50, 0, 0), (50 - own, 0, 0), "A"),
            ("B1", (50, 1, 0), (50, 1, 0), "B"),
            ("C1", (50, 2, 0), (50, 2, 0), "C"),
            ("D1", (50, 3, 0), (50, 3, 0), "D")]
    nc = _check_lab(rows, limit=3.0)
    f = nc.finding("A1")
    assert f"{f.further:.1f}" == f"{own:.1f}"
    assert nc.is_suspect("A1") is suspect


def test_never_suspected_for_lack_of_comparisons():
    """One comparison patch, however far its reading is: not judged (B2+:
    two are enough, beta 15; it was three)."""
    rows = [("A1", (50, 0, 0), (90, 40, 40), "A"),
            ("B1", (50, 2, 0), (50, 2, 0), "B"),
            ("D1", (80, 60, 0), (80, 60, 0), "D")]      # too far in colour
    nc = _check_lab(rows)
    f = nc.finding("A1")
    assert f.compared == ("B1",)
    assert not f.checked and not f.suspect
    assert nc.suspects() == []


def test_b2_two_comparisons_are_enough():
    """B2+ (Knut #182 6059912998, "Use the suggested B2+ method"): a patch
    with two read neighbours in other strips is judged."""
    rows = [("A1", (50, 0, 0), (90, 40, 40), "A"),
            ("B1", (50, 2, 0), (50, 2, 0), "B"),
            ("C1", (50, 4, 0), (50, 4, 0), "C"),
            ("D1", (80, 60, 0), (80, 60, 0), "D")]
    nc = _check_lab(rows)
    f = nc.finding("A1")
    assert f.compared == ("B1", "C1") and f.checked and f.suspect
    # its two neighbours are not: they are not the ones that are off
    assert nc.suspects() == ["A1"]


def test_b2_plus_a_healthy_patch_beside_faulty_ones_stays_unmarked():
    """The patch must be the one further from its expected colour: a good
    patch whose neighbours were ruined (a nozzle line) does not fit them
    either, and beta 11 turned it red; B2+ does not."""
    rows = [("A1", (50, 0, 0), (50, 0, 0), "A"),         # healthy
            ("B1", (50, 2, 0), (80, 30, 0), "B"),        # ruined
            ("C1", (50, 4, 0), (80, 32, 0), "C"),        # ruined
            ("D1", (50, 6, 0), (80, 34, 0), "D")]        # ruined
    nc = _check_lab(rows)
    f = nc.finding("A1")
    assert f.checked
    assert f.further < 0                               # it is not the one off
    assert not nc.is_suspect("A1")


def test_neighbours_come_from_any_strip_its_own_included():
    """Knut 6078174421: "neighbours should come from any strip" (a
    calibration chart holds its ramps on one strip; patch by patch there is
    no strip). Beta 15 took only other strips."""
    rows = [(f"A{i}", (50, i, 0), (50, i, 0), "A") for i in range(1, 9)]
    rows += [("B1", (50, 0.5, 0), (50, 0.5, 0), "B")]
    nc = _check_lab(rows)
    assert nc.finding("A1").compared == ("B1", "A2", "A3", "A4")
    # a single misread on that strip is caught by its strip neighbours
    rows[3] = ("A4", (50, 4, 0), (70, 4, 0), "A")
    assert _check_lab(rows).suspects() == ["A4"]


def test_beta15s_first_test_is_gone():
    """Readings further apart than the expected colours no longer decide
    anything: a patch far from its neighbours' READINGS but no further from
    its own expected colour than they are is not red (Knut 6085694445: no
    hidden thresholds)."""
    rows = [("A1", (50, 0, 0), (50, 30, 0), "A"),       # error 30
            ("B1", (50, 2, 0), (50, -28, 0), "B"),      # error 30
            ("C1", (50, 4, 0), (80, 4, 0), "C"),        # error 30
            ("D1", (50, 6, 0), (50, 6, -30), "D")]      # error 30
    nc = _check_lab(rows)
    f = nc.finding("A1")
    assert f.checked and f.further == pytest.approx(0.0)
    assert nc.suspects() == []


def test_only_patches_expected_within_the_radius():
    rows = [("A1", (50, 0, 0), (20, 0, 0), "A"),
            ("B1", (50, 15.5, 0), (50, 15.5, 0), "B"),
            ("C1", (50, -15.5, 0), (50, -15.5, 0), "C"),
            ("D1", (50, 0, 16), (50, 0, 16), "D")]
    assert _check_lab(rows).finding("A1").compared == ()
    # the colour-neighbour radius is the user's (30 on most chart types)
    assert _check_lab(rows, radius=30.0).finding("A1").compared == (
        "B1", "C1", "D1")
    nc = NeighbourCheck(radius=15.0)
    for r in rows:
        nc.set_reading_lab(*r)
    nc.evaluate()
    assert nc.finding("A1").compared == ()
    nc.set_radius(30.0)
    nc.evaluate()
    assert nc.finding("A1").compared == ("B1", "C1", "D1")
    assert nc.is_suspect("A1")


def test_at_most_four_the_nearest_first():
    rows = [("A1", (50, 0, 0), (50, 0, 0), "A")]
    rows += [(f"{chr(66 + i)}1", (50, 1.0 + i, 0), (50, 1.0 + i, 0),
              chr(66 + i)) for i in range(7)]
    assert _check_lab(rows).finding("A1").compared == ("B1", "C1", "D1", "E1")


def test_an_unknown_strip_compares_too():
    """Patch by patch, or a reading whose strip is not known: the strip no
    longer decides who compares (beta 17)."""
    rows = [(f"A{i}", (50, i, 0), (50, i, 0), "") for i in range(1, 6)]
    nc = _check_lab(rows)
    assert all(len(nc.finding(r[0]).compared) == 4 for r in rows)


def test_a_reread_that_fits_clears_the_suspect_and_evaluate_says_so():
    rows = _grid()
    good = {r[0]: r for r in rows}
    nc = NeighbourCheck()
    for loc, exp, meas, strip in rows:
        if loc == "D4":
            meas = (meas[0] + 25.0, meas[1], meas[2])
        nc.set_reading_lab(loc, exp, meas, strip)
    changed = nc.evaluate()
    assert list(changed) == ["D4"] and changed["D4"].suspect
    assert nc.evaluate() == {}                      # nothing new read
    loc, exp, meas, strip = good["D4"]
    nc.set_reading_lab(loc, exp, meas, strip)       # read again, fits now
    changed = nc.evaluate()
    assert list(changed) == ["D4"] and not changed["D4"].suspect
    assert nc.suspects() == []


def test_a_reread_with_the_same_reading_stays_suspected():
    """The check judges readings; that it is the same twice is the yellow
    rule's business (workflow/patch_flags.py), not this module's."""
    rows = _grid()
    nc = NeighbourCheck()
    for loc, exp, meas, strip in rows:
        if loc == "D4":
            meas = (meas[0] + 25.0, meas[1], meas[2])
        nc.set_reading_lab(loc, exp, meas, strip)
    nc.evaluate()
    loc, exp, meas, strip = next(r for r in rows if r[0] == "D4")
    nc.set_reading_lab(loc, exp, (meas[0] + 25.5, meas[1], meas[2]), strip)
    assert nc.evaluate() == {}
    assert nc.suspects() == ["D4"]


def test_forget_and_reset():
    rows = _grid()
    nc = NeighbourCheck()
    for loc, exp, meas, strip in rows:
        if loc == "D4":
            meas = (meas[0] + 25.0, meas[1], meas[2])
        nc.set_reading_lab(loc, exp, meas, strip)
    nc.evaluate()
    nc.forget("D4")
    changed = nc.evaluate()
    assert list(changed) == ["D4"] and nc.suspects() == []
    nc.reset()
    assert len(nc) == 0 and nc.evaluate() == {} and nc.suspects() == []


def test_four_thousand_patches_are_judged_in_well_under_a_second():
    """It is judged again after every strip: it must stay cheap."""
    rng = random.Random(4)
    nc = NeighbourCheck()
    for s in range(100):
        letter = f"S{s:03d}"
        for p in range(42):
            exp = (rng.uniform(5, 95), rng.uniform(-80, 80), rng.uniform(-80, 80))
            nc.set_reading_lab(f"{letter}-{p}", exp, exp, letter)
    # CPU TIME, NOT WALL TIME: the gate saturates every core, and a wall clock
    # then measures the scheduler. It failed once at 2.48 s wall in a loaded
    # everyday run and passed alone. Measured 2026-10-05 at load ~90: 0.39 to
    # 0.48 s CPU against 0.72 to 1.07 s wall for this very call, so 2.0 s of
    # CPU still names a judgement that has turned several times dearer, which
    # is what this guards, while a busy machine no longer turns it red.
    # (No threaded BLAS in neighbour_check, so process time is this thread's.)
    t = time.process_time()
    nc.evaluate()
    spent = time.process_time() - t
    assert spent < 2.0, f"judging 4,200 patches took {spent:.2f} s of CPU"
    assert nc.suspects() == []


# ---- Knut's real charts, as ANALYSIS.md section C measured them ------------
#: name: (patches, {neighbour limit: suspects}, share with >= 2 neighbours),
#: Knut's four steps (beta 17), radius 15. Beta 15's B2+ (buffer and
#: "further" above 0, other strips only) gave, at 5 / 8 / 10 / 15:
#: HP 29 / 7 / 3 / 0 at 1.0, run1 5 / 1 / 1 / 0 at 0.853, run4 all 0 at
#: 0.599, Epson 8 / 2 / 2 / 0 at 0.999, Canon 115 / 44 / 18 / 0 at 1.0,
#: scanner chart 9 / 3 / 0 / 0 at 0.711. Without the "buffer" the scanner
#: chart (a print measured through a scanner profile) has 16 at 10.
REAL = {
    # 4.3.4 beta 1 (Knut #182 6094941512): the limit and the radius are
    # compared at one decimal, so a patch ON the limit is no suspect and a
    # neighbour ON the radius is a neighbour. Beta 17 had, at 5 / 8 / 10:
    # hp 59 / 3 / 0, run1 22 / 2 / 0 (coverage 0.858), run4 9 / 1 / 0
    # (0.62), epson 17 / 6 / 2, canon 81 / 22 / 14, scanner 58 / 29 / 16
    # (0.737).
    "hp_laser_1944": (1944, {5: 56, 8: 3, 10: 0, 15: 0}, 1.0),
    "knut_run1_648": (648, {5: 18, 8: 2, 10: 0, 15: 0}, 0.86),
    "knut_run4_324": (324, {5: 9, 8: 1, 10: 0, 15: 0}, 0.623),
    "epson_p300_924": (924, {5: 17, 8: 5, 10: 2, 15: 1}, 1.0),
    "canon_pro300_1168": (1168, {5: 79, 8: 22, 10: 14, 15: 0}, 1.0),
    "knut_scanner_315": (315, {5: 56, 8: 27, 10: 15, 15: 3}, 0.74),
}


@pytest.mark.parametrize("name", sorted(REAL))
def test_real_sheets_give_the_analysis_numbers(name):
    n, counts, coverage = REAL[name]
    patches = sheet(name)
    assert len(patches) == n
    for limit, want in counts.items():
        nc = check_of(patches, limit)
        assert len(nc.suspects()) == want, (name, limit)
    assert nc.checked_count() / n == pytest.approx(coverage, abs=0.001)


def test_the_real_suspects_at_limit_ten():
    """4.3.4 beta 1: 31 of 5,323 patches (0.6 %), 14 on the wide-gamut Canon
    and 15 on the scanner chart (beta 17: 32 and 16, before the comparison
    at one decimal; beta 15's B2+: 24; beta 11: 35)."""
    total = sum(len(check_of(sheet(name)).suspects()) for name in REAL)
    assert total == 31
    assert len(check_of(sheet("canon_pro300_1168")).suspects()) == 14
    assert check_of(sheet("knut_run1_648")).suspects() == []
    assert check_of(sheet("epson_p300_924")).suspects() == ["AK19", "AM5"]


def _strips(patches):
    out = {}
    for i, p in enumerate(patches):
        out.setdefault(strip_of(p[0]), []).append(i)
    def pos(loc):
        digits = "".join(c for c in loc if c.isdigit())
        return int(digits or 0)
    for s in out:
        out[s].sort(key=lambda i: pos(patches[i][0]))
    return [out[s] for s in sorted(out, key=lambda s: (len(s), s))]


def test_read_strip_by_strip_it_ends_where_the_whole_chart_does():
    """Judged again after every strip: a patch is never suspected while it
    lacks comparisons, and the last strip leaves the same suspects as the
    measurement opened from disk."""
    patches = sheet("knut_run1_648")
    nc = NeighbourCheck()
    for idx in _strips(patches):
        for i in idx:
            loc, _rgb, exp, meas = patches[i]
            nc.set_reading(loc, exp, meas, strip_of(loc))
        nc.evaluate()
        for loc in nc.suspects():
            assert nc.finding(loc).checked
    assert nc.suspects() == check_of(patches).suspects()


@pytest.mark.parametrize("seed", range(3))
def test_a_strip_read_out_of_step_is_caught(seed):
    """Every reading of a strip one patch late (the analysis: 100 %)."""
    patches = sheet("hp_laser_1944")
    rng = random.Random(seed)
    strips = [s for s in _strips(patches) if len(s) >= 6]
    st = strips[rng.randrange(len(strips))]
    bad = [list(p) for p in patches]
    white = max(patches, key=lambda p: p[3][1])[3]
    for j, i in enumerate(st):
        bad[i][3] = patches[st[j + 1]][3] if j + 1 < len(st) else white
    clean = set(check_of(patches).suspects())
    found = set(check_of(bad).suspects()) - clean
    assert found & {patches[i][0] for i in st}


def test_most_single_glitches_are_caught():
    """One patch carrying another patch's reading (the analysis: 77 % of
    those that moved it ΔE 6 or more)."""
    patches = sheet("hp_laser_1944")
    rng = random.Random(203)
    caught = events = 0
    for _ in range(40):
        i, j = rng.randrange(len(patches)), rng.randrange(len(patches))
        a, b = engine_lab(patches[i][3]), engine_lab(patches[j][3])
        if sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5 < 6.0:
            continue
        bad = [list(p) for p in patches]
        bad[i][3] = patches[j][3]
        events += 1
        caught += check_of(bad).is_suspect(patches[i][0])
    assert events >= 30
    assert caught / events >= 0.6


def test_judging_only_what_changed_gives_what_judging_all_gives():
    """After a strip only the patches near in colour to it are judged again;
    the findings must be the ones a fresh judgement of everything gives,
    re-reads and forgotten readings included."""
    patches = sheet("canon_pro300_1168")
    rng = random.Random(11)
    nc = NeighbourCheck()
    for n_strip, idx in enumerate(_strips(patches)):
        for i in idx:
            loc, _rgb, exp, meas = patches[i]
            nc.set_reading(loc, exp, meas, strip_of(loc))
        if n_strip % 7 == 3:                     # a re-read, off by a glitch
            loc, _rgb, exp, meas = patches[rng.choice(idx)]
            other = patches[rng.randrange(len(patches))][3]
            nc.set_reading(loc, exp, other, strip_of(loc))
        if n_strip % 11 == 5:
            nc.forget(patches[idx[0]][0])
        nc.evaluate()
        fresh = NeighbourCheck()
        for loc, (e, m, s) in nc._rows.items():
            fresh.set_reading_lab(loc, e, m, s)
        fresh.evaluate()
        assert nc.suspects() == fresh.suspects()
        assert {k: v.compared for k, v in nc._findings.items()} == \
            {k: v.compared for k, v in fresh._findings.items()}


# ---- review of beta 11: kept comparisons, judged again only where needed ---

def _fresh_copy(nc):
    fresh = NeighbourCheck(limit=nc.limit, radius=nc.radius)
    for loc, (e, m, s) in nc._rows.items():
        fresh.set_reading_lab(loc, e, m, s)
    fresh.evaluate()
    return fresh


@pytest.mark.parametrize("seed", range(4))
def test_random_reads_rereads_and_forgets_end_as_a_fresh_judgement(seed):
    """Any order of whole strips, re-reads (another colour), readings
    forgotten and read again, and patches whose strip is unknown: after every
    evaluation every finding is the one judging everything afresh gives,
    comparisons, medians and verdicts."""
    rng = random.Random(seed)
    strips = [f"S{s}" for s in range(12)]
    cube = {f"{s}-{p}": (rng.uniform(30, 60), rng.uniform(-20, 20),
                         rng.uniform(-20, 20))
            for s in strips for p in range(15)}
    nc = NeighbourCheck(limit=4.0)
    for _ in range(60):
        op = rng.random()
        loc = rng.choice(sorted(cube))
        strip = loc.split("-")[0]
        if op < 0.6:
            for loc2 in [x for x in cube if x.startswith(strip + "-")]:
                e2 = cube[loc2]
                m = tuple(v + rng.gauss(0, 3) for v in e2)
                nc.set_reading_lab(loc2, e2, m, strip)
        elif op < 0.8:
            e = cube[loc]
            m = tuple(v + rng.gauss(0, 12) for v in e)
            nc.set_reading_lab(loc, e, m, strip if rng.random() < 0.9 else "")
        else:
            nc.forget(loc)
        nc.evaluate()
        fresh = _fresh_copy(nc)
        assert nc.suspects() == fresh.suspects()
        assert set(nc._findings) == set(fresh._findings)
        for k, f in fresh._findings.items():
            g = nc._findings[k]
            assert g.compared == f.compared, k
            assert g.further == pytest.approx(f.further, abs=1e-9)
            assert g.median_de == pytest.approx(f.median_de, abs=1e-9)


def test_a_strip_searches_all_readings_only_for_its_own_patches(monkeypatch):
    """No square growth (review of beta 11): at the end of a 4,096-patch
    chart a strip of 32 had every patch near it in colour search ALL the
    readings again, 0.1 s a strip in the Measure tab and growing with the
    square of the chart. Now only the strip's own patches search all the
    readings; the others only weigh the arrivals."""
    rng = random.Random(9)
    nc = NeighbourCheck()
    grid = [(lv, a, b) for lv in range(20, 95, 5) for a in range(-60, 61, 8)
            for b in range(-60, 61, 8)][:4096]
    rng.shuffle(grid)
    for i, e in enumerate(grid[:-32]):
        nc.set_reading_lab(f"S{i // 32}-{i % 32}", e, e, f"S{i // 32}")
    nc.evaluate()
    searched = []
    real = NeighbourCheck._find_fresh

    def spy(self, locs, exp, st, known, rows):
        searched.extend(int(r) for r in rows)
        return real(self, locs, exp, st, known, rows)
    monkeypatch.setattr(NeighbourCheck, "_find_fresh", spy)
    for i, e in enumerate(grid[-32:]):
        nc.set_reading_lab(f"LAST-{i}", e, e, "LAST")
    nc.evaluate()
    assert len(searched) == 32
    assert nc.suspects() == _fresh_copy(nc).suspects()
    assert {k: v.compared for k, v in nc._findings.items()} == \
        {k: v.compared for k, v in _fresh_copy(nc)._findings.items()}
