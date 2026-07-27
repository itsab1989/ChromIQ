"""#131 (Knut, 2026-07-27): every ColorMunki page size needs 30 mm at the top
and 10 mm at the bottom; the sides stay at 6 mm.

Changing a default means existing installations must be migrated — but only
where the old default is still in place, never over a value someone chose.
"""
from __future__ import annotations

from core.settings import (default_margin_thresholds,
                           upgrade_colormunki_margins)


def test_every_colormunki_page_size_has_the_new_margins():
    rows = {k: v for k, v in default_margin_thresholds().items()
            if k.startswith("ColorMunki|")}
    assert rows, "the ColorMunki must still be seeded"
    for key, r in rows.items():
        assert (r["L"], r["R"], r["T"], r["B"]) == (6, 6, 30, 10), (key, r)


def test_the_change_did_not_leak_into_other_instruments():
    """The seed builder gained a bottom argument; every other instrument must
    still get exactly what it got before."""
    rows = {k: v for k, v in default_margin_thresholds().items()
            if not k.startswith("ColorMunki|")}
    assert rows
    for key, r in rows.items():
        assert (r["T"], r["B"]) != (30, 10), (key, r)


def test_a_stored_default_is_upgraded():
    table = {"ColorMunki|A4 Portrait": {"L": 6, "R": 6, "T": 24, "B": 6,
                                        "desc": "x"}}
    table, changed = upgrade_colormunki_margins(table)
    assert changed
    r = table["ColorMunki|A4 Portrait"]
    assert (r["T"], r["B"]) == (30, 10)
    assert r["desc"] == "x", "the label must survive the upgrade"


def test_a_value_the_user_chose_is_left_alone():
    table = {"ColorMunki|A4 Portrait": {"L": 8, "R": 8, "T": 25, "B": 7,
                                        "desc": "mine"}}
    table, changed = upgrade_colormunki_margins(table)
    assert not changed
    assert table["ColorMunki|A4 Portrait"]["T"] == 25


def test_other_instruments_are_not_touched_by_the_upgrade():
    table = {"i1Pro|A4 Portrait": {"L": 9, "R": 9, "T": 9, "B": 9, "desc": ""}}
    table, changed = upgrade_colormunki_margins(table)
    assert not changed and table["i1Pro|A4 Portrait"]["T"] == 9


def test_upgrading_twice_changes_nothing_the_second_time():
    table = {"ColorMunki|A4 Portrait": {"L": 6, "R": 6, "T": 24, "B": 6,
                                        "desc": ""}}
    table, first = upgrade_colormunki_margins(table)
    table, second = upgrade_colormunki_margins(table)
    assert first and not second
