"""4.3.32 review, pass 3: the several-readings view says what it says in
the fewest, plainest words, one way.

* THE MEASUREMENT CONDITION ROW names readings by their NUMBER, as the rest
  of the section does. With ten readings that named no condition it listed
  ten file names, a ten-line block (on screen, de-light, 2026-11-11). Now:
  "Readings 1, 3 and 4 do not say ...", "Reading 2 ...", "None of the
  readings ...", and in the two-reading view "This measurement", "The second
  reading", "Neither of the two readings".
* ONE DATE FORMAT. "Measured on" showed chartread's raw "Wed Nov 11 09:30:00
  2026" while the reading rows showed 2026-11-11. Every date the window
  reads is now `2026-11-11 09:30` (or the day alone, or the file's own text
  when it does not read as a date).
* GROUPS. Two readings against two each "differed from the others
  overall ... usually taken differently", which reads as if all four were
  wrong. When the readings split cleanly into groups that agree inside, the
  window says so and does not say which group is right; a single outlier and
  a chain are judged reading by reading as before.
* THE LIST keeps the distinguishing end of a file name readable at the
  window's minimum width.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.test_4332_compare_two_readings import (  # noqa: E402
    _inspector, _noisy, _texts, _write)
from tests.test_4332_compare_several_readings import _keyword  # noqa: E402
from workflow.reading_compare import (                          # noqa: E402
    Reading, compare_several, display_date, load_reading)

TOL = 1.0
N = 60
_rng = np.random.default_rng(11)
BASE = np.c_[_rng.uniform(20, 90, N), _rng.uniform(-50, 50, N),
             _rng.uniform(-50, 50, N)]
DEV = _rng.uniform(0, 100, (N, 3))


def _rd(name: str, shift_l: float, seed: int) -> Reading:
    lab = BASE + np.random.default_rng(seed).normal(0, 0.1, BASE.shape) \
        + np.array([shift_l, 0.0, 0.0])
    return Reading(Path(name), [str(i + 1) for i in range(N)], [""] * N,
                   DEV.copy(), lab)


def _several(shifts):
    rs = [_rd(f"r{k}.ti3", s, k) for k, s in enumerate(shifts)]
    c, refused = compare_several(rs[0], rs[1:])
    assert not refused
    return c


# ---- 3. groups: the rule ----------------------------------------------------

@pytest.mark.parametrize("shifts,groups", [
    ((0, 0, 3, 3), [[0, 1], [2, 3]]),                       # 2 + 2
    ((0, 3, 0, 3), [[0, 2], [1, 3]]),                       # 2 + 2, mixed order
    ((0, 0, 0, 3, 3), [[0, 1, 2], [3, 4]]),                 # 3 + 2
    ((0, 0, 3, 3, 7), [[0, 1], [2, 3], [4]]),               # 2 + 2 + 1
    ((0, 0, 4, 4, 8, 8), [[0, 1], [2, 3], [4, 5]]),         # 2 + 2 + 2
])
def test_a_clean_split_is_named(shifts, groups):
    assert _several(shifts).groups(TOL) == groups


@pytest.mark.parametrize("shifts", [
    (0, 0, 0, 3),            # one outlier among four: "stands apart" instead
    (0, 0, 3),               # one outlier among three
    (0, 0.9, 1.8),           # a chain: 1~2, 2~3, but not 1~3
    (0, 0.9, 1.8, 2.7),      # a longer chain
    (0, 0, 0, 0),            # everybody agrees
    (0, 3, 6, 9),            # everybody disagrees: no group of two
])
def test_no_groups_are_named_without_a_clean_split(shifts):
    assert _several(shifts).groups(TOL) == []


def test_the_typical_difference_is_the_median_over_patches():
    c = _several((0, 0, 3, 3))
    t = c.typical()
    assert t.shape == (4, 4) and np.allclose(t, t.T)
    assert np.allclose(t[0, 1], np.median(c.pair[0, 1]))
    assert t[0, 1] < TOL < t[0, 2]


# ---- 3. groups: the words ---------------------------------------------------

def _dialog_with(qapp, tmp_path, scales):
    """The measurement and further readings, each XYZ * scale (1.0 = as
    the measurement)."""
    a = _write(tmp_path / "a.ti3", _noisy(seed=0, bad=range(10_000),
                                          bad_scale=scales[0]))
    paths = [_write(tmp_path / f"r{k}.ti3",
                    _noisy(seed=k, bad=range(10_000), bad_scale=s))
             for k, s in enumerate(scales[1:], start=1)]
    dlg = _inspector(qapp, a)
    dlg.add_readings(paths)
    return dlg


def test_two_against_two_is_said_as_two_groups(qapp, tmp_path):
    dlg = _dialog_with(qapp, tmp_path, (1.0, 1.0, 1.08, 1.08))
    t = _texts(dlg)
    assert ("The readings fall into two groups. The readings in each group "
            "agree with each other, but not with those of the other group: "
            "readings 1 and 2; readings 3 and 4.") in t
    assert "ChromIQ cannot tell which group is right." in t
    assert "Differs from the others overall" not in t
    assert "Agrees with reading 2, but not with the readings outside its " \
        "group" in t
    assert "Agrees with reading 3, but not" in t
    # no group is called right or wrong
    for word in ("is right:", "is wrong", "group 1 is", "correct group"):
        assert word not in t
    dlg.deleteLater()


def test_a_wider_split_names_no_slipped_strips(qapp, tmp_path):
    """With 10 % between the groups the centre between them puts some
    strips of one group just above the tolerance: that is the gap between
    the groups, not a slipped strip, and it is not called one."""
    dlg = _dialog_with(qapp, tmp_path, (1.0, 1.0, 1.10, 1.10))
    c = dlg._several
    assert c.groups(dlg._tolerance) == [[0, 1], [2, 3]]
    t = _texts(dlg)
    assert "readings 1 and 2; readings 3 and 4." in t
    assert "Read this strip again" not in t
    assert "Differs from the others" not in t
    dlg.deleteLater()


def test_two_plus_two_plus_one_names_the_reading_on_its_own(qapp, tmp_path):
    dlg = _dialog_with(qapp, tmp_path, (1.0, 1.0, 1.08, 1.08, 1.2))
    t = _texts(dlg)
    assert "readings 1 and 2; readings 3 and 4." in t
    assert "Reading 5 agrees with none of the groups." in t
    # reading 5 is in no group, so it keeps the reading-by-reading verdict
    assert t.count("Differs from the others overall") == 1
    dlg.deleteLater()


def test_a_single_outlier_keeps_stands_apart(qapp, tmp_path):
    dlg = _dialog_with(qapp, tmp_path, (1.0, 1.0, 1.0, 1.08))
    t = _texts(dlg)
    assert "fall into" not in t and "Groups" not in t
    assert "Reading 4 stands apart" in t
    assert "Differs from the others overall" in t
    dlg.deleteLater()


def test_three_plus_two_is_said_as_two_groups(qapp, tmp_path):
    dlg = _dialog_with(qapp, tmp_path, (1.0, 1.0, 1.0, 1.08, 1.08))
    t = _texts(dlg)
    assert "readings 1, 2 and 3; readings 4 and 5." in t
    assert "Agrees with reading 5, but not" in t
    assert "Agrees with reading 4, but not" in t
    dlg.deleteLater()


# ---- 1. the measurement condition row, by number ----------------------------

def _cond_line(t: str) -> str:
    return t.split("Measurement condition\n", 1)[1].split("\n", 1)[0]


def test_unnamed_conditions_are_counted_by_number(qapp, tmp_path):
    a = _keyword(_write(tmp_path / "a.ti3", _noisy(seed=0)),
                 "MEASUREMENT_CONDITION", "M0")
    named = [_keyword(_write(tmp_path / f"n{k}.ti3", _noisy(seed=k)),
                      "MEASUREMENT_CONDITION", "M0") for k in (1, 2)]
    unnamed = [_write(tmp_path / f"long-file-name-{k}.ti3", _noisy(seed=k))
               for k in (3, 4, 5)]
    dlg = _inspector(qapp, a)
    # readings 1 (a, named), 2 (unnamed), 3 (named), 4, 5 (unnamed)
    dlg.add_readings([unnamed[0], named[0], unnamed[1], unnamed[2]])
    t = _texts(dlg)
    assert ("Readings 2, 4 and 5 do not say under which measurement "
            "condition they were taken.") in t
    assert "long-file-name" not in _cond_line(t)
    assert "M0, M1 or M2" in t
    dlg.remove_readings([2, 3])                   # one unnamed left
    t = _texts(dlg)
    assert ("Reading 2 does not say under which measurement condition it "
            "was taken.") in t
    dlg.add_readings([named[1]])
    dlg.remove_readings([0])                      # all named
    assert "do not say under which" not in _texts(dlg)
    assert "does not say under which" not in _texts(dlg)
    dlg.deleteLater()


def test_ten_readings_without_conditions_make_one_short_line(qapp, tmp_path):
    a = _write(tmp_path / "a.ti3", _noisy(seed=0))
    paths = [_write(tmp_path / f"a-rather-long-reading-name-{k}.ti3",
                    _noisy(seed=k)) for k in range(1, 10)]
    dlg = _inspector(qapp, a)
    dlg.add_readings(paths)
    t = _texts(dlg)
    assert ("None of the readings says under which measurement condition "
            "it was taken.") in t
    assert ".ti3" not in t.split("Measurement condition\n", 1)[1].split(
        "Paired by", 1)[0]
    dlg.deleteLater()


@pytest.mark.parametrize("which,words", [
    ("a", "This measurement does not say under which measurement condition "
          "it was taken."),
    ("b", "The second reading does not say under which measurement "
          "condition it was taken."),
])
def test_the_two_reading_view_says_which_one(qapp, tmp_path, which, words):
    a = _write(tmp_path / "a.ti3", _noisy(seed=0))
    b = _write(tmp_path / "b.ti3", _noisy(seed=1))
    _keyword(b if which == "a" else a, "MEASUREMENT_CONDITION", "M0")
    dlg = _inspector(qapp, a)
    dlg.load_second_reading(b)
    assert words in _texts(dlg)
    dlg.deleteLater()


def test_the_condition_lists_follow_the_language(qapp, tmp_path):
    from core import i18n
    a = _write(tmp_path / "a.ti3", _noisy(seed=0))
    paths = [_write(tmp_path / f"r{k}.ti3", _noisy(seed=k)) for k in (1, 2)]
    named = _keyword(_write(tmp_path / "n.ti3", _noisy(seed=3)),
                     "MEASUREMENT_CONDITION", "M0")
    try:
        i18n.set_language("de")
        dlg = _inspector(qapp, a)
        dlg.add_readings(paths + [named])
        t = _texts(dlg)
        assert " 1, 2 und 3 " in t, t
        dlg.deleteLater()
    finally:
        i18n.set_language("en")


# ---- 2. one date format -----------------------------------------------------

@pytest.mark.parametrize("raw,shown", [
    ("Wed Nov 11 09:30:00 2026", "2026-11-11 09:30"),
    ('"Wed Nov 11 09:30:00 2026"', "2026-11-11 09:30"),
    ("Mi. Nov. 11 09:30:00 2026", "2026-11-11 09:30"),
    ("2026-11-11T09:30:05", "2026-11-11 09:30"),
    ("2026-11-11", "2026-11-11"),
    ("July 19, 2026", "2026-07-19"),
    ("sometime last week", "sometime last week"),
    ("", ""),
])
def test_display_date(raw, shown):
    assert display_date(raw) == shown


def test_the_window_shows_one_date_format(qapp, tmp_path):
    a = _write(tmp_path / "a.ti3", _noisy(seed=0))
    text = a.read_text(encoding="utf-8")
    import re
    raw = re.search(r'CREATED "([^"]+)"', text).group(1)
    b = _write(tmp_path / "b.ti3", _noisy(seed=1))
    d = _write(tmp_path / "d.ti3", _noisy(seed=2))
    dlg = _inspector(qapp, a)
    dlg.add_readings([b, d])
    t = _texts(dlg)
    shown = display_date(raw)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?", shown), shown
    assert raw not in t
    assert f"Measured on\n{shown}" in t
    assert f"measured {shown}" in t           # the reading rows, same form
    assert load_reading(b).measured_on == shown
    dlg.deleteLater()


# ---- 4. the list at the window's minimum width -------------------------------

def test_the_list_keeps_the_end_of_a_name_at_the_minimum_width(qapp,
                                                              tmp_path):
    a = _write(tmp_path / "a.ti3", _noisy(seed=0))
    names = [f"ET-8550-Hahnemuehle-Photo-Rag-second-print-{k}-measured.ti3"
             for k in (1, 2)]
    paths = [_write(tmp_path / n, _noisy(seed=k))
             for k, n in enumerate(names, start=1)]
    dlg = _inspector(qapp, a)
    dlg.show()
    dlg.add_readings(paths)
    dlg.resize(dlg.minimumWidth(), dlg.height())
    qapp.processEvents()
    lw = dlg._others_list
    fm = lw.fontMetrics()
    for row in range(lw.count()):
        shown = lw.item(row).text()
        # the distinguishing end of the name stays, and so does the date
        assert f"-{row + 1}-measured.ti3" in shown, shown
        assert "measured 20" in shown, shown
        assert "…" in shown                      # it was shortened
        # the name and the date fit; only the instrument may be cut at the
        # right by the list itself
        head = shown.split("  ·  X-Rite")[0]
        assert fm.horizontalAdvance(head) <= lw.viewport().width(), shown
        assert names[row] in lw.item(row).toolTip()
    # wider again: the whole line comes back
    dlg.resize(dlg.minimumWidth() + 900, dlg.height())
    qapp.processEvents()
    assert lw.item(0).text().startswith(names[0])
    dlg.close()
    dlg.deleteLater()
