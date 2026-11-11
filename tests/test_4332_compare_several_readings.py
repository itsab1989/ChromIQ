"""4.3.32: Tools > Inspect a measurement compares SEVERAL readings of one chart.

Basti, 2026-11-11: *"the comparison of readings must take several readings,
not only two"*. With one other reading the window stays the two-reading view
of `tests/test_4332_compare_two_readings.py`; with two or more others every
reading is measured against each patch's CENTRE (the per-patch median of L*,
a* and b*), see `workflow/reading_compare.py`.

Pinned here:
* one reading that is off as a whole, among four, is named ("differs
  overall") and the others are not;
* one misread strip in one reading is named, as that reading's strip, and
  that reading stands apart on its patches;
* two readings that share an error are NOT presented as proof: split two
  against two, no reading is named; three readings of which two share an
  error make the good one "stand apart", and the window's words say that
  standing apart is evidence, not proof;
* odd and even counts (3, 4, 5 readings) behave as the module explains;
* a refused reading (another chart) is refused alone and the others are
  compared exactly as without it;
* different measurement conditions or instruments are said, never refused;
* one other reading is the two-reading view, unchanged (also after removing
  readings until one is left);
* nine other readings of 2000 patches stay quick.

Fixtures are made from the suite's own ET-8550 verification reading, with
instrument-like noise and planted errors, never from a tester's file.
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_4332_compare_two_readings import (  # noqa: E402
    _inspector, _noisy, _texts, _write)
from workflow import measurement_messages as M          # noqa: E402
from workflow.reading_compare import (                  # noqa: E402
    MAX_OTHER_READINGS, Reading, compare, compare_several, load_reading)

TOL = 1.0


def _same(rows, fields):
    return rows


def _keyword(path: Path, name: str, value: str) -> Path:
    """*path* with the keyword *name* = *value* in its header."""
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1:1] = [f'KEYWORD "{name}"', f'{name} "{value}"']
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _offset(seed):
    """A reading 6 % brighter in XYZ everywhere: another instrument, another
    condition or another print, as a whole."""
    return _noisy(seed=seed, bad=range(10_000), bad_scale=1.06)


@pytest.fixture
def a(tmp_path):
    return _write(tmp_path / "a.ti3", _same)


def _readings(tmp_path, edits):
    return [load_reading(_write(tmp_path / f"r{k}.ti3", e))
            for k, e in enumerate(edits)]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---- the model -------------------------------------------------------------

def test_one_outlier_among_four_is_named(a, tmp_path):
    others = _readings(tmp_path, [_noisy(seed=1), _offset(2), _noisy(seed=3)])
    c, refused = compare_several(load_reading(a), others)
    assert not refused and c.r == 4 and c.n == 616
    kinds = [c.verdict(k, TOL).kind for k in range(4)]
    assert kinds[2] == "overall", kinds
    assert all(k in ("agrees", "patches") for i, k in enumerate(kinds)
               if i != 2)
    # the outlier is far from the centre, the others are not
    st = [c.stats(k) for k in range(4)]
    assert st[2].median > 1.0
    assert max(st[k].median for k in (0, 1, 3)) < 0.3
    # where the spread is above the tolerance, reading 3 (index 2) stands
    # apart on almost every patch
    apart = c.stands_apart(TOL)
    hit = apart[c.spread > TOL]
    assert len(hit) > 300 and np.mean(hit == 2) > 0.95


def test_one_misread_strip_in_one_reading_is_named(a, tmp_path):
    others = _readings(tmp_path, [_noisy(seed=1), _noisy(seed=2, strip="H"),
                                  _noisy(seed=3)])
    c, _ = compare_several(load_reading(a), others)
    v = c.verdict(2, TOL)
    assert v.kind == "strip" and v.strips == ["H"]
    for k in (0, 1, 3):
        assert c.verdict(k, TOL).kind in ("agrees", "patches")
        assert "H" not in c.verdict(k, TOL).strips
    on_h = np.array([s == "H" for s in c.strips_of])
    apart = c.stands_apart(TOL)
    assert np.all(apart[on_h & (c.spread > TOL)] == 2)
    row = next(s for s in c.strips(TOL) if s.label == "H")
    assert row.off(2) and not any(row.off(k) for k in (0, 1, 3))


def test_two_against_two_names_nobody(a, tmp_path):
    """Two readings share an error (strip H slipped the same way twice):
    split two against two, the centre lies between, and no reading is said
    to stand apart on strip H."""
    others = _readings(tmp_path, [_noisy(seed=1, strip="H"),
                                  _noisy(seed=2, strip="H"), _noisy(seed=3)])
    c, _ = compare_several(load_reading(a), others)
    on_h = np.array([s == "H" for s in c.strips_of])
    apart = c.stands_apart(TOL)
    assert np.all(apart[on_h & (c.spread > TOL)] == -1)


def test_three_readings_with_a_shared_error_are_not_proof(qapp, a, tmp_path):
    """Three readings, two of which share an error: the GOOD reading is the
    one standing apart. The tool cannot know better, so its words must not
    claim more: "stands apart", never "is wrong", and the guidance says that
    two readings can share an error."""
    b = _write(tmp_path / "b.ti3", _noisy(seed=1, strip="H"))
    d = _write(tmp_path / "d.ti3", _noisy(seed=2, strip="H"))
    c, _ = compare_several(load_reading(a), [load_reading(b),
                                             load_reading(d)])
    assert c.verdict(0, TOL).strips == ["H"]          # the good one
    dlg = _inspector(qapp, a)
    dlg.add_readings([b, d])
    t = _texts(dlg)
    assert "Reading 1 stands apart" in t
    assert "it is not proof" in t and "Two readings can share an error" in t
    for word in ("is wrong", "is right", "correct reading"):
        assert word not in t
    dlg.deleteLater()


@pytest.mark.parametrize("count", [3, 4, 5])
def test_odd_and_even_counts(a, tmp_path, count):
    """One reading off by a known amount: with three readings the centre
    is the middle value per coordinate, with an even number the mean of the
    two middle ones; either way it stays with the majority, so the outlier
    shows (nearly) its whole difference and the others very little."""
    edits = [_noisy(seed=s) for s in range(1, count - 1)] + [_offset(99)]
    c, _ = compare_several(load_reading(a), _readings(tmp_path, edits))
    k = count - 1
    whole = compare(load_reading(a), c.readings[k]).median
    assert c.stats(k).median == pytest.approx(whole, rel=0.25)
    assert max(c.stats(i).median for i in range(k)) < 0.3 * whole
    assert c.verdict(k, TOL).kind == "overall"
    # the centre really is the per-patch median of L*, a*, b*
    assert np.allclose(c.centre, np.median(c.lab, axis=0))
    # the spread is the largest difference between two readings
    i = int(np.argmax(c.spread))
    pairs = [compare(c.readings[x], c.readings[y]) for x in range(count)
             for y in range(x + 1, count)]
    by = [{p.sid: p.de for p in q.patches}[c.sids[i]] for q in pairs]
    assert c.spread[i] == pytest.approx(max(by), abs=1e-6)


def test_the_repeatability_is_the_spread(a, tmp_path):
    c, _ = compare_several(load_reading(a), _readings(
        tmp_path, [_noisy(seed=s) for s in (1, 2, 3)]))
    med, p95 = c.repeatability()
    assert med == pytest.approx(np.median(c.spread))
    assert p95 == pytest.approx(np.percentile(c.spread, 95))
    assert 0.02 < med < 0.6 and med <= p95


def test_a_refused_reading_leaves_the_others_alone(a, tmp_path):
    def other(rows, fields):
        ri = fields.index("RGB_R")
        for r in rows:
            r[ri] = f"{min(100.0, float(r[ri]) + 7.0):.5f}"
        return rows
    good = _readings(tmp_path, [_noisy(seed=1), _offset(2), _noisy(seed=3)])
    bad = load_reading(_write(tmp_path / "other.ti3", other))
    ra = load_reading(a)
    with_bad, refused = compare_several(ra, [good[0], bad, good[1], good[2]])
    without, _ = compare_several(ra, good)
    assert [r is bad for r, _e in refused] == [True]
    assert refused[0][1].message is M.M_READINGS_NOT_SAME_CHART
    assert with_bad.r == 4
    assert np.array_equal(with_bad.dev, without.dev)


def test_mixed_conditions_and_instruments_are_found(a, tmp_path):
    b = _keyword(_write(tmp_path / "b.ti3", _noisy(seed=1)),
                 "MEASUREMENT_CONDITION", "M2")
    d = _keyword(_write(tmp_path / "d.ti3", _noisy(seed=2)),
                 "MEASUREMENT_CONDITION", "M0")
    e = _keyword(_write(tmp_path / "e.ti3", _noisy(seed=3)),
                 "CHROMIQ_I1P_INSTRUMENT", "i1Pro 3")
    c, _ = compare_several(load_reading(a), [load_reading(p)
                                             for p in (b, d, e)])
    conds, insts = c.mixed()
    assert conds == {"M2": [1], "M0": [2]}
    assert len(insts) == 2 and [3] in insts.values()


def test_one_instrument_named_two_ways_is_one_instrument():
    from workflow.reading_compare import mixed_ways

    def r(name):
        return Reading(Path("x"), [], [], np.empty((0, 3)), np.empty((0, 3)),
                       instrument=name)
    assert mixed_ways([r("X-Rite i1 Pro 2"), r("i1Pro 2")]) == ({}, {})


# ---- the window ------------------------------------------------------------

def test_the_window_names_the_outlier_and_the_tolerance_moves_it(qapp, a,
                                                                 tmp_path):
    paths = [_write(tmp_path / f"r{k}.ti3", e) for k, e in
             enumerate([_noisy(seed=1), _offset(2), _noisy(seed=3)])]
    before = [_sha(p) for p in [a] + paths]
    dlg = _inspector(qapp, a)
    dlg.add_readings(paths)
    t = _texts(dlg)
    assert "Other readings of this chart" in t
    assert "Another reading of this chart" not in t
    for k in (1, 2, 3, 4):
        assert f"Reading {k}" in t
    assert "Differs from the others overall" in t
    assert "Repeatability" in t and "Centre" in t
    assert "from the centre, by reading: 1: " in t
    assert "Reading 3 stands apart" in t
    assert dlg._others_list.count() == 3
    # a tolerance far above the outlier's distance: everybody agrees
    dlg._tol_combo.setCurrentIndex(dlg._tol_combo.count() - 1)   # Custom
    dlg._tol_spin.setValue(9.0)
    qapp.processEvents()
    t2 = _texts(dlg)
    assert "Differs from the others overall" not in t2
    assert t2.count("Agrees with the others.") == 4
    assert [_sha(p) for p in [a] + paths] == before, "a file was written to"
    dlg.deleteLater()


def test_the_window_refuses_one_and_compares_the_rest(qapp, a, tmp_path):
    good = [_write(tmp_path / f"g{k}.ti3", _noisy(seed=k)) for k in (1, 2)]
    bad = _write(tmp_path / "other.ti3", lambda r, f: r[:-1])
    dlg = _inspector(qapp, a)
    dlg.add_readings([good[0], bad, good[1]])
    t = _texts(dlg)
    title, _ = M.M_READINGS_NOT_SAME_CHART.render(file="x", reason="x")
    assert title in t and "Other readings of this chart" in t
    assert "3 in all: this measurement and 2 other readings" in t
    assert "not compared" in dlg._others_list.item(1).text()
    assert "not compared" not in dlg._others_list.item(0).text()
    # removing the refused one changes nothing else
    numbers = [ln for ln in t.splitlines() if "from the centre" in ln]
    dlg.remove_readings([1])
    t2 = _texts(dlg)
    assert title not in t2
    assert [ln for ln in t2.splitlines() if "from the centre" in ln] \
        == numbers
    dlg.deleteLater()


def test_one_other_reading_is_the_two_reading_view(qapp, a, tmp_path):
    """The same text, row for row, whether the one other reading was loaded
    alone or is what is left after removing others."""
    b = _write(tmp_path / "b.ti3", _noisy(bad=(10, 200)))
    d = _write(tmp_path / "d.ti3", _offset(4))
    alone = _inspector(qapp, a)
    alone.load_second_reading(b)
    t_alone = _texts(alone)
    assert "Another reading of this chart" in t_alone
    assert "Second reading" in t_alone and "second reading: L*" in t_alone
    assert "Centre" not in t_alone and "Reading 2" not in t_alone
    left = _inspector(qapp, a)
    left.add_readings([d, b])
    assert "Other readings of this chart" in _texts(left)
    left.remove_readings([0])
    assert _texts(left) == t_alone
    assert left._report == alone._report
    alone.deleteLater()
    left.deleteLater()


def test_mixed_conditions_are_said_in_the_window(qapp, a, tmp_path):
    b = _keyword(_write(tmp_path / "b.ti3", _noisy(seed=1)),
                 "MEASUREMENT_CONDITION", "M2")
    d = _keyword(_write(tmp_path / "d.ti3", _noisy(seed=2)),
                 "MEASUREMENT_CONDITION", "M0")
    dlg = _inspector(qapp, a)
    dlg.add_readings([b, d])
    t = _texts(dlg)
    assert "Measured differently" in t
    assert "not how repeatable your readings are" in t
    assert "(reading 2)" in t and "(reading 3)" in t
    assert "Reading 3" in t           # compared all the same
    dlg.deleteLater()


def test_the_saved_inspection_carries_every_patch_above(qapp, a, tmp_path):
    paths = [_write(tmp_path / f"r{k}.ti3", e) for k, e in
             enumerate([_noisy(seed=1), _noisy(seed=2, strip="H"),
                        _noisy(seed=3)])]
    dlg = _inspector(qapp, a)
    dlg.add_readings(paths)
    text = "\n".join(dlg._report)
    c = dlg._several
    above = c.spread_above(dlg._tolerance)
    assert len(above) > 10           # more than the window lists
    assert "All patches above the tolerance" in text
    tail = text.split("All patches above the tolerance")[1]
    for i in above:
        assert f"Patch {c.sids[int(i)]}: " in tail
    assert tail.count("from the centre, by reading: 1: ") == len(above)
    assert "Reading 3: nearly the whole strip is off" in text
    dlg.deleteLater()


def test_more_than_the_limit_is_not_added_and_said(qapp, a, tmp_path):
    paths = [_write(tmp_path / f"r{k}.ti3", _noisy(seed=k))
             for k in range(MAX_OTHER_READINGS + 2)]
    dlg = _inspector(qapp, a)
    dlg.add_readings(paths[:3])
    dlg.add_readings(paths[:1])                   # already there: once
    assert dlg._others_list.count() == 3
    dlg.add_readings(paths)
    assert dlg._others_list.count() == MAX_OTHER_READINGS
    assert dlg._banner.isVisibleTo(dlg)
    assert "2 of the files you chose were not added" in dlg._banner.text()
    dlg._on_second_clear()
    assert dlg._others_list.count() == 0 and not dlg._tol_box.isVisibleTo(dlg)
    assert "Other readings of this chart" not in _texts(dlg)
    dlg.deleteLater()


# ---- quick enough ----------------------------------------------------------

def _big(tmp_path, n=2000, readings=10, seed=5):
    """*readings* .ti3 files of *n* patches: unique device values, colours
    spread over the gamut, instrument-like noise and one planted strip."""
    rng = np.random.default_rng(seed)
    dev = np.unique(rng.integers(0, 101, size=(n * 2, 3)), axis=0)
    dev = dev[rng.permutation(len(dev))[:n]].astype(float)
    xyz = 2 + 0.9 * dev @ np.array([[0.41, 0.21, 0.02], [0.36, 0.72, 0.12],
                                    [0.18, 0.07, 0.95]])
    out = []
    for k in range(readings):
        x = xyz * (1 + rng.normal(0, 0.003, size=(n, 1)))
        if k == 3:
            x[:40] *= 1.15
        rows = [f'{i + 1} "A{i + 1}" {d[0]:.4f} {d[1]:.4f} {d[2]:.4f} '
                f"{v[0]:.5f} {v[1]:.5f} {v[2]:.5f}"
                for i, (d, v) in enumerate(zip(dev, x))]
        p = tmp_path / f"big{k}.ti3"
        p.write_text("\n".join([
            "CTI3", 'DESCRIPTOR "test"', 'DEVICE_CLASS "OUTPUT"',
            'COLOR_REP "iRGB_XYZ"', "NUMBER_OF_FIELDS 8", "BEGIN_DATA_FORMAT",
            "SAMPLE_ID SAMPLE_LOC RGB_R RGB_G RGB_B XYZ_X XYZ_Y XYZ_Z",
            "END_DATA_FORMAT", f"NUMBER_OF_SETS {n}", "BEGIN_DATA", *rows,
            "END_DATA", ""]), encoding="utf-8")
        out.append(p)
    return out


def test_nine_others_of_2000_patches_are_quick(qapp, tmp_path):
    paths = _big(tmp_path)
    rs = [load_reading(p) for p in paths]
    t0 = time.perf_counter()
    c, refused = compare_several(rs[0], rs[1:])
    model = time.perf_counter() - t0
    assert not refused and c.r == 10 and c.n == 2000
    c.stands_apart(1.0), c.strips(1.0), [c.verdict(k, 1.0) for k in range(10)]
    assert model < 2.0, f"the comparison took {model:.2f} s"
    # the window: adding all nine, then a change of tolerance
    dlg = _inspector(qapp, paths[0])
    t0 = time.perf_counter()
    dlg.add_readings(paths[1:])
    qapp.processEvents()
    first = time.perf_counter() - t0
    assert dlg._several is not None and dlg._several.r == 10
    t0 = time.perf_counter()
    dlg._tol_combo.setCurrentIndex(0)
    qapp.processEvents()
    again = time.perf_counter() - t0
    # measured on the M-series host: about 0.4 s and 0.1 s; the bounds are
    # for a loaded gate
    assert first < 8.0, f"adding nine readings took {first:.2f} s"
    assert again < 3.0, f"a change of tolerance took {again:.2f} s"
    assert "Reading 4" in _texts(dlg)
    dlg.deleteLater()


# ---- the scroll fade takes the window's appearance ------------------------

@pytest.mark.parametrize("mode,colour", [("light", "#eeece8"),
                                         ("dark", "#181818")])
def test_the_details_fade_follows_the_appearance(qapp, mode, colour):
    """Basti, 2026-11-11, watching the window on screen: "it is a black
    gradient even though the app is in light mode". The details' scroll fade
    started as "dark" and nobody told it otherwise: MainWindow's appearance
    broadcast only reaches widgets that exist when it runs, and this window
    is built later, from the Tools menu. Measured in the real app (main.py)
    as well as in a driver; v4.3.30 had it too."""
    from tests.test_profile_tools import _runner, _Settings
    from ui.dialogs.ti3_info_dialog import Ti3InfoDialog
    s = _Settings()
    s.set("appearance", mode)
    dlg = Ti3InfoDialog(_runner(), s)
    assert dlg._scroll._top_fade._color.name() == colour
    assert dlg._scroll._bot_fade._color.name() == colour
    dlg.deleteLater()


def test_the_list_shows_four_whole_lines_whatever_the_count(qapp, a,
                                                            tmp_path):
    """No jumping window as readings are added, and no half-cut fifth line
    (measured on screen in the dark appearance before the refit)."""
    paths = [_write(tmp_path / f"r{k}.ti3", _noisy(seed=k)) for k in range(9)]
    dlg = _inspector(qapp, a)
    dlg.show()
    heights = []
    for n in (1, 4, 9):
        dlg.add_readings(paths[:n])
        qapp.processEvents()
        lw = dlg._others_list
        rh = lw.visualItemRect(lw.item(0)).height()
        assert lw.viewport().height() == 4 * rh, (n, rh)
        heights.append(lw.height())
    assert len(set(heights)) == 1
    dlg.close()
    dlg.deleteLater()


def test_a_condition_the_files_do_not_name_is_said(qapp, a, tmp_path):
    """Review pass 1: a .ti3 that names no measurement condition cannot be
    checked, and M0 against M2 differs by more than scatter; the window
    says so plainly, in both views."""
    b = _write(tmp_path / "b.ti3", _noisy(seed=1))
    dlg = _inspector(qapp, a)
    dlg.load_second_reading(b)
    t = _texts(dlg)
    assert "not named in a.ti3, b.ti3" in t and "M0, M1 or M2" in t
    d = _keyword(_write(tmp_path / "d.ti3", _noisy(seed=2)),
                 "MEASUREMENT_CONDITION", "M0")
    dlg.add_readings([d])
    t = _texts(dlg)
    assert "not named in a.ti3, b.ti3." in t and "d.ti3." not in \
        t.split("not named in")[1].split("ChromIQ")[0]
    dlg.deleteLater()
