"""The limits' purpose paragraph names the neighbour check and the strip test
by their names (review of beta 11; beta 17).

The reviewed limits help (Knut, #182 5983733592) said "another check, which
compares each patch with its neighbours". Since beta 17 the two tests are
rows of Preferences ▸ Measurement's table, named "Strip test" and "Neighbour
check" (Knut 6082015002: "Names for the tests, limits, chart types are all
good"; the proper names everywhere), so the paragraph names them so, in
English and in every catalogue.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _codes():
    return sorted(p.stem for p in (ROOT / "data" / "i18n").glob("*.json")
                  if not p.stem.startswith("parameters"))


def _help():
    from ui.tabs.tab_measure import LIMITS_PURPOSE_HELP
    return LIMITS_PURPOSE_HELP


def test_the_english_names_both_tests():
    text = _help()
    assert "another check" not in text
    assert "the strip test and the neighbour check" in text


def test_both_copies_are_the_same():
    from ui.dialogs.settings_dialog import LIMITS_PURPOSE_HELP as other
    assert other == _help()


@pytest.mark.parametrize("code", _codes())
def test_every_language_names_the_neighbour_check_by_its_name(code):
    cat = json.loads((ROOT / "data" / "i18n" / f"{code}.json").read_text(
        encoding="utf-8"))
    for name in ("Neighbour check", "Strip test"):
        label = cat[name].lower()
        assert label in cat[_help()].lower(), (code, name)
