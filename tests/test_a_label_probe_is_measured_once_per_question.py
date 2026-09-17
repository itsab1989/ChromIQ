"""The layout engine may not ask the font the same question 135,000 times.

Knut, beta 20: *"Loading any of the 6 Scanner presets takes 5 to 10 seconds to
load. Why? Patch sets are simple numbers for colors, so it should not take a
lot of processing power ... Also, the first preset I load after having loaded a
scanner preset will also take a long time to load. It seems the time it takes
to load a preset is dependent upon which profile I loaded last."*

Measured in the real window, on the real dropdown. `_furniture_reserves_mm`
renders glyphs twice and `row_label_band_mm` measures a row of labels, and the
area fit calls all three once per candidate patch size, per column count, per
pass. One preset load called them 3,845 and 45,227 times, which came to 135,685
`Font.getlength` calls, 49,079 font loads and 7,706 rendered glyph images:

| loaded | before | after |
|---|---|---|
| a ColorMunki preset, first | 1.25 s | 0.83 s |
| a Scanner preset (3,430 patches) | 10.21 s | 1.66 s |
| the ColorMunki one straight after it | 17.90 s | 1.29 s |
| a Scanner preset (6,860 patches) | 10.15 s | 1.86 s |
| the ColorMunki one straight after that | 5.09 s | 0.93 s |

It answers the same, byte for byte: twelve chart configurations built on both
trees, 46 files each identical once the `.ti2`'s CREATED timestamp and random
CHART_ID are normalised.

Two things have to stay true, and this file is both of them: the work must not
come back, and a cache must never answer a question it was not asked.
"""
from __future__ import annotations

import itertools

import pytest

from workflow.layout_engine import raster


_CACHED = ("_widest_row_label_px", "_indicator_band_px", "_indicator_ink_px")


@pytest.fixture(autouse=True)
def _cold_caches():
    """Start and end every test with nothing remembered.

    Tolerant of a probe that has LOST its cache, so that case fails in the test
    that says so rather than erroring in every test in the file.
    """
    def clear():
        for name in _CACHED:
            fn = getattr(raster, name, None)
            if hasattr(fn, "cache_clear"):
                fn.cache_clear()
    clear()
    yield
    clear()


def test_the_three_label_probes_are_cached_at_all():
    missing = [n for n in _CACHED
               if not hasattr(getattr(raster, n, None), "cache_clear")]
    assert not missing, (
        f"{missing} lost their cache, so the engine is back to measuring the "
        f"same text tens of thousands of times per preset load")


def _geom():
    from workflow.layout_engine import instruments
    return instruments.geom_from_build_kwargs({"instrument": "i1"})


