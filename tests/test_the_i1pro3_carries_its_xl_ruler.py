"""The i1Pro 3+ is paired with the XL scanning ruler, and says so.

Knut, 2026-09-17: *"The i1Pro 3 Plus is paired with an XL scanning ruler, which
supports a maximum scan length of 515 mm. Currently, the Instrument margins in
Preferences ==> Instrument Limits, with selected instrument i1Pro3+ and any
paper size, the 'Strip length limit' is set to 220 mm. Change the 'Strip length
limit' to 515 mm for all combinations of any paper size and the i1Pro3+
instrument. At the same time, change the description for the paper and
instrument combinations mentioned to 'i1Pro 3+ XL scanning ruler / jig'."*

**The 220 drove the WARNING and nothing else**, measured before it was changed:
charts already build strips of 280 mm on A4 and 403 mm on A2 against it, so
raising it lays no chart out differently. `mxrowl`, one line above `ruler_mm` in
`instruments.py` and a textually identical expression, is the one that binds the
layout and is deliberately untouched. That distinction is what the last test
here is for.
"""
from __future__ import annotations

import pytest

from core.settings import (SETTINGS_SCHEMA, _I1P3_DESC,
                           _I1P3_DESC_BEFORE_SCHEMA24,
                           default_margin_thresholds,
                           upgrade_i1pro3_ruler_description)
from workflow.layout_engine import instruments


def test_the_i1pro3_ruler_is_the_xl_length():
    assert instruments.default_ruler_mm("p3") == 515.0
    assert instruments.default_ruler_mm("i1Pro 3+") == 515.0, (
        "the friendly Settings label must resolve to the same number as the "
        "device key, or Preferences and the warning disagree")


def test_no_other_instrument_moved():
    """The i1Pro keeps its 240 mm, and the rulerless ones keep having none."""
    assert instruments.default_ruler_mm("i1") == 240.0
    for key in ("CM", "SS", "CR30"):
        assert instruments.default_ruler_mm(key) == 0.0, key


def test_the_layout_cap_is_not_the_ruler():
    """`mxrowl` binds the layout; `ruler_mm` only drives the warning.

    They were one expression, and a careless edit would have raised both. That
    would change how every i1Pro 3+ chart is laid out on paper longer than
    220 mm, which is not what was asked for.
    """
    g = instruments.build("p3")
    assert g.ruler_mm == 515.0
    assert g.mxrowl == pytest.approx(220.0), (
        f"the layout cap moved with the ruler ({g.mxrowl} mm); raising the "
        f"warning threshold must not re-lay-out a single chart")


def test_every_i1pro3_row_names_the_xl_ruler():
    rows = {k: v for k, v in default_margin_thresholds().items()
            if k.startswith("i1Pro 3+|")}
    assert rows, "the seed has no i1Pro 3+ rows at all"
    assert all(v.get("desc") == _I1P3_DESC for v in rows.values()), (
        "a fresh install must seed the new description on every i1Pro 3+ "
        "paper and orientation")
    assert "XL" in _I1P3_DESC


def test_the_migration_renames_only_the_shipped_description():
    """A description the user typed is theirs, and is left alone."""
    table = {
        "i1Pro 3+|A4 Portrait": {"L": 28, "R": 9, "T": 40, "B": 9,
                                 "desc": _I1P3_DESC_BEFORE_SCHEMA24},
        "i1Pro 3+|A3 Portrait": {"L": 9, "R": 9, "T": 9, "B": 9,
                                 "desc": "my own jig"},
        "i1Pro|A4 Portrait": {"L": 9, "R": 9, "T": 9, "B": 9,
                              "desc": "i1Pro ruler / jig"},
    }
    out, changed = upgrade_i1pro3_ruler_description(table)
    assert changed
    assert out["i1Pro 3+|A4 Portrait"]["desc"] == _I1P3_DESC
    assert out["i1Pro 3+|A3 Portrait"]["desc"] == "my own jig"
    assert out["i1Pro|A4 Portrait"]["desc"] == "i1Pro ruler / jig"
    # …and it is idempotent, so a second startup changes nothing.
    out2, changed2 = upgrade_i1pro3_ruler_description(out)
    assert not changed2


def test_the_schema_was_bumped_for_it():
    """A changed default needs a migration, and a migration needs a number."""
    assert SETTINGS_SCHEMA >= 24


def test_a_stored_ruler_override_is_never_migrated():
    """Nobody has one by default, and anyone who does chose it.

    Measured on a real store: `_commit_margin_combo` writes a `ruler` key only
    when the value differs from the instrument's built-in, so an untouched box
    stores nothing and keeps tracking `default_ruler_mm`. The migration must
    not touch a row that carries one.
    """
    table = {"i1Pro 3+|A4 Portrait": {"L": 28, "R": 9, "T": 40, "B": 9,
                                      "desc": _I1P3_DESC_BEFORE_SCHEMA24,
                                      "ruler": 300}}
    out, _ = upgrade_i1pro3_ruler_description(table)
    assert out["i1Pro 3+|A4 Portrait"]["ruler"] == 300
