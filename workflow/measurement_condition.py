"""The measurement condition (M0, M1, M2) a ``.ti3`` was measured under, and
what it means for brightener compensation (FWA, ``colprof``/``profcheck -f``).

ISO 13655 names the light a spectrophotometer shines on the paper:

* **M0**, the instrument's own lamp (on an i1Pro a tungsten lamp, with some
  ultraviolet, how much depending on the instrument);
* **M1**, light with a defined amount of ultraviolet, like D50 daylight;
* **M2**, ultraviolet cut: the paper's brighteners do not glow.

ArgyllCMS's FWA compensation estimates the brighteners' glow from the lamp of
the instrument that took the readings (``spectro/insttypes.c``,
``inst_illuminant``: the tungsten "A" lamp of the i1Pro family). That model
only fits readings taken under that lamp, M0. Readings taken under M1 already
carry the glow as daylight shows it, and M2 readings carry none, so applying
``-f`` to either corrects a glow that is not there in the form it assumes
(measured on jctay's M2 readings, 2026-11-03: ``spec2cie -f`` moved them by
0.37 mean / 0.72 max dE76 for nothing).

So a ``.ti3`` that SAYS it is M1 or M2 (``MEASUREMENT_CONDITION``, written by
the i1Profiler import since 4.3.23, and by the Beta instrument reader of
4.3.22) never gets ``-f``. That refusal lives in THE FWA GATE,
``workflow.fwa_gate``, beside every other reason ``-f`` cannot be used, so
there is one answer to "can FWA be used for this .ti3, and if not, why". A
``chartread`` file names its condition when the Measure tab passed ``-F``
(:func:`record_condition`, review round 1); one that names none is judged as
before.
"""
from __future__ import annotations

import re
from pathlib import Path

from core.i18n import tr

#: The conditions the import offers, in the order the window lists them.
CONDITIONS = ("M0", "M1", "M2")

#: Header keyword carrying the condition (the name the Beta instrument's
#: writer of 4.3.22 already uses).
CONDITION_KEYWORD = "MEASUREMENT_CONDITION"

_CONDITION_RE = re.compile(
    rf'^\s*{CONDITION_KEYWORD}\s+"?([^"\s]*)"?\s*$', re.MULTILINE)


def read_condition(ti3_path: "str | Path | None") -> "str | None":
    """The ``MEASUREMENT_CONDITION`` a measurement's header names ("M0",
    "M1", "M2", upper case), or None: no path, no file, no keyword. Reads the
    header only."""
    if not ti3_path:
        return None
    try:
        with open(ti3_path, "r", encoding="utf-8", errors="replace") as fh:
            head = []
            for n, line in enumerate(fh):
                if line.strip() == "BEGIN_DATA" or n > 400:
                    break
                head.append(line)
    except OSError:
        return None
    m = _CONDITION_RE.search("".join(head))
    if not m:
        return None
    value = m.group(1).strip().upper()
    return value or None


def condition_name(condition: str) -> str:
    """A condition's short name for the information window and the log."""
    names = {
        "M0": tr("M0 (the instrument's own lamp)"),
        "M1": tr("M1 (daylight with UV, D50)"),
        "M2": tr("M2 (UV cut)"),
        "M3": tr("M3 (polarising filter)"),
    }
    return names.get(str(condition).upper(), str(condition))


# ---------------------------------------------------------------------------
# The condition chartread measured under (review round 1, S3)
# ---------------------------------------------------------------------------

#: chartread's ``-F`` value -> the ISO 13655 condition it measures under, as
#: the Measure tab's "Spectral filter type (-F)" row names them: ``n`` no
#: filter (M0, the instrument's own lamp), ``5`` D50 (M1), ``u`` UV cut
#: (M2), ``p`` polarising (M3). ``6`` (a D65 filter) is no ISO 13655
#: condition and is not recorded; chartread itself writes
#: ``INSTRUMENT_FILTER`` for it.
FILTER_CONDITIONS = {"n": "M0", "5": "M1", "u": "M2", "p": "M3"}


def filter_choices() -> "list[tuple[str, str]]":
    """The Measure tab's "Spectral filter type (-F)" entries, in list order:
    (the value chartread is given, the entry as the list shows it). 4.3.42:
    the M number first, then what the light is (the owner's ruling,
    2026-11-16); the values are those of chartread's -F and never change,
    and saved settings and presets store the value, not the text. ``6`` is
    a D65 filter fitted to the instrument (Spectrolino), no ISO 13655
    condition, so it carries no M number."""
    return [("n", tr("M0: no filter (lamp as it is)")),
            ("5", tr("M1: D50 daylight (with UV)")),
            ("6", tr("D65 daylight filter")),
            ("u", tr("M2: UV cut (no UV)")),
            ("p", tr("M3: polarising filter"))]