def test_the_engine_loads_a_font_once_however_often_it_asks(monkeypatch):
    """The reserves for one layout, asked for fifty times, may build a handful
    of fonts, not fifty times a handful."""
    calls = {"n": 0}
    real = raster._font

    def counted(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(raster, "_font", counted)
    geom = _geom()
    kw = {"instrument": "i1", "dpi": 200, "draw_indicators": True}
    raster._furniture_reserves_mm(geom, kw)
    first = calls["n"]
    assert first > 0, "the fixture never reached the font at all"
    for _ in range(49):
        raster._furniture_reserves_mm(geom, kw)
    assert calls["n"] == first, (
        f"the same layout was measured again: {calls['n']} font loads for 50 "
        f"identical calls, {first} for the first one")


def test_the_row_label_band_is_measured_once_per_question(monkeypatch):
    calls = {"n": 0}
    real = raster._font

    def counted(*a, **k):
        calls["n"] += 1
        return real(*a, **k)

    monkeypatch.setattr(raster, "_font", counted)
    geom = _geom()
    raster.row_label_band_mm(geom, dpi=200, rows=24)
    first = calls["n"]
    assert first > 0, "the fixture never reached the font at all"
    for _ in range(39):
        raster.row_label_band_mm(geom, dpi=200, rows=24)
    # THE COUNT MUST NOT GROW, which is the property; it is not 1, because
    # `effective_row_label_size_mm` resolves an auto size with a font of its
    # own before the band is measured at all.
    assert calls["n"] == first, (
        f"{calls['n']} font loads for 40 identical questions, {first} for the "
        f"first one")


#: Every argument, varied, so a key that dropped one is caught. The family is
#: **Inter** and one of the sizes is 40 px because that is where bold is
#: OBSERVABLE: at the default JetBrains Mono, and at small sizes, a bold face
#: measures the same as the regular one, and a test built on those inputs
#: cannot tell a cache that ignores the style from one that honours it.
_ROW_CASES = list(itertools.product(
    (8, 19, 40), ("Inter", "Instrument Serif"), (False, True), (False, True),
    ("", "0-9;A-Z"), (0, 24, 200)))
_PROBE_CASES = list(itertools.product(
    (19, 40), ("Inter",), (False, True), (False, True), (0, 90), (1, 3)))


def test_a_cached_label_measurement_never_answers_a_different_question():
    """Warm every answer, then re-ask each one with a cold cache.

    A cache whose key misses an argument gives a DIFFERENT answer here from
    the one it gives on its own, which is the only way to catch a key that has
    fallen behind its function's parameters.
    """
    warm = {c: raster._widest_row_label_px(*c) for c in _ROW_CASES}
    for c in _ROW_CASES:
        raster._widest_row_label_px.cache_clear()
        assert raster._widest_row_label_px(*c) == warm[c], f"row label {c}"

    warm_b = {c: raster._indicator_band_px(*c) for c in _PROBE_CASES}
    warm_i = {c: raster._indicator_ink_px("ABQ", *c) for c in _PROBE_CASES}
    for c in _PROBE_CASES:
        raster._indicator_band_px.cache_clear()
        raster._indicator_ink_px.cache_clear()
        assert raster._indicator_band_px(*c) == warm_b[c], f"band {c}"
        assert raster._indicator_ink_px("ABQ", *c) == warm_i[c], f"ink {c}"


def test_every_argument_of_a_label_probe_really_changes_its_answer():
    """Otherwise the test above passes on a probe that ignores its arguments.

    One argument is deliberately not claimed here: **the style does not change
    the BAND**, at any size tried. The band is the ink height of "W8", and a
    bold face is no taller than its regular one, so there is nothing to assert
    and asserting it anyway would be a test of the font rather than of the
    code. The ink probe does see bold, at 40 px, and that is asserted.
    """
    row = lambda **k: raster._widest_row_label_px(
        **{"ind_px": 40, "family": "Inter", "bold": False, "italic": False,
           "patch_pattern": "", "rows": 24, **k})
    assert row(ind_px=19) < row(), "the size does not change the row label"
    assert row(bold=True) > row(), "bold does not change the row label"
    # Italic is checked on **Instrument Serif**, whose italic really is a
    # different face: Inter's italic measures the same width for these glyphs,
    # so asserting it there would test the font and not the cache.
    assert raster._widest_row_label_px(40, "Instrument Serif", False, True, "", 24) \
        != raster._widest_row_label_px(40, "Instrument Serif", False, False, "", 24), \
        "italic does not change the row label"
    # A pattern whose ROW half is alphabetic, not just any string: the row
    # labeller reads the part after the ";", so "1" and "A" and "" all give the
    # same digits and would prove nothing.
    assert row(patch_pattern="0-9;A-Z") != row(), \
        "the patch pattern does not change the row label"
    # 200, not 24: with 0 the band is measured from 1, 9 and 99, which is two
    # digits wide, and so is every label from 1 to 24. Three digits is the
    # first count that can be seen at all.
    assert row(rows=200) != row(rows=0), "the row count does not change it"

    band = lambda **k: raster._indicator_band_px(
        **{"ind_px": 40, "fam": "Inter", "bold": False, "italic": False,
           "rot": 0, "spc": 3, **k})
    assert band(ind_px=19) != band(), "the size does not change the band"
    assert band(rot=90) != band(), "the rotation does not change the band"

    ink = lambda **k: raster._indicator_ink_px(
        "ABQ", **{"ind_px": 40, "fam": "Inter", "bold": False, "italic": False,
                  "rot": 0, "spc": 3, **k})
    assert ink(ind_px=19) != ink(), "the size does not change the ink"
    assert ink(bold=True) != ink(), "bold does not change the ink"
    assert ink(rot=90) != ink(), "the rotation does not change the ink"
    # "AB" against "ABQ", because the Q is the whole reason this probe takes
    # the labeller's own output rather than a hand-picked pair of glyphs: it is
    # the only label glyph with a descender.
    assert raster._indicator_ink_px("AB", 40, "Inter", False, False, 0, 3) \
        != ink(), "the probe text does not change the ink"
