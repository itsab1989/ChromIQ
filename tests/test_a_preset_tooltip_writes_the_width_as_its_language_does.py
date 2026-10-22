"""A built-in preset's tooltip writes the patch width the way its language
does (the reviewer's finding, 4.3.10): German read "Messfeldbreite 18.0mm",
with a decimal point and no space before the unit. It now reads "18,0 mm" in
every language with a decimal comma, "18.0 mm" in the others, and the
opening line says "Built-in chart: it cannot be deleted." in every language.
The preset's NAME keeps "-w18.0mm": that is an identifier, not prose."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _a_preset_with_a_width():
    from ui.tabs import tab_chart as T
    for p in T.KNUT_PRESETS_BY_KEY.values():
        if (p.layout_recipe is not None and p.group != "Scanner"
                and T._WIDTH_TOKEN_RE.search(p.name)):
            return p
    pytest.skip("no built-in preset carries a width in its name")


def _number(p) -> str:
    from ui.tabs import tab_chart as T
    return T._WIDTH_TOKEN_RE.search(p.name).group(0)[2:-2]


def test_english_has_a_space_before_the_unit(qapp):
    from ui.tabs.tab_chart import TabChart
    p = _a_preset_with_a_width()
    tip = TabChart._knut_tooltip(p.key)
    assert tip.startswith("Built-in chart: it cannot be deleted.\n")
    assert f"{_number(p)} mm patches" in tip
    assert f"{_number(p)}mm" not in tip


@pytest.mark.parametrize("code", ["de", "es", "fr", "it", "nl", "no", "pl",
                                  "pt", "ru", "sv", "uk"])
def test_a_decimal_comma_language_writes_a_comma(qapp, code):
    from core import i18n
    from ui.tabs.tab_chart import TabChart
    p = _a_preset_with_a_width()
    i18n.set_language(code)
    try:
        tip = TabChart._knut_tooltip(p.key)
    finally:
        i18n.set_language(i18n.SOURCE_LANGUAGE)
    assert _number(p).replace(".", ",") + " mm" in tip, tip
    assert _number(p) + "mm" not in tip
    assert "cannot be deleted" not in tip, "the opening line is untranslated"


@pytest.mark.parametrize("code", ["ja", "zh_CN"])
def test_a_decimal_point_language_keeps_the_point(qapp, code):
    from core import i18n
    from ui.tabs.tab_chart import TabChart
    p = _a_preset_with_a_width()
    i18n.set_language(code)
    try:
        tip = TabChart._knut_tooltip(p.key)
    finally:
        i18n.set_language(i18n.SOURCE_LANGUAGE)
    assert _number(p) + " mm" in tip, tip
    assert "cannot be deleted" not in tip, "the opening line is untranslated"