def filter_choice_label(code: "str | None") -> str:
    """The entry the list shows for the -F value *code*, or *code* itself
    when it is none of them."""
    return dict(filter_choices()).get(str(code or "").lower(), str(code or ""))


def filter_code_from_args(extra_args: "str | None") -> "str | None":
    """The value of ``-F`` in chartread's extra arguments (``"-F 5"``,
    ``"-F5"``), or None when there is no ``-F``."""
    if not extra_args:
        return None
    import shlex
    try:
        toks = shlex.split(extra_args)
    except ValueError:
        toks = str(extra_args).split()
    for i, t in enumerate(toks):
        if t == "-F":
            return toks[i + 1] if i + 1 < len(toks) else None
        if t.startswith("-F") and len(t) > 2:
            return t[2:]
    return None


def condition_for_filter(code: "str | None") -> "str | None":
    """The condition chartread's ``-F`` *code* measures under, or None (no
    ``-F``: the instrument's normal mode, which is not recorded, so the file
    is judged as before; or a filter that is no ISO 13655 condition)."""
    if not code:
        return None
    return FILTER_CONDITIONS.get(str(code).strip().lower())


#: R4 (4.3.39): the instruments whose normal mode (no ``-F``) is a KNOWN
#: ISO 13655 condition, by ``core.measure_pace.model_key``. Every one of them
#: reads under its own tungsten lamp, M0, unless the driver says a physical
#: UV-cut filter is fitted (the original i1Pro and the i1Pro 2 came with one
#: as an option; their driver reads it from the instrument's calibration
#: data at open, i1pro.c inst_stat_get_filter, and the helper reports it as
#: its "filter" event). The i1Pro 3 has no such variant: its driver's own
#: mode filter is "none" unless -F asks for another (i1pro3.c).
_NORMAL_MODE_M0 = {"i1pro3": "any", "i1pro3plus": "any",
                   "i1pro2": "filter", "i1pro": "filter"}


def default_condition(model: "str | None",
                      driver_filter: "str | None") -> "str | None":
    """The condition an instrument measures under in its normal mode (no
    ``-F``), where that IS known, else None (R4, 4.3.39).

    *model* is the instrument's name as ArgyllCMS reports it; *driver_filter*
    the helper's ``filter`` event ("none", "uvcut", "unknown"...), or None
    when no helper said (stock chartread). M0 for the i1Pro 3 family (no
    filter, or the driver's own "none"); M0 for the i1Pro / i1Pro 2 only when
    the driver says no filter is fitted. Nothing for an i1Pro with a physical
    UV-cut filter, for a driver that did not say, and for every other
    instrument: ChromIQ writes no condition it cannot know, and a file that
    names none is judged exactly as before (the FWA gate treats M0 like none,
    so recording M0 changes no decision)."""
    from core.measure_pace import model_key
    rule = _NORMAL_MODE_M0.get(model_key(model) or "")
    f = (str(driver_filter).strip().lower() or None) if driver_filter else None
    if rule == "any" and f in (None, "none"):
        return "M0"
    if rule == "filter" and f == "none":
        return "M0"
    return None


#: R4: beside a condition ChromIQ recorded from the instrument's normal mode
#: (no -F), so that continuing that measurement with -F still off is "the
#: same setting" (S-A1), while one recorded from an explicit -F keeps the
#: S-A1 rule unchanged.
CONDITION_SOURCE_KEYWORD = "MEASUREMENT_CONDITION_SOURCE"
SOURCE_INSTRUMENT_DEFAULT = "INSTRUMENT_DEFAULT"


def condition_fits_normal_mode(ti3_path: "str | Path | None") -> bool:
    """Whether the measurement at *ti3_path* may be continued with ``-F``
    off (R4): it records M0 AND says ChromIQ recorded that from the
    instrument's normal mode, i.e. it was itself measured with ``-F`` off.
    A measurement whose M0 came from an explicit ``-F n`` is judged by S-A1
    exactly as before."""
    return (read_condition(ti3_path) == "M0"
            and (read_header_keyword(ti3_path, CONDITION_SOURCE_KEYWORD)
                 or "").upper() == SOURCE_INSTRUMENT_DEFAULT)


