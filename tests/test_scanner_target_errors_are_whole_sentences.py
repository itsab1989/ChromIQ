"""The scanner-target errors are whole translated sentences, for every count.

Review 38 of 4.3.11: three errors in ``workflow/scanin_target.py`` were English
f-strings with only the counted fragment translated, so a Russian user read
"The .cht files don't belong to this chart: у 21 клеток нет no patch in the
reference". Each is now one ``tr()`` string with a singular and a plural key,
and the plural has per-number forms in Russian, Ukrainian and Polish.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core import i18n
from workflow import scanin_target as S


@pytest.fixture(autouse=True)
def _reset_language():
    yield
    i18n.set_language("en")


def _locs(n: int) -> "list[str]":
    return [f"A{i}" for i in range(1, n + 1)]


def _raise_cover(monkeypatch, missing: int, extra: int) -> str:
    """Run layout_from_cht_files on one fake .cht page whose boxes leave
    `missing` reference patches uncovered, or add `extra` unknown boxes."""
    ref = _locs(30)
    boxes = ref[missing:] + [f"Z{i}" for i in range(extra)]
    monkeypatch.setattr(S, "read_text", lambda p, lenient=False: "cht")
    monkeypatch.setattr(S, "_cht_x_box_locs", lambda text: list(boxes))
    monkeypatch.setattr(S, "parse_ti3", lambda p: SimpleNamespace(sample_locs=ref))
    with pytest.raises(S.ScaninTargetError) as e:
        S.layout_from_cht_files(["page.cht"], "ref.cie")
    return str(e.value)


def _raise_unmeasured(missing: int) -> str:
    geom = _locs(30)
    with pytest.raises(S.GeometryMismatch) as e:
        S._check_measured(geom, SimpleNamespace(sample_locs=geom[missing:]))
    return str(e.value)


_EXPECT = {
    "ru": {
        "cover": {1: "у 1 патча", 21: "у 21 патча", 22: "у 22 патчей"},
        "extra": {1: "у 1 клетки", 21: "у 21 клетки", 22: "у 22 клеток"},
        "unmeasured": {1: "У 1 патча", 21: "У 21 патча", 22: "У 22 патчей"},
    },
    "uk": {
        "cover": {1: "у 1 патча", 21: "у 21 патча", 22: "у 22 патчів"},
        "extra": {1: "у 1 рамки", 21: "у 21 рамки", 22: "у 22 рамок"},
        "unmeasured": {1: "У 1 патча", 21: "У 21 патча", 22: "У 22 патчів"},
    },
    "pl": {
        "cover": {1: "1 pole", 21: "21 pól", 22: "22 pola z pliku referencyjnego nie mają"},
        "extra": {1: "1 ramka", 21: "21 ramek", 22: "22 ramki w nich nie mają"},
        "unmeasured": {1: "1 pole", 21: "21 pól", 22: "22 pola tego wzorca nie mają"},
    },
}


@pytest.mark.parametrize("lang", sorted(_EXPECT))
def test_every_number_reads_right(lang, monkeypatch):
    i18n.set_language(lang)
    for n, want in _EXPECT[lang]["cover"].items():
        assert want in _raise_cover(monkeypatch, missing=n, extra=0), (lang, n)
    for n, want in _EXPECT[lang]["extra"].items():
        assert want in _raise_cover(monkeypatch, missing=0, extra=n), (lang, n)
    for n, want in _EXPECT[lang]["unmeasured"].items():
        assert want in _raise_unmeasured(n), (lang, n)


@pytest.mark.parametrize("lang", ["de", "fr", "ja", "ru", "uk", "pl", "zh_CN"])
def test_no_english_is_left_in_a_translated_error(lang, monkeypatch):
    i18n.set_language(lang)
    for text in (_raise_cover(monkeypatch, missing=2, extra=0),
                 _raise_cover(monkeypatch, missing=0, extra=2),
                 _raise_unmeasured(2)):
        for english in ("no patch in the reference", "have no box",
                        "no measurement", "e.g.", "Re-measure", "Pick "):
            assert english not in text, (lang, text)
        assert "A1, A2" in text or "Z0, Z1" in text, text


def test_english_names_its_examples_plainly(monkeypatch):
    text = _raise_unmeasured(1)
    assert text.startswith("1 patch of this chart has no measurement")
    assert "(for example A1)" in text
    assert "['A1']" not in text
