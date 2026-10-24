"""A number ChromIQ formats itself for the screen is written the way the
reader's language writes numbers, and never anywhere else.

4.3.12: the Ukrainian reading-pace summary read "A 4.8 с" and the German
one "A 4.8 s", in languages that write 4,8. The Measurement Report already
followed the language inside its sentences (B8-950); everything else that
formatted a number itself kept the point. Two mechanisms now cover it:

* ``core.i18n.decimal_text(value, places)`` for a number a caller formats
  and hands to a text, and
* a text that formats the number itself ("{secs:.1f}", "{pct:.1f}%") does
  it in the language's way when tr() gave it, in a decimal-comma language.

What must NOT change is just as pinned: English, Japanese and Chinese keep
the point; a plain "{x}" field is filled exactly as str.format fills it; and
what ChromIQ writes for a program to read (the refinement strip list,
ArgyllCMS arguments) keeps the point in every language.
"""
from __future__ import annotations

import pytest

from core import i18n
from core.i18n import decimal_text, tr

COMMA = sorted(i18n.DECIMAL_COMMA)
POINT = ["en", "ja", "zh_CN"]


@pytest.fixture
def lang():
    previous = i18n.current_language()

    def switch(code: str) -> None:
        i18n.set_language(code)

    yield switch
    i18n.set_language(previous)


def test_the_comma_languages_are_the_ones_that_write_a_comma():
    assert set(COMMA) == {"de", "es", "fr", "it", "nl", "no", "pl", "pt",
                          "ru", "sv", "uk"}
    # the two older copies read the same list rather than keep their own
    from workflow import measurement_messages as mm
    from ui.dialogs import measurement_report_dialog as mrd
    assert mm._DECIMAL_COMMA is i18n.DECIMAL_COMMA
    assert mrd._DECIMAL_COMMA is i18n.DECIMAL_COMMA


@pytest.mark.parametrize("code", COMMA)
def test_decimal_text_writes_a_comma(code, lang):
    lang(code)
    assert decimal_text(4.8, 1) == "4,8"
    assert decimal_text(0.25, 2) == "0,25"
    assert decimal_text(59.4) == "59,4"
    assert decimal_text(50.0) == "50"
    assert decimal_text("4.80") == "4,80"


@pytest.mark.parametrize("code", POINT)
def test_decimal_text_keeps_the_point(code, lang):
    lang(code)
    assert decimal_text(4.8, 1) == "4.8"
    assert decimal_text(59.4) == "59.4"


@pytest.mark.parametrize("code", COMMA)
def test_a_text_that_formats_its_own_number_writes_a_comma(code, lang):
    lang(code)
    got = tr("Out of gamut: {pct:.1f}%").format(pct=12.345)
    assert "12,3" in got and "12.3" not in got, got
    # a grouped count must not read as a decimal: 123 457, never 123,457
    got = tr("Compare: {v:,.0f} units³  (Δ {sign}{delta:.1f}%)").format(
        v=123456.7, sign="+", delta=3.25)
    assert "123 457" in got and "3,2" in got, got


@pytest.mark.parametrize("code", POINT)
def test_a_point_language_is_untouched(code, lang):
    lang(code)
    got = tr("Out of gamut: {pct:.1f}%").format(pct=12.345)
    assert "12.3" in got, got
    assert type(tr("Out of gamut: {pct:.1f}%")) is str


def test_a_plain_field_is_filled_exactly_as_given(lang):
    """Only a numeric format spec is localised: a name, a path or a version
    in a plain "{x}" comes out as it went in, dots and all."""
    lang("de")
    got = tr("{name} {secs} s").format(name="v4.3.12.ti3", secs="4.8")
    assert got.startswith("v4.3.12.ti3 4.8"), got
    assert tr("{name} {secs} s").format(name=1.5, secs=2) == "1.5 2 s"


def test_a_counted_text_localises_its_numbers_too(lang, monkeypatch):
    lang("uk")
    key = "{n} strips in {secs:.1f} s"
    monkeypatch.setitem(i18n._catalog, key, "{n} смуг за {secs:.1f} с")
    monkeypatch.setitem(i18n._plurals, key, {
        "count": "n", "one": "{n} смуга за {secs:.1f} с",
        "few": "{n} смуги за {secs:.1f} с",
        "many": "{n} смуг за {secs:.1f} с"})
    assert tr(key).format(n=2, secs=4.83) == "2 смуги за 4,8 с"


def test_the_reading_pace_summary_reads_like_ukrainian(lang):
    """The text the review found: "A 4.8 с" is now "A 4,8 с"."""
    from core.measure_pace import session_summary
    lang("uk")
    text = session_summary({"A": (4.83, True), "B": (3.21, True)}, 70)
    assert "A 4,8 с" in text and "B 3,2 с" in text, text
    assert "4.8" not in text and "3.2" not in text, text
    lang("en")
    text = session_summary({"A": (4.83, True), "B": (3.21, True)}, 70)
    assert "A 4.8 s" in text, text


@pytest.mark.parametrize("code", ["de", "uk", "ru", "fr"])
def test_the_strip_limit_phrase_follows_the_language(code, lang):
    from core.measure_pace import PaceConfig, strip_limit_phrase
    lang(code)
    phrase = strip_limit_phrase(PaceConfig(sample_hz=100.0, min_samples=25),
                                24)
    assert "6,0" in phrase and "6.0" not in phrase, phrase


@pytest.mark.parametrize("code", ["de", "uk", "ru", "fr"])
def test_what_a_program_reads_keeps_the_point(code, lang, tmp_path):
    """The refinement strip list is read back by ChromIQ: its numbers keep
    the point whatever language the app is in."""
    from workflow.profcheck_runner import write_refine_strips
    lang(code)
    path = write_refine_strips(tmp_path, "chart", [("A", 1.234), ("B", 2.5)])
    text = path.read_text(encoding="utf-8")
    assert "A\t1.23" in text and "B\t2.50" in text, text
    assert "1,23" not in text
