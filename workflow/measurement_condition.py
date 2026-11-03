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
the i1Profiler import since 4.3.23, and by the Beta instrument reader
of 4.3.22) never gets ``-f``:
the option is greyed in Build Profile and Check & Refine, and the builders
take it out with a line in the log whichever door asked for it. A file that
names no condition (every ``chartread`` file) is judged as before.

THIS GATE SITS BESIDE THE INSTRUMENT-NAME ONE, NOT IN IT. The 4.3.22
branch's ``ui.ti2_loader.fwa_unavailable`` refuses ``-f`` for an instrument
ArgyllCMS does not know; this module refuses it for a condition the model does
not fit. Two reasons, two helpers, so either can change alone.
"""
from __future__ import annotations

import re
import shlex
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


def fwa_refused_by_condition(condition: "str | None") -> bool:
    """Whether FWA compensation must not be applied to readings taken under
    *condition*: True for M1 and M2 (and any other named condition that is
    not M0), False for M0 and for no condition at all."""
    if not condition:
        return False
    return str(condition).strip().upper() != "M0"


def fwa_refused_for_file(ti3_path: "str | Path | None") -> bool:
    """:func:`fwa_refused_by_condition` for the measurement at *ti3_path*."""
    return fwa_refused_by_condition(read_condition(ti3_path))


def fwa_condition_reason(condition: str) -> str:
    """The tooltip on the greyed FWA option while a measurement of
    *condition* (M1 or M2) is loaded, Build Profile and Check & Refine."""
    return tr(
        "Brightener compensation (FWA) is not available for this "
        "measurement, because it was measured under condition {condition}.\n\n"
        "Optical brighteners in paper turn invisible ultraviolet light into "
        "visible blue light, which makes the paper look whiter. FWA "
        "compensation works out that glow from the lamp inside the instrument, "
        "so it only fits readings taken under that lamp: condition M0.\n\n"
        "M1 readings already include the glow as daylight (D50) shows it, and "
        "M2 readings leave the ultraviolet out, so the brighteners do not glow "
        "at all. Applying FWA compensation to either would correct something "
        "that is not there.\n\n"
        "To use FWA compensation, import the M0 readings of the same "
        "measurement (i1Profiler saves all of its conditions in one .mxf "
        "file), or measure the chart in M0."
    ).format(condition=condition)


def fwa_condition_dropped_log_line(condition: str) -> str:
    """The log line when FWA compensation was switched on (the box, a saved
    setting, a preset, the extra arguments) and is left out for a
    measurement of *condition*."""
    return tr(
        "[NOTE] Brightener compensation (FWA, -f) was left out: this "
        "measurement was taken under condition {condition}, and FWA "
        "compensation only fits readings taken under the instrument's own "
        "lamp (M0)."
    ).format(condition=condition)


def remove_fwa(params) -> bool:
    """Take FWA compensation out of a colprof / profcheck parameter object,
    in place: the ``fwa_enabled`` switch, and any ``-f`` typed into the extra
    arguments. True when anything was removed."""
    dropped = False
    if getattr(params, "fwa_enabled", False):
        params.fwa_enabled = False
        dropped = True
    extra = getattr(params, "extra_args", "") or ""
    if extra.strip():
        try:
            toks = shlex.split(extra)
        except ValueError:          # unbalanced quotes: left as typed
            toks = None
        if toks is not None:
            kept = [t for t in toks if not t.startswith("-f")]
            if len(kept) != len(toks):
                params.extra_args = shlex.join(kept)
                dropped = True
    return dropped


def without_fwa_unless_m0(params, keywords_from=None):
    """*params* without FWA compensation when its measurement names a
    condition other than M0, as ``(params, condition_or_None)``: the
    condition when something was dropped, else None. A copy is returned when
    anything is dropped, so the caller's object is left as it was.
    *keywords_from* is the file to ask when *params*' own measurement does
    not exist yet (a merge still to be made)."""
    from dataclasses import replace
    wants = bool(getattr(params, "fwa_enabled", False)) or "-f" in (
        getattr(params, "extra_args", "") or "")
    if not wants:
        return params, None
    ti3 = getattr(params, "ti3_path", None)
    asked = ti3 if ti3 is not None and Path(ti3).is_file() else keywords_from
    condition = read_condition(asked)
    if not fwa_refused_by_condition(condition):
        return params, None
    copy = replace(params)
    return (copy, condition) if remove_fwa(copy) else (params, None)


def condition_name(condition: str) -> str:
    """A condition's short name for the information window and the log."""
    names = {
        "M0": tr("M0 (the instrument's own lamp)"),
        "M1": tr("M1 (daylight with UV, D50)"),
        "M2": tr("M2 (UV cut)"),
    }
    return names.get(str(condition).upper(), str(condition))
