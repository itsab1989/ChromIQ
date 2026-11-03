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


def record_condition(ti3_path: "str | Path", condition: str) -> bool:
    """Write ``MEASUREMENT_CONDITION`` into the header of the measurement at
    *ti3_path*, as the i1Profiler import does. Only the
    header changes: the two lines go in after the file's first line (or the
    value of one already there is replaced), and every other byte, the data
    included, stays as it was. True when the file was changed."""
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
    key = CONDITION_KEYWORD.encode("ascii")
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
