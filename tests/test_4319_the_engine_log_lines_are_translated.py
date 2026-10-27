"""4.3.19: the ChromIQ layout engine's log lines are translated.

The Create Chart log showed "[ChromIQ layout engine] 441 patches (21×21),
1 page, random start 1007764308" as an English f-string in every language
(only "1 page" was translated), and "random start" is not what the panel calls
it: the Randomisation group's control is "Seed:". The padding line
("patch count: 896 designed + ...") and "building chart from the targen .ti1…"
were English-only too, and so was the frame of the engine's error line.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core import i18n

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru", "sv",
         "uk", "zh_CN")
TAG = "[ChromIQ layout engine] "
K_BUILD = TAG + "building chart from the targen .ti1…"
K_SUMMARY = TAG + "{patches} ({steps}×{passes}), {pages}, {seed_label} {seed}"
K_PADDING = (TAG + "patch count: {designed} designed + {fill} completing the "
             "last strip = {total} total. Instruments read whole strips; the "
             "fill-up patches are measured like any others.")
K_ERROR = "[ERROR] ChromIQ layout engine: {error}"
KEYS = (K_BUILD, K_SUMMARY, K_PADDING, K_ERROR)


@pytest.fixture(autouse=True)
def _english_after():
    i18n.set_language("en")
    yield
    i18n.set_language("en")


def _summary(*a):
    from workflow.chart_creator import _engine_summary_log_line
    return _engine_summary_log_line(*a)


def _padding(*a):
    from workflow.chart_creator import _engine_padding_log_line
    return _engine_padding_log_line(*a)


def test_the_english_summary_names_the_seed_as_the_panel_does():
    line = _summary(441, 21, 21, 1, 1007764308)
    assert line == ("[ChromIQ layout engine] 441 patches (21×21), 1 page, "
                    "Seed: 1007764308")
    assert "random start" not in line
    assert _summary(1, 1, 1, 3, 7) == (
        "[ChromIQ layout engine] 1 patch (1×1), 3 pages, Seed: 7")


def test_the_seed_label_is_the_panels_own_key():
    src = (ROOT / "ui/dialogs/layout_options_panel.py").read_text("utf-8")
    assert 'QLabel(tr("Seed:")' in src
    creator = (ROOT / "workflow/chart_creator.py").read_text("utf-8")
    assert 'seed_label=tr("Seed:")' in creator
    assert "random start" not in creator


def test_the_english_padding_line_is_unchanged():
    assert _padding(910, 14) == (
        "[ChromIQ layout engine] patch count: 896 designed + 14 paper-white "
        "fill-up patches completing the last strip = 910 total. Instruments "
        "read whole strips; the fill-up patches are measured like any others.")
    assert "1 paper-white fill-up patch completing" in _padding(897, 1)


def test_no_engine_log_line_is_an_english_f_string_any_more():
    src = (ROOT / "workflow/chart_creator.py").read_text("utf-8")
    assert not re.search(r'f"\[ChromIQ layout engine\] [^{]', src)
    assert 'f"[ERROR] ChromIQ layout engine' not in src
    assert 'on_line("[ChromIQ layout engine]' not in src


def test_the_extractor_sees_every_key():
    from scripts.i18n_extract import extract_keys
    keys = set(extract_keys())
    for k in KEYS:
        assert k in keys, k


@pytest.mark.parametrize("lang", LANGS)
def test_every_language_has_the_keys_with_their_placeholders(lang):
    cat = json.loads((ROOT / f"data/i18n/{lang}.json").read_text("utf-8"))
    for k in KEYS:
        v = cat.get(k)
        assert v, (lang, k)
        assert set(re.findall(r"{\w+}", v)) == set(re.findall(r"{\w+}", k))
        assert "—" not in v
        assert v.startswith(k.split("]")[0] + "]"), (lang, v)
    # The prose lines are really translated, not copied.
    assert cat[K_BUILD] != K_BUILD and cat[K_PADDING] != K_PADDING


@pytest.mark.parametrize("lang", LANGS)
def test_the_summary_reads_in_the_language_with_the_seed_label(lang):
    i18n.set_language(lang)
    line = _summary(441, 21, 21, 2, 1007764308)
    assert line.startswith(TAG + "441 ")
    assert i18n.tr("Seed:") + " 1007764308" in line
    assert "patches" not in line
    if lang != "fr":  # French writes "2 pages" too
        assert "pages" not in line
    assert "random start" not in line
    # The seed is printed as it is, never grouped or comma-formatted.
    assert "1007764308" in line


@pytest.mark.parametrize("lang,n,form", [
    ("ru", 1, "1 патч "), ("ru", 22, "22 патча "), ("ru", 25, "25 патчей "),
    ("ru", 21, "21 патч "),
    ("uk", 22, "22 патчі "), ("uk", 25, "25 патчів "),
    ("pl", 22, "22 pola "), ("pl", 25, "25 pól "), ("pl", 1, "1 pole "),
])
def test_the_patch_count_takes_the_form_its_number_needs(lang, n, form):
    i18n.set_language(lang)
    assert form in _summary(n, 21, 21, 1, 5)


@pytest.mark.parametrize("lang,pages,form", [
    ("ru", 2, "2 страницы"), ("ru", 5, "5 страниц"), ("ru", 21, "21 страница"),
    ("uk", 3, "3 сторінки"), ("pl", 22, "22 strony"), ("pl", 5, "5 stron"),
])
def test_the_page_count_takes_the_form_its_number_needs(lang, pages, form):
    i18n.set_language(lang)
    assert form in _summary(441, 21, 21, pages, 5)


@pytest.mark.parametrize("lang", LANGS)
def test_the_padding_line_is_translated(lang):
    i18n.set_language(lang)
    line = _padding(910, 14)
    assert line.startswith(TAG)
    assert "designed" not in line and "Instruments" not in line
    for num in ("896", "14", "910"):
        assert num in line
    fill = i18n.count_phrase(14, i18n.tr("1 paper-white fill-up patch"),
                             i18n.tr("{n} paper-white fill-up patches"))
    assert fill in line


@pytest.mark.parametrize("lang", LANGS)
def test_the_build_and_error_lines_are_translated(lang):
    i18n.set_language(lang)
    assert i18n.tr(K_BUILD) != K_BUILD
    err = i18n.tr(K_ERROR).format(error="boom")
    assert err.startswith("[ERROR] ") and err.endswith("boom")
