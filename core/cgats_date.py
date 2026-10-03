"""The ``CREATED`` date of a CGATS file (.ti1/.ti2/.ti3/.txt), written the
way ArgyllCMS writes it and read back whatever language wrote it.

ArgyllCMS stamps ``CREATED`` with C's ``asctime`` (``"Fri Oct 02 13:04:05
2026"``), in English, because it never calls ``setlocale``. ChromIQ used
``strftime("%a %b %d …")``, and Qt's ``QApplication`` sets the process's
``LC_TIME`` to the user's locale (``core/numeric_locale.py`` pins only
``LC_NUMERIC`` back), so under German the same line came out as
``"Fr. Okt. 02 13:04:05 2026"`` and in Japanese as ``"金 10月 02 …"``.

:func:`created_stamp` writes the English form without asking the locale, and
:func:`parse_created_date` reads it, the localized forms ChromIQ has already
written in every shipped language, ISO dates and i1Profiler's own
``"October 02, 2026"``.
"""
from __future__ import annotations

import re
from datetime import date, datetime

_DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_LONG_MONTHS = ("January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November",
                "December")


def created_stamp(when: "datetime | None" = None) -> str:
    """``when`` (default: now) as C's ``asctime`` writes it, in English
    whatever the process locale: ``"Fri Oct 02 13:04:05 2026"``."""
    when = when or datetime.now()
    return (f"{_DAYS[when.weekday()]} {_MONTHS[when.month - 1]} "
            f"{when.day:02d} {when:%H:%M:%S} {when.year}")


def long_english_date(when: "datetime | date | None" = None) -> str:
    """``"October 02, 2026"``: the form i1Profiler writes in its exports,
    in English whatever the process locale."""
    when = when or datetime.now()
    return f"{_LONG_MONTHS[when.month - 1]} {when.day:02d}, {when.year}"


# Month names as ``strftime("%b")`` / ``"%B"`` gives them under each language
# ChromIQ ships (measured with macOS's locales, 2026-10-03), lower-cased and
# without a trailing full stop. English first; a name two languages share
# means the same month in both, so one table is enough.
_MONTH_WORDS: "dict[str, int]" = {}


def _add(month: int, *words: str) -> None:
    for w in words:
        _MONTH_WORDS[w.lower().rstrip(".")] = month


for _i, (_short, _long) in enumerate(zip(_MONTHS, _LONG_MONTHS), 1):
    _add(_i, _short, _long)
# Generated from macOS's own locales (``%b`` and ``%B`` for de, es, fr, it,
# nl, nb, pl, pt, ru, sv, uk), so the genitive forms pl/ru/uk use are there
# too, plus English. ja and zh_CN write ``"10月"``, which `_CJK_MONTH` reads.
_add(1, "jan", "januar", "ene", "enero", "janv", "janvier", "gen", "gennaio", "januari", "sty", "stycznia", "janeiro", "янв", "января", "січ", "січня", "january")
_add(2, "feb", "februar", "febrero", "févr", "février", "febbraio", "februari", "lut", "lutego", "fev", "fevereiro", "февр", "февраля", "лют", "лютого", "february")
_add(3, "märz", "mär", "mar", "marzo", "mars", "mrt", "maart", "marca", "março", "марта", "бер", "березня", "march")
_add(4, "apr", "april", "abr", "abril", "avr", "avril", "aprile", "kwi", "kwietnia", "апр", "апреля", "квіт", "квітня")
_add(5, "mai", "may", "mayo", "mag", "maggio", "mei", "maj", "maja", "maio", "мая", "трав", "травня")
_add(6, "juni", "jun", "junio", "juin", "giu", "giugno", "cze", "czerwca", "junho", "июня", "черв", "червня", "june")
_add(7, "juli", "jul", "julio", "juil", "juillet", "lug", "luglio", "lip", "lipca", "julho", "июля", "лип", "липня", "july")
_add(8, "aug", "august", "ago", "agosto", "août", "augustus", "sie", "sierpnia", "авг", "августа", "augusti", "серп", "серпня")
_add(9, "sep", "september", "sept", "septiembre", "septembre", "set", "settembre", "wrz", "września", "setembro", "сент", "сентября", "вер", "вересня")
_add(10, "okt", "oktober", "oct", "octubre", "octobre", "ott", "ottobre", "paź", "października", "out", "outubro", "окт", "октября", "жовт", "жовтня", "october")
_add(11, "nov", "november", "noviembre", "novembre", "lis", "listopada", "novembro", "нояб", "ноября", "лист", "листопада")
_add(12, "dez", "dezember", "dic", "diciembre", "déc", "décembre", "dicembre", "dec", "december", "des", "desember", "gru", "grudnia", "dezembro", "дек", "декабря", "груд", "грудня")

_CJK_MONTH = re.compile(r"^(\d{1,2})月$")
_YEAR = re.compile(r"^\d{4}$")
_DAY = re.compile(r"^(\d{1,2}),?$")


def _month_of(word: str) -> "int | None":
    w = word.lower().rstrip(".,")
    m = _CJK_MONTH.match(w)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 12 else None
    return _MONTH_WORDS.get(w)


def parse_created_date(raw: str) -> "date | None":
    """The day in a ``CREATED`` value, or None when it cannot be read.

    Accepts ``"Fri Oct 02 13:04:05 2026"`` in any shipped language (the
    words are only used for the month; the day and year are numbers),
    ``"2026-10-02…"``, and ``"October 02, 2026"``. Never raises.
    """
    if not raw:
        return None
    raw = raw.strip().strip('"').strip()
    iso = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw)
    try:
        if iso:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        tokens = raw.split()
        years = [t for t in tokens if _YEAR.match(t.rstrip(",."))]
        if not years:
            return None
        year = int(years[-1].rstrip(",."))
        # The month is the word right before the day number.
        for i, tok in enumerate(tokens):
            d = _DAY.match(tok)
            if d is None or i == 0:
                continue
            month = _month_of(tokens[i - 1])
            if month is not None:
                return date(year, month, int(d.group(1)))
    except ValueError:
        return None
    return None


_CLOCK = re.compile(r"(?<!\d)(\d{1,2}):(\d{2}):(\d{2})(?!\d)")


def parse_created_datetime(raw: str) -> "datetime | None":
    """The moment in a ``CREATED`` value, or None when it cannot be read.

    The day comes from :func:`parse_created_date`, so every language it
    reads is read here too; the time is the ``HH:MM:SS`` token, which is
    written the same way in every locale (``"Fri Oct 02 21:27:02 2026"``,
    ``"Fr. Okt. 02 21:27:02 2026"``, ``"2026-10-02T21:27:02"``). A value
    with a day and no time is None, not midnight: a caller comparing
    moments must not be handed one that was guessed (#182, verifications
    from an earlier profile). Local time, as ChromIQ and ArgyllCMS write
    it. Never raises.
    """
    day = parse_created_date(raw)
    if day is None:
        return None
    clock = _CLOCK.search(raw or "")
    if clock is None:
        return None
    try:
        return datetime(day.year, day.month, day.day, int(clock.group(1)),
                        int(clock.group(2)), int(clock.group(3)))
    except ValueError:
        return None
