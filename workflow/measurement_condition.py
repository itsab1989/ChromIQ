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
file that names no condition (every ``chartread`` file) is judged as before.
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
    }
    return names.get(str(condition).upper(), str(condition))
