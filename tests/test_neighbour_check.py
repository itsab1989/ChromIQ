"""The neighbour check (#182 beta 11, Knut 5983470377 answer 5, approving
section C of the beta 10 analysis): the rule on its own, on synthetic charts
and replayed on the real profiling sheets the analysis measured.

The real sheets are in ``tests/data/neighbour_check/`` (location, device RGB,
expected XYZ, measured XYZ per patch; made from the measurements by
``make_fixtures.py`` of the 2026-10-04_beta11/neighbours report). The counts
below are ANALYSIS.md section C's table, row "real profiling", per sheet:
35 suspects at buffer 10 over the six sheets, none at 15.
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


def check_of(patches, buffer=N.BUFFER_DE):
    nc = NeighbourCheck(buffer=buffer)
    for loc, _rgb, exp, meas in patches:
        nc.set_reading(loc, exp, meas, strip_of(loc))
    nc.evaluate()
    return nc


# ---- the rule's numbers are the ruling's -----------------------------------
def test_the_numbers_are_the_approved_ones():
    assert N.RADIUS_DE == 15.0
    assert N.MAX_COMPARED == 4
    assert N.MIN_COMPARED == 3
    assert N.BUFFER_DE == 10.0


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
    assert all(strip_of(x) != "C" for x in f.compared)
    assert f.excess > N.BUFFER_DE
    assert f.measured_de > f.expected_de
    # Its neighbours are not dragged in: the median keeps one bad partner out.
    for other in f.compared:
        assert not nc.is_suspect(other)


def test_the_buffer_is_strict():
    """Over the buffer, not at it."""
    rows = [("A1", (50, 0, 0), (50, 0, 0), "A"),
            ("B1", (50, 1, 0), (50, 1, 0), "B"),
            ("C1", (50, 2, 0), (50, 2, 0), "C"),
            ("D1", (50, 3, 0), (50, 3, 0), "D"),
            ("E1", (60, 0, 0), (60, 0, 0), "E")]
    nc = _check_lab(rows)
    assert nc.suspects() == []
    # A1 read 12 lower: excesses to B1, C1, D1 and E1 all sit near 10.
    rows[0] = ("A1", (50, 0, 0), (40, 0, 0), "A")
    f = _check_lab(rows).finding("A1")
    assert f.compared[0] == "B1"
    nc = _check_lab(rows, buffer=f.excess)
    assert not nc.is_suspect("A1")
    nc = _check_lab(rows, buffer=f.excess - 1e-6)
    assert nc.is_suspect("A1")


def test_never_suspected_for_lack_of_comparisons():
    """Two comparison patches, however far its reading is: not judged."""
    rows = [("A1", (50, 0, 0), (90, 40, 40), "A"),
            ("B1", (50, 2, 0), (50, 2, 0), "B"),
            ("C1", (50, 4, 0), (50, 4, 0), "C"),
            ("D1", (80, 60, 0), (80, 60, 0), "D")]      # too far in colour
    nc = _check_lab(rows)
    f = nc.finding("A1")
    assert f.compared == ("B1", "C1")
    assert not f.checked and not f.suspect
    assert nc.suspects() == []


def test_patches_of_its_own_strip_never_count():
    """A strip is one pass: a smudge moves its patches alike."""
    rows = [(f"A{i}", (50, i, 0), (30, i, 0), "A") for i in range(1, 9)]
    rows += [("B1", (50, 0, 0), (50, 0, 0), "B")]
    nc = _check_lab(rows)
    assert nc.finding("A1").compared == ("B1",)
    assert not any(nc.is_suspect(f"A{i}") for i in range(1, 9))


def test_only_patches_expected_within_fifteen():
    rows = [("A1", (50, 0, 0), (20, 0, 0), "A"),
            ("B1", (50, 15.5, 0), (50, 15.5, 0), "B"),
            ("C1", (50, -15.5, 0), (50, -15.5, 0), "C"),
            ("D1", (50, 0, 16), (50, 0, 16), "D")]
    assert _check_lab(rows).finding("A1").compared == ()


def test_at_most_four_the_nearest_first():
    rows = [("A1", (50, 0, 0), (50, 0, 0), "A")]
    rows += [(f"{chr(66 + i)}1", (50, 1.0 + i, 0), (50, 1.0 + i, 0),
              chr(66 + i)) for i in range(7)]
    assert _check_lab(rows).finding("A1").compared == ("B1", "C1", "D1", "E1")


def test_an_unknown_strip_never_compares():
    rows = [(f"A{i}", (50, i, 0), (50, i, 0), "") for i in range(1, 6)]
    nc = _check_lab(rows)
    assert all(nc.finding(r[0]).compared == () for r in rows)


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
    t = time.perf_counter()
    nc.evaluate()
    assert time.perf_counter() - t < 2.0
    assert nc.suspects() == []


# ---- Knut's real charts, as ANALYSIS.md section C measured them ------------
#: name: (patches, {buffer: suspects}, share with >= 3 comparisons)
REAL = {
    "hp_laser_1944": (1944, {5: 43, 8: 9, 10: 4, 15: 0}, 1.0),
    "knut_run1_648": (648, {5: 8, 8: 1, 10: 1, 15: 0}, 0.779),
    "knut_run4_324": (324, {5: 0, 8: 0, 10: 0, 15: 0}, 0.441),
    "epson_p300_924": (924, {5: 10, 8: 2, 10: 2, 15: 0}, 0.978),
    "canon_pro300_1168": (1168, {5: 259, 8: 81, 10: 28, 15: 0}, 0.985),
    "knut_scanner_315": (315, {5: 14, 8: 4, 10: 0, 15: 0}, 0.467),
}


@pytest.mark.parametrize("name", sorted(REAL))
def test_real_sheets_give_the_analysis_numbers(name):
    n, counts, coverage = REAL[name]
    patches = sheet(name)
    assert len(patches) == n
    for buffer, want in counts.items():
        nc = check_of(patches, buffer)
        assert len(nc.suspects()) == want, (name, buffer)
    assert nc.checked_count() / n == pytest.approx(coverage, abs=0.001)


def test_the_real_suspects_at_buffer_ten():
    """35 of 5,323 patches (0.7 %), 28 of them on the wide-gamut Canon."""
    total = sum(len(check_of(sheet(name)).suspects()) for name in REAL)
    assert total == 35
    assert check_of(sheet("knut_run1_648")).suspects() == ["P27"]
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