def record_condition(ti3_path: "str | Path", condition: str,
                     source: "str | None" = None) -> bool:
    """Write ``MEASUREMENT_CONDITION`` into the header of the measurement at
    *ti3_path*, as the i1Profiler import does. Only the
    header changes: the two lines go in after the file's first line (or the
    value of one already there is replaced), and every other byte, the data
    included, stays as it was. True when the file was changed.

    *source* (R4): :data:`SOURCE_INSTRUMENT_DEFAULT` when the condition is
    the instrument's normal mode (no -F), written as
    ``MEASUREMENT_CONDITION_SOURCE``; without it any such line is taken out,
    because the condition is then a choice."""
    changed = _set_keyword(ti3_path, CONDITION_KEYWORD, condition)
    if source:
        changed = _set_keyword(ti3_path, CONDITION_SOURCE_KEYWORD,
                               source) or changed
    elif read_header_keyword(ti3_path, CONDITION_SOURCE_KEYWORD) is not None:
        changed = clear_header_keyword(ti3_path,
                                       CONDITION_SOURCE_KEYWORD) or changed
    return changed


def _set_keyword(ti3_path: "str | Path", keyword: str, condition: str) -> bool:
    """One header keyword, as :func:`record_condition` writes it."""
    p = Path(ti3_path)
    try:
        raw = p.read_bytes()
    except OSError:
        return False
    cond = str(condition).strip().upper()
    if not cond:
        return False
    nl = b"\r\n" if b"\r\n" in raw[:4096] else b"\n"
    head, sep, rest = raw.partition(b"BEGIN_DATA_FORMAT")
    if not sep:
        return False
    key = keyword.encode("ascii")
    value_re = re.compile(rb'^([ \t]*' + key + rb'[ \t]+).*$', re.MULTILINE)
    m = value_re.search(head)
    if m:
        line = m.group(1) + b'"' + cond.encode("ascii") + b'"'
        old = m.group(0).rstrip(b"\r")
        if old == line:
            return False
        head = head[:m.start()] + line + head[m.start() + len(old):]
    else:
        first, nl_found, after = head.partition(b"\n")
        if not nl_found:
            return False
        lines = (b'KEYWORD "' + key + b'"' + nl
                 + key + b' "' + cond.encode("ascii") + b'"' + nl)
        head = first + b"\n" + lines + after
    try:
        p.write_bytes(head + sep + rest)
    except OSError:
        return False
    return True


def clear_condition(ti3_path: "str | Path") -> bool:
    """Take ``MEASUREMENT_CONDITION`` (and its ``KEYWORD`` line) out of the
    header of the measurement at *ti3_path*; every other byte stays. True
    when the file was changed."""
    a = clear_header_keyword(ti3_path, CONDITION_KEYWORD)
    b = clear_header_keyword(ti3_path, CONDITION_SOURCE_KEYWORD)
    return a or b


def read_header_keyword(ti3_path: "str | Path | None", key: str
                        ) -> "str | None":
    """The value of header keyword *key* of the measurement at *ti3_path*
    (quotes taken off), or None: no file, no keyword. Header only."""
    if not ti3_path:
        return None
    try:
        with open(ti3_path, "r", encoding="utf-8", errors="replace") as fh:
            head = []
            for n, line in enumerate(fh):
                if line.strip() in ("BEGIN_DATA_FORMAT", "BEGIN_DATA") \
                        or n > 400:
                    break
                head.append(line)
    except OSError:
        return None
    m = re.search(rf'^\s*{re.escape(key)}\s+"?([^"\r\n]*?)"?\s*$',
                  "".join(head), re.MULTILINE)
    return m.group(1).strip() if m else None


def clear_header_keyword(ti3_path: "str | Path", key: str) -> bool:
    """Take header keyword *key* (and its ``KEYWORD`` line) out of the
    measurement at *ti3_path*; every other byte stays. True when the file
    was changed."""
    p = Path(ti3_path)
    try:
        raw = p.read_bytes()
    except OSError:
        return False
    head, sep, rest = raw.partition(b"BEGIN_DATA_FORMAT")
    if not sep:
        return False
    k = re.escape(key.encode("ascii"))
    line_re = re.compile(
        rb'^[ \t]*(?:KEYWORD[ \t]+"?' + k + rb'"?|' + k
        + rb'[ \t]+[^\r\n]*)[ \t]*\r?\n', re.MULTILINE)
    new_head, n = line_re.subn(b"", head)
    if not n:
        return False
    try:
        p.write_bytes(new_head + sep + rest)
    except OSError:
        return False
    return True
