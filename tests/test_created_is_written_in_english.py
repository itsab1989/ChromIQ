"""A CGATS file's ``CREATED`` line is written the way ArgyllCMS writes it, in
English, whatever language the computer runs in, and is read back in any of
them.

The gamut chart (``workflow/gamut_target.py``) and five other writers used
``strftime("%a %b %d …")``. Qt's ``QApplication`` sets the process's
``LC_TIME`` to the user's locale, so a German Mac wrote ``"Fr. Okt. 02
13:04:05 2026"`` where ArgyllCMS writes ``"Fri Oct 02 13:04:05 2026"``, and
the chart-date reader (``_chart_date_from_ti2``) then found no date in it.
Charts already on disk keep their localized line, so the readers accept every
shipped language.
"""
from __future__ import annotations

import locale
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from core.cgats_date import created_stamp, long_english_date, parse_created_date

ROOT = Path(__file__).resolve().parents[1]

#: What ``strftime("%a %b %d %H:%M:%S %Y")`` wrote on 2026-10-02 13:04:05
#: under each shipped language (macOS locales, measured 2026-10-03), and the
#: long form ``"%B %d, %Y"`` the i1Profiler export wrote, where it differs.
LOCALIZED = {
    "de": ["Fr. Okt. 02 13:04:05 2026", "Mo. März 02 13:04:05 2026",
           "Oktober 02, 2026"],
    "es": ["vie. oct. 02 13:04:05 2026", "mié. sept. 02 13:04:05 2026",
           "octubre 02, 2026"],
    "fr": ["ven. oct. 02 13:04:05 2026", "lun. févr. 02 13:04:05 2026",
           "octobre 02, 2026"],
    "it": ["ven ott 02 13:04:05 2026", "ottobre 02, 2026"],
    "ja": ["金 10月 02 13:04:05 2026", "金  1月 02 13:04:05 2026"],
    "nl": ["vr okt. 02 13:04:05 2026", "ma mrt. 02 13:04:05 2026"],
    "no": ["fre. okt. 02 13:04:05 2026", "ons. des. 02 13:04:05 2026"],
    "pl": ["pt. paź 02 13:04:05 2026", "października 02, 2026"],
    "pt": ["sex out 02 13:04:05 2026", "outubro 02, 2026"],
    "ru": ["пт окт. 02 13:04:05 2026", "октября 02, 2026"],
    "sv": ["fre okt. 02 13:04:05 2026", "oktober 02, 2026"],
    "uk": ["Пт жовт. 02 13:04:05 2026", "жовтня 02, 2026"],
    "zh_CN": ["五 10月 02 13:04:05 2026"],
    "en": ["Fri Oct 02 13:04:05 2026", "October 02, 2026", "2026-10-02"],
}
_EXPECT = {"Mo. März": date(2026, 3, 2), "lun. févr.": date(2026, 2, 2),
           "金  1月": date(2026, 1, 2), "ma mrt.": date(2026, 3, 2),
           "ons. des.": date(2026, 12, 2), "mié. sept.": date(2026, 9, 2)}


def _expected(raw: str) -> date:
    for prefix, d in _EXPECT.items():
        if raw.startswith(prefix):
            return d
    return date(2026, 10, 2)


@pytest.mark.parametrize("lang", sorted(LOCALIZED))
def test_every_shipped_languages_created_line_is_read(lang):
    for raw in LOCALIZED[lang]:
        assert parse_created_date(raw) == _expected(raw), (lang, raw)


def test_an_unreadable_created_is_no_date_not_an_error():
    for raw in ("", "May 2015", "garbage", "Fri Foo 02 13:04:05 2026"):
        assert parse_created_date(raw) is None, raw


def test_the_stamp_is_english_under_a_german_locale():
    when = datetime(2026, 10, 2, 13, 4, 5)
    saved = locale.setlocale(locale.LC_TIME)
    try:
        try:
            locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
        except locale.Error:
            pytest.skip("no German locale on this machine")
        assert when.strftime("%b") != "Oct", "the locale did not take"
        assert created_stamp(when) == "Fri Oct 02 13:04:05 2026"
        assert long_english_date(when) == "October 02, 2026"
    finally:
        locale.setlocale(locale.LC_TIME, saved)


def test_the_chart_date_reader_reads_a_german_gamut_chart(tmp_path):
    from ui.tabs.tab_chart import _chart_date_from_ti2
    ti2 = tmp_path / "c-verify.ti2"
    ti2.write_text('CTI2\nCREATED "Fr. Okt. 02 13:04:05 2026"\n',
                   encoding="utf-8")
    assert _chart_date_from_ti2(ti2) == "2026-10-02"


def test_an_i1profiler_export_written_in_german_keeps_its_date(tmp_path):
    from workflow.reference_convert import read_measurement_date
    txt = tmp_path / "x.txt"
    txt.write_text('CGATS.17\nCREATED "Oktober 02, 2026"\n', encoding="utf-8")
    assert read_measurement_date(txt) == "2026-10-02"


def test_no_writer_asks_the_locale_for_day_or_month_names():
    """``%a``/``%A``/``%b``/``%B`` in app code is the user's language under
    Qt. CREATED goes through `core.cgats_date`."""
    pat = re.compile(r"strftime\([^)]*%[aAbB]|:[^}\"']*%[aAbB][^}]*}")
    hits = []
    for folder in ("core", "workflow", "ui"):
        for p in (ROOT / folder).rglob("*.py"):
            if p.name == "cgats_date.py":
                continue
            for n, line in enumerate(p.read_text(encoding="utf-8")
                                     .splitlines(), 1):
                if pat.search(line):
                    hits.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()}")
    demo = (ROOT / "scripts" / "make_demo_projects.py").read_text(
        encoding="utf-8")
    hits += [f"make_demo_projects: {ln.strip()}" for ln in demo.splitlines()
             if pat.search(ln)]
    assert not hits, "\n".join(hits)


# ---------------------------------------------------------------------------
# The moment, not only the day (#182, verifications from an earlier profile)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", sorted(LOCALIZED))
def test_the_moment_is_read_in_every_shipped_language(lang):
    """A FROM PROFILE GAMUT chart is told from one made from the current
    profile by its CREATED moment, and charts written before the English stamp
    carry the localized form."""
    from core.cgats_date import parse_created_datetime
    for raw in LOCALIZED[lang]:
        got = parse_created_datetime(raw)
        if ":" not in raw:
            assert got is None, f"{raw!r} has no time, so no moment: {got}"
            continue
        d = _expected(raw)
        assert got == datetime(d.year, d.month, d.day, 13, 4, 5), (raw, got)


def test_the_moment_reads_iso_and_refuses_garbage():
    from core.cgats_date import parse_created_datetime
    assert parse_created_datetime("2026-10-02T21:27:02") == \
        datetime(2026, 10, 2, 21, 27, 2)
    assert parse_created_datetime(created_stamp(
        datetime(2026, 10, 2, 21, 27, 2))) == datetime(2026, 10, 2, 21, 27, 2)
    for raw in ("", "garbage", "Fri Oct 02 2026", "Fri Oct 02 25:61:00 2026"):
        assert parse_created_datetime(raw) is None, raw
