"""The ColorMunki's per-page margin thresholds, and the two upgrades that got
them there.

#131 (Knut, 2026-07-27) gave every ColorMunki page size 30 mm at the top and
10 mm at the bottom, the sides staying at 6 mm.

#151 (Knut, 2026-08-14) raised the top again, to **33 mm**:

    *"Due to two knobs underneath the colormunki, which keeps getting caught in
    the paper edge when starting a strip, the top margin instrument limit should
    be set to 33.0 mm."*

So the head needs a little more paper in front of the first patch than the
optics alone would suggest — the obstruction is mechanical, not optical.

Changing a default means existing installations must be migrated — but only
where a shipped default is still in place, never over a value someone chose.
These thresholds are explicitly *seeds a user adjusts to their own rig*, so
overwriting a tuned value would be the worse bug.
"""
from __future__ import annotations

from core.settings import (default_margin_thresholds,
                           upgrade_colormunki_margins,
                           upgrade_colormunki_top_margin_33)

CM_TOP = 33
CM_BOTTOM = 10
CM_SIDE = 6


def test_every_colormunki_page_size_has_the_new_margins():
    rows = {k: v for k, v in default_margin_thresholds().items()
            if k.startswith("ColorMunki|")}
    assert rows, "the ColorMunki must still be seeded"
    for key, r in rows.items():
        assert (r["L"], r["R"], r["T"], r["B"]) == \
            (CM_SIDE, CM_SIDE, CM_TOP, CM_BOTTOM), (key, r)


def test_every_paper_and_orientation_is_covered():
    """#151 is explicitly "all Colormunki instrument and paper size
    combinations" — a page size missed here would keep the old clearance and
    catch the knobs exactly as reported."""
    rows = [k for k in default_margin_thresholds() if k.startswith("ColorMunki|")]
    for paper in ("A4", "Letter", "A3", "A3+", "A2", "Tabloid", "Legal"):
        for orient in ("Portrait", "Landscape"):
            assert f"ColorMunki|{paper} {orient}" in rows, (paper, orient)


def test_the_change_did_not_leak_into_other_instruments():
    """The seed builder gained a bottom argument; every other instrument must
    still get exactly what it got before."""
    rows = {k: v for k, v in default_margin_thresholds().items()
            if not k.startswith("ColorMunki|")}
    assert rows
    for key, r in rows.items():
        assert (r["T"], r["B"]) != (CM_TOP, CM_BOTTOM), (key, r)


# --- #151: the 33 mm upgrade -----------------------------------------------

def test_the_schema_13_default_is_raised_to_33():
    """Anyone who installed since #131 carries 6/6/30/10."""
    table = {"ColorMunki|A4 Portrait": {"L": 6, "R": 6, "T": 30, "B": 10,
                                        "desc": "x"}}
    table, changed = upgrade_colormunki_top_margin_33(table)
    assert changed
    r = table["ColorMunki|A4 Portrait"]
    assert (r["T"], r["B"]) == (CM_TOP, CM_BOTTOM)
    assert r["desc"] == "x", "the label must survive the upgrade"


def test_the_pre_schema_13_default_is_also_raised_to_33():
    """A user who has not opened Preferences since before #131 still holds
    6/6/24/6, and must land on the current values in one step rather than being
    stranded on an intermediate one."""
    table = {"ColorMunki|A2 Landscape": {"L": 6, "R": 6, "T": 24, "B": 6,
                                         "desc": ""}}
    table, changed = upgrade_colormunki_top_margin_33(table)
    assert changed
    r = table["ColorMunki|A2 Landscape"]
    assert (r["L"], r["R"], r["T"], r["B"]) == \
        (CM_SIDE, CM_SIDE, CM_TOP, CM_BOTTOM)


def test_a_value_the_user_chose_is_left_alone():
    """These are seeds to adjust, not physical minima — a tuned rig must win."""
    table = {"ColorMunki|A4 Portrait": {"L": 8, "R": 8, "T": 45, "B": 7,
                                        "desc": "mine"}}
    table, changed = upgrade_colormunki_top_margin_33(table)
    assert not changed
    assert table["ColorMunki|A4 Portrait"]["T"] == 45


def test_a_user_value_that_merely_looks_close_is_left_alone():
    """31 is not a default ChromIQ ever shipped, so it is someone's choice."""
    table = {"ColorMunki|A4 Portrait": {"L": 6, "R": 6, "T": 31, "B": 10,
                                        "desc": ""}}
    table, changed = upgrade_colormunki_top_margin_33(table)
    assert not changed and table["ColorMunki|A4 Portrait"]["T"] == 31


def test_other_instruments_are_not_touched_by_the_33_upgrade():
    table = {"i1Pro|A4 Portrait": {"L": 26, "R": 9, "T": 38, "B": 9, "desc": ""}}
    table, changed = upgrade_colormunki_top_margin_33(table)
    assert not changed and table["i1Pro|A4 Portrait"]["T"] == 38


def test_upgrading_to_33_twice_changes_nothing_the_second_time():
    table = {"ColorMunki|A4 Portrait": {"L": 6, "R": 6, "T": 30, "B": 10,
                                        "desc": ""}}
    table, first = upgrade_colormunki_top_margin_33(table)
    table, second = upgrade_colormunki_top_margin_33(table)
    assert first and not second


def test_the_two_upgrades_compose_in_either_order():
    """Both migrations run on the same blob. Whichever order they fire in, a
    stale row must end on 33 — never stranded at 30."""
    for order in ((upgrade_colormunki_margins, upgrade_colormunki_top_margin_33),
                  (upgrade_colormunki_top_margin_33, upgrade_colormunki_margins)):
        table = {"ColorMunki|A4 Portrait": {"L": 6, "R": 6, "T": 24, "B": 6,
                                            "desc": ""}}
        for fn in order:
            table, _ = fn(table)
        assert table["ColorMunki|A4 Portrait"]["T"] == CM_TOP, order


# --- #131: the original upgrade still behaves -------------------------------

def test_the_schema_13_upgrade_still_works_on_its_own():
    table = {"ColorMunki|A4 Portrait": {"L": 6, "R": 6, "T": 24, "B": 6,
                                        "desc": "x"}}
    table, changed = upgrade_colormunki_margins(table)
    assert changed
    r = table["ColorMunki|A4 Portrait"]
    assert (r["T"], r["B"]) == (30, 10)
    assert r["desc"] == "x"


def test_other_instruments_are_not_touched_by_the_schema_13_upgrade():
    table = {"i1Pro|A4 Portrait": {"L": 9, "R": 9, "T": 9, "B": 9, "desc": ""}}
    table, changed = upgrade_colormunki_margins(table)
    assert not changed and table["i1Pro|A4 Portrait"]["T"] == 9
