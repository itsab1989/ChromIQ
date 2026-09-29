"""B8-1396: Create Chart's FROM PROFILE GAMUT help does not say "drift".

Knut, #182 5849392788: *"The word drift is not used at all ... Use the word
"Change" instead of "Drift"."* B8-1394 applied that to the report and its
help; the two help texts of the FROM PROFILE GAMUT module in Create Chart
(the module's own help and the patch count's) still asked "has anything
drifted" and spoke of "a drifting printer". They describe verification, so
they follow the same ruling.

Mutations (each run red): M1396-a put "drifted" back into the module help;
M1396-b put "a drifting printer" back into the count help; M1396-c put an em
dash back into either; M1396-d left the German on the old key.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest                                                  # noqa: E402

from ui.tabs import tab_chart as TC                            # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEXTS = ("_GAMUT_MODULE_HELP_BODY", "_GAMUT_SIZE_HELP_BODY")


def _catalogue(code: str) -> dict:
    return json.loads((ROOT / f"data/i18n/{code}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", TEXTS)
def test_the_help_says_change_not_drift(name):
    text = getattr(TC, name)
    assert "drift" not in text.lower(), name
    assert "—" not in text, f"{name} carries an em dash"


def test_the_module_help_asks_what_changed():
    assert "has anything changed since I made this profile?" in TC._GAMUT_MODULE_HELP_BODY
    assert "A change in the printer shows in the greys first" in TC._GAMUT_SIZE_HELP_BODY


@pytest.mark.parametrize("name", TEXTS)
def test_german_is_written_by_hand_and_says_change(name):
    de = _catalogue("de")
    text = getattr(TC, name)
    assert text in de, f"{name}: no German for the new key"
    german = de[text]
    assert german != text, f"{name}: German carries the English"
    assert "drift" not in german.lower()
    assert "—" not in german
    assert "verändert" in german or "Veränderung" in german


@pytest.mark.parametrize("name", TEXTS)
def test_every_catalogue_has_the_new_key(name):
    text = getattr(TC, name)
    for path in sorted((ROOT / "data/i18n").glob("*.json")):
        assert text in _catalogue(path.stem), f"{path.name}: {name} missing"
