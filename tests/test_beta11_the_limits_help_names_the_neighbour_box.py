"""The limits' purpose paragraph names the neighbour check by its box
(review of beta 11).

The reviewed limits help (Knut, #182 5983733592) said "another check, which
compares each patch with its neighbours" while the neighbour check was on
another branch. Merged, the check has a box in Preferences ▸ Measurement, so
the paragraph names it by the box's own words, as it already names the strip
check by its checkbox's, in English and in every catalogue.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
#: k44 (beta 15): the neighbour check's own checkbox, named after it
LABEL = ("Neighbour check: flag a patch that does not fit the patches "
         "nearest to it in colour")


def _codes():
    return sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json")
                  if not p.stem.startswith("parameters"))


def _help():
    from ui.tabs.tab_measure import LIMITS_PURPOSE_HELP
    return LIMITS_PURPOSE_HELP


def test_the_english_names_the_box():
    text = _help()
    assert "another check" not in text
    assert "the neighbour check (“" + LABEL.rstrip(":") + "”)" in text


def test_both_copies_are_the_same():
    from ui.dialogs.settings_dialog import LIMITS_PURPOSE_HELP as other
    assert other == _help()


@pytest.mark.parametrize("code", _codes())
def test_every_language_quotes_its_own_box_label(code):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text(
        encoding="utf-8"))
    label = cat[LABEL].rstrip(":： ").strip()
    assert label in cat[_help()], code
